# Perfect Dark AIO — Product Specification (index)

**Version:** 0.3.0-spec (super-specific contracts)  
**Branch:** `port-mods/all-in-one`  
**Kit:** `KIT_VERSION` (currently 0.2.0) · **Port:** `PORT_VERSION` (currently 0.1.0)

This file is the **requirement index**. Implementation details with exact paths, numbers, pad indices, argv templates, and verification commands live in **`docs/spec/`** — those files are normative for their domains.

| Domain spec | Path |
|-------------|------|
| **Kit IPC & HTTP** | [`API_CONTRACTS.md`](API_CONTRACTS.md) |
| **Kit architecture** | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Environments & debug** | [`ENVIRONMENTS.md`](ENVIRONMENTS.md) |
| Kit manifest (machine) | [`tools/pd_kit/kit.json`](tools/pd_kit/kit.json) |
| Agent Office slice | [`journal/agent_office/SPEC.md`](journal/agent_office/SPEC.md) |
| War Colors mp13 | [`docs/spec/WAR_COLORS.md`](docs/spec/WAR_COLORS.md) |
| Map Launcher | [`docs/spec/MAP_LAUNCHER.md`](docs/spec/MAP_LAUNCHER.md) |
| Curriculum 31 steps | [`docs/spec/CURRICULUM.md`](docs/spec/CURRICULUM.md) |
| CLI flags & engine limits | [`docs/spec/CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) |
| Map invariants (generated) | [`docs/MAP_DETERMINISTIC_SPEC.md`](docs/MAP_DETERMINISTIC_SPEC.md) |
| War Colors narrative | [`docs/WAR_COLORS_LEVEL.md`](docs/WAR_COLORS_LEVEL.md) |
| User stories + verification | [`STORIES.md`](STORIES.md) |
| Operator guide | [`PERFECT_DARK_KIT.md`](PERFECT_DARK_KIT.md) |

---

## 1. Requirement registry

### 1.1 PC port (`build/pd.arm64`)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-PORT-01 | Load ROM from `data/pd.ntsc-final.z64` and mods from `--moddir` | `fsFileLoad: name=pd.ntsc-final.z64 resolved to=./data/...` in log | |
| R-PORT-02 | Parse boot flags in `port/src/bootmp.c` per [`CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) §1 | `rg 'Battle64 teams' log` after launch | |
| R-PORT-03 | Enforce `MAX_CHRSPERTEAM=32`: teams MP with human MUST NOT exceed 32 chrs | `--num-sims 32` on War Colors → exit **138** SIGBUS; 31 → alive 15s | [`WAR_COLORS.md`](docs/spec/WAR_COLORS.md) §6 |
| R-PORT-04 | Accept modconfig stages `0x02`–`0xff` inclusive | `0x5b` loads without `malformed stage block` | `port/src/mod.c:291` |
| R-PORT-05 | Emit `war_colors_spawn:` and `spawn: stage=5b` on `STAGE_EXTRA26` | `rg war_colors_spawn journal/map_learn/.conker_war_sentry_inf_test.log` | `player.c` |
| R-PORT-06 | NULL-guard bot shade on custom geometry | 50-sim matrix session no crash in `propobj.c` | PR #8 |

### 1.2 pdmap pipeline

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-PDMAP-01 | `python3 tools/pdmap.py build <level> --deploy` writes to `mods/mod_allinone/files/` (or `--mod`) | File mtimes update under `bgdata/` | |
| R-PDMAP-02 | `validate_mapdef()` enforces invariants in `MAP_DETERMINISTIC_SPEC.md` | `validate_curriculum()` 31/31 | |
| R-PDMAP-03 | Default `PDMAP_SEG_MODE=empty` for FPS box arenas | Step 15 vs 14 in curriculum | |
| R-PDMAP-04 | `add_loadout_intro` emits ailist **0x1000** | Step 5 curriculum | |
| R-PDMAP-05 | Spawn pads at **Y=10.0**, not Y=0 | Step 11 autocorrect test | `PAD_FLOOR_OFFSET` |

### 1.3 Curriculum

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-LEARN-01 | Exactly **31** steps in `curriculum.py` | See command in [`CURRICULUM.md`](docs/spec/CURRICULUM.md) §1 | |
| R-LEARN-02 | Fixture per step at `journal/map_learn/maps/learn_XX_<slug>.json` | File exists for N=1..31 | |
| R-LEARN-03 | Map Launcher manifest lists 31 steps in 8 phases | `len(manifest['steps'])==31` | [`MAP_LAUNCHER.md`](docs/spec/MAP_LAUNCHER.md) §6 |
| R-LEARN-04 | `play-learn-step.sh N` deploys and launches step N | `./scripts/play-learn-step.sh 7` → `--scenario-4` | Full table §2 |

### 1.4 Kit Hub & Electron platform

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-KIT-01 | `scripts/build-pd-kit.sh` produces `scripts/release/Perfect Dark Kit.app` | `test -d 'scripts/release/Perfect Dark Kit.app'` | [`ARCHITECTURE.md`](ARCHITECTURE.md) §8 |
| R-KIT-02 | `pd-kit.sh open <key>` resolves app from `kit.json` | `./scripts/pd-kit.sh open anim-lab` | |
| R-KIT-03 | Each app: unique icon, `requestSingleInstanceLock()` | Icons in `.tmp-map-editor-app-build/`; second Dock click focuses window | |
| R-KIT-04 | Electron apps read baked `repo-config.json` `{ repoRoot }` | File in `Contents/Resources/` after build | |
| R-KIT-05 | Hub launch cooldown **1200 ms** per `appKey` | 5 rapid clicks → ≤1 `Launch animLab:` per 1.2 s in `kit-hub.log` | [`API_CONTRACTS.md`](API_CONTRACTS.md) §1.2 |
| R-KIT-06 | IPC handlers return `{ ok: false, error }` — never throw | Induce bad path; hub stays alive | `tools/pd_kit/electron/main.js` |
| R-KIT-07 | `process.on('unhandledRejection')` logs only (Electron 33) | No `EXC_BREAKPOINT` within 30 s idle | [`ENVIRONMENTS.md`](ENVIRONMENTS.md) §8 |
| R-KIT-08 | Python apps: single `ensureBootstrap()` mutex | One `=== electron anim-lab start ===` per process | [`STORIES.md`](STORIES.md) AC-ANIM-1.1 |
| R-KIT-09 | Map Editor ports **8765–8775**; Anim Lab **8776–8795** | `curl …/api/health` service id matches | [`API_CONTRACTS.md`](API_CONTRACTS.md) §3–4 |
| R-KIT-10 | Hub wraps child apps to `Resources/Apps/`; optional missing = warn only | `jq .apps.kitHub.wrappedApps kit-manifest.json` | |
| R-KIT-11 | `kit-manifest.json` generated at build — never hand-edited | `builtAt` updates after rebuild | [`API_CONTRACTS.md`](API_CONTRACTS.md) §6 |
| R-KIT-12 | iCloud paths normalize `MobileDocuments` → `Mobile Documents` before I/O | Repo under iCloud; AC-ANIM-1.x pass | |

**Normative algorithms:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §4–5 · **Full IPC/HTTP schemas:** [`API_CONTRACTS.md`](API_CONTRACTS.md)

### 1.5 Map Launcher

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-ML-01 | Only `MAP_LAUNCHERS[].script` paths spawnable | 9 IDs in [`MAP_LAUNCHER.md`](docs/spec/MAP_LAUNCHER.md) §4 | |
| R-ML-02 | Both Map Launcher + Map Learning tabs on default view | Manual UI check | |
| R-ML-03 | War Colors: solo omits `--num-sims`; fullBattle=**31** | `resolveWarColorsSimOptions` unit behavior | §5 |
| R-ML-04 | Launch via `open --env PD_REPO_ROOT=…`; window visible ≤3s | PID alive 15s | §7 |
| R-ML-05 | War Colors `numSims` max **31** in UI | `max: 31` in `MAP_LAUNCHERS` options | |
| R-ML-06 | Second launch focuses existing instance | stderr message exact string in §7 | |

### 1.6 Matrix Battle 64

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MATRIX-01 | `MAX_BOTS=60` on PC; chrslots bitmask for slot index >31 | 64-bot config in `chrslots.h` | |
| R-MATRIX-02 | Deploy `matrix_battle_64` to uff via `--test-map` | `play-matrix-battle.sh` pre-deploy line | |
| R-MATRIX-03 | Sentry scripts pass `--laptop-sentry-infinite-ammo --unlimited-sentries` | argv in log | |
| R-MATRIX-04 | Team 0 spawn `z<0`, team 1 `z>0` on uff + teams | `player.c` STAGE_TEST_UFF block | |

### 1.7 War Colors

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-WC-01 | `--kakarikomoddir mods/mod_kakariko` on every launch | Script hard-fail otherwise | [`WAR_COLORS.md`](docs/spec/WAR_COLORS.md) §5 |
| R-WC-02 | Setup spawn pads exactly `[35,116,113,0,218,108,88,80,16,82,20,89]` | `setup verify:` line | §3.1 |
| R-WC-03 | `bg_mp13_padsZ` = **6096 bytes** RareZip from ROM envelope | `deployed: ... (6096 bytes` | §2 |
| R-WC-04 | Team spawn Z: SHC `z≥1200`, Tediz `z≤-1200` | `WAR_COLORS_SHC_Z_MIN` / `TEDIZ_Z_MAX` | §4 |
| R-WC-05 | `WAR_COLORS_MAX_TEAM_SIMS=31` in play script | `--full-battle` → 31 not 50 | §6 |
| R-WC-06 | Default **8** sims; `--solo` → 0 sims | `NUM_SIMS=8` in script | |
| R-WC-07 | Purge `Ump_setupmp13Z` / `bg_mp13_padsZ` outside kakariko before launch | `remove_mp13_overrides` log | |

### 1.8 KOTH

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-KOTH-01 | Position-bounds scoring on box arenas | learn_07 playable | PR #5 |
| R-KOTH-02 | Hill collision duplicated room 1 | learn_28 no fall-through | |
| R-KOTH-03 | Hill counter restarts on re-entry | Manual re-entry test | |

---

## 2. Non-functional requirements

| ID | Requirement | Measure |
|----|-------------|---------|
| NFR-01 | Primary platform macOS arm64 | `build/pd.arm64` Mach-O arm64 |
| NFR-02 | Map Launcher window ≤3s | `ready-to-show` log timestamp |
| NFR-03 | Stale `pd.arm64` same `--boot-stage 0x5b` killed before relaunch | `kill_stale_war_colors` in script |
| NFR-04 | Logs under `journal/map_learn/*.log` and `~/Library/Logs/PerfectDarkKit/` | Paths in domain specs |
| NFR-05 | No arbitrary script spawn from Electron | Whitelist only (Map Launcher); hub uses `kit.json` actionGroups |
| NFR-06 | Hub renderer: status line for errors; buttons disabled during long IPC | Manual UI check |
| NFR-07 | PRs cite spec IDs; max ~6 open slices | See §3 |
| NFR-08 | Local HTTP binds `127.0.0.1` only; non-localhost Origin → 403 | [`API_CONTRACTS.md`](API_CONTRACTS.md) |

---

## 3. Delivery state (2026-07-02)

| PR | Branch | Spec domains |
|----|--------|--------------|
| [#5](https://github.com/moyoteg/perfect_dark/pull/5) | `fix/koth-pdmap-arenas` | R-KOTH-* |
| [#6](https://github.com/moyoteg/perfect_dark/pull/6) | `feat/map-learn-curriculum-31` | R-LEARN-*, R-PDMAP-* |
| [#7](https://github.com/moyoteg/perfect_dark/pull/7) | `feat/perfect-dark-kit-hub` | R-KIT-* |
| [#8](https://github.com/moyoteg/perfect_dark/pull/8) | `feat/matrix-battle-64-mp` | R-MATRIX-*, R-PORT-06 |
| [#9](https://github.com/moyoteg/perfect_dark/pull/9) | `feat/map-launcher-electron` | R-ML-* |
| [#10](https://github.com/moyoteg/perfect_dark/pull/10) | `feat/war-colors-conker-mp13` | R-WC-* |

**Merge order:** 5 → 6 → 7 → 9 → 8 → 10

---

## 4. Spec-driven workflow

1. Open domain spec in `docs/spec/` for the feature.
2. Implement only what the SHALL rows require.
3. Run the **Verify** column command exactly; attach log excerpt to PR.
4. PR body lists spec IDs: `Implements R-WC-02, R-WC-05`.
5. If adding a new invariant, extend via `pdmap learn` → `MAP_DETERMINISTIC_SPEC.md` (generated).

**Changing numbers** (pad indices, sim caps, file sizes): update domain spec first, then code, then `STORIES.md` acceptance commands.

---

## 5. Backlog (uncommitted on `port-mods/all-in-one`)

- `tools/pdmap/{builders,deploy,validate,weapons}.py` delta not in PR #6
- `src/game/{env,lv,romdata,stagetable}.c` engine fixes
- Package `PD Map Launcher.app` in `build-pd-kit.sh --apps-only`
- Domain spec for Virtual Agent Office (`STAGE_AGENT_OFFICE` `0x83`)

---

*Normative detail: `docs/spec/*.md`, [`API_CONTRACTS.md`](API_CONTRACTS.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`ENVIRONMENTS.md`](ENVIRONMENTS.md). Stories: [`STORIES.md`](STORIES.md).*
