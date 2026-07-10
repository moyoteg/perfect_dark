# Virtual Agent Office — Session Notes (2026-07-02)

**2026-07-04 update — Slack mirror Phase 1 (workspace config + channels)**

Progressive Slack mirroring plan: [`SLACK_MIRROR_ROADMAP.md`](./SLACK_MIRROR_ROADMAP.md) (8 phases, 0–7).

**Shipped Phase 1:**
- Shared config: `journal/agent_office/workspace_config.json` (member + workspace location + Slack-shaped `channels[]`)
- Module: `tools/agent_office_llm/service/workspace_config.py`
- Office Service REST: `GET/POST /workspace/config`, `GET /slack/channels`
- Electron: **Channels** panel; auto-sync on profile/workspace change via IPC
- Tests: `tests/test_workspace_config.py`, extended `tests/test_office_service_http_api.py`

**Next:** Phase 2 — channel unread + lobby console `#general` ticker wired to service events.

---

**2026-07-04 update — Workspace model (Slack analogy)**

Product direction: onboarding that asks users to **create a Perfect Dark agent profile** before
entering the office is intentional — analogous to joining a Slack workspace (workspace = office
location; your profile = member identity; team agents = NPCs at desks).

**Documented in [`SPEC.md`](./SPEC.md) §1 Workspace model.** Electron launcher now has a
minimal **Your agent profile** form (display name + codename → `localStorage`); **Enter Office**
requires a display name. Profile is not yet wired to in-game identity or Office Service.

**Gaps for future work:** pass human agent to Office Service / Projex host; in-game callsign
HUD; avatar or chr binding; workspace membership persistence beyond localStorage.

---

**2026-07-04 update — CI visor/pause fix + Fresh Lobby architecture**

User reported Escape still showed no visor and no proper return to gameplay on CI (`0x84`) despite prior `menu.c`/`player.c` hudpiece patches. Root cause: peaceful agent-office boots via **MP quick-start** (`mplayerisrunning` + `normmplayerisrunning` both true). Retail solo/CI lobby keeps `normmplayerisrunning=false`, which drives `var8009dfc0` / `menuisactive` / gunmem for visor render and resume.

**Shipped fixes:**

1. **CI Fresh Lobby (recommended):** `--boot-stage 0x26 --agent-office-ci-lobby --profile 0` — true solo `STAGE_CITRAINING` with `Ump_setupagent_office_ciZ` injected in `setup.c`. Native visor, pause, and PC interact. Script: `scripts/play-agent-office-ci-lobby.sh`. Electron: *Carrington Institute (Fresh / Lobby)*.
2. **Legacy `0x84` path:** after `setupLoadFiles`, peaceful `--solo` clears `normmplayerisrunning` (`lv.c` + `bootmp.c`) while keeping MP setup for agents/spawns.

Verified boot log: `Ump_setupagent_office_ciZ` loads on stage 26; spawn `(637,360,923)` Jo's office; PID healthy ~8% CPU.

---

Comprehensive record of the Virtual Agent Office work session: two retail-geometry MP maps,
eight friendly NPC agents with Z-target examine, lobby-console interact, Electron launcher,
retail door/lift props (static), and the stability fixes required to ship lobby mode.

**Doc revision:** First pass at ~18:29 documented doors as *omitted* (intermediate fix).
This revision (~18:35+) reflects the **current packer source and deployed setups** after the
user request to restore doors/elevators while keeping peaceful explore mode.

---

## Overview

**Virtual Agent Office** is a Perfect Dark AIO mod feature that places eight `TEAM_NONCOMBAT`
virtual agents in familiar single-player mission geometry. The player walks a pre-mission
lobby hub, Z-targets agents for throttled HUD status lines, and uses **(Z)** on a tagged
console for a room overview.

Two variants share the same gameplay pattern but use different retail backgrounds:

| Variant | Map id | Stage constant | Stage id | Retail geometry | MP setup asset |
|---------|--------|----------------|----------|-----------------|----------------|
| **dataDyne G5** | `agent_office` | `STAGE_AGENT_OFFICE` | `0x83` | `bg_depo` (seg/tiles/pads) | `Ump_setupagent_officeZ` |
| **Carrington Institute** | `agent_office_ci` | `STAGE_AGENT_OFFICE_CI` | `0x84` | `bg_dish` (seg/tiles/pads) | `Ump_setupagent_office_ciZ` |

Both maps use **retail geometry overlay**: only the MP setup binary is deployed from the mod;
collision, tiles, and pad graph load from the NTSC-final ROM. MapDef sets `SKIP_SEG`,
`SKIP_TILES`, and `SKIP_PADS` so pdmap does not rebuild or replace retail level data.

---

## Architecture

### Retail geometry + custom setup

```
ROM (pd.ntsc-final.z64)
  └── bg_depo / bg_dish  →  seg, tiles, pads (unchanged)

mods/mod_allinone/
  └── Ump_setupagent_officeZ      →  doors, agents, console, ailists (G5)
  └── Ump_setupagent_office_ciZ   →  doors, lifts, agents, console, ailists (CI)
  └── files/LdepoE, LdishE       →  overridden lang banks (HUD strings)
```

Stage table entries in `src/game/stagetable.c` point each stage at ROM file slots
(`FILE_BG_DEPO_*` / `FILE_BG_DISH_*`) and mod setup slots (`FILE_UMP_SETUPAGENT_OFFICE*`).
`port/src/romdata.c` registers external mod filenames for the setup assets.

### Agent interaction model

Each agent gets a custom ailist (`AILIST_AGENT_BASE` + index) that:

1. Loops a briefing animation (`CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS`).
2. On Z-target (`if_target_aiming_at_me`), shows a HUD message via `aiShowHudmsg` (cmd `0x00CB`).
3. Enforces a ~3 s cooldown (`EXAMINE_COOLDOWN_TICKS = 180`).

A background monitor ailist (`AILIST_CONSOLE_MONITOR = 0x1002`) watches tag
`OBJ_AGENT_CONSOLE` (`0x20`). When the player activates the tagged console with **(Z)**,
it shows a room-overview string with the same cooldown pattern.

### Eight agent roles (both variants)

Director, Orchestrator, Research, Code, QA, Security, Ops, Comms — each mapped to a
retail lobby pad at **Y ≈ 35** so the briefing ring is walkable without opening doors.

---

## Current state (2026-07-02, end of session)

### Lobby hub UX

Retail missions use a walkable lobby before locked briefing wings (G5 guard foyer at
`PAD_DEPO_0080`; CI room `0x0014` at `PAD_DISH_000E`). Agent Office mirrors that UX:
player, agents, and console all live in the open lobby.

### Doors and lifts (verified in packer + deployed binaries)

Retail door props are **included** in MP setup — not omitted. Strategy:

| Step | What happens |
|------|----------------|
| Parse | All `door(...)` lines from `setupdepo.c` / `setupdish.c` with **`mp_unlock=False`** (retail flags preserved) |
| Prepare | `prepare_agent_office_doors()`: **`sibling = 0`**, **`OBJFLAG_DEACTIVATED`**, strip `CANNOT_ACTIVATE` / `KEEPOPEN` |
| Runtime | `propobj.c` skips `doorTick()` when deactivated — static mesh + collision, no CPU load |
| CI lifts | `ci_retail_lifts.py`: two retail `MODEL_CI_LIFT` assemblies (18 props); car doors deactivated |

**Counts (packer source, verified after `pdmap build --deploy`):**

| Variant | Retail doors in setup | Lift assemblies | Zipped setup size | Unpacked size |
|---------|----------------------|-----------------|-------------------|---------------|
| G5 | **47** | — (depo has no lift blocks) | 823 B | 12 096 B |
| CI | **88** (96 in retail; 8 lift-car pads excluded) | **2** (18 props) | 1 041 B | 23 332 B |

Doors **render** as static panels/frames but **do not open** (deactivated by design).
Briefing wings behind closed retail doorways remain inaccessible without re-enabling
`mp_unlock` (which previously caused ~100% CPU freeze).

### G5 (`agent_office`)

| Element | Pad | Notes |
|---------|-----|-------|
| Player spawn (primary) | `0x0080` | Retail guard patrol lobby (2612, 35, 340) |
| Player spawn (alts) | `0x0009`, `0x0061` | North corridor, south inner |
| Console | `0x0006` | `MODEL_PD_CONSOLE` — west lobby alcove |
| Director | `0x00BE` | NE lobby |
| Orchestrator | `0x0009` | North corridor |
| Research | `0x0008` | East wing |
| Code | `0x0060` | West inner |
| QA | `0x007E` | West outer |
| Security | `0x009E` | South entry |
| Ops | `0x0061` | South inner |
| Comms | `0x007F` | South outer |

### CI (`agent_office_ci`)

| Element | Pad | Notes |
|---------|-----|-------|
| Player spawn (primary) | `0x000E` | CI foyer centre (604, 35, 317) |
| Player spawn (alts) | `0x0000`, `0x0010` | South foyer, east lobby |
| Console | `0x0017` | `MODEL_CIHUB` — north lobby alcove |
| Director | `0x0010` | East lobby |
| Orchestrator | `0x0000` | South foyer |
| Research | `0x000F` | West outer |
| Code | `0x000D` | West inner |
| QA | `0x0001` | North foyer |
| Security | `0x0012` | NW corner |
| Ops | `0x0011` | East inner |
| Comms | `0x0003` | NE alcove |

---

## Peaceful explore mode (default)

Default launch is **non-combat**. Combat sims only when explicitly requested.

| Layer | Mechanism |
|-------|-----------|
| **Play scripts** | Default: `--solo`. `--with-bots` adds `--num-sims 4`. |
| **Electron app** | “Enter Office” → solo; “With Combat Sims” → `--with-bots`. |
| **Agents** | `team=TEAM_NONCOMBAT` (`0x80`), `spawnflags=SPAWNFLAG_BASICGUARD \| SPAWNFLAG_DONTSHOOTME`. |
| **Scenario** | `--scenario-0`, `--skip-intro`, direct `--boot-stage 0x83` / `0x84`. |
| **MP init ailist** | `AILIST_MP_INIT` (`0x1000`) emitted in setup; simulant spawn only when `--num-sims` > 0. |

No weapon pickups or hostile AI are placed in either setup. `--with-bots` restores standard
MP combat-sim behaviour for regression testing.

---

## Language strings

Strings live in JSON source files and are compiled to binary lang banks loaded from moddir.

### G5 — `LANGBANK_DEPO` (`src/assets/ntsc-final/lang/depo.json`)

| Slot | Used by | Purpose |
|------|---------|---------|
| `L_DEPO_004`–`008` | Director–QA agents | Custom agent status lines |
| `L_DEPO_053` | Comms agent | Reused retail slot (still retail CamSpy-adjacent text until repurposed) |
| `L_DEPO_061` | Console (Z interact) | Reused retail slot (CamSpy hint text in JSON — candidate for custom overview copy) |
| `L_DEPO_066` | Security agent | Custom: "Security - perimeter clear…" |
| `L_DEPO_067` | Ops agent | Custom: "Ops - deploy pipeline idle…" |

Mod override: `mods/mod_allinone/files/LdepoE`

### CI — `LANGBANK_DISH` (`src/assets/ntsc-final/lang/dish.json`)

| Slot | Used by | Purpose |
|------|---------|---------|
| `L_DISH_000`–`007` | All eight agents | Custom agent status lines |
| `L_DISH_125` | Console (Z interact) | Custom room overview |

Mod override: `mods/mod_allinone/files/LdishE`

**Important:** JSON strings must be **latin-1** encodable. After editing JSON, rebuild
lang assets and copy to moddir (see [Lang rebuild](#lang-rebuild-mklang--moddir) below).

Stage → bank routing in `src/game/lang.c`: `STAGE_AGENT_OFFICE` → `LANGBANK_DEPO`,
`STAGE_AGENT_OFFICE_CI` → `LANGBANK_DISH`.

---

## Electron app

**Location:** `tools/agent-office-electron/`

**Product:** Virtual Agent Office.app (also bundled in Perfect Dark Kit)

### Features

- **Location picker:** G5 (`0x83`) vs Carrington Institute (`0x84`)
- **Deploy + Play / Deploy only / Force relaunch / Quit game**
- **With Combat Sims** button → `--with-bots`
- Loads agent layout from Python (`agent_office_layout_payload` /
  `agent_office_ci_layout_payload`) for the UI agent roster
- Single-instance guard via Kit `electron_single_instance.js`
- **`launchInFlight` Set** (main) + renderer guard — prevents overlapping deploy/play spawns per location+mode
- Repo root resolution: `PD_REPO_ROOT` → baked `repo-config.json` → walk up to `tools/pd_kit/kit.json`

### Kit integration

Registered in `tools/pd_kit/kit.json`:

- App id: `agent-office`
- Dev launch: `scripts/launch-agent-office-app.sh`
- Build: `scripts/build-agent-office-electron.sh`
- Kit Hub action `playAgentOffice` runs G5 script only (CI via Electron picker or shell)

Built bundle output: `scripts/release/Virtual Agent Office.app` (symlink at repo root when built with default flags).

---

## Session timeline (full conversation)

Chronological arc from initial implementation through final door restoration.

| Phase | User / trigger | Outcome |
|-------|------------------|---------|
| **1. G5 map** | Initial feature request | `agent_office` on retail depo; 8 agents at computer stations; meeting-room layout |
| **2. Missing doors** | “there are no doors” | Added retail doors via `depo_retail_doors.py` (~47 props) |
| **3. Locked meeting room** | “door to meeting room is locked” | `mp_unlock=True` on sliding/swinging doors; strip lock flags |
| **4. Polish** | “make it great” | Agent roles, Z-target examine ailists, console interact, layout pass |
| **5. CI variant** | “also carrington institute” | `agent_office_ci` + location picker in Electron |
| **6. Relaunch loop** | Multiple game instances stacking | `pgrep` guards, removed macOS `open -na`, Electron `launchInFlight` |
| **7. hudmsg SIGSEGV** | Crash report on Z-target | `mklang` + deploy `LdepoE`/`LdishE`; `aiShowHudmsg` null guard in `chraicommands.c` |
| **8. Rate limits** | Repeated rebuild/relaunch requests | Many agent turns failed with Cursor rate limit — fixes landed asynchronously via subagents |
| **9. CPU freeze** | “it's freezing” | Root cause: ~90 `doorTick`/frame from `mp_unlock=True`; fix: deactivate all doors, `sibling=0`, skip tick in `propobj.c` |
| **10. g_Stages[92]** | CI/G5 stage lookup segfault | `g_Stages[91]` → **`g_Stages[92]`** in `data.h` + `stagetable.c` (92 entries) |
| **11. G5 spawn snap** | Player below lobby floor | `player.c`: trust pad Y when ground >10 units below on `STAGE_AGENT_OFFICE` |
| **12. CI fall-through** | Fell from Y≈460 sofa lounge | Moved spawns/agents to foyer Y≈35; `player.c` CI high-pad guard |
| **13. Lobby redesign** | “lobby mode like before playing a mission” | Player + agents + console on open foyer pads; no door transit required |
| **14. Exploding meshes** | “weird exploding meshes” | **Sibling root cause** (see below); interim fix: **omit all door props** (`return []`) |
| **15. First doc pass** | “document this whole conversation” (~18:29) | `SESSION_NOTES.md` + `NEXT_STEPS.md` — recorded door omission as final state |
| **16. Restore props** | “no combat + doors and elevators present” (~18:32) | Restored doors (static/deactivated, sibling cleared); added `ci_retail_lifts.py`; default remains `--solo` |
| **17. Second doc pass** | This revision (~18:35+) | Docs synced to packer/deployed state |

---

## Issues fixed (technical detail)

### 1. Relaunch loop

**Symptom:** Repeated game launches; multiple `pd.arm64` instances stacking.

**Cause:** macOS `open -na` fallback after Terminal launch created duplicate processes;
Electron could also spawn overlapping play scripts.

**Fix:**

- `scripts/play-agent-office.sh` and `scripts/play-agent-office-ci.sh`:
  - `pgrep_play()` detects existing game for the target `--boot-stage`
  - Skip launch unless `--force` (kill existing PID first)
  - Terminal-only launch on macOS; **removed `open -na` fallback**
  - PID written to `journal/agent_office/.last_play.pid` (or `agent_office_ci/`)
- `tools/agent-office-electron/main.js`: `launchInFlight` guard on IPC launch handler

### 2. `hudmsg` SIGSEGV on Z-target

**Symptom:** Crash when Z-targeting an agent (`hudmsgCreateFromArgs` null deref).

**Cause:** `aiShowHudmsg` called `langGet()` and passed NULL/empty text into `hudmsgCreate`
when moddir lang banks were missing or slots empty.

**Fix:**

- Added agent-office strings to `depo.json` / `dish.json`
- Built `LdepoE` / `LdishE` and copied to `mods/mod_allinone/files/`
- `src/game/chraicommands.c` — null/empty guard in `aiShowHudmsg()` before `hudmsgCreate`

### 3. Freeze (~100% CPU)

**Symptom:** Game hung shortly after load; CPU pegged.

**Cause:** Dozens of retail automatic doors in MP setup running `doorTick` every frame when
`mp_unlock=True` activated sliding/swinging doors.

**Fix (staged):**

1. `prepare_agent_office_doors()`: clear `door.sibling = 0`, set `OBJFLAG_DEACTIVATED`
2. `parse_*_doors(mp_unlock=False)` — do not reactivate automatic doors
3. `src/game/propobj.c` — skip `doorTick(prop)` when `OBJFLAG_DEACTIVATED` is set

### 4. `g_Stages[92]` truncation segfault

**Symptom:** Segfault during stage lookup after adding CI stage.

**Cause:** Array declared `[91]` but **92** initializer entries — last row truncated.

**Fix:** `struct stagetableentry g_Stages[92]` in `data.h` and `stagetable.c`.

### 5. G5 spawn ground snap

**Symptom:** Player spawned below lobby floor or snapped to wrong Y.

**Cause:** `cdFindGround` hit a lower floor column at the same XY as lobby pads (Y≈35).

**Fix:** `src/game/player.c` — for `STAGE_AGENT_OFFICE`, when ground Y is more than
10 units below spawn pad Y, trust the retail pad height.

### 6. CI fall-through to second floor

**Symptom:** Player or agents fell to Y≈460 sofa lounge (non-walkable).

**Cause:** Legacy upper-briefing pads at Y≈460; ground snap pulled entities to walkable floor far below pad height.

**Fix:** Moved all spawns and agents to foyer pads at Y≈35; CI high-pad guard in `player.c`.

### 7. Lobby mode redesign

**Goal:** Pre-mission foyer UX — agents reachable without opening any doors.

**Changes:** G5 lobby ring on pads `0x0008`–`0x00BE`; CI foyer ring `0x0001`–`0x0012`, `0x0017`, `0x0003`;
consoles in west G5 / north CI alcoves.

### 8. Door exploding meshes (sibling index root cause)

**Symptom:** Door models stretched/garbled; continued CPU pressure even with deactivation attempts.

**Cause:** Retail `sibling` fields are **relative command indices** into the full
`setupdepo.c` / `setupdish.c` props array. Agent Office packed **door-only** subsets;
`setupCreateDoor()` resolved siblings to non-door commands → garbage pointers →
`doorsCalcFrac()` wrote extreme `frac` values → mesh explosion in `doorInitMatrices()`.

**Interim fix (~18:27):** `agent_office_depo_doors()` / `agent_office_ci_doors()` returned
`[]` — zero door props (documented in first doc pass).

**Current fix (~18:32+):** Re-include all retail doors with **`sibling = 0`** and
**`OBJFLAG_DEACTIVATED`** + `propobj.c` tick skip. Meshes render statically; no sibling walk;
no `doorTick` CPU load. Doors still not openable.

### 9. Elevators (CI only)

**User request:** “elevators … should be present.”

**Fix:** New `tools/pdmap/ci_retail_lifts.py` parses two retail lift assemblies from
`setupdish.c` (lift + 4 doors + 4 lift_door per assembly). Lift-car door pads excluded from
flat door list to avoid duplicates. Car doors deactivated; lifts provide visual presence +
collision shell (not rideable without mission scripts).

---

## Launch commands

### Prerequisites

- NTSC-final ROM at `data/pd.ntsc-final.z64` (or fallback paths in play scripts)
- Built port: `build/pd.arm64`
- Deployed setup + lang in `mods/mod_allinone/`

### Play (deploy + launch)

```bash
# dataDyne G5 (0x83) — peaceful explore (default)
./scripts/play-agent-office.sh

# Carrington Institute (0x84)
./scripts/play-agent-office-ci.sh

# Electron UI (location picker)
./scripts/launch-agent-office-app.sh
```

### Play script flags

| Flag | Effect |
|------|--------|
| `--no-play` | Deploy setup only |
| `--with-bots` | Add 4 combat sims (`--num-sims 4`) |
| `--force` | Kill existing game for that boot-stage and relaunch |

### Rebuild port (after C changes)

```bash
cmake --build build --target pd -j8
```

### Validate / deploy maps only

```bash
python3 tools/pdmap.py validate agent_office
python3 tools/pdmap.py validate agent_office_ci
python3 tools/pdmap.py build agent_office --deploy
python3 tools/pdmap.py build agent_office_ci --deploy
```

Play scripts run `build … --deploy` automatically before launch.

### Build Electron app

```bash
./scripts/build-agent-office-electron.sh          # release .app
./scripts/build-agent-office-electron.sh --dev    # npm install only
./scripts/launch-agent-office-app.sh --foreground # dev without open
```

### Lang rebuild (mklang + moddir)

After editing `src/assets/ntsc-final/lang/depo.json` or `dish.json`:

```bash
cmake --build build --target pd_headers -j8

cp build/ntsc-final/assets/files/LdepoE.o mods/mod_allinone/files/LdepoE
cp build/ntsc-final/assets/files/LdishE.o mods/mod_allinone/files/LdishE

cmake --build build --target pd -j8   # if chraicommands.c changed
```

Manual mklang (if needed outside CMake):

```bash
ROMID=ntsc-final tools/assetmgr/mklang src/assets/ntsc-final/lang/depo.json en
ROMID=ntsc-final tools/assetmgr/mklang src/assets/ntsc-final/lang/dish.json en
```

### Logs

| Log | Path |
|-----|------|
| G5 deploy/play | `journal/agent_office/.last_launch.log` |
| CI deploy/play | `journal/agent_office_ci/.last_launch.log` |
| Electron | `journal/agent_office/virtual-agent-office.log` (when app writes it) |
| Last game PID | `journal/agent_office/.last_play.pid` or `agent_office_ci/.last_play.pid` |

---

## Key files

### Maps & packing

| File | Role |
|------|------|
| `src/levels/agent_office.py` | MapDef entry — SKIP_*, retail pads, spawns |
| `src/levels/agent_office_ci.py` | CI MapDef entry |
| `tools/pdmap/agent_office.py` | G5 agents, ailists, console, `pack_agent_office_setup()` |
| `tools/pdmap/agent_office_ci.py` | CI agents, ailists, console, lifts, `pack_agent_office_ci_setup()` |
| `tools/pdmap/depo_retail_doors.py` | 47 G5 doors — parse, `prepare_agent_office_doors()`, pack |
| `tools/pdmap/ci_retail_doors.py` | 88 CI doors (lift pads excluded) |
| `tools/pdmap/ci_retail_lifts.py` | 2 CI lift assemblies (18 props) |
| `tools/pdmap/deploy.py` | `--deploy` copies setup into moddir |

### Engine / port

| File | Role |
|------|------|
| `src/include/constants.h` | `STAGE_AGENT_OFFICE` (`0x83`), `STAGE_AGENT_OFFICE_CI` (`0x84`) |
| `src/game/stagetable.c` | Stage rows → ROM geo + mod setup file ids |
| `src/include/data.h` | `g_Stages[92]` declaration |
| `port/src/romdata.c` | External mod filenames for setup assets |
| `src/game/player.c` | G5/CI spawn ground-snap guards |
| `src/game/chraicommands.c` | `aiShowHudmsg` null guard |
| `src/game/propobj.c` | Skip `doorTick` on deactivated doors |
| `src/game/setup.c` | `setupCreateDoor()` sibling resolution (retail index semantics) |

### Lang

| File | Role |
|------|------|
| `src/assets/ntsc-final/lang/depo.json` | G5 HUD strings |
| `src/assets/ntsc-final/lang/dish.json` | CI HUD strings |
| `mods/mod_allinone/files/LdepoE` | Deployed G5 lang bank |
| `mods/mod_allinone/files/LdishE` | Deployed CI lang bank |
| `tools/assetmgr/mklang` | JSON → binary lang compiler |

### Scripts & app

| File | Role |
|------|------|
| `scripts/play-agent-office.sh` | G5 deploy + launch |
| `scripts/play-agent-office-ci.sh` | CI deploy + launch |
| `scripts/launch-agent-office-app.sh` | Dev Electron launcher |
| `scripts/build-agent-office-electron.sh` | electron-builder release |
| `tools/agent-office-electron/main.js` | Electron main — locations, launch guards |
| `tools/agent-office-electron/renderer/app.js` | UI — picker, agent roster, launch |
| `tools/pd_kit/kit.json` | Kit app registration |

---

## Known limitations

- **MP menu names:** Stages may appear as raw ids (`0x83` / `0x84`) rather than human-readable arena names.
- **G5 console / Comms text:** `L_DEPO_061` and `L_DEPO_053` still carry retail mission copy in JSON; CI console uses purpose-written `L_DISH_125`.
- **Doors static, not openable:** All retail doors deactivated; briefing wings behind closed doorways not accessible without re-enabling `mp_unlock` (CPU risk).
- **CI lifts visual only:** Elevator cars present; ride logic requires retail mission ailists not included in MP setup.
- **Lang deploy is manual:** Editing JSON requires `pd_headers` rebuild + copy to moddir (not part of `pdmap build --deploy`).
- **Kit Hub shortcut:** `playAgentOffice` action launches G5 only; CI requires Electron picker or `play-agent-office-ci.sh`.
- **macOS Terminal launch:** Game opens in a Terminal tab; focus the separate `pd.arm64` game window.
- **Expected GL noise on macOS:** GL 3.0 compat fails, 4.1 core succeeds; missing compat-only entry points are benign.
- **Sibling remapping not implemented:** Current fix zeros siblings rather than remapping indices for a door-only pack with working paired animation — sufficient for static render.

---

## Optional next steps

See `journal/agent_office/NEXT_STEPS.md` for the living checklist. Highlights:

- [ ] Verify in-game: static door meshes render correctly on G5 + CI after restoration (no explosions)
- [ ] MP menu human-readable arena names for both stages
- [ ] `PERFECT_DARK_KIT.md` section linking both variants + Electron app
- [ ] Repurpose `L_DEPO_061` / `L_DEPO_053` with custom G5 overview/comms copy
- [ ] Automate lang-bank copy into moddir on deploy
- [ ] Kit Hub action for CI (`play-agent-office-ci.sh`)
- [ ] Remap door sibling indices (or pack intervening retail props) if openable doors needed without CPU freeze
- [ ] Functional lift script for CI (optional; high effort)
- [ ] Proximity trigger volumes (one-shot VO) if desired

---

## Status summary

**As of 2026-07-02 (end of session):** Both variants deploy and launch in **lobby mode** with
**peaceful explore default** (`--solo`). Eight agents + console interact work when lang banks
are in moddir. **47 G5 / 88 CI retail doors** and **2 CI lift assemblies** ship in MP setup as
**static deactivated props** (sibling cleared, `doorTick` skipped). Rebuild `pd.arm64` after
any C changes before testing.

**Not committed** per user request throughout session.

---

## Follow-up session (2026-07-02) — polish + live-AI groundwork

Cleared the optional next-steps and laid the foundation for live LLM agents. All changes
are additive; the shipped examine/console behavior is unchanged (regression-tested).

**Polish (all six prior next-steps):**

- **Menu names** — `src/game/lang.c` sentinel handlers: `0x7FFA` → "Virtual Agent Office",
  `0x7FF9` → "Agent Office: Carrington", `0x7FFB` → "Animation Lab" (the stages were already
  in `g_MpArenas` with these sentinel name ids; only the resolver was missing).
- **G5 lang copy** — `L_DEPO_053` (Comms) and `L_DEPO_061` (console overview) rewritten from
  leftover retail CamSpy text to purpose-built agent-office copy (`depo.json`, latin-1 clean).
- **Lang auto-deploy** — `deploy_lang_bank()` in `play-agent-office.sh` / `-ci.sh` copies the
  built `LdepoE`/`LdishE` into the mod on every deploy (covers the Electron app too, which
  spawns those scripts). No-op with a helpful hint when `pd_headers` hasn't been built.
- **Kit CI action** — `playAgentOfficeCi` added to `tools/pd_kit/kit.json`; `PERFECT_DARK_KIT.md`
  gained a dedicated Virtual Agent Office section linking both variants + the Electron app.
- **Proximity greeting (one-shot VO)** — new `if_distance_to_target_lt` (`0x0052`) ailist
  branch, gated by an opt-in `greet_text` on `VirtualAgentSpec` in **both** `agent_office.py`
  and `agent_office_ci.py`. Fires once when the player crosses `GREET_RANGE` (400u), latches
  until they leave. Demo greeter enabled on each **Security** agent (reuses its status string —
  swap for a dedicated line or the live LLM utterance). `tests/test_agent_office_ailist.py`
  proves the examine-only agents are byte-for-byte unchanged.

**Live LLM conversation layer (design + scaffold):** the seam where the static HUD line
becomes a per-character LLM agent you approach and talk to, in voice.

- Spec: [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md) — grounds the four additive
  engine/sidecar seams (observe office chrs, `/act` `agents[].say`, per-agent brains, voice).
- Scaffold: `tools/agent_office_llm/` — runnable director (proximity engine w/ hysteresis +
  view cone, brain dispatch, act payloads, `--dry-run`), `characters/{director,security}/brain.json`.

**Verification:** all Python compiles; kit/lang/brain JSON valid; `depo.json` latin-1 clean;
ailist regression test green; `lang.c` sentinel block well-formed; `stagetable.c`/`data.h`
untouched (no `g_Stages` size regression). **Still needs an in-engine rebuild + play** to
confirm menu names, new strings, and the Security proximity greeter (macOS `cmake` build —
not run here). Not committed.

---

## Follow-up session (2026-07-04) — CI door sibling crash fix + rebuild/relaunch

**Problem:** CI map (`agent_office_ci`, stage `0x84`) SIGSEGV in `doorsCalcFrac` — retail
`door.sibling` offsets assumed the full `setupdish.c` props[] layout; door-only MP packs
walked garbage pointers when siblings targeted omitted chr/std/lift props.

**Fixes applied (pdmap packer, uncommitted):**

| File | Change |
|------|--------|
| `tools/pdmap/setup_c_preprocess.py` | **New** — resolve `#if VERSION` branches for ntsc-final parsing (avoids duplicate doors on version-guarded pads). |
| `tools/pdmap/retail_door_siblings.py` | **New** — remap retail sibling offsets door-to-door within packed lists; `validate_packed_door_siblings()` for build-time checks. |
| `tools/pdmap/ci_retail_doors.py` | Remap siblings via `prepare_agent_office_doors()` instead of zeroing; MP-unlock all flat doors; use preprocessed setup lines. |
| `tools/pdmap/ci_retail_lifts.py` | Preprocessed setup lines; unlock lift-car doors (internal sibling offsets stay intact within lift assemblies). |
| `tools/pdmap/ci_retail_office_props.py` | Filter extraneous lobby-lift desk/monitor props (`0x0226`–`0x022D` excluded). |
| `tools/pdmap/validate.py` | Build-time sibling validation for `agent_office` and `agent_office_ci`. |

**Validation:** `analyze_setup_door_siblings('dish')` → 0 bad siblings / 63 doors.
`validate_packed_door_siblings()` on full CI props → **0 errors** (71 doors).

**Rebuild + relaunch (2026-07-04 ~14:35 local):**

1. `cmake --build build -j8` — rebuilt `build/pd.arm64` (C sources had local changes).
2. `./scripts/play-agent-office-ci.sh --force` — killed stale PID, rebuilt/deployed
   `agent_office_ci` → `Ump_setupagent_office_ciZ`, launched stage `0x84`.
3. Stability check: direct `nohup ./build/pd.arm64 … --boot-stage 0x84` ran **30+ s**
   with spawn complete, **no SIGSEGV**, no `doorsCalcFrac` fault, no premature shutdown.

**Outcome:** CI boots successfully with remapped door siblings. Relaunch command:

```bash
./scripts/play-agent-office-ci.sh --force
```

Log: `journal/agent_office_ci/.last_launch.log`. Not committed.

---

## Follow-up session (2026-07-04) — CI floating lobby console fix

**Problem:** Grey metallic cabinet/console (`MODEL_CIHUB`) floating mid-air in the north-lobby
corridor (blue reflective floor, `PAD_DISH_0017` alcove). Screenshot matched the tagged agent
console, not retail desk PCs (`0x0226`–`0x022D` — those are already excluded by
`ci_retail_office_props.py`).

**Root cause:** `agent_office_ci_std_props()` packed the interact `MultiMonitor` with
`OBJFLAG_*TOPADBOUNDS`, but `PAD_DISH_0017` has a generic ±100 u bbox (same pitfall as G5
`PAD_DEPO_0062`). `setupCreateObject` scales the console to that volume and it hangs in open
corridor space instead of sitting on the floor.

**Fix:** `tools/pdmap/agent_office_ci.py` — drop TOPADBOUNDS on the lobby console; keep
`OBJFLAG_FALL | OBJFLAG_00000100 | OBJFLAG_IGNOREFLOORCOLOUR` (mirrors G5
`agent_office_std_props()`).

| Prop | Pad | Model | Fix |
|------|-----|-------|-----|
| `MultiMonitor` (tagged agent console) | `0x0017` (`-100, 35, 128`) | `MODEL_CIHUB` | Removed `OBJFLAG_X/Y/ZTOPADBOUNDS` |

**Validation:** `python3 scripts/validate-door-siblings.py` → OK (CI + G5).  
`python3 tools/pdmap.py validate agent_office_ci` → OK (retail pad warnings only).

**Rebuild + relaunch (2026-07-04 ~14:39 local):**

1. `python3 tools/pdmap.py build agent_office_ci --deploy`
2. `./scripts/play-agent-office-ci.sh --force` → PID 43647, stage `0x84`
3. `journal/agent_office_ci/.last_launch.log`: setup loaded, spawn `(637,360,923)`, no SIGSEGV

**Outcome:** Console flags now `0x00000501` (was `0x000005E1`). Not committed.

---

## Follow-up session (2026-07-04) — Visor pause + lobby console interact

**Problem:** In agent-office solo explore (`--solo`, stages `0x83`/`0x84`/`0x85`), **Escape** opened the
MP pause scoreboard (or nothing useful) instead of the visor / Perfect Menu. **(Z)** on the tagged
lobby console only showed a throttled HUD overview line — not retail CI-lobby PC interaction
(`g_CiMenuViaPcMenuDialog`).

**Root cause:**

1. Agent-office maps boot through MP setup (`g_Vars.mplayerisrunning == true`), so `bondmove.c`
   routed Escape/Start to `mpPushPauseDialog()` instead of `playerPause(MENUROOT_MAINMENU)`.
2. Retail CI lobby PC uses tag `0x47` handled only on `STAGE_CITRAINING` in `propobjGetCiTagId()`.
   Agent-office consoles use custom tag `OBJ_AGENT_CONSOLE` (`0x20`) with monitor ailist HUD only.

**Fix (C engine — no map redeploy required):**

| File | Change |
|------|--------|
| `src/include/constants.h` | `STAGE_IS_AGENT_OFFICE()`, `OBJ_AGENT_CONSOLE` |
| `src/game/player.c` | `playerShouldUseSoloPauseMenu()`; eyespy/slayer pause paths |
| `src/game/bondmove.c` | Escape/Start → solo pause on agent-office stages |
| `src/game/mainmenu.c` | `soloChoosePauseDialog()` — G5 → solo visor; CI/Lab → CI Perfect Menu pause |
| `src/game/propobj.c` | `(Z)` on tagged console → `g_CiMenuViaPcMenuDialog` on agent-office stages |
| `journal/agent_office/SPEC.md` | US-3 / US-3b acceptance criteria |

**Validation (2026-07-04 ~14:44 local):**

1. `cmake --build build --target pd -j8` → OK
2. `./scripts/play-agent-office-ci.sh --force` → PID 51214, stage `0x84`, no crash in log tail

**Manual checks:** Escape → visor/Perfect Menu pause; Z on north-lobby CIHUB → Perfect Menu.

**Also test:** `./scripts/play-agent-office.sh --force` (G5 `0x83`), `./scripts/play-agent-office-lab.sh --force` (`0x85`).

**Outcome:** Not committed.

---

## Follow-up session (2026-07-04) — Visor missing + dark screen after unpause

**Problem:** After the Escape→solo-pause routing fix, **Escape** opened the Perfect Menu but **without
the visor overlay** (3D hudpiece / Joanna model). Closing pause (Escape again) and moving again
left a **dark viewport** — world rendering skipped while menu gfx state was stale.

**Root cause:**

1. Agent-office hubs boot via MP setup (`g_Vars.mplayerisrunning == true`). `menuReset()` only
   allocated the hudpiece (`FILE_GHUDPIECE`) when `!mplayerisrunning`, so solo visor pause had
   menu text + blur but no 3D visor frame.
2. Solo pause uses `MENUROOT_MAINMENU` + `MENUBG_BLUR`, which sets `var8009dfc0` and
   `g_MenuData.unk5d4`. The hudpiece teardown path in `menuRender()` only removes the piece when
   `g_MenuData.root != MENUROOT_MAINMENU`, so after closing pause `unk5d4` / `menuisactive` could
   stick — `lv.c` then hit the `var8009dfc0 && !menuisactive` branch (viewport edges only).

Retail solo missions avoid both issues: `mplayerisrunning == false` (hudpiece init) and pause
teardown runs on mission end / stage change.

**Fix (C engine):**

| File | Change |
|------|--------|
| `src/game/menu.c` | `menuReset()` — also init hudpiece + menu model pool on `STAGE_IS_AGENT_OFFICE` |
| `src/game/menu.c` | `func0f0fa6ac()` — on agent-office unpause, clear `unk5d4` / hudpiece flags |
| `src/game/player.c` | `playerUnpause()` — also clear `lvIsPaused()` on agent-office stages |

**Validation (2026-07-04 ~14:50 local):**

1. `cmake --build build --target pd -j8` → OK
2. `./scripts/play-agent-office-ci.sh --force` → relaunched stage `0x84`, PID 66468

**Manual checks:** Escape → blurred game + visor frame + Perfect Menu; Escape/Start to close →
world visible, movement restored (no dark screen). Repeat on G5 (`play-agent-office.sh`) and Lab
(`play-agent-office-lab.sh`).

**Outcome:** Not committed.

---

## Follow-up session (2026-07-04) — Visor missing + dark screen after unpause

**Problem:** After the Escape→solo-pause routing fix, **Escape** opened the Perfect Menu but **without
the visor overlay** (3D hudpiece / Joanna model). Closing pause (Escape again) and moving again
left a **dark viewport** — world rendering skipped while menu gfx state was stale.

**Root cause:**

1. Agent-office hubs boot via MP setup (`g_Vars.mplayerisrunning == true`). `menuReset()` only
   allocated the hudpiece (`FILE_GHUDPIECE`) when `!mplayerisrunning`, so solo visor pause had
   menu text + blur but no 3D visor frame.
2. Solo pause uses `MENUROOT_MAINMENU` + `MENUBG_BLUR`, which sets `var8009dfc0` and
   `g_MenuData.unk5d4`. The hudpiece teardown path in `menuRender()` only removes the piece when
   `g_MenuData.root != MENUROOT_MAINMENU`, so after closing pause `unk5d4` / `menuisactive` could
   stick — `lv.c` then hit the `var8009dfc0 && !menuisactive` branch (viewport edges only).

Retail solo missions avoid both issues: `mplayerisrunning == false` (hudpiece init) and pause
teardown runs on mission end / stage change.

**Fix (C engine):**

| File | Change |
|------|--------|
| `src/game/menu.c` | `menuReset()` — also init hudpiece + menu model pool on `STAGE_IS_AGENT_OFFICE` |
| `src/game/menu.c` | `func0f0fa6ac()` — on agent-office unpause, clear `unk5d4` / hudpiece flags |
| `src/game/player.c` | `playerUnpause()` — also clear `lvIsPaused()` on agent-office stages |

**Validation (2026-07-04 ~14:50 local):**

1. `cmake --build build --target pd -j8` → OK
2. `./scripts/play-agent-office-ci.sh --force` → relaunched stage `0x84`

**Manual checks:** Escape → blurred game + visor frame + Perfect Menu; Escape/Start to close →
world visible, movement restored (no dark screen). Repeat on G5 (`play-agent-office.sh`) and Lab
(`play-agent-office-lab.sh`).

**Outcome:** Not committed.

**2026-07-04:** Rebuilt `Virtual Agent Office.app` + Kit Hub after adding **Carrington Institute (Fresh / Lobby)** (`ci_lobby`) to agent-office Electron; release + wrapped bundles grep-clean.

**2026-07-04:** Rebuilt Virtual Agent Office + Kit Hub after agent-profile panel (display name gates Enter Office); strings in release + wrapped app.asar.

## Follow-up session (2026-07-04) — CI Fresh Lobby doorInit sibling SIGSEGV

**Problem:** `pd.arm64` SIGSEGV at load on **CI Fresh Lobby** (`--boot-stage 0x26 --agent-office-ci-lobby`):
`door0f068c04` → `func0f068fc8` → `propCalculateShadeInfo` → `doorInit` → `setupCreateDoor`.
Fault address `0x0001100000000017` — walking `sibling->sibling` during init shade calc with an
unconverted packed offset (or non-door target) cast to `doorobj *`.

**Root cause:** `setupCreateDoor()` resolved only the **current** door's sibling before
`doorInit()`. `door0f068c04()` walks the full sibling ring during init shade setup; links
further around the ring still held packed cmd offsets until those doors were created → garbage
pointer deref. Fresh Lobby (`STAGE_CITRAINING` + `Ump_setupagent_office_ciZ`) hits this on first
load; stage `0x84` could survive depending on creation order. Packer sibling remap was already
valid (`validate-door-siblings.py` → 0 errors); runtime resolution order was the bug.

**Fixes applied (uncommitted):**

| File | Change |
|------|--------|
| `src/game/setup.c` | **`setupResolveAllDoorSiblings()`** — pre-pass resolves every door sibling to a `doorobj *` (or NULL if target cmd is not `OBJTYPE_DOOR`) before the props loop; called after optional `setupMarkLiftDoors()`. |
| `src/game/setup.c` | **`setupResolveOneDoorSibling()`** — shared resolver with `LOG_WARNING` on bad targets; `setupCreateDoor()` uses fallback only when pre-pass skipped. |
| `src/game/propobj.c` | **`door0f068c04()`** — guard sibling ring walk: require `OBJTYPE_DOOR` + live `prop` before following `sibling->sibling`. |

**Validation:**

```bash
python3 scripts/validate-door-siblings.py          # OK (CI 71 doors, G5 47 doors)
python3 tools/pdmap.py validate agent_office_ci    # OK
python3 tools/pdmap.py build agent_office_ci --deploy
cmake --build build --target pd -j8
```

**Stability (2026-07-04 ~15:06 local):**

| Path | Args | Result (12 s after spawn) |
|------|------|---------------------------|
| **CI Fresh Lobby** (crashed before) | `--boot-stage 0x26 --agent-office-ci-lobby` | **ALIVE** — spawn `(637,360,923)`, no SIGSEGV |
| CI explore | `--boot-stage 0x84 --solo --scenario-0` | **ALIVE** — spawn OK |

Logs: `journal/agent_office_ci/.crash_test_lobby.log`, `.crash_test_ci.log`.

**Outcome:** Not committed. Relaunch: `./scripts/play-agent-office-ci-lobby.sh --force` and
`./scripts/play-agent-office-ci.sh --force`.

**2026-07-04 — Pass 6 (DM panel bundles):** Renderer has Direct messages panel (`tools/agent-office-electron/renderer/index.html`); rebuilt `./scripts/build-agent-office-electron.sh` + `./scripts/build-pd-kit-launcher-electron.sh` — `strings` on release VAO and Kit-wrapped VAO `app.asar` both contain `Direct messages` (bundles updated y/y).
