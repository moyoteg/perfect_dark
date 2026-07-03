# Virtual Agent Office — SPEC Conformance Audit

**Audits:** [`SPEC.md`](./SPEC.md) (source of truth) vs. actual code, both variants.
**Date:** 2026-07-02 · **Mode:** static analysis only (no code changed).
**Scope:** all four reported symptom areas — spawn, agents, doors/geometry, greeter/lang/crash — plus stage-registration, lang, and NFR contracts.

---

## Method & hard limitation

Every check below is **static**: reading code, data, and the deploy artifacts, plus running
the packer/validator in Python. **I cannot build or run the macOS `pd.arm64`**, so anything
that is only observable at runtime (where you actually spawn, whether an agent is visible /
facing right / animating, whether a mesh renders, CPU load, whether the greeter fires, how
the menu name displays) is marked **RUNTIME-UNVERIFIABLE** and mapped to a `V-` step in
SPEC §13. The audit tells you which contracts are provably met, which are provably broken,
and which need your playtest to close.

**Verdict up front:** the setups **conform to the documented data/registration contracts**
(door counts, agent counts, stage array, lang slots, C-guards all present). There is **one
concrete, high-severity defect provable from the data — spawn/agent pad collisions (F1)** —
which alone explains "wrong spawn location" *and* "agents misplaced," since 2 of the 3 player
spawn pads sit on top of an agent. The remaining symptoms are runtime-gated and need a rebuild
+ playtest to localize; this audit narrows where to look.

---

## Conformance matrix

Legend: ✅ pass · ❌ fail · ⚠️ pass-with-risk · 🎮 runtime-unverifiable (needs playtest)

### A. Spawn & lobby (US-6, AC-6.1–6.4, §7, FR-1.4)

| Contract | Status | Evidence |
|----------|--------|----------|
| Three intro `Spawn` pads per variant | ✅ | `src/levels/agent_office.py` L43–45; `_ci.py` same |
| G5 spawn pads = `0x80/0x09/0x61`, coords Y≈35 | ✅ | pad `0x80`=(2612,35,340), `0x09`=(2312,35,440), `0x61`=(2535,35,-320) |
| CI spawn pads = `0x0E/0x00/0x10` | ✅ | `PAD_BRIEFING_ENTRY/ALT/LOBBY` resolve to these |
| **Spawn pads must not collide with agent pads** | ❌ **F1** | G5 `0x09`=Orchestrator, `0x61`=Ops; CI `0x00`=Orchestrator, `0x10`=Director |
| `playerSnapSpawnGroundY` guards both stages (AC-6.2/6.3) | ✅ | `src/game/player.c` L228 (G5 trust pad Y), L236 (CI high-pad→ground) |
| Player lands on walkable lobby floor | 🎮 | **V-1** — boot logs inconsistent (see F2) |
| All 8 agents reachable without doors | 🎮 | **V-1/V-7** |

### B. Agents (§7, FR-3.2/3.3, AC-2.1–2.4)

| Contract | Status | Evidence |
|----------|--------|----------|
| 8 `Chr` agents, chrnum `0x31`+ sequential | ✅ | `agent_office.py` `CHR_AGENT_FIRST=0x31`, 8 specs |
| G5 pad assignments match §7 table | ✅ | Director `0xBE`, Orch `0x09`, Research `0x08`, Code `0x60`, QA `0x7E`, Sec `0x9E`, Ops `0x61`, Comms `0x7F` |
| CI pad assignments match §7 table | ✅ | Director `0x10`, Orch `0x00`, Research `0x0F`, Code `0x0D`, QA `0x01`, Sec `0x12`, Ops `0x11`, Comms `0x03` |
| Per-agent ailist `0x0401+N` | ✅ | `AILIST_AGENT_BASE=0x0401`; `agent_ailist_chunks()` |
| Briefing anim locked at pad (AC-2.4) | ✅ (static) | `_AGENT_ANIM_FLAGS = SLOWUPDATE\|LOCKPOS` |
| Agents visible, upright, facing briefing ring | 🎮 | **V-1** — body/anim ids only checkable in-engine |
| Two agents share a pad with player spawn | ❌ **F1** | see A |

### C. Doors & geometry (US-5, §8, FR-4, NFR-1)

| Contract | Status | Evidence |
|----------|--------|----------|
| G5 = 47 doors | ✅ | `len(agent_office_depo_doors())==47` |
| CI = 88 doors + 2 lift assemblies (18 props) | ✅ | `ci_retail_doors()==88`, `ci_retail_lifts()==18 props` |
| `prepare_agent_office_doors`: sibling=0, DEACTIVATED, strip CANNOT_ACTIVATE/KEEPOPEN | ✅ | `depo_retail_doors.py` L256–272 |
| No `mp_unlock=True` shipped (NFR-1.2) | ✅ | `agent_office_depo_doors()` calls `parse_setupdepo_doors(mp_unlock=False)` |
| `propobj.c` skips `doorTick` when DEACTIVATED (NFR-1.1) | ✅ | `propobj.c` L11385–11386 gated on `!OBJFLAG_DEACTIVATED` |
| Door meshes render without exploding | 🎮 | **V-5** |
| No ~100% CPU freeze at idle | 🎮 | **V-6** |
| Lobby not blocked by a static door | 🎮 | **V-1** — deactivated doors keep collision; a closed leaf across the lobby path would trap the player |

### D. Lang, greeter, crash-safety (§9, US-8, AC-2.3, NFR-4)

| Contract | Status | Evidence |
|----------|--------|----------|
| G5 slots `L_DEPO_004–008,053,061,066,067` present | ✅ | none missing in `depo.json` |
| CI slots `L_DISH_000–007,125` present | ✅ | none missing in `dish.json` |
| All strings latin-1 encodable (FR-5.6) | ✅ | 0 issues |
| `aiShowHudmsg` null/empty guard (AC-2.3/NFR-4.3) | ✅ | `chraicommands.c` L4350+: `if (text==NULL\|\|text[0]=='\0') return false` |
| `hudmsgCreateWithColour` variants guarded | ⚠️ **F3** | `aiShowHudmsgMiddle/TopMiddle` pass `langGet(...)` straight into `hudmsgCreateWithColour` — no null guard. Not hit by current ailists (they use `0x00CB`→`aiShowHudmsg`), latent only |
| Security greeter opt-in, both variants (US-8) | ✅ | `greet_text` set: G5 `L_DEPO_066` (0x1842), CI `L_DISH_005` (0x1C05) |
| `if_distance_to_target_lt 0x0052` @ 400u, latched | ✅ | `agent_office*.py`; opcode `0052 0028 <lbl>` |
| Examine-only agents byte-identical (AC-8.3) | ✅ | `tests/test_agent_office_ailist.py` (7/7 + CI) |
| Greeter actually fires / no double-line with examine | 🎮 | **V-4** |
| Deployed lang bank auto-copied (FR-5.5) | ✅ | `deploy_lang_bank()` in both play scripts; confirmed firing in `.last_launch.log` ("Lang bank up to date: LdepoE") |

### E. Stage registration (§6)

| Artifact | Status | Evidence |
|----------|--------|----------|
| `constants.h` `0x83`/`0x84` | ✅ | L4054–4055 |
| `files.h` `FILE_UMP_SETUPAGENT_OFFICE*` `0x07f2`/`0x07f4` | ✅ | L2045/2047 |
| `stagetable.c` rows (ROM geo + mod setup) | ✅ | rows `0x07f1`/`0x07f3` |
| `data.h` `g_Stages[92]` == 92 initializer rows (NFR-4.1) | ✅ | declared 92, counted 92 |
| `romdata.c` external mod filenames | ✅ | L590/611 |
| `mplayer/setup.c` arena rows + sentinel ids | ✅ | `0x7FFA`/`0x7FF9` |
| `lang.c` sentinel name handlers (FR-2.4) | ✅ | added this session: `0x7FFA/0x7FF9/0x7FFB` |
| Menu name displays in-game | 🎮 | **V-9** (needs `pd` rebuild) |

### F. Electron / CLI (FR-6, FR-7, US-4, US-7)

| Contract | Status | Evidence |
|----------|--------|----------|
| Play scripts G5/CI, `--solo` default argv | ✅ | `--boot-stage 0x83/0x84 --skip-intro --scenario-0 --solo` |
| Launch guards `pgrep_play` + `--force` (NFR-2) | ✅ | present in both scripts |
| Electron LOCATIONS g5/ci + Kit actions | ✅ | `main.js` LOCATIONS; `kit.json` `playAgentOffice`/`playAgentOfficeCi` |
| No `open -na` fallback (regression sentinel) | ✅ | Terminal-only launch |

---

## Findings (prioritized)

### F1 — Player spawns on top of agents *(HIGH · provable · explains 2 symptoms)*

**What.** Of the 3 intro spawn pads, 2 are the exact pads two agents stand on:

| Variant | Colliding spawn pad | Agent on that pad |
|---------|--------------------|-------------------|
| G5 | `0x09` (alt) | **Orchestrator** |
| G5 | `0x61` (lobby alt) | **Ops** |
| CI | `0x00` (alt) | **Orchestrator** |
| CI | `0x10` (lobby alt) | **Director** |

MP quick-start picks among all intro spawns, so on ~2 of 3 boots the player materializes
inside/against an agent → "spawned in the wrong place" + "agent shoved / misplaced." Only the
**primary** pad (G5 `0x80` @ Z=+340; CI `0x0E`) is clear of agents (agents cluster at Z −192…−466 / the foyer ring).

**Spec impact.** SPEC §7 itself lists these same overlapping values, so the **spec is internally
inconsistent** — it must be fixed together with the code.

**Proposed fix (code + spec).** Replace the two colliding alt pads with empty lobby pads, or
drop to a single guaranteed-clear spawn. Candidate clear G5 lobby pads near the ring but
unoccupied need picking from the retail pad list (e.g. a pad between the console `0x06` and the
ring, Y≈35, not in the agent set). Then update SPEC §7 tables + AC-6.1. **Do not** reuse any
pad in the agent set `{0xBE,0x09,0x08,0x60,0x7E,0x9E,0x61,0x7F}` (G5) / `{0x10,0x00,0x0F,0x0D,0x01,0x12,0x11,0x03}` (CI).

### F2 — Spawn location inconsistent across boot logs *(MED · runtime)*

`.boot_test_g5.log` / `.boot_test.log` show `spawn … pos=(2584,27,2807) room=67` and `(2911,27,2811) room=65` — far from the lobby and at **Y=27**, not 35. `.last_launch.log` (newer) shows `(2312,35,380)` / `(2535,35,-380)` — *near* the alt pads `0x09`/`0x61` (i.e. the F1 collision). Two readings: the room-67 spawns are **stale** (older setup before lobby pads), or a spawn path still resolves to a non-lobby pad under some flag. **Cannot disambiguate without a rebuild.** → **V-1**: run `play-agent-office.sh`, note spawn coords; if room 65/67 recurs, it's a live bug beyond F1.

### F3 — Unguarded HUD-message variant *(LOW · latent)*

`aiShowHudmsg` (the path the agent/console ailists use via cmd `0x00CB`) is null-guarded ✅.
The sibling `aiShowHudmsgMiddle` / `TopMiddle` handlers feed `langGet(...)` straight into
`hudmsgCreateWithColour` with no null/empty check. Not reachable from current ailists, so no
crash today — but NFR-4.3 ("`aiShowHudmsg` null guard prevents SIGSEGV") is only *partially*
true. Harden if any future agent line uses a Middle/TopMiddle command.

### F4 — Validator pad-Y warning noise *(INFO · not a defect)*

`pdmap validate` prints dozens of `[WARN] Pad NNN: Y=… far above the floor`. These are the
**full retail pad graph** (`SKIP_PADS` + `load_retail_pads`, FR-1.3) — briefing-wing/upper-floor
pads the agent office never spawns on (only the 3 intro pads matter). Benign, but it buries real
warnings. Consider limiting the fall-damage check to pads referenced by intro `Spawn` commands,
or suppressing it under `agent_office`/retail-overlay maps.

### F5 — Runtime-only symptoms still open *(needs playtest)*

"Agents misplaced/missing," "doors/geometry broken," and "greeter/crash" cannot be confirmed
or cleared statically beyond F1/F3. Body/head/anim ids, mesh integrity, CPU, and greeter timing
are all in-engine. Map to **V-1…V-9** in SPEC §13. F1 is the most likely root of the
agent-misplacement report; fix it first, then re-observe before chasing the rest.

---

## Prioritized fix list

| # | Fix | Files | Verify |
|---|-----|-------|--------|
| 1 | **F1** — repoint the 2 colliding alt spawns to clear lobby pads (both variants); update SPEC §7 + AC-6.1 | `tools/pdmap/agent_office*.py` (`PAD_PLAYER_SPAWN_ALT/_LOBBY`), `SPEC.md` | V-1 |
| 2 | **F2** — rebuild + `play-agent-office.sh`, record spawn coords; confirm lobby, not room 65/67 | — (playtest) | V-1 |
| 3 | Re-run V-2..V-9 after F1: agent placement, doors, console, greeter, menu names | — (playtest) | V-2…V-9 |
| 4 | **F3** — add null guard to `hudmsgCreateWithColour` variants (hardening) | `src/game/chraicommands.c` | rebuild |
| 5 | **F4** — scope the pad-Y fall-damage warning to spawn pads only | `tools/pdmap/validate.py` | `pdmap validate` |

**Build gate for any of the above:** C changes → `cmake --build build --target pd -j8`; lang/data
changes are Python-only and deploy via the play scripts (which now auto-copy lang banks).

---

## What this audit could NOT check (must playtest)

`V-1` spawn location & no fall damage · `V-1` agent visual placement/facing/anim · `V-4` greeter
fires once & no double-line · `V-5` door meshes don't explode · `V-6` no CPU freeze · `V-9` menu
names render · CI-specific `V-7/V-8`. All gated on a macOS `pd.arm64` build I can't run here.

## Spec corrections this audit surfaces

- **§7 (both tables):** player alt-spawn pads duplicate agent pads (F1) — the spec encodes the bug; correct spec + code together.
- **NFR-4.3:** scope-narrow the claim to "`aiShowHudmsg`" (the guarded path); the `WithColour` variants are unguarded (F3).
- **§13 smoke test:** `len(agent_office_ci_lifts())` returns **18** (props), not 2 (assemblies) — the table's "2" is assemblies; clarify to avoid a false "MISMATCH" when someone runs the smoke check.
