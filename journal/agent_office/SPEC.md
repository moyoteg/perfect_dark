# Virtual Agent Office — Product & Engineering Spec

**Status:** Spec-driven development source of truth (2026-07-02)  
**Parent:** [`SPEC.md`](../../SPEC.md) (Perfect Dark AIO kit-wide contracts)  
**Scope:** Two retail-geometry MP maps (dataDyne G5 + Carrington Institute), Electron launcher, CLI play scripts, and the live-LLM conversation layer roadmap.

Companion docs (historical / slice detail):

| Doc | Role |
|-----|------|
| [`PHENOMENAL_VISION.md`](./PHENOMENAL_VISION.md) | **North-star thesis** — the dual mandate: extremely *productive* AND extremely *fun*, each reinforcing the other. Pillars, cast, moment-to-moment loop, emotional design, metrics, anti-goals. **Start here for *what* and *why*.** |
| [`VISION.md`](./VISION.md) | **Dream vision** — vivid Slack/chat ↔ 3D office mapping, journey map v0→dream |
| [`SLACK_MIRROR_ROADMAP.md`](./SLACK_MIRROR_ROADMAP.md) | **Slack mirror plan** — phased roadmap (Phase 0–7); Phase 1 status |
| [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md) | **North-star vision** — 3D game interface for managing AI agents; lobby-as-control-plane, Slack/connector model, full system design (this spec is its shipped P0) |
| [`SPEC_AUDIT.md`](./SPEC_AUDIT.md) | Conformance audit of the shipped setups vs. this spec (fix list, incl. F1 spawn collision) |
| [`PRODUCTION_ENGINEERING.md`](./PRODUCTION_ENGINEERING.md) | **Production loop** — domain type catalog, pass log, scenario ladder |
| [`SESSION_NOTES.md`](./SESSION_NOTES.md) | Full session chronology and bug-fix archaeology |
| [`NEXT_STEPS.md`](./NEXT_STEPS.md) | Living checklist — defers to **this spec** for contracts |
| [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md) | Live LLM / voice layer build spec (Phase 2+) |
| [`PERFECT_DARK_KIT.md`](../../PERFECT_DARK_KIT.md) § Virtual Agent Office | Kit Hub integration summary |

---

## 1. Product vision & goals

### North star

**Virtual Agent Office** is a Perfect Dark AIO mod feature: a **virtual agent simulation hub** where the player walks familiar single-player mission lobbies, meets eight friendly non-combat NPC “agents,” and interacts via Z-target examine lines and a lobby console — before (eventually) talking to live LLM-driven characters in voice.

The experience mirrors retail **pre-mission lobby UX**: an open, walkable foyer where briefing happens without opening locked wings.

### Two variants, one pattern

| Variant | Map id | Stage | Menu name | Retail geometry | MP setup asset |
|---------|--------|-------|-----------|-----------------|----------------|
| **dataDyne G5** | `agent_office` | `STAGE_AGENT_OFFICE` `0x83` | *Virtual Agent Office* | ROM `bg_depo` | `Ump_setupagent_officeZ` |
| **Carrington Institute** | `agent_office_ci` | `STAGE_AGENT_OFFICE_CI` `0x84` | *Agent Office: Carrington* | ROM `bg_dish` | `Ump_setupagent_office_ciZ` |
| **CI Fresh Lobby** (recommended) | `agent_office_ci` | `STAGE_CITRAINING` `0x26` + `--agent-office-ci-lobby` | *Carrington Institute (Fresh / Lobby)* | ROM `bg_dish` | `Ump_setupagent_office_ciZ` (injected on solo boot) |
| **Office Lab / Matrix** | `agent_office_lab` | `STAGE_AGENT_OFFICE_LAB` `0x85` | *Office Lab / Matrix* | mod `bg_agent_office_lab` | `Ump_setupagent_office_labZ` |

Both retail variants share:

- **Retail geometry overlay** — collision, tiles, pads from NTSC-final ROM; only MP setup + lang banks deployed from mod.
- **Lobby hub layout** — player, eight agents, and console on open foyer pads at **Y ≈ 35**.
- **Peaceful explore default** — solo, no weapons, no combat sims unless explicitly requested.
- **Retail door/lift props** — sibling-remapped door-only packs; doors **unlocked** and animate normally via (Z).

### Goals (v1 shipped baseline)

1. Deploy and boot either variant reliably from CLI, Kit Hub, or Electron.
2. Eight `TEAM_NONCOMBAT` agents with briefing animations, Z-target HUD status, optional proximity greeting.
3. Tagged lobby console: **(Z)** shows room overview (throttled).
4. Retail doors and CI lifts **present and openable** without CPU freeze or mesh corruption.
5. Human-readable MP menu names; lang strings resolve without crash.
6. Foundation for live LLM conversation layer (static lines remain fallback).

### Workspace model (Slack analogy)

Product intent: entering Agent Office should feel like **joining a Slack workspace**, not
loading a bare game map. Three layers stay distinct:

| Concept | What it is today | Slack analogy |
|---------|------------------|---------------|
| **Workspace** | One office location — G5, CI (Fresh Lobby recommended), or Office Lab | A Slack workspace / team instance |
| **Your agent profile** | Your identity in that workspace (display name + optional codename); stored locally in the Electron launcher until a host (Projex/PragChat) owns it | Your Slack member profile |
| **Team agents** | Eight pre-placed `TEAM_NONCOMBAT` NPCs at desks (Director … Comms) | Teammates / bots in channels — not you | 

**Onboarding is intentional.** Before **Enter Office**, the Electron app asks you to create
your Perfect Dark agent profile (name + codename). That step is acceptable and expected — like
signing up for a workspace — not friction to remove.

**What “create agent” means today (2026-07-04):**

| Surface | Behavior |
|---------|----------|
| **Electron launcher** | Minimal profile form → `localStorage` (`vao_agent_profile`). **Enter Office** requires a display name. Profile syncs to `journal/agent_office/workspace_config.json` (Phase 1); Office Service reads via `GET /workspace/config`. |
| **In-game** | You spawn as the default Perfect Dark player (Joanna). No custom avatar, callsign HUD, or profile picker. CI Fresh Lobby uses `--profile 0` (solo **save slot**, not agent identity). |
| **Office Service / LLM** | Eight **team** agents pre-seeded; **human member** record in `workspace_config.json` + REST (`POST/GET /workspace/config`, `GET /slack/channels`). See [`SLACK_MIRROR_ROADMAP.md`](./SLACK_MIRROR_ROADMAP.md) Phase 1. |
| **Future host (Projex/PragChat)** | Workspace membership + agent profile should live in the host; Perfect Dark 3D tab and Electron become clients of the same Office Service state (see [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md)). |

**Workspace picker (Electron “Location”):** each option is a separate spatial workspace over
the same eight-role team roster:

| Workspace key | Label | Notes |
|---------------|-------|-------|
| `g5` | dataDyne G5 Building | Meeting-room corridor spawn |
| `ci_lobby` | Carrington Institute (Fresh / Lobby) | **Recommended** — retail solo visor |
| `ci` | Carrington Institute (legacy MP boot) | `0x84`; visor fixes applied |
| `lab` | Office Lab / Matrix | White-room furniture sandbox |

Copy and UI should say **workspace** where the user picks an office, and **team agents** for
the NPC roster — not “virtual agents” for both you and the desk NPCs.

---

## 2. User stories & acceptance criteria

### US-1 — Peaceful explore (default)

**As a** player launching Agent Office for the first time,  
**I want** to spawn alone in the lobby with no weapons or hostile AI,  
**So that** I can walk and examine agents without combat pressure.

| # | Acceptance criterion |
|---|---------------------|
| AC-1.1 | Default launch uses `--solo --scenario-0 --skip-intro --boot-stage 0x83` or `0x84`. |
| AC-1.2 | `port/src/bootmp.c` clears MP weapon loadout and sim quick-team when `--solo` on agent-office stages; MP time/score limits disabled (no match end). |
| AC-1.3 | All eight agents use `team=TEAM_NONCOMBAT`, `SPAWNFLAG_DONTSHOOTME`. |
| AC-1.4 | No weapon pickups or hostile AI in either MP setup. |
| AC-1.5 | Electron **Enter Office** maps to solo; **With Combat Sims** maps to `--with-bots`. |

### US-2 — Z-target agent examine

**As a** player in the lobby,  
**I want** to Z-target an agent and see a status HUD line,  
**So that** I learn each agent’s role.

| # | Acceptance criterion |
|---|---------------------|
| AC-2.1 | Z-targeting an agent triggers `aiShowHudmsg` with role-specific lang string. |
| AC-2.2 | Same agent cannot spam messages — ~3 s cooldown (`EXAMINE_COOLDOWN_TICKS = 180`). |
| AC-2.3 | Missing lang bank does **not** crash (`chraicommands.c` null/empty guard). |
| AC-2.4 | Standing agents play pad-locked briefing anims (`SLOWUPDATE \| LOCKPOS`). CI sitting agents (Ops `0x00FC`, QA `0x00FE`) use retail chair snap: `chair` tag + `FIXEDHEIGHT` + `naturalanim` + `PAUSEATEND \| SLOWUPDATE` (no `LOCKPOS`), matching `setupdish.c` Beau/Russ/QA colleagues. |

### US-3 — Console interact

**As a** player at the lobby console,  
**I want** to press **(Z)** on the tagged console for lobby-style Perfect Menu access (same as retail CI hub PC),  
**So that** I can browse missions / options from the console like pre-mission lobby mode.

| # | Acceptance criterion |
|---|---------------------|
| AC-3.1 | Console prop tagged `OBJ_AGENT_CONSOLE` (`0x20`); monitor ailist `AILIST_CONSOLE_MONITOR` (`0x1002`) may still show overview HUD (throttled). |
| AC-3.2 | G5: `MODEL_PD_CONSOLE` @ `PAD_DEPO_0062` (scale `0x0100`, no TOPADBOUNDS — pad bbox is generic); CI: `MODEL_CIHUB` @ `PAD_DISH_0017`. |
| AC-3.3 | **(Z)** on console opens `g_CiMenuViaPcMenuDialog` (Perfect Menu) on all agent-office stages via `propobjInteract` — same handler as retail CI tag `0x47`. |
| AC-3.4 | Overview string (`L_DEPO_061` / `L_DISH_125`) may still appear from monitor ailist after menu close. |

### US-3b — Visor pause (Escape)

**As a** player in peaceful agent-office explore,  
**I want** **Escape** to open the visor pause menu (not MP scoreboard),  
**So that** I can access inventory / Perfect Menu like solo or CI lobby.

| # | Acceptance criterion |
|---|---------------------|
| AC-3b.1 | `playerShouldUseSoloPauseMenu()` returns true on `STAGE_AGENT_OFFICE` / `_CI` / `_LAB` even when `mplayerisrunning`. |
| AC-3b.2 | Escape/Start routes to `playerPause(MENUROOT_MAINMENU)` → `soloChoosePauseDialog()`. |
| AC-3b.3 | G5 opens `g_SoloMissionPauseMenuDialog`; CI and Lab open `g_CiMenuViaPauseMenuDialog`. |
| AC-3b.4 | **CI Fresh Lobby** (`STAGE_CITRAINING` `0x26` + `--agent-office-ci-lobby`): native retail solo pause/visor — no MP-boot hacks. |
| AC-3b.5 | **Legacy CI MP boot** (`0x84` + `--solo`): after `setupLoadFiles`, `normmplayerisrunning` cleared so visor render + resume viewport match solo paths. |

### US-4 — Location picker

**As a** macOS user,  
**I want** to pick G5 vs Carrington in the Electron app,  
**So that** I don’t need separate shell scripts.

| # | Acceptance criterion |
|---|---------------------|
| AC-4.1 | Electron location picker switches boot stage `0x83` / `0x84` / `0x26` (CI lobby) and spawns correct play script. |
| AC-4.2 | Agent roster UI loads from Python `agent_office_layout_payload` / `agent_office_ci_layout_payload`. |
| AC-4.3 | Kit Hub exposes both variants (`playAgentOffice`, `playAgentOfficeCi`). |

### US-5 — Retail doors & lifts present

**As a** player who knows the retail missions,  
**I want** to see familiar door frames and CI elevators,  
**So that** the space feels authentic even if wings stay closed.

| # | Acceptance criterion |
|---|---------------------|
| AC-5.1 | G5 setup includes **47** retail door props; CI includes **88** doors + **2** lift assemblies (18 props). |
| AC-5.2 | Door meshes render correctly — no “exploding” geometry (sibling remapping). |
| AC-5.3 | All retail doors spawn **closed** (`frac=0`); normal `doorTick` on stages `0x83`/`0x84`. |
| AC-5.4 | All retail sliding/swinging/laser doors unlocked; player opens/closes via **(Z)** interact. |

### US-6 — Spawn & navigation

**As a** player spawning in the meeting room (G5) or lobby/office (CI),  
**I want** to land on the walkable floor,  
**So that** I don’t fall through or snap below the floor.

| # | Acceptance criterion |
|---|---------------------|
| AC-6.1 | G5 primary spawn `PAD_DEPO_003D` (2403, 27, 3165) — west corridor into holograph meeting room; alts `0x003E` (3131, 27, 3160), `0x008F` (2646, 27, 1990). CI primary `PAD_DISH_00F5` (637, 360, 923) — retail intro / Jo's office; alts `0x0053`, `0x00F6`. |
| AC-6.2 | `playerSnapSpawnGroundY` trusts pad Y on G5 when ground is >10 u below pad (meeting corridor Y≈27). |
| AC-6.3 | CI high-pad guard prevents Y≈460 sofa-lounge fall-through for legacy pad heights. |
| AC-6.4 | G5: all eight agents in holograph meeting room; CI: office-wing desks reachable from foyer spawns. |

### US-7 — Launch safety & performance

**As a** developer or player relaunching frequently,  
**I want** guarded launches and stable runtime,  
**So that** I don’t stack game instances or freeze the machine.

| # | Acceptance criterion |
|---|---------------------|
| AC-7.1 | Play scripts skip launch if same `--boot-stage` game already running unless `--force`. |
| AC-7.2 | macOS uses Terminal-only launch (no `open -na` duplicate spawn). |
| AC-7.3 | Electron `launchInFlight` blocks overlapping deploy/play per location+mode. |
| AC-7.4 | macOS GL 3.0 compat warnings in log are benign when 4.1 core succeeds. |

### US-8 — Proximity greeting (opt-in, v1.1)

**As a** player approaching Security,  
**I want** a one-shot greeting when I enter range,  
**So that** agents feel alive before live LLM lands.

| # | Acceptance criterion |
|---|---------------------|
| AC-8.1 | Opt-in via `VirtualAgentSpec.greet_text`; demo on Security (both variants). |
| AC-8.2 | `if_distance_to_target_lt` (`0x0052`) at `GREET_RANGE = 400`; latches until player leaves. |
| AC-8.3 | Examine-only agents byte-identical to pre-greeting build (`tests/test_agent_office_ailist.py`). |

---

## 2A. Vision contracts — pillars → testable acceptance

The north-star thesis ([`PHENOMENAL_VISION.md`](./PHENOMENAL_VISION.md)) states nine pillars: three
productive (P1–P3), three fun (F1–F3), three fusion (X1–X3). This section makes each pillar a
**buildable, verifiable contract** — the bridge from "why" to the FRs below. Each `VC-*` names the
pillar, the observable behaviour, the engine/service seam that carries it, and acceptance criteria
that can be checked (in-engine or by unit test). Status: **spec** = defined here, not yet built;
**partial** = seam exists; **shipped** = verified. This is the backlog the phased path (§14, VISION
§12) draws from.

### VC-P1 — Legibility at a glance *(pillar P1 · status: partial)*

**Contract:** standing at the entrance, the player can identify the whole fleet's state and what
needs them in **< 5 s without any menu**, purely from ambient signal (posture, animation, per-desk
glyph).

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-P1.1 | Every agent's `state` (`idle`/`working`/`awaiting_approval`/`blocked`) maps to a distinct, distinguishable standing/sitting animation or posture. | `OfficeService` agent `state` → ailist anim select; §5 interaction model |
| VC-P1.2 | Each agent desk carries a **status glyph** whose colour encodes urgency (green idle / amber working / red needs-you), readable across the room. | new per-desk prop + `/observe agents[].status` (C1) |
| VC-P1.3 | The single most-urgent agent is the single most-salient thing on the floor (brightest glyph + facing aisle) — "urgency maps to salience" (VISION §9 legibility law). | glyph intensity ranked by `state` severity |
| VC-P1.4 | A fresh observer, 60 s in, correctly names who is busy / blocked / waiting (the "read the room" test, §metrics). | manual test protocol |

### VC-P2 — Delegation at the speed of speech *(pillar P2 · status: partial)*

**Contract:** handing a task to an agent costs **≤ 2 actions** (approach + say, or approach + drop);
no form, no modal, no context switch.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-P2.1 | Facing an agent within engage range scopes the next spoken/typed intent to *that* agent (`dispatch(agent_id, intent)`). | C3 director-engage → `OfficeService.dispatch`; `/act` |
| VC-P2.2 | Addressing the room (no agent faced) routes via the Orchestrator, which picks the agent and reports where it went. | `dispatch("orchestrator", …)` + routing |
| VC-P2.3 | A dispatched task produces immediate multi-sensory feedback (sound + visible token on the desk) within one tick. | `task.created` event → HUD/audio (F3) |
| VC-P2.4 | Delegation requires no textual form fields; free intent only. Measured: median actions-to-dispatch ≤ 2. | interaction instrumentation |

### VC-P3 — Trust through transparency + control *(pillar P3 · status: partial)*

**Contract:** every side-effecting action is auditable and gated by a **human-present approval** by
default; nothing irreversible happens without the player, and the "why" is always inspectable.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-P3.1 | 100% of `write`/`destructive` connector calls pass through `ConnectorGateway.invoke` with an `AuditEntry` recorded. | `connectors.py` `invoke` + `audit[]` |
| VC-P3.2 | A `write`/`destructive` action by an agent whose autonomy is `ask-approval` blocks (`PolicyError`) and stages an `Approval`; the task pauses `awaiting_approval`. | `office_service.py` `perform`/`_run` |
| VC-P3.3 | Approval is cleared by the player being present (walk to the agent, or to Security), then `approve()` resumes the plan at the staged action. | `approve()` + cursor resume |
| VC-P3.4 | `destructive` risk never auto-executes even at autonomy `act` — always requires approval. | `invoke` risk branch |
| VC-P3.5 | The player can inspect *why* any completed action happened (agent, connector, action, args, autonomy, human-present flag, result). | `AuditEntry` fields |

### VC-F1 — Presence *(pillar F1 · status: partial)*

**Contract:** an agent reads as *a person in a place* — a body, a fixed desk, a voice from its
position, and a gaze that finds the player on approach.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-F1.1 | Each agent has an assigned home pad (§7) and is reliably found there. | per-agent home pads |
| VC-F1.2 | Crossing engage range makes the agent turn to face the player (`face_player`) and pause its idle/briefing loop. | `/act` `face_player`; US-8 greet |
| VC-F1.3 | Agent speech is anchored to the agent's world position (HUD line from agent; future TTS spatialised). | `aiShowHudmsg` at chr; §Phase 2 TTS |
| VC-F1.4 | Leaving range latches the engagement closed; returning re-engages fresh. | greet latch (AC-8.2) |

### VC-F2 — Character *(pillar F2 · status: spec)*

**Contract:** each agent is a distinct *someone* — a personality, a way of talking, opinions, moods,
and memory of the player — not a role label.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-F2.1 | Each agent has a persona definition (system prompt, knowledge, what it withholds) distinct from every other. | per-agent `brain.json` (LLM layer) |
| VC-F2.2 | Lines are delivered in-character, not as bare status strings (Comms gossips; the guard grumbles). | brain prompt + lang authoring |
| VC-F2.3 | Each agent has a distinct voice, position-anchored and intelligibility-gated. | voice pipeline (Phase 2) |
| VC-F2.4 | An agent references the player's prior interaction within and across sessions (memory). | agent memory store; VC-X3 |

### VC-F3 — Responsiveness / juice *(pillar F3 · status: partial)*

**Contract:** the world answers every player action instantly and with weight; ambient life never
stops.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-F3.1 | Every spatial verb (look/approach/target/speak/use/leave) produces immediate visual + audio feedback — no dead inputs. | interaction handlers |
| VC-F3.2 | Task hand-off and approval each have a discrete, satisfying feedback beat (sound + animation), not a silent state flip. | `task.*`/`approval.*` events → FX |
| VC-F3.3 | Ambient floor life runs continuously (typing loops, idle shifts, footsteps) even with zero player input. | idle ailists; ambient audio |
| VC-F3.4 | Motion has weight — doors take a beat; agents pivot rather than snap-rotate. | doorTick timing; turn anim |

### VC-X1 — Ambient room = live dashboard *(pillar X1 · status: spec)*

**Contract:** there is **no separate dashboard** — the room *is* the status surface. The signal that
makes it feel alive is the same signal that makes the player productive.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-X1.1 | Fleet state is derivable entirely from in-world signal (posture + desk glyphs + monitors); the console mirrors, never replaces, it. | VC-P1 signals + console |
| VC-X1.2 | No management action *requires* an out-of-world panel; the lobby console is a convenience overview, not a dependency (VISION §9 no-chrome law). | `fleet_status()` mirrors world |
| VC-X1.3 | Inspect/approve panels appear anchored to the agent/object they concern and dismiss on step-away (diegetic, not global chrome). | anchored HUD panels |

### VC-X2 — Consequence / emergence *(pillar X2 · status: spec)*

**Contract:** what agents do matters to the world and to each other, and the player feels it;
perception is **sliced**, not god-view, which is what unlocks surprise.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-X2.1 | Each agent perceives only its neighbourhood + what is addressed to it — never a global god-view of all events. | scoped `/observe` per agent; event `target` |
| VC-X2.2 | A fact/event can propagate agent-to-agent (hand-off, rumor) via the event bus rather than teleporting to omniscience. | `EventBus` + agent-to-agent hand-off |
| VC-X2.3 | A floor-wide event (alarm/incident) visibly changes multiple agents' behaviour, not just one desk. | broadcast event → multi-agent anim |
| VC-X2.4 | Inbound Slack that mentions the player flips Comms to a needs-you state (consequence from outside the world). | `ingest_slack` → Comms `blocked` |

### VC-X3 — Mastery / the office compounds *(pillar X3 · status: spec)*

**Contract:** as the player learns the floor they get better at running it, **and** the office gets
better at running itself (memory + granted autonomy + routines). Same growth curve.

| # | Acceptance criterion | Seam |
|---|---------------------|------|
| VC-X3.1 | Per-agent autonomy is player-configurable (`suggest`/`ask-approval`/`act`) per tool; raising trust reduces required approvals. | `Agent.autonomy_for`; gateway |
| VC-X3.2 | Agent memory persists across sessions so repeated context need not be re-supplied. | agent memory store; `service_state` |
| VC-X3.3 | Return-pull is measurable: sessions opened with **no** task dispatched (the player came to *be there*), tracked over time. | session instrumentation |
| VC-X3.4 | Over time, share of tasks completed without a human-present approval rises for trusted agent/tool pairs (office self-runs more). | audit trend on `human=False` |

### Contract coverage map

| Pillar | Contract | Primary seam today | Nearest phase (§14 / VISION §12) |
|--------|----------|--------------------|----------------------------------|
| P1 legibility | VC-P1 | `/observe agents[]` (C1) | Alive |
| P2 delegate | VC-P2 | `dispatch` + `/act` (C2/C3) | Alive → Voiced |
| P3 trust | VC-P3 | `ConnectorGateway` + `Approval` | Acting |
| F1 presence | VC-F1 | greet + `face_player` | Alive |
| F2 character | VC-F2 | `brain.json` + voice pipeline | Voiced |
| F3 juice | VC-F3 | event → FX/anim | Alive |
| X1 ambient=dash | VC-X1 | world signal + console mirror | Living |
| X2 consequence | VC-X2 | scoped observe + `EventBus` | Living |
| X3 mastery | VC-X3 | autonomy + memory + `service_state` | Living → Yours |

---

## 3. Functional requirements

### FR-1 — Maps & MapDef

| Req | Detail |
|-----|--------|
| FR-1.1 | Level modules: `src/levels/agent_office.py`, `src/levels/agent_office_ci.py`. |
| FR-1.2 | MapDef flags: `SKIP_SEG`, `SKIP_TILES`, `SKIP_PADS` — retail geometry from ROM. |
| FR-1.3 | Full retail pad graph loaded via `load_retail_pads()` (`depo` / `dish`). |
| FR-1.4 | Three intro `Spawn` pads per variant — retail mission intro pads (G5 lobby Y≈35; CI office Y≈360). |
| FR-1.5 | Validate: `python3 tools/pdmap.py validate agent_office[_ci]`. |
| FR-1.6 | Deploy: `python3 tools/pdmap.py build agent_office[_ci] --deploy`. |

### FR-2 — Stages & MP arena registration

| Req | Detail |
|-----|--------|
| FR-2.1 | Stage constants in `src/include/constants.h`: `0x83`, `0x84`. |
| FR-2.2 | Stage table rows in `src/game/stagetable.c` → ROM geo file ids + mod setup file ids. |
| FR-2.3 | MP arena entries in `src/game/mplayer/setup.c` with sentinel name ids `0x7FFA`, `0x7FF9`. |
| FR-2.4 | Menu name resolution in `src/game/lang.c` sentinel handlers. |
| FR-2.5 | `g_Stages` array size **must** match initializer count — currently **`[92]`** in `data.h` + `stagetable.c`. |

### FR-3 — MP setup packing

| Req | Detail |
|-----|--------|
| FR-3.1 | Packer modules: `tools/pdmap/agent_office.py`, `tools/pdmap/agent_office_ci.py`. |
| FR-3.2 | Eight `Chr` agents at `CHR_AGENT_FIRST` (`0x31`) + chrnums sequential. |
| FR-3.3 | Per-agent ailist `AILIST_AGENT_BASE + index` (`0x0401`…). |
| FR-3.4 | Console monitor ailist `AILIST_CONSOLE_MONITOR` (`0x1002`). |
| FR-3.5 | MP init ailist `AILIST_MP_INIT` (`0x1000`) — simulant spawn only when `--num-sims > 0`. |
| FR-3.6 | Console prop + tagged object for `(Z)` activation. |
| FR-3.7 | CI setup additionally includes lift assemblies from `ci_retail_lifts.py`. |
| FR-3.8 | CI setup includes office-wing desk/chair/monitor props from `ci_retail_office_props.py` — **four agent desk clusters** at pads `0x021A`–`0x0225` only (excludes lobby/lift-adjacent `0x0226`–`0x022B`, `0x022D`; chr pads `0x00F5`–`0x00FE` are separate). |

### FR-4 — Retail geometry overlay (doors/lifts)

| Req | Detail |
|-----|--------|
| FR-4.1 | G5 doors: `depo_retail_doors.py` — parse `setupdepo.c`, 47 props. |
| FR-4.2 | CI doors: `ci_retail_doors.py` — parse `setupdish.c`, 88 props (8 lift-car pads excluded). |
| FR-4.3 | CI lifts: `ci_retail_lifts.py` — 2 assemblies, 18 props, internal offsets preserved. |
| FR-4.4 | All doors pass through `prepare_agent_office_doors()` before pack. |
| FR-4.5 | Deploy copies setup binaries to `mods/mod_allinone/` via `tools/pdmap/deploy.py`. |

### FR-5 — Language / HUD strings

| Req | Detail |
|-----|--------|
| FR-5.1 | G5 bank `LANGBANK_DEPO` — JSON `src/assets/ntsc-final/lang/depo.json`. |
| FR-5.2 | CI bank `LANGBANK_DISH` — JSON `src/assets/ntsc-final/lang/dish.json`. |
| FR-5.3 | Stage → bank routing in `src/game/lang.c`. |
| FR-5.4 | Mod overrides: `mods/mod_allinone/files/LdepoE`, `LdishE`. |
| FR-5.5 | Play scripts auto-copy lang banks on deploy (`deploy_lang_bank()`). |
| FR-5.6 | All JSON strings **latin-1** encodable. |

### FR-6 — Electron launcher

| Req | Detail |
|-----|--------|
| FR-6.1 | App: `tools/agent-office-electron/` → `Virtual Agent Office.app`. |
| FR-6.2 | Location picker (G5 / CI), deploy+play, deploy-only, with-bots, quit game. |
| FR-6.3 | Kit registration in `tools/pd_kit/kit.json` (`agent-office` app id). |
| FR-6.4 | Single-instance via Kit `electron_single_instance.js`. |
| FR-6.5 | **Slack mirror Phase 1:** profile + workspace sync to `journal/agent_office/workspace_config.json`; renderer **Channels** panel; IPC `office:save-workspace-config` / `office:get-workspace-config`. |

### FR-7 — CLI play scripts

| Req | Detail |
|-----|--------|
| FR-7.1 | `scripts/play-agent-office.sh` — G5 deploy + launch. |
| FR-7.2 | `scripts/play-agent-office-ci.sh` — CI deploy + launch (`0x84` MP-boot path; `normmplayerisrunning` cleared on peaceful solo). |
| FR-7.2b | `scripts/play-agent-office-ci-lobby.sh` — **recommended** CI Fresh Lobby (`0x26` solo + `--agent-office-ci-lobby`). |
| FR-7.3 | `scripts/launch-agent-office-app.sh` — dev Electron. |
| FR-7.4 | `scripts/build-agent-office-electron.sh` — release bundle. |

---

## 4. Non-functional requirements

### NFR-1 — Performance (door CPU)

| Req | Detail |
|-----|--------|
| NFR-1.1 | Agent-office stages: normal `doorTick` for all non-deactivated doors; idle closed doors are cheap. |
| NFR-1.2 | Never ship door-only packs with retail sibling offsets unremapped (mesh corruption / CPU storm). |
| NFR-1.3 | CI lift car doors unlocked; lift motion still requires retail mission ailists. |

### NFR-2 — Launch guards

| Req | Detail |
|-----|--------|
| NFR-2.1 | `pgrep_play()` matches `pd.arm64` + repo binary path + target `--boot-stage`. |
| NFR-2.2 | `--force` kills existing matching PID before relaunch. |
| NFR-2.3 | Electron refuses launch when game already running for location (must Quit first). |
| NFR-2.4 | `launchInFlight` Set retained 120 s after IPC launch to block double-clicks. |

### NFR-3 — macOS OpenGL

| Req | Detail |
|-----|--------|
| NFR-3.1 | Expected log: GL 3.0 compat fails, 4.1 core succeeds — classify as benign in Electron log tail. |
| NFR-3.2 | Game window is separate from Terminal; notification reminds user to focus `pd.arm64`. |
| NFR-3.3 | Stage-specific GL limits in `port/src/pdmain.c` for agent-office stages. |

### NFR-4 — Stability & data integrity

| Req | Detail |
|-----|--------|
| NFR-4.1 | `g_Stages` array size must equal initializer entry count (segfault if truncated). |
| NFR-4.2 | Door `sibling` fields remapped to packed door-only indices before deploy. |
| NFR-4.3 | `aiShowHudmsg` null guard prevents SIGSEGV on missing lang. |

### NFR-5 — Accessibility & UX (Electron)

| Req | Detail |
|-----|--------|
| NFR-5.1 | High-contrast dark theme; readable status line for deploy/launch errors. |
| NFR-5.2 | Buttons disabled while launch in flight; game status polled. |
| NFR-5.3 | Log tail + reveal-in-Finder for deploy logs. |

### NFR-6 — Determinism & testability

| Req | Detail |
|-----|--------|
| NFR-6.1 | Ailist bytecode regression test for proximity layer. |
| NFR-6.2 | Packer inventory counts documented and verifiable after `pdmap build --deploy`. |
| NFR-6.3 | Play script logs timestamped to `journal/agent_office[_ci]/.last_launch.log`. |

---

## 5. Architecture

### Data flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Authoring layer                                                            │
│  src/levels/agent_office[_ci].py  →  MapDef (SKIP_*, retail pads, spawns)   │
│  tools/pdmap/agent_office[_ci].py →  agents, ailists, console, doors/lifts  │
│  tools/pdmap/*_retail_doors.py    →  parse setupdepo/setupdish door lines    │
│  tools/pdmap/ci_retail_lifts.py   →  parse lift assemblies (CI only)         │
│  lang/{depo,dish}.json             →  mklang → LdepoE / LdishE              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ pdmap build --deploy
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Mod directory (mods/mod_allinone/)                                         │
│  Ump_setupagent_officeZ      Ump_setupagent_office_ciZ                      │
│  files/LdepoE                files/LdishE                                   │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ play-agent-office*.sh / Electron IPC
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Runtime (build/pd.arm64)                                                   │
│  ROM bg_depo / bg_dish  →  seg, tiles, pads (unchanged)                   │
│  stagetable.c row         →  FILE_BG_* + FILE_UMP_SETUPAGENT_OFFICE*        │
│  bootmp.c --solo          →  peaceful MP init (no weapons/sims)             │
│  lv.c peaceful solo       →  clear normmplayerisrunning after setup load     │
│  setup.c CI lobby flag    →  inject Ump_setupagent_office_ci on STAGE 0x26 │
│  setup load               →  doors, agents, console, ailists                │
│  player.c                 →  spawn ground snap guards                       │
│  propobj.c                →  doorTick for active doors; deactivated skip   │
│  chraicommands.c          →  aiShowHudmsg → HUD                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent interaction model

```
Each agent (AILIST 0x0401+N):
  loop briefing anim (slow tick, lock pos)
  if Z-target → aiShowHudmsg(status_text) [cooldown 180 ticks]
  if greet_text set:
    if distance < GREET_RANGE → one-shot greet [latch until far]

Console monitor (AILIST 0x1002):
  if player (Z) activates OBJ_AGENT_CONSOLE → aiShowHudmsg(overview) [cooldown]
```

### Eight agent roles (both variants)

Director, Orchestrator, Research, Code, QA, Security, Ops, Comms — pad assignments differ by variant; see §7.

---

## 6. Stage registration contract

Adding or changing an agent-office stage **must** update all of:

| Artifact | Contract |
|----------|----------|
| `src/include/constants.h` | `#define STAGE_AGENT_OFFICE` / `_CI`, stage index constants |
| `src/include/files.h` | `FILE_USETUPAGENT_OFFICE*`, `FILE_UMP_SETUPAGENT_OFFICE*` file ids |
| `src/game/stagetable.c` | Row: stage id, ROM seg/tiles/pads ids, mod setup ids |
| `src/include/data.h` | `extern struct stagetableentry g_Stages[N]` — **N = entry count** |
| `port/src/romdata.c` | External mod filenames (`Ump_setupagent_officeZ`, etc.) |
| `src/game/mplayer/setup.c` | `g_MpArenas` row with sentinel menu name id |
| `src/game/lang.c` | (a) stage→langbank in switch; (b) sentinel name handler if using `0x7FFx` |
| `port/src/pdmain.c` | Optional per-stage GL limit string |
| `tools/pdmap/deploy.py` | Deploy target filename mapping |
| Play scripts | `--boot-stage` hex value |
| Electron `LOCATIONS` | `bootStage`, script path, layout import |

**Current invariant:** `g_Stages[92]` with **92** initializer entries including both agent-office rows.

**Stage table rows (NTSC-final overlay):**

| File slot prefix | G5 | CI |
|------------------|----|----|
| Seg / tiles / pads | `FILE_BG_DEPO_*` | `FILE_BG_DISH_*` |
| Setup | `FILE_USETUPAGENT_OFFICE`, `FILE_UMP_SETUPAGENT_OFFICE` | `FILE_USETUPAGENT_OFFICE_CI`, `FILE_UMP_SETUPAGENT_OFFICE_CI` |

---

## 7. Spawn & lobby model

### Design intent

Retail missions place the player in a **walkable lobby or office** before locked briefing wings. Agent Office G5 spawns the player **inside the holograph meeting room corridor** (Y≈27); CI keeps retail intro spawn pads. Agents remain at their briefing/desk pads.

### G5 (`agent_office`)

| Element | Pad | Notes |
|---------|-----|-------|
| Player spawn (primary) | `0x003D` | West corridor into meeting room (2403, 27, 3165) |
| Player spawn (alts) | `0x003E`, `0x008F` | East approach corridor (3131, 27, 3160); south approach (2646, 27, 1990) |
| Console | `0x0062` | `MODEL_PD_CONSOLE` — meeting-room doorway |
| Director | `0x0088` | Meeting table |
| Orchestrator | `0x0089` | East side |
| Research | `0x0064` | South terminal |
| Code | `0x0063` | Centre terminal |
| QA | `0x008A` | West side |
| Security | `0x008B` | West entry (+ proximity greeter) |
| Ops | `0x00F8` | North desk (sitting typing) |
| Comms | `0x0087` | North-east |

### CI (`agent_office_ci`)

| Element | Pad | Notes |
|---------|-----|-------|
| Player spawn (primary) | `0x00F5` | Jo's office — retail intro (637, 360, 923) — `setupdish.c` `intro[]` |
| Player spawn (alts) | `0x0053`, `0x00F6` | Outside Jo's office door; Carrington office desk |
| Console | `0x0017` | `MODEL_CIHUB` — north lobby alcove |
| Director | `0x00F6` | Carrington office desk |
| Orchestrator | `0x00F5` | Jo's office / retail intro desk |
| Research | `0x00F7` | West lab colleague desk |
| Code | `0x00FA` | East lab colleague desk |
| QA | `0x00FE` | West office chair — `chair=0x02`, retail snap |
| Security | `0x002F` | West corridor entry (+ proximity greeter) |
| Ops | `0x00FC` | East wing chair — `chair=0x00`, retail snap (Beau desk) |
| Comms | `0x00F8` | Far west colleague desk |

### `playerSnapSpawnGroundY` rules (`src/game/player.c`)

| Stage | Rule |
|-------|------|
| `STAGE_AGENT_OFFICE` | If `cdFindGround` Y is **>10 u below** spawn pad Y, **trust pad Y** (meeting corridor Y≈27 over lower floor column). |
| `STAGE_AGENT_OFFICE_CI` | If spawn pad Y **>300** and ground **>40 u below** pad, use ground (office / upper-level pad guard). |
| General port | If ground invalid or `\|ground - spawn\| > 80`, trust spawn Y. |

---

## 8. Door & lift model

### Openable doors (v3 — sibling remap + normal animation)

Retail `door(...)` entries use **`sibling`** as a **relative command index** into the full `setupdepo.c` / `setupdish.c` props array. Agent Office packs a **door-only subset**; retail sibling values must be **remapped** to relative indices within the packed door list or `setupCreateDoor()` resolves garbage pointers → **exploding meshes**.

**Shipped strategy:**

| Step | Behavior |
|------|----------|
| Parse | All retail `door(...)` lines with **`mp_unlock=True`** (strip locks, `DEACTIVATED`, `CANNOT_ACTIVATE`, blanket `KEEPOPEN`) |
| Remap | `tools/pdmap/retail_door_siblings.py`: retail props[] cmd index → packed door index; rewrite `sibling` |
| Init | `doorInit` → `frac = 0` (closed) unless retail setup already had `KEEPOPEN` and mp_unlock preserved it |
| Runtime | Normal `doorTick` / `doorsCalcFrac` on stages `0x83`/`0x84`; player opens/closes via **(Z)** |
| Lifts | CI lift assemblies packed intact; car doors mp-unlocked (no blanket `KEEPOPEN`) |
| Result | Authentic door frames; paired leaves stay in sync; no mesh explosion when siblings remapped |

**Approach-glitch note:** Earlier static-open (`KEEPOPEN` + zero `doorTick`) avoided visual pop caused by bad sibling walks writing garbage `frac` values. With remapped siblings, normal tick is safe. If perf regresses, prefer distance-gated tick (not static open) — profile ~135 doors idle-closed first.

**Verified:** all 47 depo + 88 dish flat-door siblings target another door in the same stage — safe door-to-door remap.

### Inventory (post-deploy, verified)

| Variant | Retail doors | Lift assemblies | Zipped setup | Unpacked setup |
|---------|-------------|-----------------|--------------|----------------|
| G5 | **47** | — | 823 B | 12 096 B |
| CI | **88** (96 retail − 8 lift-car pads) | **2** (18 props) | 1 041 B | 23 332 B |

### CI lifts

- Parsed as **self-contained assemblies** (lift + 4 doors + 4 lift_door) with internal offsets intact.
- Lift-car door pads excluded from flat door list to avoid duplicates.
- Car doors **mp-unlocked**; lifts provide visual presence + collision — **not rideable** without retail mission ailists.

### Historical note (v1 static doors)

Earlier builds zeroed siblings and set `DEACTIVATED|CANNOT_ACTIVATE` to avoid mesh corruption and CPU freeze before remapping landed. v2 briefly used blanket `KEEPOPEN` + zero `doorTick` (static open). Superseded by §8 v3: remap + unlock + normal animation.

---

## 9. Lang contract

### String slots

**G5 — `LANGBANK_DEPO` (`depo.json` → mod `LdepoE`)**

| Slot | Consumer | Purpose |
|------|----------|---------|
| `L_DEPO_004`–`008` | Director–QA agents | Custom agent status lines |
| `L_DEPO_053` | Comms agent | Custom comms copy (repurposed from retail) |
| `L_DEPO_061` | Console (Z) | Custom room overview |
| `L_DEPO_066` | Security agent | Status + proximity greeter |
| `L_DEPO_067` | Ops agent | Custom status line |

**CI — `LANGBANK_DISH` (`dish.json` → mod `LdishE`)**

| Slot | Consumer | Purpose |
|------|----------|---------|
| `L_DISH_000`–`007` | All eight agents | Custom agent status lines |
| `L_DISH_125` | Console (Z) | Custom room overview |

### Lang id encoding in ailists

Text ids passed to `aiShowHudmsg` use `(LANGBANK << 9) | index` — see `VirtualAgentSpec.status_text` constants in packer modules.

### Rebuild & deploy pipeline

```bash
# After JSON edits:
cmake --build build --target pd_headers -j8

# Auto on play (deploy_lang_bank in play scripts):
./scripts/play-agent-office.sh --no-play

# Manual copy if needed:
cp build/ntsc-final/assets/files/LdepoE.o mods/mod_allinone/files/LdepoE
cp build/ntsc-final/assets/files/LdishE.o mods/mod_allinone/files/LdishE

# After chraicommands.c / lang.c changes:
cmake --build build --target pd -j8
```

### MP menu names (sentinel ids)

| Sentinel | Resolved string | Arena stage |
|----------|-----------------|-------------|
| `0x7FFA` | Virtual Agent Office | G5 |
| `0x7FF9` | Agent Office: Carrington | CI |

Handlers live in `src/game/lang.c`; arena rows in `src/game/mplayer/setup.c`.

---

## 10. Electron app contract

**Location:** `tools/agent-office-electron/`  
**Product:** Virtual Agent Office.app (`scripts/release/`, nested in Perfect Dark Kit)

### IPC surface (`preload.js` → `main.js`)

| Channel | Args | Returns |
|---------|------|---------|
| `office:get-info` | `locationKey` | title, versions, repo root, locations list, game status, layout, log path |
| `office:launch` | `mode`, `locationKey` | spawn result, game status, log tail, launch hints |
| `office:kill-game` | `locationKey` | killed PIDs |
| `office:game-status` | `locationKey` | PID / running processes |
| `office:tail-log` | `lines`, `locationKey` | log tail + GL compat hints |
| `office:reveal-path` | path | Finder reveal |
| `office:get-workspace-config` | — | Read `workspace_config.json` |
| `office:save-workspace-config` | `{ locationKey, displayName, codename }` | Persist member + workspace channels |

### Launch modes

| UI / mode | Script args | Behavior |
|-----------|-------------|----------|
| Enter Office (solo) | _(none)_ | `--solo` default |
| Deploy only | `--no-play` | build + deploy only |
| With Combat Sims | `--with-bots` | `--num-sims 4` |
| Force relaunch | _(CLI only)_ | `--force` on play scripts |

### Location config (`LOCATIONS` in `main.js`)

| Key | bootStage | Script | Layout import |
|-----|-----------|--------|---------------|
| `g5` | `0x83` | `scripts/play-agent-office.sh` | `agent_office_layout_payload` |
| `ci` | `0x84` | `scripts/play-agent-office-ci.sh` | `agent_office_ci_layout_payload` |
| `ci_lobby` | `0x26` + `--agent-office-ci-lobby` | `scripts/play-agent-office-ci-lobby.sh` | `agent_office_ci_layout_payload` |

### Repo root resolution (priority)

1. `PD_REPO_ROOT` env  
2. Baked `repo-config.json`  
3. Walk up to `tools/pd_kit/kit.json`

### Kit integration (`tools/pd_kit/kit.json`)

| Field | Value |
|-------|-------|
| App id | `agent-office` |
| Dev launch | `scripts/launch-agent-office-app.sh` |
| Build | `scripts/build-agent-office-electron.sh` |
| Hub actions | `playAgentOffice`, `playAgentOfficeCi` |

---

## 11. CLI / scripts contract

### `scripts/play-agent-office.sh` (G5)

| Flag | Effect |
|------|--------|
| _(default)_ | `pdmap build agent_office --deploy` + `deploy_lang_bank` + launch `--solo` |
| `--no-play` | Deploy only |
| `--with-bots` | Add `--num-sims 4` (combat sim regression) |
| `--force` | Kill existing game for `0x83` and relaunch |
| Extra args | Forwarded to `pd.arm64` |

**Launch argv (default):**

```
--basedir data/ --moddir mods/mod_allinone/ --savedir $REPO
--boot-stage 0x83 --skip-intro --scenario-0 --solo
```

### `scripts/play-agent-office-ci.sh` (CI, legacy MP boot `0x84`)

Same contract as G5 with `agent_office_ci`, boot stage `0x84`, log dir `journal/agent_office_ci/`, lang bank `LdishE`. Peaceful solo clears `normmplayerisrunning` after setup load (visor/resume fix).

### `scripts/play-agent-office-ci-lobby.sh` (CI Fresh Lobby — **recommended**)

| Flag | Effect |
|------|--------|
| _(default)_ | Deploy `agent_office_ci` + launch `--boot-stage 0x26 --profile 0 --agent-office-ci-lobby` (true solo; no `--solo`/`--scenario-0`) |
| `--no-play` | Deploy only |
| `--force` | Kill existing lobby game and relaunch |

**Launch argv (default):**

```
--basedir data/ --moddir mods/mod_allinone/ --savedir $REPO
--boot-stage 0x26 --skip-intro --profile 0 --agent-office-ci-lobby
```

Retail `STAGE_CITRAINING` provides native visor pause, PC interact, and menu textures; `setup.c` injects `Ump_setupagent_office_ciZ` for agents/console/doors.

### Prerequisites

| Requirement | Path / command |
|-------------|----------------|
| NTSC-final ROM | `data/pd.ntsc-final.z64` (fallback paths in scripts) |
| Built port | `build/pd.arm64` (`cmake --build build --target pd -j8`) |
| Lang objects (for fresh strings) | `cmake --build build --target pd_headers -j8` |

### Logs & PID files

| Variant | Deploy/play log | PID file |
|---------|-----------------|----------|
| G5 | `journal/agent_office/.last_launch.log` | `journal/agent_office/.last_play.pid` |
| CI | `journal/agent_office_ci/.last_launch.log` | `journal/agent_office_ci/.last_play.pid` |
| CI Fresh Lobby | `journal/agent_office_ci/.last_launch_lobby.log` | `journal/agent_office_ci/.last_play_lobby.pid` |
| Electron | `~/Library/Logs/PerfectDarkKit/virtual-agent-office.log` | — |

---

## 12. Known limitations & out of scope (v1)

| Limitation | Notes |
|------------|-------|
| Doors not openable | ~~Deactivated by design~~ — **fixed:** sibling remap + mp_unlock (2026-07-04) |
| CI lifts not rideable | Visual + collision only; no retail mission lift scripts |
| Sibling remapping | **Implemented** in `retail_door_siblings.py` |
| macOS Terminal launch | Game runs in Terminal tab; separate `pd.arm64` window |
| In-engine LLM / voice | Out of scope v1 — see `LLM_CONVERSATION_LAYER.md` |
| Multiplayer human players | Maps are MP stages but designed for solo explore |
| PAL / other ROMs | NTSC-final retail overlay only |
| Automated in-engine CI | Manual play verification required for visual/regression |
| Briefing room interior access | G5 agents spawn inside holograph meeting room; doors openable |

---

## 13. Verification / test plan

### Automated (run without game)

```bash
# Map validation
python3 tools/pdmap.py validate agent_office
python3 tools/pdmap.py validate agent_office_ci

# Ailist regression (proximity layer)
python3 tests/test_agent_office_ailist.py

# Packer smoke — door counts
python3 -c "
from tools.pdmap.depo_retail_doors import agent_office_depo_doors
from tools.pdmap.ci_retail_doors import agent_office_ci_doors
from tools.pdmap.ci_retail_lifts import agent_office_ci_lifts
print('G5 doors', len(agent_office_depo_doors()))
print('CI doors', len(agent_office_ci_doors()))
print('CI lifts', len(agent_office_ci_lifts()))
"

# Lang latin-1 sanity (after JSON edits)
python3 -c "
import json
for p in ['src/assets/ntsc-final/lang/depo.json','src/assets/ntsc-final/lang/dish.json']:
    json.load(open(p)).encode('latin-1')
print('latin-1 OK')
"
```

### Build + deploy

```bash
cmake --build build --target pd_headers -j8
cmake --build build --target pd -j8
python3 tools/pdmap.py build agent_office --deploy
python3 tools/pdmap.py build agent_office_ci --deploy
```

Expected deploy artifacts in `mods/mod_allinone/`:

- `Ump_setupagent_officeZ`, `Ump_setupagent_office_ciZ`
- `files/LdepoE`, `files/LdishE` (after play script or manual copy)

### In-engine manual checklist

| # | Step | Pass criteria |
|---|------|---------------|
| V-1 | `./scripts/play-agent-office.sh` | Spawns in G5 meeting room; 8 agents at briefing pads; doors openable |
| V-2 | Z-target each G5 agent | HUD status line; ~3 s cooldown; no crash |
| V-3 | (Z) on west console | Overview HUD (`L_DEPO_061` copy) |
| V-4 | Walk Security within ~400 u | One-shot proximity greet; no repeat until leave |
| V-5 | Visual door pass | Door frames render; **no** exploding meshes; **(Z)** opens nearby doors |
| V-6 | CPU check (30 s idle) | No freeze; fan not pegged |
| V-7 | `./scripts/play-agent-office-ci.sh` | CI foyer spawn; 8 agents; console north alcove |
| V-8 | CI lifts visible | Elevator assemblies present; static |
| V-9 | MP menu names | *Virtual Agent Office* / *Agent Office: Carrington* |
| V-10 | `./scripts/play-agent-office.sh --with-bots` | 4 sims spawn; combat regression only |
| V-11 | Relaunch without `--force` | Second launch skipped (pgrep guard) |
| V-12 | Electron picker | Both locations deploy+play; `launchInFlight` blocks double-click |
| V-13 | Kit Hub actions | Both `playAgentOffice` and `playAgentOfficeCi` work |

### Regression sentinels (do not break)

- `g_Stages[92]` size matches initializer count
- Examine-only agents: byte-identical ailist vs pre-`greet_text` baseline
- `aiShowHudmsg` null guard remains
- `propobj.c` runs normal `doorTick` for non-deactivated doors on agent-office stages
- Play scripts: no `open -na` fallback restored

---

## 14. Future work & open questions

### Phase 2 — Live LLM conversation ([`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md))

| Id | Work | Owner files |
|----|------|-------------|
| C1 | `/observe` emits office `agents[]` | `port/src/llm_observe.c` |
| C2 | `/act` accepts `agents[].say` | `port/src/llm_bridge.c` |
| C3 | Per-agent LLM brain | `tools/agent_office_llm/` |
| C4 | Voice pipeline (ASR/TTS) | llm-play / `voice_pipeline/` |
| C5 | Memory, `face_player`, world events | director + engine hooks |

Static HUD lines **remain fallback** when director offline.

### Phase 3 — Openable doors & briefing access

**Open question:** Pack full retail prop sequences between door pairs, or build sibling remapping table for door-only subset?

**Constraint:** Any solution must not reintroduce `doorTick` CPU storm without gating (e.g. only doors near player active).

### Phase 4 — Functional CI elevators

Requires porting retail lift ailists / triggers — **high effort**; visual-only lifts acceptable until then.

### Other open questions

| Question | Options / notes |
|----------|-----------------|
| Dedicated greeting strings vs reusing status text? | Security currently reuses status slot; may want `L_*` greet-only lines |
| In-map warp to briefing wing? | Depends on openable doors + interior agent placement |
| Windows/Linux Electron launch? | Currently macOS Terminal pattern; may need platform branch |
| PAL retail overlay? | Separate pad/door inventories |
| Proximity greet on more agents? | Opt-in `greet_text` per `VirtualAgentSpec` |
| Electron `--force` button? | CLI has it; UI requires Quit first by design |

---

## 15. File index (canonical paths)

### Maps & packing

| Path | Role |
|------|------|
| `src/levels/agent_office.py` | G5 MapDef entry |
| `src/levels/agent_office_ci.py` | CI MapDef entry |
| `tools/pdmap/agent_office.py` | G5 agents, ailists, console, `pack_agent_office_setup()` |
| `tools/pdmap/agent_office_ci.py` | CI agents, ailists, console, lifts |
| `tools/pdmap/depo_retail_doors.py` | 47 G5 doors — parse, prepare, pack |
| `tools/pdmap/ci_retail_doors.py` | 88 CI doors |
| `tools/pdmap/ci_retail_lifts.py` | 2 CI lift assemblies |
| `tools/pdmap/retail_door_siblings.py` | Sibling remapping for door-only packs |
| `tools/pdmap/ci_retail_office_props.py` | CI office-wing desks/chairs/monitors |
| `tools/pdmap/deploy.py` | `--deploy` → moddir |

### Engine / port

| Path | Role |
|------|------|
| `src/include/constants.h` | Stage ids `0x83`, `0x84` |
| `src/include/data.h` | `g_Stages[92]` declaration |
| `src/include/files.h` | Setup file id constants |
| `src/game/stagetable.c` | Stage rows |
| `src/game/mplayer/setup.c` | MP arena + sentinel name ids |
| `src/game/lang.c` | Lang bank routing + menu name sentinels |
| `src/game/player.c` | Spawn ground snap guards |
| `src/game/chraicommands.c` | `aiShowHudmsg` null guard |
| `src/game/propobj.c` | Normal `doorTick`; skip when `OBJFLAG_DEACTIVATED` |
| `src/game/setup.c` | `setupCreateDoor()` sibling resolution |
| `port/src/romdata.c` | External mod setup filenames |
| `port/src/bootmp.c` | Peaceful solo MP init for agent-office stages |
| `port/src/pdmain.c` | Per-stage GL limits |

### Lang

| Path | Role |
|------|------|
| `src/assets/ntsc-final/lang/depo.json` | G5 HUD strings |
| `src/assets/ntsc-final/lang/dish.json` | CI HUD strings |
| `mods/mod_allinone/files/LdepoE` | Deployed G5 bank |
| `mods/mod_allinone/files/LdishE` | Deployed CI bank |
| `tools/assetmgr/mklang` | JSON → binary compiler |

### Scripts & apps

| Path | Role |
|------|------|
| `scripts/play-agent-office.sh` | G5 deploy + launch |
| `scripts/play-agent-office-ci.sh` | CI deploy + launch |
| `scripts/launch-agent-office-app.sh` | Dev Electron |
| `scripts/build-agent-office-electron.sh` | Release `.app` |
| `tools/agent-office-electron/main.js` | Electron main process |
| `tools/agent-office-electron/preload.js` | IPC bridge |
| `tools/agent-office-electron/renderer/app.js` | UI |
| `tools/pd_kit/kit.json` | Kit app + Hub actions |

### Tests & LLM scaffold

| Path | Role |
|------|------|
| `tests/test_agent_office_ailist.py` | Ailist bytecode regression |
| `tools/agent_office_llm/` | LLM director scaffold (`--dry-run`) |
| `journal/agent_office/LLM_CONVERSATION_LAYER.md` | Live conversation spec |

### Documentation

| Path | Role |
|------|------|
| `journal/agent_office/SPEC.md` | **This document — source of truth** |
| `journal/agent_office/SESSION_NOTES.md` | Session history |
| `journal/agent_office/NEXT_STEPS.md` | Checklist (references SPEC) |
| `PERFECT_DARK_KIT.md` | Kit integration summary |

---

## 16. Office Lab sandbox map (`agent_office_lab`)

**Purpose:** Learn and regression-test office setups (desks, chairs, monitors, agent sit/operate anims, console interact, simple doors) in the Matrix Test Room white space **before** packing retail G5/CI geometry overlays.

| Item | Value |
|------|-------|
| Map id | `agent_office_lab` |
| Stage | `STAGE_AGENT_OFFICE_LAB` `0x85` |
| Menu name | *Office Lab / Matrix* (sentinel `0x7FF8`) |
| Geometry | Custom pdmap box arena — grey floor / black sky (same env as `STAGE_TEST_UFF`) |
| Deploy | `PDMAP_SEG_MODE=empty python3 tools/pdmap.py build agent_office_lab --seg --deploy` |
| Play | `./scripts/play-agent-office-lab.sh` → `--boot-stage 0x85 --solo` |
| Electron | Location picker third option **Office Lab / Matrix** |

### Sandbox contents (white room)

| Element | Count / detail |
|---------|----------------|
| Player spawn | Center `(0, 10, 0)` + two aisle alt spawns |
| Agents | 8 × `TEAM_NONCOMBAT` — standing operate/briefing + sitting QA/Ops (chair snap) |
| Desks | 8 × `MODEL_DD_DESK` |
| Chairs | 2 × `MODEL_DD_CHAIR` + chair tags (QA `0x02`, Ops `0x00`) |
| Monitors | 8 × `MODEL_GOODPC` (`SingleMonitor`) |
| Console | 1 × `MODEL_PD_CONSOLE` tagged `OBJ_AGENT_CONSOLE` |
| Test doors | 2 × `MODEL_DD_OFFICEDOOR` sliding, **sibling=-1** (no retail remap) |
| Lang | Reuses `LANGBANK_DEPO` / mod `LdepoE` (G5 agent status strings) |

### Registration contract (lab-specific)

Same six-file mod bundle as `animlab`: `bg_agent_office_lab.seg`, `_tilesZ`, `_padsZ`, `Usetupagent_office_labZ`, `Ump_setupagent_office_labZ`.  
`g_Stages[93]` — lab row uses `FILE_BG_AGENT_OFFICE_LAB_*` file ids `0x07f5`–`0x07f9`.  
Peaceful `--solo` init in `bootmp.c` includes `STAGE_AGENT_OFFICE_LAB`.

### Files

| Path | Role |
|------|------|
| `src/levels/agent_office_lab.py` | MapDef — matrix box tiles + pad wiring |
| `tools/pdmap/agent_office_lab.py` | Furniture, agents, doors, setup packer |
| `scripts/play-agent-office-lab.sh` | Deploy + launch script |

---

## Spec change log

| Date | Change |
|------|--------|
| 2026-07-06 | **C1 drift fix** — `/observe agents[]` (office NPC chrnums `0x31`–`0x38`) was absent from `port/src/llm_observe.c` despite task #14 being marked done (lost to a later revert/sync); rebuilt the `agents[]` serialization (new `LLM_AGENT_CHRNUM_FIRST/LAST` in `llm_bridge.h`), restoring the VC-P1/VC-F1 foundation the director already consumes (`office_director.py` `obs.get("agents")`) |
| 2026-07-06 | **§2A Vision contracts** — nine pillars (P1–P3, F1–F3, X1–X3) from `PHENOMENAL_VISION.md` translated into testable `VC-*` acceptance criteria + engine/service seams + coverage map; north-star doc linked at top of companion table |
| 2026-07-06 | Add [`PHENOMENAL_VISION.md`](./PHENOMENAL_VISION.md) — dual-mandate north-star thesis (productive AND fun) |
| 2026-07-04 | **CI Fresh Lobby** (`STAGE_CITRAINING` `0x26` + `--agent-office-ci-lobby`): solo boot + injected `Ump_setupagent_office_ciZ`; Electron option *Carrington Institute (Fresh / Lobby)* |
| 2026-07-04 | **0x84 visor fix:** clear `normmplayerisrunning` after peaceful `--solo` setup load (`lv.c` / `bootmp.c`) — MP setup kept, solo pause render path restored |
| 2026-07-04 | Visor pause on Escape + lobby PC interact on agent-office consoles (C: `playerShouldUseSoloPauseMenu`, `propobjInteract`) |
| 2026-07-04 | Add Office Lab sandbox map (`agent_office_lab`, STAGE 0x85) — matrix white room for furniture/agent/door testing |
| 2026-07-04 | G5 player spawn repointed to meeting-room corridor (`0x003D` primary; alts `0x003E`, `0x008F`); agents unchanged |
| 2026-07-04 | Revert static-open doors: sibling remap + mp_unlock only; normal doorTick animation |
| 2026-07-04 | Retail intro spawns restored (G5 `0x0083`, CI `0x00F5`); sibling remap + mp_unlock all doors |
| 2026-07-04 | Fix MP match-end on agent office (unlimited time/score); G5 console scale; doorTick open/cull |
| 2026-07-04 | G5 meeting-room spawns/agents restored; sibling remap + mp_unlock all doors; doorTick distance gate |
| 2026-07-04 | CI: pack office furniture props (`0x021A`–`0x022B`); doors set `CANNOT_ACTIVATE`; `propdoorInteract` guard |
| 2026-07-04 | CI: restrict office furniture to four agent desk clusters (`0x021A`–`0x0225`); drop lobby/lift-adjacent extras |
| 2026-07-04 | **Slack mirror Phase 1:** `SLACK_MIRROR_ROADMAP.md`; `workspace_config.json` + Office Service `/workspace/config` + `/slack/channels`; Electron Channels panel |
| 2026-07-04 | **Workspace model:** Slack-workspace analogy documented; Electron agent-profile onboarding (local); team vs human agent terminology |
| 2026-07-02 | Initial comprehensive spec from session notes + codebase state; spec-driven development mode |
