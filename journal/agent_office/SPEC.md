# Virtual Agent Office — Product & Engineering Spec

**Status:** Spec-driven development source of truth (2026-07-02)  
**Parent:** [`SPEC.md`](../../SPEC.md) (Perfect Dark AIO kit-wide contracts)  
**Scope:** Two retail-geometry MP maps (dataDyne G5 + Carrington Institute), Electron launcher, CLI play scripts, and the live-LLM conversation layer roadmap.

Companion docs (historical / slice detail):

| Doc | Role |
|-----|------|
| [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md) | **North-star vision** — 3D game interface for managing AI agents; lobby-as-control-plane, Slack/connector model, full system design (this spec is its shipped P0) |
| [`SPEC_AUDIT.md`](./SPEC_AUDIT.md) | Conformance audit of the shipped setups vs. this spec (fix list, incl. F1 spawn collision) |
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

Both variants share:

- **Retail geometry overlay** — collision, tiles, pads from NTSC-final ROM; only MP setup + lang banks deployed from mod.
- **Lobby hub layout** — player, eight agents, and console on open foyer pads at **Y ≈ 35**.
- **Peaceful explore default** — solo, no weapons, no combat sims unless explicitly requested.
- **Retail door/lift props** — included as **static deactivated** meshes (visual + collision; not openable in v1).

### Goals (v1 shipped baseline)

1. Deploy and boot either variant reliably from CLI, Kit Hub, or Electron.
2. Eight `TEAM_NONCOMBAT` agents with briefing animations, Z-target HUD status, optional proximity greeting.
3. Tagged lobby console: **(Z)** shows room overview (throttled).
4. Retail doors and CI lifts **present** without CPU freeze or mesh corruption.
5. Human-readable MP menu names; lang strings resolve without crash.
6. Foundation for live LLM conversation layer (static lines remain fallback).

---

## 2. User stories & acceptance criteria

### US-1 — Peaceful explore (default)

**As a** player launching Agent Office for the first time,  
**I want** to spawn alone in the lobby with no weapons or hostile AI,  
**So that** I can walk and examine agents without combat pressure.

| # | Acceptance criterion |
|---|---------------------|
| AC-1.1 | Default launch uses `--solo --scenario-0 --skip-intro --boot-stage 0x83` or `0x84`. |
| AC-1.2 | `port/src/bootmp.c` clears MP weapon loadout and sim quick-team when `--solo` on agent-office stages. |
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
| AC-2.4 | Agent plays locked briefing animation at pad (`CHRANIMFLAG_SLOWUPDATE \| CHRANIMFLAG_LOCKPOS`). |

### US-3 — Console interact

**As a** player at the lobby console,  
**I want** to press **(Z)** on the tagged console for a room overview,  
**So that** I get situational context.

| # | Acceptance criterion |
|---|---------------------|
| AC-3.1 | Console prop tagged `OBJ_AGENT_CONSOLE` (`0x20`); monitor ailist `AILIST_CONSOLE_MONITOR` (`0x1002`). |
| AC-3.2 | G5: `MODEL_PD_CONSOLE` @ `PAD_DEPO_0006`; CI: `MODEL_CIHUB` @ `PAD_DISH_0017`. |
| AC-3.3 | Overview string uses `L_DEPO_061` (G5) or `L_DISH_125` (CI) with same cooldown pattern. |

### US-4 — Location picker

**As a** macOS user,  
**I want** to pick G5 vs Carrington in the Electron app,  
**So that** I don’t need separate shell scripts.

| # | Acceptance criterion |
|---|---------------------|
| AC-4.1 | Electron location picker switches boot stage `0x83` / `0x84` and spawns correct play script. |
| AC-4.2 | Agent roster UI loads from Python `agent_office_layout_payload` / `agent_office_ci_layout_payload`. |
| AC-4.3 | Kit Hub exposes both variants (`playAgentOffice`, `playAgentOfficeCi`). |

### US-5 — Retail doors & lifts present

**As a** player who knows the retail missions,  
**I want** to see familiar door frames and CI elevators,  
**So that** the space feels authentic even if wings stay closed.

| # | Acceptance criterion |
|---|---------------------|
| AC-5.1 | G5 setup includes **47** retail door props; CI includes **88** doors + **2** lift assemblies (18 props). |
| AC-5.2 | Door meshes render statically — no “exploding” geometry. |
| AC-5.3 | Game remains responsive — no ~100% CPU from `doorTick` storm. |
| AC-5.4 | Briefing wings behind closed retail doorways remain inaccessible in v1 (by design). |

### US-6 — Spawn & navigation

**As a** player spawning in the lobby,  
**I want** to land on the walkable foyer floor,  
**So that** I don’t fall through or snap below the floor.

| # | Acceptance criterion |
|---|---------------------|
| AC-6.1 | G5 primary spawn `PAD_DEPO_0080` (Y≈35); CI primary `PAD_DISH_000E` (604, 35, 317). |
| AC-6.2 | `playerSnapSpawnGroundY` trusts lobby pad Y on G5 when ground is >10 u below pad. |
| AC-6.3 | CI high-pad guard prevents Y≈460 sofa-lounge fall-through for legacy pad heights. |
| AC-6.4 | All eight agents reachable on foot without opening any door. |

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

## 3. Functional requirements

### FR-1 — Maps & MapDef

| Req | Detail |
|-----|--------|
| FR-1.1 | Level modules: `src/levels/agent_office.py`, `src/levels/agent_office_ci.py`. |
| FR-1.2 | MapDef flags: `SKIP_SEG`, `SKIP_TILES`, `SKIP_PADS` — retail geometry from ROM. |
| FR-1.3 | Full retail pad graph loaded via `load_retail_pads()` (`depo` / `dish`). |
| FR-1.4 | Three intro `Spawn` pads per variant (primary + two alts), all lobby Y≈35. |
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

### FR-7 — CLI play scripts

| Req | Detail |
|-----|--------|
| FR-7.1 | `scripts/play-agent-office.sh` — G5 deploy + launch. |
| FR-7.2 | `scripts/play-agent-office-ci.sh` — CI deploy + launch. |
| FR-7.3 | `scripts/launch-agent-office-app.sh` — dev Electron. |
| FR-7.4 | `scripts/build-agent-office-electron.sh` — release bundle. |

---

## 4. Non-functional requirements

### NFR-1 — Performance (door CPU)

| Req | Detail |
|-----|--------|
| NFR-1.1 | Deactivated doors must not call `doorTick()` — enforced in `src/game/propobj.c`. |
| NFR-1.2 | Never ship `mp_unlock=True` on automatic retail doors in agent-office setups (~90+ ticks/frame freeze). |
| NFR-1.3 | CI lift cars: car doors deactivated; lift motion skipped when `OBJFLAG_DEACTIVATED`. |

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
| NFR-4.2 | Door `sibling` fields zeroed in door-only packs (garbage sibling → mesh explosion). |
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
│  setup load               →  doors, agents, console, ailists                │
│  player.c                 →  spawn ground snap guards                       │
│  propobj.c                →  skip doorTick on deactivated doors             │
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

Retail missions place the player in a **walkable lobby** before locked briefing wings. Agent Office copies that: all gameplay-critical entities live in the open foyer at **Y ≈ 35** — no door transit required.

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
| Security | `0x009E` | South entry (+ proximity greeter) |
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
| Security | `0x0012` | NW corner (+ proximity greeter) |
| Ops | `0x0011` | East inner |
| Comms | `0x0003` | NE alcove |

### `playerSnapSpawnGroundY` rules (`src/game/player.c`)

| Stage | Rule |
|-------|------|
| `STAGE_AGENT_OFFICE` | If `cdFindGround` Y is **>10 u below** spawn pad Y, **trust pad Y** (lobby over lower floor column). |
| `STAGE_AGENT_OFFICE_CI` | If spawn pad Y **>300** and ground **>40 u below** pad, use ground (legacy upper-briefing pad guard). |
| General port | If ground invalid or `\|ground - spawn\| > 80`, trust spawn Y. |

---

## 8. Door & lift model

### Why doors are static in v1

Retail `door(...)` entries use **`sibling`** as a **relative command index** into the full `setupdepo.c` / `setupdish.c` props array. Agent Office packs a **door-only subset**; preserving retail sibling values caused `setupCreateDoor()` to resolve non-door siblings → garbage pointers → extreme `frac` values → **exploding meshes**.

**Interim v1 strategy (shipped):**

| Step | Behavior |
|------|----------|
| Parse | All retail `door(...)` lines with **`mp_unlock=False`** |
| Prepare | `prepare_agent_office_doors()`: **`sibling = 0`**, **`OBJFLAG_DEACTIVATED`**, strip `CANNOT_ACTIVATE` / `KEEPOPEN` |
| Runtime | `propobj.c` skips `doorTick()` when deactivated |
| Result | Static mesh + collision; **not openable**; no CPU load |

**Why not `mp_unlock=True`:** Reactivating ~47–88 automatic doors runs `doorTick` every frame → **~100% CPU freeze** (observed in session).

### Inventory (post-deploy, verified)

| Variant | Retail doors | Lift assemblies | Zipped setup | Unpacked setup |
|---------|-------------|-----------------|--------------|----------------|
| G5 | **47** | — | 823 B | 12 096 B |
| CI | **88** (96 retail − 8 lift-car pads) | **2** (18 props) | 1 041 B | 23 332 B |

### CI lifts

- Parsed as **self-contained assemblies** (lift + 4 doors + 4 lift_door) with internal offsets intact.
- Lift-car door pads excluded from flat door list to avoid duplicates.
- Car doors **deactivated**; lifts provide visual presence + collision shell — **not rideable** without retail mission ailists.

### Future: openable doors

Requires **sibling remapping** or packing intervening retail props so sibling indices remain valid — see §14.

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

### `scripts/play-agent-office-ci.sh` (CI)

Same contract as G5 with `agent_office_ci`, boot stage `0x84`, log dir `journal/agent_office_ci/`, lang bank `LdishE`.

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
| Electron | `~/Library/Logs/PerfectDarkKit/virtual-agent-office.log` | — |

---

## 12. Known limitations & out of scope (v1)

| Limitation | Notes |
|------------|-------|
| Doors not openable | Deactivated by design; briefing wings behind closed doorways inaccessible |
| CI lifts not rideable | Visual + collision only; no retail mission lift scripts |
| Sibling remapping not implemented | Zero siblings sufficient for static render |
| macOS Terminal launch | Game runs in Terminal tab; separate `pd.arm64` window |
| In-engine LLM / voice | Out of scope v1 — see `LLM_CONVERSATION_LAYER.md` |
| Multiplayer human players | Maps are MP stages but designed for solo explore |
| PAL / other ROMs | NTSC-final retail overlay only |
| Automated in-engine CI | Manual play verification required for visual/regression |
| Briefing room interior access | Out of scope until openable doors solved |

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
| V-1 | `./scripts/play-agent-office.sh` | Spawns at G5 lobby Y≈35; no weapons; 8 agents visible |
| V-2 | Z-target each G5 agent | HUD status line; ~3 s cooldown; no crash |
| V-3 | (Z) on west console | Overview HUD (`L_DEPO_061` copy) |
| V-4 | Walk Security within ~400 u | One-shot proximity greet; no repeat until leave |
| V-5 | Visual door pass | Door frames render; **no** exploding meshes |
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
- `propobj.c` deactivated door tick skip remains
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
| `src/game/propobj.c` | Skip `doorTick` on deactivated doors |
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

## Spec change log

| Date | Change |
|------|--------|
| 2026-07-02 | Initial comprehensive spec from session notes + codebase state; spec-driven development mode |
