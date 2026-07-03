# Spec: CLI flags and engine limits

**Spec IDs:** `R-PORT-02`, `R-PORT-03`, `R-MATRIX-01` in [`SPEC.md`](../../SPEC.md)

---

## 1. Boot MP CLI (`port/src/bootmp.c`)

Parsed when any boot-mp flag present (`bootmpHasCliOverrides()`).

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `--boot-stage` | int hex | -1 (invalid) | Sets `g_Vars.stagenum` before level load |
| `--skip-intro` | bool | off | Skip title intro |
| `--solo` | bool | off | `g_Vars.mpquickteamnumsims = 0`; human only |
| `--num-sims` | int | **8** | `g_Vars.mpquickteamnumsims` |
| `--sim-difficulty` | int | `BOTDIFF_NORMAL` | Clamped to bot difficulty range |
| `--teams-battle` | bool | off | Enables `MPOPTION_TEAMSENABLED`; team split in setup |
| `--scenario-0` … `--scenario-5` | bool | off | Sets `g_MpSetup.scenario` 0–5 |
| `--time-limit` | int | existing | Minutes; 0 = unlimited |
| `--score-limit` | int | existing | Kill limit |
| `--team-score-limit` | int | existing | Team score limit |
| `--laptop-sentry-infinite-ammo` | bool | off | Sentry laptop ammo |
| `--laptop-sentry-x4` | bool | off | 4× sentry laptop |
| `--unlimited-sentries` | bool | off | Unlimited sentry deploys |
| `--test-map` | bool | off | Boot `STAGE_TEST_UFF` uff slot; `chrslots=0x01` quick-team path |

**War Colors probe flags** (`port/src/warcolors_probe.c`):

| Flag | Effect |
|------|--------|
| `--probe-war-colors-pads` | Probe default pad set on `STAGE_EXTRA26` |
| `--probe-war-colors-all` | Probe all pads in mp13 file |
| `--write-corrected-pads <path>` | Write RareZip output |

---

## 2. Engine numeric limits (`src/include/constants.h`)

| Symbol | N64 | PC (`!PLATFORM_N64`) | Spec impact |
|--------|-----|----------------------|-------------|
| `MAX_BOTS` | 24 | **60** | Matrix 64 approaches with `MPFEATURE_8BOTS` |
| `MAX_CHRSPERTEAM` | 32 | **32** | War Colors max 31 sims + 1 human |
| `MAX_PLAYERS` | 4 | 4 | Split-screen cap |
| `MAX_MPCHRS` | — | `MAX_PLAYERS + MAX_BOTS` | |
| `MAX_SPAWN_POINTS` | 256 | 256 | |

---

## 3. Stage IDs (custom maps in this repo)

| Name | Hex | Decimal | Boot example |
|------|-----|---------|--------------|
| `STAGE_TEST_UFF` | `0x4d` | 77 | `--test-map` or `--boot-stage 0x4d` |
| `STAGE_MP_VILLA` | `0x35` | 53 | Retail Villa (shares mp13 files) |
| `STAGE_EXTRA26` | **`0x5b`** | 91 | War Colors — `--boot-stage 0x5b` |
| `STAGE_MY_ARENA` | **`0x80`** | 128 | `--boot-stage 0x80` |
| `STAGE_AGENT_OFFICE` | `0x83` | 131 | Virtual Agent Office |

**Menu vs combat stages:** `STAGE_IS_MENU()` pattern in engine — custom arenas use `STAGE_IS_PDMAP_BOX_ARENA` / `STAGE_IS_MENU` guards in `bg.c`, `wallhit.c`, `pdmain.c`.

---

## 4. Matrix Battle 64 launch argv

From `scripts/play-matrix-battle.sh` (default `NUM_SIMS=50`):

```bash
build/pd.arm64 \
  --test-map \
  --scenario-0 \
  --basedir data \
  --moddir mods/mod_allinone \
  --savedir . \
  --num-sims 50 \
  --teams-battle \
  --sim-difficulty 5
```

**Pre-deploy:**

```bash
python3 tools/pdmap.py build matrix_battle_64 --seg --deploy
```

**Team spawn zoning** (`player.c`): on `STAGE_TEST_UFF` + `--teams-battle`: team 0 `z < 0`, team 1 `z > 0`.

---

## 5. pdmap coordinate contract

| Rule | Value | Source |
|------|-------|--------|
| Up axis | **+Y** | `MAP_MAKING_WIKI.md` |
| Floor tiles | **Y = 0** | `floor_box_tiles` |
| Spawn/weapon pads | **Y = 10** | `PAD_FLOOR_OFFSET`; `Y=0` pads fall through |
| Setup ailist | **id 0x1000** | `mp_init_simulants` |
| Quick-team chrslots | **0x01** only before team select | `title.c` + `--test-map` |

---

## 6. modconfig stage validation (`port/src/mod.c`)

```c
if (stagenum <= 0x01 || stagenum > 0xff) {
    sysLogPrintf(LOG_ERROR, "modconfig: malformed stage block at offset %d", prev - data);
}
```

**War Colors `0x5b` MUST pass.** Historical bug: cap at `0x50` blocked modconfig.
