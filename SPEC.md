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

### 1.10 Lifecycle observability & failure scenarios (Pass 7)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-35 | `tests/test_pdmap_failure_scenarios.py` covers **≥5** deterministic failure injectors with non-zero exit or `outcome.ok` false | `python3 tests/test_pdmap_failure_scenarios.py` → **ok** | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.10 |
| R-MAP-36 | Typed validation failures emit **`validation_failed`** lifecycle JSON with **`rule_codes`** and **`error_kind`** | Failure tests assert `PdmapLifecycleEvent.VALIDATION_FAILED` payload fields | `tools/pdmap/domain.py:PdmapLifecycleEvent`, `validate.py:run_validation` |
| R-MAP-37 | Catalogued validation errors map to **`PdmapValidationRuleCode`** (not **`UNKNOWN`**) for injectors in §4.10 | Failure tests assert `PdmapValidationRuleCode.UNKNOWN ∉ outcome.rule_codes` | `tools/pdmap/domain.py:classify_validation_rule_codes`, `ValidationOutcome.rule_codes` |
| R-MAP-38 | Deploy corrupt-seg refusal classified **`error_kind=seg`** with **`deploy_failed`** lifecycle | `test_failure_deploy_corrupt_seg_refusal` in failure scenario tests | `tools/pdmap/deploy.py:run_deploy`, `classify_deploy_failure` |

### 1.11 Dependency failures (Pass 8)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-39 | `tests/test_pdmap_dependency_failures.py` covers **≥3** dependency injectors with `outcome.ok` false and lifecycle **`recovery_class`** | `python3 tests/test_pdmap_dependency_failures.py` → **ok** | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.11 |
| R-MAP-40 | Missing assetmgr tools classify **`error_kind=tool_unavailable`**; missing BUILD_DIR artifacts at typed deploy classify **`error_kind=asset_missing`** | Dependency tests assert `PdmapFailureKind` on build/deploy outcomes | `tools/pdmap/domain.py:classify_build_failure`, `classify_deploy_failure` |
| R-MAP-41 | Dependency failures emit **`recovery_class=user_action_required`** except documented transient resource-busy messages | Dependency tests + §4.11 recovery policy | `tools/pdmap/domain.py:classify_failure_recovery`, `pipeline.py:run_build`, `deploy.py:run_deploy` |

### 1.12 Validation recovery & unified test gate (Pass 9)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-42 | **`scripts/run-pdmap-domain-tests.sh`** runs all **9** pdmap domain test modules plus curriculum **31/31**; exits non-zero on any failure | `./scripts/run-pdmap-domain-tests.sh` → **PASS: pdmap domain test gate** | [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.12 |
| R-MAP-43 | `validation_completed` emits **`recovery_class=none`** when `outcome=ok` | `test_lifecycle_events_emitted_on_run_validation` asserts `recovery_class` | `tools/pdmap/validate.py:run_validation` |
| R-MAP-44 | `validation_failed` emits **`recovery_class`** via `classify_failure_recovery` (typically **`user_action_required`**) | ≥2 tests assert `recovery_class` on `validation_failed` payloads | `tools/pdmap/domain.py:failure_lifecycle_fields`, `validate.py:run_validation` |

### 1.13 CI gate & curriculum recovery (Pass 10)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-45 | GitHub Actions runs **`scripts/run-pdmap-domain-tests.sh`** on **`port-net-mods/*`** push/PR (and fork CI on `port-mods/all-in-one`) | Workflow YAML present; local `./scripts/run-pdmap-domain-tests.sh` → **PASS** | [`.github/workflows/pdmap-domain.yml`](.github/workflows/pdmap-domain.yml), [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.13 |
| R-MAP-46 | `curriculum_validate_completed` emits **`recovery_class=none`** when `outcome=ok`, else **`user_action_required`** | `test_validate_curriculum_lifecycle_started_completed` + collect-all failure test assert `recovery_class` | `tools/pdmap/learn/curriculum.py:validate_curriculum`, [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.13 |

### 1.14 Production limits (Pass 12)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-47 | **`PdmapDomainLimit`** enum surfaces engine ceilings (`seg_g_vtx_load` max **16**, `spawn_pad_count` max **256**) | `tests/test_pdmap_limit_reached.py` asserts `limit_id` + `limit_max` | `tools/pdmap/domain.py:PdmapDomainLimit`, `seg.py:MAX_G_VTX_LOAD`, `constants.h:MAX_SPAWN_POINTS` |
| R-MAP-48 | Validation failures at a typed limit emit **`limit_reached`** lifecycle JSON with **`recovery_class=user_action_required`** | ≥2 tests in `test_pdmap_limit_reached.py` assert `PdmapLifecycleEvent.LIMIT_REACHED` payload | `tools/pdmap/validate.py:run_validation`, `domain.py:emit_limit_reached_events` |
| R-MAP-49 | **`ValidationOutcome.limits_reached`** populated via `detect_domain_limits` on error messages | Limit tests assert non-empty `limits_reached` tuple | `tools/pdmap/domain.py:detect_domain_limits`, `make_validation_outcome` |

### 1.15 Build timeout & safe recovery (Pass 14)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-50 | **`PdmapBuildTimeoutSeconds`** (default **300**) bounds mkpads/mktiles/seg-script subprocesses; overridable via **`PDMAP_BUILD_TIMEOUT_SECONDS`** | `test_pdmap_build_timeout_seconds_env_override` + `core.run_tool` timeout kwarg | `tools/pdmap/domain.py:pdmap_build_timeout_seconds`, `core.py:run_tool`, `pipeline.py`, `deploy.py` |
| R-MAP-51 | Subprocess timeout emits **`build_failed`** with **`error_kind=build`**, **`recovery_class=transient`**, **`reason=timeout`**, **`recovery_attempted=false`** | ≥2 tests in `test_pdmap_build_timeout.py` assert lifecycle payload | `tools/pdmap/domain.py:is_build_timeout`, `build_timeout_lifecycle_fields`, `pipeline.py:run_build` |

### 1.16 Build timeout retry (Pass 15)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-52 | **`PdmapRetryPolicy`** (`max_attempts`, `backoff_ms`) and **`should_retry_build_timeout`** provide a pure retry decision for transient timeout failures | `test_should_retry_build_timeout_pure_decision` in `test_pdmap_build_retry.py` | `tools/pdmap/domain.py:PdmapRetryPolicy`, `should_retry_build_timeout`, `default_build_retry_policy` |
| R-MAP-53 | **`run_build_with_retry`** emits **`retry_scheduled`**, **`recovery_attempted`**, then **`recovery_succeeded`** or **`recovery_failed`**; default **one retry** (two attempts total) when **`PDMAP_BUILD_RETRY_ON_TIMEOUT=1`** | ≥3 tests in `test_pdmap_build_retry.py` (success, exhausted, env-off regression) | `tools/pdmap/pipeline.py:run_build_with_retry` |
| R-MAP-54 | **`PDMAP_BUILD_RETRY_ON_TIMEOUT`** defaults **off** — single-attempt behavior unchanged from Pass 14 | `test_retry_disabled_single_attempt_regression` | `tools/pdmap/domain.py:pdmap_build_retry_on_timeout_enabled` |

### 1.17 Lifecycle documentation refs (Pass 12 step 11)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-55 | Typed lifecycle JSON emitted via **`emit_lifecycle_event`** includes **`documentation_ref`**; events with indexed acceptance criteria also include **`acceptance_criterion_ref`** when catalogued | ≥2 tests in `test_pdmap_validation_domain.py` assert `documentation_ref` on `validation_completed` / `validation_failed` | `tools/pdmap/domain.py:lifecycle_ref_fields`, `_LIFECYCLE_EVENT_REFS`, [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.17 |

### 1.18 Limit reached explicit handling (Pass 13)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-56 | Validation failures at a typed limit emit **`limit_reached`** lifecycle JSON with **`limit_name`**, **`limit_value`**, **`observed_value`**, **`documentation_ref`**, **`acceptance_criterion_ref`**, and **`recovery_class=user_action_required`** | ≥2 tests in `test_pdmap_limit_reached.py` assert canonical payload fields | `tools/pdmap/domain.py:emit_limit_reached_events`, `extract_domain_limit_observed_value`, [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.18 |

### 1.19 Legacy path observability (Pass 16 — ladder step 12)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-57 | Legacy APIs without **`run_id`** (`validate_all`, `deploy_all`, `deploy`) emit **one** **`lifecycle_path_selected`** JSON line with **`path=legacy_silent`**, **`operation`**, **`asset_name`** (when known), **`reason=run_id_not_bound`**, and spec refs — without changing return types or exit codes | ≥2 tests in `test_pdmap_legacy_path_observability.py`: `validate_all` emits marker; `run_validation` does not | `tools/pdmap/domain.py:emit_legacy_silent_path_selected`, `validate.py:validate_all`, `deploy.py:deploy_all` / `deploy`, [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.19 **Assumption A20** |

### 1.20 Production scenario (Pass 18 — ladder step 14)

| ID | SHALL | Verify | Detail |
|----|-------|--------|--------|
| R-MAP-58 | End-to-end production scenario test simulates operator workflow: typed **`run_map_pipeline`** success with lifecycle **`documentation_ref`**, injected validation failure with catalogued **`rule_codes`** + **`recovery_class`**, legacy **`validate_all`** on same level emits **`lifecycle_path_selected`** only (mixed typed+legacy), unified gate subprocess exit **0** | ≥1 test in `test_pdmap_production_scenario.py`: `test_production_operator_workflow_mixed_states` | `tools/pdmap/pipeline.py:run_map_pipeline`, `validate.py:run_validation` / `validate_all`, [`MAP_CREATION.md`](docs/spec/MAP_CREATION.md) §4.20 |

**Note:** Loop spec referenced R-MAP-47 for this slice; that id is reserved for **`PdmapDomainLimit`** (§1.14). Lifecycle traceability uses **R-MAP-55**. Limit emission at validation boundaries uses **R-MAP-48** (Pass 12) and canonical field names **R-MAP-56** (Pass 13). Legacy path markers use **R-MAP-57** (Pass 16). Production scenario uses **R-MAP-58** (Pass 18).

---

## 2. Non-functional requirements (map creation)

**Production readiness (Pass 11):** The map-learn typed-lifecycle ladder (Passes 1–10) is audited in [`journal/map_learn/PRODUCTION_READINESS.md`](journal/map_learn/PRODUCTION_READINESS.md). Local bar: `./scripts/run-pdmap-domain-tests.sh` (46 unit tests + curriculum **31/31**), wired in [`.github/workflows/pdmap-domain.yml`](.github/workflows/pdmap-domain.yml) for `port-net-mods/*`. That document is the honest readiness verdict — **not 100% success until GitHub Actions is green on a user-committed push**; treat the slice as ready for review until then. Pass receipts: [`journal/map_learn/passes/`](journal/map_learn/passes/).

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
