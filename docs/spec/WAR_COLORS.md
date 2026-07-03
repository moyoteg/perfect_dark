# Spec: War Colors (STAGE_EXTRA26 / mp13)

**Spec IDs:** `R-WC-01` … `R-WC-07` in [`SPEC.md`](../../SPEC.md)

---

## 1. Identifiers (exact)

| Field | Value |
|-------|-------|
| Stage constant | `STAGE_EXTRA26` = `0x5b` (`src/include/constants.h:4111`) |
| Retail alias | `STAGE_MP_VILLA` = `0x35` (same mp13 file IDs) |
| Mod slot | `MOD_KAKARIKO` = `2` |
| ROM file IDs | `FILE_BG_MP13_SEG` `0x0035`, `FILE_BG_MP13_PADS` `0x0213`, `FILE_BG_MP13_TILES` `0x0214`, `FILE_UMP_SETUPMP13` `0x0212` |
| Level module | `src/levels/war_colors_conker.py` |
| Deploy target | `mods/mod_kakariko/files/` (never `mod_allinone` for mp13 geometry) |
| Play script | `scripts/play-conker-war-sentry.sh` |
| Log file | `journal/map_learn/.conker_war_sentry_inf_test.log` |

---

## 2. Deployed file paths (must exist after play script preflight)

| File | Expected size (approx) | Format |
|------|------------------------|--------|
| `mods/mod_kakariko/files/Ump_setupmp13Z` | ~375 B | RareZip setup blob |
| `mods/mod_kakariko/files/bgdata/bg_mp13_padsZ` | **6096 B** | RareZip N64 pad envelope (NOT host-preprocessed) |
| `mods/mod_kakariko/files/bgdata/bg_mp13.seg` | Conker BFD | From kakariko mod |
| `mods/mod_kakariko/files/bgdata/bg_mp13_tilesZ` | Conker BFD | From kakariko mod |

**Deploy commands (exact):**

```bash
python3 tools/pdmap.py build war_colors_conker --deploy --mod mod_kakariko
python3 tools/war_colors_correct_pads.py --pd build/pd.arm64 --all
```

**Setup spawn pad verify** (embedded in `play-conker-war-sentry.sh`):

```python
expected = [35, 116, 113, 0, 218, 108, 88, 80, 16, 82, 20, 89]
# stdout MUST contain: "setup verify: 12 Conker in-base spawn pads OK"
```

---

## 3. Spawn pad indices (source of truth: `war_colors_conker.py`)

### 3.1 Deathmatch spawns (12 pads)

**SHC fortress (+Z interior, `z > 1500` in module comment):**

`35, 116, 113, 0, 218, 108`

**Tediz tunnels (−Z interior, `z < -2000` in module comment):**

`88, 80, 16, 82, 20, 89`

### 3.2 Floor weapons (10 pads + ammo pad lists)

| Faction | Weapon pad | Ammo pads | MP location slot |
|---------|------------|-----------|------------------|
| SHC | 190 | 201, 202 | `_MPLOCATION00` (240) |
| SHC | 198 | 129, 130 | `_MPLOCATION01` (241) |
| SHC | 192 | 205, 206 | `_MPLOCATION02` (242) |
| SHC | 100 | 101, 105 | `_MPLOCATION03` (243) |
| SHC | 35 | 106, 107 | `_MPLOCATION04` (244) |
| Tediz | 16 | 17, 84 | `_MPLOCATION05` (245) |
| Tediz | 80 | 89, 95 | `_MPLOCATION06` (246) |
| Tediz | 88 | 215 | `_MPLOCATION07` (247) |
| Tediz | 20 | 83, 90 | `_MPLOCATION08` (248) |
| Tediz | 82 | 176, 174 | `_MPLOCATION09` (249) |

### 3.3 Retail CTF/KOTH pads (unchanged from Villa setup in module)

- CTF cases: pads `6, 13, 19, 27` (teams 0–3)
- CaseRespawn groups per team as in `_add_retail_scenarios()`
- KOTH hills: pads `76, 142, 170, 67`

### 3.4 Excluded retail DM pads (void on Conker — do NOT use)

Retail indices `0x001C`–`0x0027` (decimal 28–39) and weapons `0x00BD`–`0x00C6` — **seven spawns + six weapons** at Villa-only XY.

---

## 4. Engine spawn rules (`src/game/player.c`)

```c
#define WAR_COLORS_SHC_Z_MIN     1200.0f   // team 0 allowed spawn Z minimum
#define WAR_COLORS_TEDIZ_Z_MAX  -1200.0f   // team 1 allowed spawn Z maximum
```

| Rule | Implementation |
|------|----------------|
| Void filter | `playerWarColorsSpawnPadIsUsable()` — `cdFindGround` from `pos.y + 2000`; reject `groundy <= -100000` |
| Team filter | `playerWarColorsTeamsPadAllowed(spawnteam, padz)` — SHC requires `z >= 1200`, Tediz requires `z <= -1200` |
| Log line | `war_colors_spawn: team=%d side=%s pos=(%.0f,%.0f,%.0f) bot=%d` — `side` is `SHC` or `Tediz` |

**Acceptance grep:**

```bash
rg 'war_colors_spawn: team=0 side=SHC' journal/map_learn/.conker_war_sentry_inf_test.log
# MUST match; pos z MUST be > 1200 for SHC human/bot 0
```

---

## 5. Launch argv (exact template)

**Default (8 sims, teams, sentry):**

```bash
build/pd.arm64 \
  --boot-stage 0x5b \
  --skip-intro \
  --scenario-0 \
  --basedir data \
  --moddir mods/mod_allinone \
  --kakarikomoddir mods/mod_kakariko \
  --savedir . \
  --num-sims 8 \
  --sim-difficulty 5 \
  --teams-battle \
  --laptop-sentry-infinite-ammo \
  --unlimited-sentries
```

| Flag | Required | Notes |
|------|----------|-------|
| `--kakarikomoddir` | **YES** | MUST resolve to `mods/mod_kakariko`; script hard-fails otherwise |
| `--moddir` | YES | `mods/mod_allinone` for shared textures/menu |
| `--boot-stage 0x5b` | YES | Not `--test-map` |
| `--solo` | optional | Sets `NUM_SIMS=0`; omit `--num-sims` when solo |
| `--full-battle` | optional | Sets `NUM_SIMS=31` (NOT 50) |

---

## 6. Simulant limits (SIGBUS contract)

| Constant | Value | Source |
|----------|-------|--------|
| `MAX_CHRSPERTEAM` | **32** | `constants.h:23` |
| `MAX_PLAYERS` | 4 | Human slots |
| War Colors max team sims | **31** | 31 bots + 1 human = 32 |

| `--num-sims` | Expected result |
|--------------|-----------------|
| 0 (`--solo`) | Alive ≥15s |
| 8 (default) | Alive ≥15s |
| 31 (`--full-battle`) | Alive ≥15s |
| 32 | **SIGBUS** exit **138** within ~3s |
| 50 | **SIGBUS** exit **138** within ~3s |

**Script cap** (`play-conker-war-sentry.sh`):

```bash
WAR_COLORS_MAX_TEAM_SIMS=31
# If TEAMS_BATTLE && NUM_SIMS > 31 → clamp + stderr WARN
```

---

## 7. mod.c stage cap

```c
// port/src/mod.c — stagenum MUST accept 0x5b
if (stagenum <= 0x01 || stagenum > 0xff) { /* reject */ }
```

**Failure mode if cap is 0x50:** `modconfig: malformed stage block` — War Colors modconfig never applies.

---

## 8. Pad probe CLI (`port/src/warcolors_probe.c`)

| Flag | Purpose |
|------|---------|
| `--probe-war-colors-pads` | Probe default spawn/weapon pad set |
| `--probe-war-colors-all` | Probe all 219 usable pads |
| `--write-corrected-pads <path>` | Write RareZip from **ROM** envelope patches |

**Probe log regex** (`tools/war_colors_correct_pads.py`):

```
PROBE_PAD index=(\d+) x=([-\d.]+) y=([-\d.]+) z=([-\d.]+) ground=([-\d.]+) room=(-?\d+) usable=(\d+) patched=(\d+)
```

**Double-preprocess failure:** writing host-preprocessed runtime blob → `convertWayPoints` SIGBUS in `port/src/preprocess/filepads.c:141` on reload.

---

## 9. Verification checklist (copy-paste)

```bash
# 1. Deploy only
./scripts/play-conker-war-sentry.sh --no-play
# EXPECT stdout contains:
#   setup verify: 12 Conker in-base spawn pads OK ([35, 116, 113, 0, 218, 108, 88, 80, 16, 82, 20, 89])
#   pads verify: mod_kakariko bg_mp13_padsZ present

# 2. Solo smoke
./scripts/play-conker-war-sentry.sh --solo
# EXPECT: pid detected; log has war_colors_spawn SHC with z>1200

# 3. Default battle
./scripts/play-conker-war-sentry.sh
# EXPECT: 8 sims; process alive 15s: pgrep -x pd.arm64

# 4. Must NOT crash
./build/pd.arm64 ... --num-sims 32 ...  # manual — expect exit 138
```
