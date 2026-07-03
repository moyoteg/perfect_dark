# Spec: Map Learn Curriculum (31 steps)

**Spec IDs:** `R-LEARN-01` … `R-LEARN-04` in [`SPEC.md`](../../SPEC.md)  
**Source:** `tools/pdmap/learn/curriculum.py` → `_curriculum_registry()`

---

## 1. Global constants

| Constant | Value |
|----------|-------|
| Step count | **31** |
| JSON fixture dir | `journal/map_learn/maps/learn_XX_<slug>.json` |
| Level module pattern | `src/levels/learn_XX_<slug>.py` |
| Deploy slot (most steps) | `uff` / `STAGE_TEST_UFF` (`0x4d`) via `play-learn-step.sh` |
| Default spawn Y | **10.0** (`PAD_FLOOR_OFFSET` in `builders.py`) |
| Small box | `box_half=1500`, `box_height` per `_BOX_SMALL` |
| Large box | `box_half=2500` (step 6+) |

**Validate command:**

```bash
python3 -c "from tools.pdmap.learn.curriculum import validate_curriculum; r=validate_curriculum(verbose=True); assert len([x for x in r if not x.ok])==0"
# EXPECT: 31/31 steps OK
```

**Launch command (step N):**

```bash
./scripts/play-learn-step.sh N
# Example: ./scripts/play-learn-step.sh 7  → learn_07_hill, --scenario-4
```

---

## 2. Full step table

| Step | Slug | Module | Scenario | Seg mode | Launch flags (typical) |
|------|------|--------|----------|----------|------------------------|
| 1 | `spawn` | `learn_01_spawn` | 0 Combat | empty | `--scenario-0` |
| 2 | `four_spawns` | `learn_02_four_spawns` | 0 | empty | `--scenario-0` |
| 3 | `weapon` | `learn_03_weapon` | 0 | empty | `--scenario-0`; weaponnum `0x0A` CMP150 at pad 1 |
| 4 | `ammo` | `learn_04_ammo` | 0 | empty | `--scenario-0`; `AMMOTYPE_RIFLE` pad 1 |
| 5 | `loadout` | `learn_05_loadout` | 0 | empty | ailist **0x1000** required in setup |
| 6 | `waypoints` | `learn_06_waypoints` | 0 | empty | `--scenario-0 --num-sims 1` min |
| 7 | `hill` | `learn_07_hill` | **4** KOTH | empty | `--scenario-4`; hill pad room=2 at +Z |
| 8 | `ctf_case` | `learn_08_ctf_case` | **5** CTF | empty | `--scenario-5`; Case −Z, CaseRespawn +Z team 0 |
| 9 | `deploy_uff` | `learn_09_deploy_uff` | 0 | empty | confirms uff test slot deploy |
| 10 | `full_arena` | `learn_10_full_arena` | **5** | ctf | 4 spawns, 2 weapons, CTF 4-team, hill room 2 |
| 11 | `y_autocorrect` | `learn_11_y_autocorrect` | 0 | empty | JSON pad Y=0 → corrected to 10 |
| 12 | `testarena_fixture` | `learn_12_testarena_fixture` | **5** | ctf | mirrors `minimal_map.json`; box 5000×3000 |
| 13 | `fixture_compact` | `learn_13_fixture_compact` | **4** | hill | `minimal_map 2.json` pattern |
| 14 | `procedural_seg` | `learn_14_procedural_seg` | 0 | **full** | visible walls; may near-plane clip |
| 15 | `seg_empty` | `learn_15_seg_empty` | 0 | **empty** | no visible seg; tiles only |
| 16 | `my_arena_registered` | `learn_16_my_arena_registered` | **5** | ctf | `STAGE_MY_ARENA` layout; textid **0x7FFD** |
| 17 | `from_json_cli` | `learn_17_from_json_cli` | 0 | empty | `pdmap from-json` path |
| 18 | `register_scratch` | `learn_18_register_scratch` | 0 | empty | `pdmap register` dry-run |
| 19 | `hold_briefcase` | `learn_19_hold_briefcase` | **1** Hold | empty | 30s hold countdown |
| 20 | `overlap_pads` | `learn_20_overlap_pads` | 0 | **marker** | spawn+weapon+ammo same XZ; green centre square |
| 21 | `hacker_central` | `learn_21_hacker_central` | **2** Hacker | empty | HTM bank pads; MODEL_GOODPC terminal |
| 22 | `pop_a_cap` | `learn_22_pop_a_cap` | **3** Pop-a-Cap | empty | solo: victim timer 1:00 green |
| 23 | `bot_four_cap` | `learn_23_bot_four_cap` | 0 | empty | `--num-sims 8` → **only 4 bots** spawn (stock cap) |
| 24 | `mpweapon_loadout` | `learn_24_mpweapon_loadout` | 0 | empty | `--loadout 1,9,16,4,0,37` (MPWEAPON ids) |
| 25 | `boot_stage` | `learn_25_boot_stage` | **5** | ctf | `--boot-stage 0x80` NOT `--test-map` |
| 26 | `solo_ctf` | `learn_26_solo_ctf` | **5** | ctf | `--num-sims 0` human-only CTF |
| 27 | `multi_weapon` | `learn_27_multi_weapon` | 0 | empty | weaponnums `0x11, 0x0A, 0x13` at −X, 0, +X |
| 28 | `hill_collision` | `learn_28_hill_collision` | **4** | hill | hill room 1 collision mirror; no fall-through |
| 29 | `custom_seg_script` | `learn_29_custom_seg_script` | 0 | full | `scripts/learn_29_seg_build.py`; G_VTX ≤16 |
| 30 | `mod_hygiene` | `learn_30_mod_hygiene` | 0 | empty | log: `loaded externally` for `bg_uff.*` |
| 31 | `cover_points` | `learn_31_cover_points` | 0 | marker | `add_cover` at X=±800; `--num-sims 2` |

---

## 3. Scenario index

| `--scenario-N` | Mode | Steps using it |
|----------------|------|----------------|
| 0 | Combat | 1–6, 9, 11, 14–15, 17–18, 20, 23–24, 27, 29–31 |
| 1 | Hold Briefcase | 19 |
| 2 | Hacker Central | 21 |
| 3 | Pop a Cap | 22 |
| 4 | King of the Hill | 7, 13, 28 |
| 5 | Capture the Case | 8, 10, 12, 16, 25, 26 |

---

## 4. Map Launcher phase mapping

Identical to `CURRICULUM_PHASES` in `tools/map-launcher-electron/main.js` — see [`MAP_LAUNCHER.md`](MAP_LAUNCHER.md) §6.

---

## 5. Per-step acceptance (automated minimum)

For each step `N` in 1..31:

1. `python3 tools/pdmap.py build learn_XX_<slug> --dry-run` → exit 0
2. `./scripts/play-learn-step.sh N --no-play` → deploy OK
3. `./scripts/play-learn-step.sh N` → `pd.arm64` alive 15s (unless step documents manual-only, e.g. 18 live register)

**Step 23 specific:** stderr MUST show ≤4 bots despite `--num-sims 8` without `MPFEATURE_8BOTS`.

**Step 25 specific:** argv MUST include `--boot-stage 0x80` (`STAGE_MY_ARENA`), NOT `--test-map`.
