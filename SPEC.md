# Perfect Dark AIO — Map Creation Specification (index)

**Version:** 0.4.0-map-creation  
**Branch:** `port-mods/all-in-one`  
**Scope:** Custom multiplayer arena authoring only (pdmap → mod → engine). Kit Hub, Map Launcher UI, Agent Office, LLM Play, and War Colors playtest sims are **out of scope** for this index — see footnotes in [`docs/spec/README.md`](docs/spec/README.md).

**Normative detail:** [`docs/spec/MAP_CREATION.md`](docs/spec/MAP_CREATION.md) · **Curriculum:** [`docs/spec/CURRICULUM.md`](docs/spec/CURRICULUM.md) · **Stories:** [`STORIES.md`](STORIES.md)

| Reference | Path |
|-----------|------|
| **Primary normative spec** | [`docs/spec/MAP_CREATION.md`](docs/spec/MAP_CREATION.md) |
| Curriculum (31 steps) | [`docs/spec/CURRICULUM.md`](docs/spec/CURRICULUM.md) |
| CLI flags (map test subset) | [`docs/spec/CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) |
| Map invariants (generated) | [`docs/MAP_DETERMINISTIC_SPEC.md`](docs/MAP_DETERMINISTIC_SPEC.md) |
| Operator wiki | [`docs/MAP_MAKING_WIKI.md`](docs/MAP_MAKING_WIKI.md) |
| Binary / wiring deep reference | [`docs/MAP_CREATION.md`](docs/MAP_CREATION.md) |
| Workflow commands | [`.agents/skills/perfect-dark-workflow/SKILL.md`](.agents/skills/perfect-dark-workflow/SKILL.md) |
| Operator guide | [`PERFECT_DARK_KIT.md`](PERFECT_DARK_KIT.md) |

---

## 1. Requirement registry

Each row is **SHALL** unless marked optional. Run the **Verify** command exactly; attach log excerpt to PRs.

### 1.1 Five-file contract & paths

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-01 | Every playable arena ships **five assets**: `bg_<name>.seg`, `bg_<name>_tilesZ`, `bg_<name>_padsZ`, `Ump_setup<name>Z`, `Usetup<name>Z` (solo alias of setup) | `ls build/ntsc-final/assets/files/bgdata/bg_uff* build/ntsc-final/Ump_setupuffZ 2>/dev/null \| wc -l` ≥ 3 after build | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §1 |
| R-MAP-02 | Built bgdata lives under `build/ntsc-final/assets/files/bgdata/`; setup under `build/ntsc-final/` (`SETUP_DIR`) | `python3 -c "from tools.pdmap.core import BUILD_DIR,SETUP_DIR; print(BUILD_DIR); print(SETUP_DIR)"` | `tools/pdmap/core.py` |
| R-MAP-03 | Default deploy copies into `mods/mod_allinone/files/bgdata/` (and sibling `MOD_DIRS`) | `python3 tools/pdmap.py build uff --deploy 2>&1 \| rg 'Deployed bg_uff'` | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §6 |

### 1.2 Coordinates

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-04 | World up axis is **+Y**; floor tiles at **Y = 0** | Grep wiki + `floor_box_tiles` usage | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §3 |
| R-MAP-05 | Spawn/weapon/scenario pads use **Y = 10.0** (`PAD_FLOOR_OFFSET`); `Y ≤ 0` pads fail validation | `python3 tools/pdmap.py validate learn_11_y_autocorrect 2>&1; echo exit:$?` → exit 0 | `tools/pdmap/builders.py:PAD_FLOOR_OFFSET` |
| R-MAP-06 | Pads with **Y > 200** emit warnings (fall damage risk) | `python3 tools/pdmap.py validate uff 2>&1` — no spurious Y>200 on stock uff | `tools/pdmap/validate.py` |

### 1.3 Validation (`validate_mapdef`)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-07 | Pad indices **contiguous 0..N−1** matching array order | Inject gap → `python3 tools/pdmap.py validate <name>` exit ≠ 0 | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4 |
| R-MAP-08 | Pad **room ≥ −1**; room must exist in tiles when tiles JSON present | Step 7 hill pad room=2 passes | `validate.py` |
| R-MAP-09 | Intro includes at least one **Spawn** command | Map without Spawn → validate error | `validate.py` |
| R-MAP-10 | Each CTF **Case** team has matching **CaseRespawn** | Step 8 curriculum; missing respawn → validate error | `validate.py` |
| R-MAP-11 | Seg **G_VTX** passes before deploy (max 16 verts/load) | `python3 tools/pdmap.py build uff --seg --deploy` — no `Refusing to deploy corrupt seg` | `deploy.py:_validate_seg_before_deploy` |
| R-MAP-12 | Generated invariants in `MAP_DETERMINISTIC_SPEC.md` match probes | `python3 tools/pdmap.py learn run 2>&1 \| tail -5` — no unexpected drift | Do not hand-edit generated spec |

### 1.4 Seg modes (`PDMAP_SEG_MODE`)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-13 | Default box arena seg mode is **`empty`** (no viewport sheet in FPS) | Step 15 vs 14 in curriculum | `pipeline.py`, `seg.py` |
| R-MAP-14 | **`full`** emits all six box faces (editor preview; may near-plane clip in FPS) | `./scripts/play-learn-step.sh 14 --no-play 2>&1 \| rg PDMAP_SEG_MODE=full` | Step 14 |
| R-MAP-15 | **`hill`** / **`ctf`** emit floor quads for KOTH / CTF lesson markers | Steps 7, 8, 10, 28 | `seg.py` |
| R-MAP-16 | **`marker`** emits overlap-pad lesson geometry (grey arena + green centre) | Step 20 / 31 | `seg.py` |

### 1.5 Deploy & retail-slot overlay

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-17 | `deploy(name, deploy_as=…)` copies built artifacts under module name to **asset_name** paths | `python3 tools/pdmap.py build learn_09_deploy_uff --deploy 2>&1 \| rg 'bg_uff'` | `deploy.py` |
| R-MAP-18 | Level module may set **`DEPLOY_AS`** (e.g. build `my_arena`, deploy as `uff`) | Step 9 curriculum | `pipeline.py` |
| R-MAP-19 | **`MOD_DIRS`** default: `mod_allinone`, `mod_kakariko`, `mod_moyoteg` bgdata | `python3 -c "from tools.pdmap.core import MOD_DIRS; print(len(MOD_DIRS))"` → **3** | `core.py` |
| R-MAP-20 | *(Optional)* Retail-slot overlay: build module X, deploy as retail asset name (War Colors pattern) | See [`docs/spec/WAR_COLORS.md`](docs/spec/WAR_COLORS.md) on PR branch — not primary map-creation path | Overlay only |

### 1.6 Setup, bots, waypoints

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-21 | MP setup emits ailist id **`0x1000`** (`mp_init_simulants`) | Step 5 curriculum; `rg 0x1000 build/ntsc-final/Ump_setupuffZ` or setup hex dump | `core.py:MapDef.pack_setup` |
| R-MAP-22 | Waypoint graph is **symmetric** (K_NEAREST=**6** neighbours, reciprocal edges) | Step 6 curriculum; `--num-sims 1` bots navigate | `core.py:MapDef.pack_pads_json` |
| R-MAP-23 | Stock sim cap **4 bots** without `MPFEATURE_8BOTS` | Step 23: `--num-sims 8` → only 4 spawn | [`CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) §2 |
| R-MAP-24 | `--test-map` sets quick-team **`chrslots = 0x01`** before team select | Boot log on `--test-map`; `title.c` | [`CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) §1 |

### 1.7 Stage registration & test boot

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-25 | **`STAGE_TEST_UFF`** = **`0x4d`** loads `bg_uff.*` via `--test-map` | `./build/pd.arm64 --test-map --moddir mods/mod_allinone --basedir data --savedir . 2>&1 \| rg -i 'uff\|0x4d'` | `stagetable.c`, `title.c` |
| R-MAP-26 | **`STAGE_MY_ARENA`** = **`0x80`**, menu textid **`0x7FFD`** | Step 16; `rg STAGE_MY_ARENA src/game/stagetable.c src/game/mplayer/setup.c` | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §7 |
| R-MAP-27 | `pdmap register` emits wiring plan for `files.h`, `list.c`, `stagetable.c`, `setup.c` | `python3 tools/pdmap.py register my_arena --dry-run 2>&1 \| rg stagetable` | Step 18 |
| R-MAP-28 | Editor JSON → **`from-json`** → build → deploy → **`--test-map`** | `python3 journal/uff_viewer/test_map.py journal/map_learn/maps/learn_01_spawn.json --level uff --seg --deploy --play` or step 17 | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §8 |

### 1.8 Curriculum

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-29 | Exactly **31** curriculum steps in `curriculum.py` | `python3 -c "from tools.pdmap.learn.curriculum import validate_curriculum; r=validate_curriculum(verbose=True); assert len([x for x in r if not x.ok])==0"` → **31/31** | [`CURRICULUM.md`](docs/spec/CURRICULUM.md) §1 |
| R-MAP-30 | Fixture JSON per step at `journal/map_learn/maps/learn_XX_<slug>.json` | `ls journal/map_learn/maps/learn_*.json \| wc -l` → **31** | [`CURRICULUM.md`](docs/spec/CURRICULUM.md) §2 |
| R-MAP-31 | `./scripts/play-learn-step.sh N` deploys step N to uff slot and launches with correct `--scenario-*` | `./scripts/play-learn-step.sh 7 --no-play 2>&1 \| rg scenario-4` | [`CURRICULUM.md`](docs/spec/CURRICULUM.md) §1 |

### 1.9 Engine boot (map author subset)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-32 | PC port loads ROM + `--moddir mods/mod_allinone` | `./build/pd.arm64 --moddir mods/mod_allinone --basedir data --savedir .` boots | |
| R-MAP-33 | Modconfig accepts custom stages **`0x02`–`0xff`** | `--boot-stage 0x80` on registered arena | `port/src/mod.c` |
| R-MAP-34 | **`--scenario-0`…`--scenario-5`** select MP scenario | Step 7 → `--scenario-4` (KOTH); step 8 → `--scenario-5` (CTF) | [`CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) §1 |

---

## 2. Non-functional requirements (map creation)

| ID | Requirement | Measure |
|----|-------------|---------|
| NFR-MAP-01 | Primary platform macOS arm64 | `file build/pd.arm64` → Mach-O arm64 |
| NFR-MAP-02 | Validation logs under `journal/map_learn/` | `play-learn-step.sh` writes `.last_validation_launch.log` |
| NFR-MAP-03 | PRs cite `R-MAP-*` ids implemented | PR body lists ids |
| NFR-MAP-04 | Changing pad indices, paths, or seg rules: update `docs/spec/MAP_CREATION.md` first, then code | Review checklist |

---

## 3. Spec-driven workflow

1. Open [`docs/spec/MAP_CREATION.md`](docs/spec/MAP_CREATION.md) for the feature area.
2. Implement only what the SHALL rows require.
3. Run the **Verify** column command; attach log excerpt to PR.
4. PR body: `Implements R-MAP-05, R-MAP-17`.
5. New invariants: extend via `python3 tools/pdmap.py learn run` → refresh [`docs/MAP_DETERMINISTIC_SPEC.md`](docs/MAP_DETERMINISTIC_SPEC.md).

**User stories with copy-paste acceptance:** [`STORIES.md`](STORIES.md)

---

## 4. Out of scope (other PR branches / docs)

| Domain | Where to look |
|--------|----------------|
| Kit Hub, Electron IPC | [`API_CONTRACTS.md`](API_CONTRACTS.md), [`ARCHITECTURE.md`](ARCHITECTURE.md) — not indexed here |
| Map Launcher UI | [`docs/spec/MAP_LAUNCHER.md`](docs/spec/MAP_LAUNCHER.md) — footnote in [`docs/spec/README.md`](docs/spec/README.md) |
| War Colors mp13 overlay | [`docs/spec/WAR_COLORS.md`](docs/spec/WAR_COLORS.md) — optional retail-slot pattern (R-MAP-20) |
| Agent Office / LLM Play | Separate product slices |

---

*Normative: [`docs/spec/MAP_CREATION.md`](docs/spec/MAP_CREATION.md). Verification: [`STORIES.md`](STORIES.md). Operator: [`PERFECT_DARK_KIT.md`](PERFECT_DARK_KIT.md).*
