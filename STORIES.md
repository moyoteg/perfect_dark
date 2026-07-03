# Perfect Dark AIO — Map Creation User Stories

**Parent spec:** [`SPEC.md`](SPEC.md) (`R-MAP-*`)  
**Normative detail:** [`docs/spec/MAP_CREATION.md`](docs/spec/MAP_CREATION.md)  
**Curriculum table:** [`docs/spec/CURRICULUM.md`](docs/spec/CURRICULUM.md)

Each story includes **copy-paste bash** and **expected log substrings**. Reference the AC id in PRs: `Fixes AC-MAP-AUTHOR-1.2`.

---

## How to verify

1. Run commands from **repo root** with `build/pd.arm64` built (`make -j8`) and ROM at `data/pd.ntsc-final.z64`.
2. Grep launch/build output for **Pass substrings**; any **Fail substring** is a blocker.
3. Map acceptance criteria to `R-MAP-*` ids in [`SPEC.md`](SPEC.md).

---

## US-MAP-AUTHOR — Author a level module

**As a** map author,  
**I want** to define a level in `src/levels/<name>.py` and validate it,  
**So that** invalid pads and intro commands fail before deploy.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-AUTHOR-1.1 | Module loads and builds | `python3 tools/pdmap.py validate uff` | exit 0; no `Pad at position` errors | `Cannot load level module` |
| AC-MAP-AUTHOR-1.2 | Contiguous pad indices enforced | `python3 tools/pdmap.py validate learn_01_spawn` | exit 0 | `must be contiguous from 0` |
| AC-MAP-AUTHOR-1.3 | Spawn required | `python3 tools/pdmap.py validate learn_01_spawn` | exit 0 | `no Spawn commands` |

```bash
python3 tools/pdmap.py validate learn_01_spawn
echo "exit:$?"
# EXPECT: exit:0
```

**Spec:** R-MAP-07, R-MAP-09

---

## US-MAP-BUILD — Build and deploy

**As a** map author,  
**I want** `pdmap build --deploy` to write assets to build tree and mod,  
**So that** the game loads my map from `--moddir`.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-BUILD-1.1 | Five-file deploy to mod | See bash below | `Deployed bg_uff`; files exist under mod | `WARNING: … not found` (all assets) |
| AC-MAP-BUILD-1.2 | Seg validated before deploy | `python3 tools/pdmap.py build uff --seg --deploy` | no `Refusing to deploy corrupt seg` | `Seg G_VTX` error + refuse |

```bash
python3 tools/pdmap.py build uff --seg --deploy 2>&1 | tee /tmp/pdmap-deploy.log
test -f mods/mod_allinone/files/bgdata/bg_uff.seg && echo "seg:OK"
test -f mods/mod_allinone/files/bgdata/bg_uff_tilesZ && echo "tiles:OK"
test -f mods/mod_allinone/files/bgdata/bg_uff_padsZ && echo "pads:OK"
test -f mods/mod_allinone/files/Ump_setupuffZ && echo "setup:OK"
rg 'Deployed bg_uff' /tmp/pdmap-deploy.log
# EXPECT: seg/tiles/pads/setup OK; Deployed lines in log
```

**Spec:** R-MAP-01, R-MAP-03, R-MAP-11, R-MAP-17

---

## US-MAP-CURRICULUM — Validate full learn path

**As a** curriculum maintainer,  
**I want** all 31 steps to validate,  
**So that** regressions are caught in CI.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-CURR-1.1 | 31/31 steps OK | See bash | `31/31`; `steps OK` | any `FAIL` or assertion |

```bash
python3 -c "
from tools.pdmap.learn.curriculum import validate_curriculum
r = validate_curriculum(verbose=True)
bad = [x for x in r if not x.ok]
assert not bad, bad
print(f'{len(r)}/31 steps OK')
"
# EXPECT: 31/31 steps OK
```

**Spec:** R-MAP-29, R-MAP-30

---

## US-MAP-PADY — Fix pad Y height

**As a** map author,  
**I want** pads at Y=10 not Y=0,  
**So that** players don't fall through the floor.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-PADY-1.1 | Y=0 rejected or autocorrected | Step 11 play script | `learn_11`; Y=10 in output | `at/below the floor` on final validate |
| AC-MAP-PADY-1.2 | PAD_FLOOR_OFFSET is 10.0 | Python one-liner | `10.0` | |

```bash
python3 -c "from tools.pdmap.builders import PAD_FLOOR_OFFSET; assert PAD_FLOOR_OFFSET==10.0"
./scripts/play-learn-step.sh 11 --no-play 2>&1 | rg -i 'learn_11|y=10|autocorrect'
python3 tools/pdmap.py validate learn_11_y_autocorrect && echo validate:OK
# EXPECT: PAD_FLOOR_OFFSET 10.0; validate:OK
```

**Spec:** R-MAP-05, R-MAP-08 (validate)

---

## US-MAP-UFF — Deploy to uff test slot

**As a** map author,  
**I want** to deploy any curriculum map into the **uff** retail test slot,  
**So that** `--test-map` loads my latest build.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-UFF-1.1 | deploy-as uff | Step 9 | `Deploy-as`; `bg_uff` | wrong asset basename |
| AC-MAP-UFF-1.2 | Mod hygiene | Step 30 | `loaded externally`; `bg_uff` | stale vanilla assets |

```bash
./scripts/play-learn-step.sh 9 --no-play 2>&1 | tee /tmp/step9.log
rg -i 'learn_09|Deployed bg_uff|Deploy-as' /tmp/step9.log
# EXPECT: learn_09 + bg_uff deploy lines
```

**Spec:** R-MAP-17, R-MAP-18, R-MAP-25

---

## US-MAP-REGISTER — Register a dedicated stage

**As a** map author,  
**I want** to register `my_arena` as `STAGE_MY_ARENA` (`0x80`),  
**So that** it appears in Combat Simulator and boots with `--boot-stage 0x80`.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-REG-1.1 | Register plan generated | `pdmap register --dry-run` | `stagetable`; `STAGE_` | empty plan / traceback |
| AC-MAP-REG-1.2 | Registered arena in engine | grep C sources | `STAGE_MY_ARENA`; `0x7FFD` | missing symbol |
| AC-MAP-REG-1.3 | Step 16 curriculum | play-learn-step 16 | `my_arena`; `scenario-5` | wrong stage |

```bash
python3 tools/pdmap.py register my_arena --dry-run 2>&1 | rg -i 'stagetable|setup.c|STAGE'
rg 'STAGE_MY_ARENA' src/include/constants.h src/game/stagetable.c src/game/mplayer/setup.c
./scripts/play-learn-step.sh 16 --no-play 2>&1 | rg -i 'learn_16|my_arena|scenario-5'
# EXPECT: register mentions stagetable; STAGE_MY_ARENA in C; step 16 deploy log
```

**Spec:** R-MAP-26, R-MAP-27

---

## US-MAP-JSON — Editor JSON pipeline

**As a** map author using the Map Editor JSON export,  
**I want** `from-json` and `test_map.py` to build without a hand-written level module,  
**So that** I can iterate in the editor.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-JSON-1.1 | from-json CLI | See bash | `Deployed bg_uff`; validate OK | traceback |
| AC-MAP-JSON-1.2 | test_map.py deploy | `--deploy` without `--play` | build + deploy lines | 500 / import error |

```bash
python3 tools/pdmap.py from-json journal/map_learn/maps/learn_17_from_json_cli.json \
  --deploy-as uff --seg --deploy 2>&1 | tee /tmp/from-json.log
rg 'Deployed bg_uff|validate' /tmp/from-json.log
python3 journal/uff_viewer/test_map.py journal/map_learn/maps/learn_01_spawn.json \
  --level uff --seg --deploy 2>&1 | rg -i 'deploy|build|uff'
# EXPECT: Deployed bg_uff; test_map completes without error
```

**Spec:** R-MAP-28

---

## US-MAP-SEG — Seg mode selection

**As a** map author,  
**I want** `PDMAP_SEG_MODE=empty` for FPS test and `full` only for preview lessons,  
**So that** I don't get a dark viewport sheet in-game.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-SEG-1.1 | Step 15 empty | play-learn-step 15 | `PDMAP_SEG_MODE=empty` or empty seg build | `full` |
| AC-MAP-SEG-1.2 | Step 14 full lesson | play-learn-step 14 | `full` or `learn_14` | |

```bash
./scripts/play-learn-step.sh 15 --no-play 2>&1 | rg -i 'learn_15|empty|PDMAP_SEG_MODE'
./scripts/play-learn-step.sh 14 --no-play 2>&1 | rg -i 'learn_14|full|PDMAP_SEG_MODE'
# EXPECT: step 15 mentions empty; step 14 mentions full/procedural
```

**Spec:** R-MAP-13, R-MAP-14, R-MAP-15, R-MAP-16

---

## US-MAP-SETUP — Bots and loadout intro

**As a** Combat Simulator author,  
**I want** ailist 0x1000 and symmetric waypoints,  
**So that** bots spawn and navigate without crashing.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-SETUP-1.1 | Loadout intro step 5 | validate + play-learn | `learn_05`; exit 0 | validate errors |
| AC-MAP-SETUP-1.2 | Waypoints step 6 | play-learn-step 6 --no-play | `learn_06`; `--num-sims 1` | missing sim flag |
| AC-MAP-SETUP-1.3 | 4-bot stock cap step 23 | curriculum metadata | `learn_23`; bot cap note | |

```bash
python3 tools/pdmap.py validate learn_05_loadout && echo loadout:OK
./scripts/play-learn-step.sh 6 --no-play 2>&1 | rg 'learn_06|num-sims'
./scripts/play-learn-step.sh 23 --no-play 2>&1 | rg 'learn_23'
# EXPECT: loadout:OK; learn_06 with num-sims; learn_23 deploy
```

**Spec:** R-MAP-21, R-MAP-22, R-MAP-23, R-MAP-24

---

## US-MAP-PLAY — Playtest via CLI

**As a** map author,  
**I want** to boot the last deployed uff map with `--test-map`,  
**So that** I can smoke-test without the Map Launcher UI.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-PLAY-1.1 | play-learn-step launches | Step 1 deploy+play flags | `--test-map`; `--scenario-0` | wrong moddir |
| AC-MAP-PLAY-1.2 | Direct pd boot | Manual launch | game window / stage load | immediate exit |
| AC-MAP-PLAY-1.3 | KOTH scenario | Step 7 | `--scenario-4` | `--scenario-0` only |

```bash
./scripts/play-learn-step.sh 1 --no-play 2>&1 | tee /tmp/step1.log
rg '--test-map|--scenario-0|learn_01|Deployed bg_uff' /tmp/step1.log
./scripts/play-learn-step.sh 7 --no-play 2>&1 | rg '--scenario-4|learn_07'
# EXPECT: test-map + scenario flags per step

# Optional interactive smoke:
# ./build/pd.arm64 --test-map --scenario-0 --basedir data \
#   --moddir mods/mod_allinone --savedir . --num-sims 0
```

**Spec:** R-MAP-25, R-MAP-31, R-MAP-32, R-MAP-34

---

## US-MAP-DETERMINISTIC — Generated spec stays in sync

**As a** maintainer,  
**I want** `pdmap learn run` to refresh deterministic invariants,  
**So that** docs match probed code behavior.

| ID | Criterion | Procedure | Pass substrings | Fail substrings |
|----|-----------|-----------|-----------------|-----------------|
| AC-MAP-DET-1.1 | Learn run completes | See bash | probe completion; no traceback | Python exception |
| AC-MAP-DET-1.2 | Spec mentions 0x1000 | grep generated spec | `0x1000`; `mp_init_simulants` | missing ailist fact |

```bash
python3 tools/pdmap.py learn run 2>&1 | tail -20
rg '0x1000|mp_init_simulants|PAD_FLOOR_OFFSET' docs/MAP_DETERMINISTIC_SPEC.md
# EXPECT: learn run exits 0; generated spec contains key invariants
```

**Spec:** R-MAP-12

---

## Story → spec traceability

| Story | Spec IDs | Detail |
|-------|----------|--------|
| US-MAP-AUTHOR | R-MAP-07, R-MAP-09 | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4 |
| US-MAP-BUILD | R-MAP-01, R-MAP-03, R-MAP-11, R-MAP-17 | §1, §6 |
| US-MAP-CURRICULUM | R-MAP-29, R-MAP-30 | [`CURRICULUM.md`](docs/spec/CURRICULUM.md) |
| US-MAP-PADY | R-MAP-04, R-MAP-05 | §3 |
| US-MAP-UFF | R-MAP-17, R-MAP-18, R-MAP-25 | §6, §7 |
| US-MAP-REGISTER | R-MAP-26, R-MAP-27 | §7 |
| US-MAP-JSON | R-MAP-28 | §8 |
| US-MAP-SEG | R-MAP-13 … R-MAP-16 | §5 |
| US-MAP-SETUP | R-MAP-21 … R-MAP-24 | §9 |
| US-MAP-PLAY | R-MAP-25, R-MAP-31, R-MAP-32 | §8, §10 |
| US-MAP-DETERMINISTIC | R-MAP-12 | §4.3 |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-07-02 | Map-creation-only stories; removed Kit Hub / Launcher / Anim Lab / Agent Office |
| 2026-07-02 | Initial AC ids for kit v0.2 (superseded hub stories) |
