# Spec: CLI flags and engine limits (map creation appendix)

**Spec IDs:** `R-MAP-24`, `R-MAP-25`, `R-MAP-26`, `R-MAP-32` … `R-MAP-34` in [`SPEC.md`](../../SPEC.md)  
**Primary normative spec:** [`MAP_CREATION.md`](MAP_CREATION.md)

This file is an **appendix** for map authors booting custom arenas. Kit Hub IPC, Map Launcher UI, War Colors probe flags, and Matrix Battle argv are **out of scope** — see [`WAR_COLORS.md`](WAR_COLORS.md) and [`MAP_LAUNCHER.md`](MAP_LAUNCHER.md) on their PR branches.

---

## 1. Boot MP CLI (`port/src/bootmp.c`)

Parsed when any boot-mp flag is present (`bootmpHasCliOverrides()`).

| Flag | Type | Default | Map author effect |
|------|------|---------|-------------------|
| `--test-map` | bool | off | Boot **`STAGE_TEST_UFF`** (`0x4d`); quick-team `chrslots=0x01` |
| `--boot-stage` | int hex | -1 | Sets `g_Vars.stagenum` (e.g. `0x80` = My Arena) |
| `--skip-intro` | bool | off | Skip title intro |
| `--solo` | bool | off | `g_Vars.mpquickteamnumsims = 0`; human only |
| `--num-sims` | int | **8** | `g_Vars.mpquickteamnumsims` |
| `--sim-difficulty` | int | `BOTDIFF_NORMAL` | Bot difficulty |
| `--teams-battle` | bool | off | Team split in setup (uff zoning: team0 z<0, team1 z>0) |
| `--scenario-0` … `--scenario-5` | bool | off | Sets `g_MpSetup.scenario` 0–5 |
| `--time-limit` | int | existing | Minutes; 0 = unlimited |
| `--score-limit` | int | existing | Kill limit |
| `--team-score-limit` | int | existing | Team score limit |

**Typical map smoke test:**

```bash
./build/pd.arm64 --test-map --scenario-0 --basedir data \
  --moddir mods/mod_allinone --savedir . --num-sims 0
```

**Verify `--test-map` stage:**

```bash
rg 'STAGE_TEST_UFF|0x4d' src/game/title.c src/include/constants.h
# EXPECT: STAGE_TEST_UFF 0x4d; title.c assigns teststagenum
```

---

## 2. Engine numeric limits (map-relevant)

From `src/include/constants.h`:

| Symbol | PC value | Map author impact |
|--------|----------|-------------------|
| `MAX_BOTS` | **60** | Upper bound with features unlocked |
| `MAX_CHRSPERTEAM` | **32** | Team MP chr budget |
| `MAX_PLAYERS` | 4 | Split-screen cap |
| `MAX_SPAWN_POINTS` | 256 | Pad index ceiling |

**Stock curriculum fact:** without `MPFEATURE_8BOTS`, only **4 bots** spawn even when `--num-sims 8` (step 23).

---

## 3. Stage IDs (custom maps in this repo)

| Name | Hex | Decimal | Boot example |
|------|-----|---------|--------------|
| `STAGE_TEST_UFF` | **`0x4d`** | 77 | `--test-map` or `--boot-stage 0x4d` |
| `STAGE_MY_ARENA` | **`0x80`** | 128 | `--boot-stage 0x80` |

Engine wiring: `stagetable.c`, `mplayer/setup.c` (menu textid **0x7FFD** for My Arena).

**Out of scope here:** `STAGE_EXTRA26` (`0x5b` War Colors) — [`WAR_COLORS.md`](WAR_COLORS.md).

---

## 4. pdmap coordinate contract

| Rule | Value | Source |
|------|-------|--------|
| Up axis | **+Y** | [`MAP_CREATION.md`](MAP_CREATION.md) §3 |
| Floor tiles | **Y = 0** | `floor_box_tiles` |
| Spawn/weapon pads | **Y = 10.0** | `PAD_FLOOR_OFFSET` in `builders.py` |
| Setup ailist | **id 0x1000** | `mp_init_simulants` in `core.py` |
| Quick-team chrslots | **0x01** with `--test-map` | `title.c` |

---

## 5. modconfig stage validation (`port/src/mod.c`)

Custom stages **`0x02`–`0xff`** MUST load from modconfig without `malformed stage block`.

```bash
# After registering STAGE_MY_ARENA and rebuilding:
./build/pd.arm64 --boot-stage 0x80 --skip-intro --moddir mods/mod_allinone \
  --basedir data --savedir . --num-sims 0
# EXPECT: stage loads (no modconfig error in stderr)
```

---

## 6. Out of scope (other docs)

| Topic | Doc |
|-------|-----|
| War Colors probe flags (`--probe-war-colors-*`) | [`WAR_COLORS.md`](WAR_COLORS.md) |
| Matrix Battle 64 argv | PR branch / `scripts/play-matrix-battle.sh` |
| Map Launcher whitelist IDs | [`MAP_LAUNCHER.md`](MAP_LAUNCHER.md) |

---

*Normative map pipeline: [`MAP_CREATION.md`](MAP_CREATION.md). Requirement index: [`SPEC.md`](../../SPEC.md).*
