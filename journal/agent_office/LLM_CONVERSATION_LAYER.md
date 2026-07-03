# Live LLM Conversation Layer — build spec

> Turn the Virtual Agent Office's **static** briefing NPCs into **live** per-character
> LLM agents you can walk up to and talk to, in their own voice. This is the bridge
> between the shipped office maps (`agent_office`, `agent_office_ci`) and the north-star
> vision in [`../../../llm-play/VISION.md`](../../../llm-play/VISION.md).
>
> Companion implementation: [`../../tools/agent_office_llm/`](../../tools/agent_office_llm/).
> Status: **C3 implemented** (llm-play backend replies + Office Service dispatch).
> Scripted HUD lines keep working as the fallback.

---

## 1. What exists vs. what's missing

| Capability | Today | Needed for live conversation |
|------------|-------|------------------------------|
| Agents in the world | 8 `Chr` NPCs, custom ailists, briefing anims | (keep) |
| Player-facing output | `aiShowHudmsg` HUD line on Z-target / proximity | LLM utterance injected as the line (+ voice) |
| Proximity trigger | ailist `if_distance_to_target_lt` → one-shot line (`GREET_RANGE`) | same trigger, but hands off to the LLM director |
| Perception (bridge `/observe`) | serializes **players + MP bots only** (`g_MpNumChrs`) | must also serialize the office agent chrs (chrnum ≥ `0x31`) |
| Actuation (bridge `/act`) | drives player + bot slots (`llm_bot.c`) | must inject a per-chr **utterance** (and optional face-player turn) |
| Cognition | none (ailist bytecode) | per-agent LLM brain (llm-play orchestrator, one per agent) |
| Voice | none in-game | `voice_pipeline/` TTS per character, anchored to agent position |

**The gap is four seams, all additive.** Scripted lines remain the fallback: if the
director isn't running, agents behave exactly as they do today.

---

## 2. Architecture

```
  Perfect Dark (agent_office / _ci)                 llm-play sidecar (Office Director)
  ┌───────────────────────────────┐                 ┌────────────────────────────────────┐
  │ 8 Chr agents (chrnum 0x31+)    │  GET /observe   │ 1. poll player + agent positions   │
  │   briefing ailist + greet_text │ ───────────────▶│ 2. proximity + view-cone → "approach"│
  │                                │  (+agents[])    │ 3. mic ASR → player utterance       │
  │ llm_bridge.c :8780             │                 │ 4. per-agent LLM brain → reply      │
  │   /observe  (extend)           │  POST /act      │ 5. TTS (voice_pipeline) at agent pos│
  │   /act  (add agents[].say)  ◀──┼─────────────────│ 6. POST utterance back for HUD line │
  │   aiShowHudmsg(chr, text)      │                 └────────────────────────────────────┘
  └───────────────────────────────┘
```

The director is the llm-play `AdapterOrchestrator` pattern, instantiated **once per
agent**, with a per-character system prompt + memory (VISION §6). The office map is
unchanged except for the two bridge extensions in §3.

---

## 3. Engine changes (Perfect Dark side)

### 3a. Observe the office agents  — `port/src/llm_observe.c`

`/observe` today loops `g_MpNumChrs` and tags each actor `"player"` or `"bot"`. The
office agents are `TEAM_NONCOMBAT` `Chr` NPCs in the chr slot pool, **not** MP chrs, so
they never appear. Add a second pass that walks `g_ChrSlots` for chrs with
`chrnum >= CHR_AGENT_FIRST` (`0x31`, see `tools/pdmap/agent_office.py`) and emits an
`"agents"` array:

```json
"agents":[
  {"chrnum":49,"role_hint":0,"pos":{"x":2888,"y":35,"z":-458},
   "facing_deg":270.0,"player_dist":812.4,"talking":false}
]
```

`player_dist` is cheap to compute here (engine already has both positions) and saves the
director a sqrt per agent per tick. `role_hint` can be `chrnum - CHR_AGENT_FIRST` so the
director maps slot→role via the same `VIRTUAL_AGENTS` order.

### 3b. Inject an agent utterance  — `port/src/llm_bridge.c` + a small hook

Extend the `POST /act` body with an `agents` array carrying a spoken line:

```json
{"agents":[{"chrnum":49,"say":"You again. The vault logs are clean, I checked twice.","face_player":true}]}
```

Handler (new `llmAgentApply()` next to the bot path):

1. Resolve `chrnum` → `struct chrdata *` via the slot pool (reuse the validation in
   `llm_observe.c`).
2. `say` → call the **same** `aiShowHudmsg(player, text)` path the ailist uses
   (`src/game/chraicommands.c`, already null-guarded), or a new `llmAgentSay()` that
   writes into a per-chr utterance buffer the HUD renders above the agent.
3. `face_player` (optional) → set the chr's `yrot`/look toward the player, mirroring the
   yaw logic in `llm_bot.c`. Gives "the agent turns to face you" (VISION P1) for free.

**No new opcode** is required for text: `say` reuses `aiShowHudmsg`. Voice is entirely
sidecar-side (§4) — the engine only needs to show the line and optionally turn the head.

### 3c. Hand-off latch (optional, ailist side)

The proximity greeting (`greet_text`, `GREET_RANGE` in `agent_office*.py`) already fires
once on approach. When the director is live it can suppress the static line by setting a
chrflag the ailist checks, so the LLM line isn't double-shown with the scripted one. If
the director is absent, the scripted line shows as today. This is the fallback contract.

---

## 4. Sidecar: the Office Director (llm-play side)

Scaffolded in [`../../tools/agent_office_llm/office_director.py`](../../tools/agent_office_llm/office_director.py).
Loop (≈4–10 Hz, faster than the idle briefing tick):

1. **Perceive** — `GET /observe`; read `players[0].pos` and `agents[]`.
2. **Detect approach** — for each agent, `player_dist < ENGAGE_RANGE` **and** player
   roughly facing the agent (dot of player-facing vs. agent-bearing). Rising edge =
   `approach`; falling edge past `DISENGAGE_RANGE` = `leave` (hysteresis, like the ailist
   latch).
3. **Listen** — on approach, open mic; `voice_pipeline/asr.py` (Whisper) → transcript.
   Text input is the fallback when no mic.
4. **Think** — route to that agent's brain using the llm-play backend contract
   (`--llm --backend auto|ollama|mlx`) with the character's system prompt + rolling
   memory. Output = one short in-character JSON reply (+ optional intent later,
   e.g. "turn to face", "look busy").
5. **Speak** — `voice_pipeline` TTS for that character → play the clip; the ASR
   intelligibility gate (`asr.py`) rejects garbled synthesis before it's spoken.
6. **Show + face** — `POST /act` with `agents:[{chrnum, say, face_player:true}]`.
7. **Remember** — append the exchange to the agent's memory file; optionally raise a
   world event (VISION §5: "guard heard you ask about the vault").

Only the **engaged** agent(s) run the fast/expensive path; the rest idle. On a local
`gemma3:4b` (llm-play default) one conversation at a time is comfortably real-time.

---

## 5. A character is a folder

Reuse the `voice_pipeline` character contract (`assets/characters/<slug>/`) and add a
`brain.json` beside `voice/config.json`:

```
tools/agent_office_llm/characters/
  director/         brain.json   (role, persona, goals, memory seed)
  research/         brain.json
  security/         brain.json
  …
assets/characters/<slug>/voice/config.json   (existing TTS contract)
```

`brain.json` (see the scaffolded `characters/director/brain.json`): `slug`, `role`,
`chrnum`, `system_prompt`, `voice_slug`, `memory_file`, `knowledge` (what this agent
knows / must not reveal). The map's `VIRTUAL_AGENTS` order fixes `chrnum`; the director
binds slug→chrnum on start.

---

## 6. Phased plan

| Phase | Deliverable | Demo |
|-------|-------------|------|
| **C0** | This spec + scaffold (director skeleton, one `brain.json`) | — |
| **C1** | `/observe` emits `agents[]`; director prints who you're near | Console logs "approaching Director (712u)" |
| **C2** | `/act` `agents[].say` → `aiShowHudmsg`; director sends a **canned** line on approach | Walk up → agent shows a director-driven line |
| **C3** | Per-agent LLM brain (text in, text out) replaces canned line; engage dispatches an Office Service task | `office_director.py --dry-run --llm --utterance "status?"` returns an in-character HUD payload |
| **C4** | Voice: `voice_pipeline` TTS out; mic ASR in | Speak to Dr. Caroll, hear him answer |
| **C5** | Memory + `face_player` + world events | He remembers; the guard reports; agents turn to you |

C1–C2 are a few hours of engine work; C3 reuses llm-play wholesale; C4 wires the existing
`voice_pipeline`; C5 is the depth.

## 7. Open decisions (from VISION §9, narrowed to the office)

- **Perception scope:** give each brain only its `agents[]` neighbours + the player, not
  the god view — enables secrets/rumor.
- **Turn-taking:** push-to-talk (hold a key near an agent) is the simplest robust start;
  always-listening ASR later.
- **Line length:** cap utterances to ~2 HUD lines; the HUD isn't a chat window.
- **Where the director runs:** as an llm-play adapter (`game_llm/adapters/agent_office/`)
  so it shares backends/UI, or standalone in `tools/agent_office_llm/`. Scaffold is
  standalone now; folding into llm-play is a C3 task.
```
