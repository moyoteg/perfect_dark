# Map learn — master plan

_Comprehensive checklist of every map-making topic to master. One dedicated learn map per distinct objective where player-testable. Status reflects manual in-game validation unless noted “auto” (pipeline validate only)._

**Branch:** `port-mods/all-in-one`  
**Last audit:** 2026-07-01  
**Curriculum generator:** `python3 tools/pdmap.py learn curriculum generate`  
**Play step N:** `./scripts/play-learn-step.sh N`

## Summary

| Metric | Count |
|--------|------:|
| **Total plan items** | 42 |
| **Done (manual validated)** | 33 |
| **Done (auto / probe only)** | 5 |
| **Pending (map exists, needs manual play)** | 0 |
| **Pending (map to create / extend)** | 4 |

Manual curriculum validation **complete** (2026-07-01): play-learn-step **0–31** (includes **my_arena**, **testarena**, **learn_01–31**). `.validation_step` = **31**.

---

## 1. Pads (spawn, weapon, ammo, hill, case, waypoints, deploy, rooms)

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 1.1 | `learn_01_spawn` | 0 Combat | Single spawn Y=10; stand on floor; no fall-through | **done** |
| 1.2 | `learn_02_four_spawns` | 0 | Four corner spawns; quick-team fills corners | **done** |
| 1.3 | `learn_03_weapon` | 0 | CMP150 floor pickup at center works | **done** |
| 1.4 | `learn_04_ammo` | 0 | Ammo crate at +X; pickup refills rifle ammo | **done** |
| 1.5 | `learn_06_waypoints` | 0 | 1–4 simulants pathfind; no waypoint crash | **done** |
| 1.6 | `learn_07_hill` | 4 KOTH | Green hill square + dark ring at +Z; score only in hill room | **done** |
| 1.7 | `learn_08_ctf_case` | 5 CTF | Case + CaseRespawn pair; steal + touch home to score | **done** |
| 1.8 | `learn_11_y_autocorrect` | 0 | Spawn safe despite JSON Y=0 (pipeline autocorrect) | **done** |
| 1.9 | `learn_20_overlap_pads` | 0 | Spawn + weapon + ammo at same XZ; all three work (cross-type overlap) | **done** |
| 1.10 | `learn_27_multi_weapon` | 0 | AR34 + shotgun + CMP150 at distinct pads; each pickup correct weaponnum | **done** |
| 1.11 | — (probe) | — | Pad indices contiguous 0..N-1; validate rejects gaps | **auto** |
| 1.12 | — (probe) | — | Room 0 empty in tiles JSON (engine void room) | **auto** |

---

## 2. Tiles / collision / seg modes (empty, hill, ctf, composite)

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 2.1 | `learn_14_procedural_seg` | 0 | `--seg-mode full`: visible box walls; collision from tiles | **done** |
| 2.2 | `learn_15_seg_empty` | 0 | `--seg-mode empty`: grey floor only; no viewport sheet | **done** |
| 2.3 | `learn_13_fixture_compact` | 4 | Hill seg mode; room-2 hill tiles + room-1 collision quad | **done** |
| 2.4 | `learn_10_full_arena` | 5 | Composite: CTF seg markers + hill zone in one map | **done** |
| 2.5 | `learn_28_hill_collision` | 4 | Walk hill boundary: no fall-through at room-1 collision mirror | **done** |
| 2.6 | `learn_29_custom_seg_script` | 0 | Custom SEG_SCRIPT seg builds; no relinkPtr crash | **done** |
| 2.7 | — (probe) | — | G_VTX max 16; box seg uses G_VTX(4) per face | **auto** |

---

## 3. Scenarios (0–5+), props, loadouts

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 3.1 | `learn_05_loadout` | 0 | Default loadout (Falcon2, CMP150, …) at combat start | **done** |
| 3.2 | `learn_19_hold_briefcase` | 1 Hold | Green 30s countdown while holding briefcase | **done** |
| 3.3 | `learn_21_hacker_central` | 2 Hacker | Download timer while hacking (stock scenario) | **done** |
| 3.4 | `learn_22_pop_a_cap` | 3 Pop a Cap | Solo: green 1:00 victim survival timer at top (+1 pt/min alive); spawns-only map loads | **done** |
| 3.5 | `learn_24_mpweapon_loadout` | 0 | `--loadout 1,9,16,4,0,37` gives Falcon2/CMP150/AR34/MagSec (MPWEAPON space) | **done** |
| 3.6 | `learn_08_ctf_case` | 5 | Instant capture at home CaseRespawn (no hold timer) | **done** |
| 3.7 | — (wiki) | — | Two weapon ID namespaces: weaponnum (props) vs MPWEAPON (CLI loadout) | **done** |

---

## 4. Deploy paths (uff test slot, boot-stage arenas, moddir)

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 4.1 | `learn_09_deploy_uff` | 0 | `--test-map` loads bg_uff.* from mod_allinone | **done** |
| 4.2 | `learn_17_from_json_cli` | 0 | from-json → build_from_spec without level-module edit | **done** |
| 4.3 | `my_arena` (registered) | 5 | Combat Sim menu “My Arena”; assets from mod | **done** |
| 4.4 | `testarena` (registered) | 5 | Combat Sim menu “Test Arena” | **done** |
| 4.5 | `learn_25_boot_stage` | 5 | `./build/pd.arm64 --boot-stage STAGE_MY_ARENA --skip-intro --moddir …` loads registered map | **done** |
| 4.6 | — (wiki §10) | — | Always `--moddir mods/mod_allinone`; log shows “loaded externally” | **auto** (probe) |
| 4.7 | `learn_30_mod_hygiene` | 0 | Rebuild+deploy; confirm external asset mtime changes | **done** |

---

## 5. Engine edge cases (Y autocorrect, high stage IDs, solo CTF, bot guards)

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 5.1 | `learn_11_y_autocorrect` | 0 | Y=0 pads corrected to 10 | **done** |
| 5.2 | `learn_16_my_arena_registered` | 5 | textid 0x7FFD; high custom stage id wired | **done** |
| 5.3 | `learn_12_testarena_fixture` | 5 | textid 0x7FFC; 4-team CTF fixture | **done** |
| 5.4 | `learn_23_bot_four_cap` | 0 | `--num-sims 8` → only 4 bots (stock cap) | **done** |
| 5.5 | `learn_26_solo_ctf` | 5 | `--num-sims 0`; human-only CTF capture still scores | **done** |
| 5.6 | `learn_18_register_scratch` | 0 | register --apply dry-run passes (live needs make) | **auto** |
| 5.7 | — (probe) | — | chrslots=0x01 under --test-map before bot alloc | **auto** |
| 5.8 | — (probe) | — | ailist 0x1000 required or bots fall to Y≈−99900 | **auto** |

---

## 6. Visual markers, radar, room highlights

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 6.1 | `learn_07_hill` | 4 | Green hill seg square + dark ring boundary | **done** |
| 6.2 | `learn_08_ctf_case` | 5 | Red CaseRespawn square + muted Case marker | **done** |
| 6.3 | `learn_10_full_arena` | 5 | CTF coloured squares at pads only (seg mode ctf) | **done** |
| 6.4 | — (engine) | — | KOTH pulse tints tile room 2; radar room highlights | **pending** (no dedicated map; observe in 6.1) |

---

## 7. Multi-room, doors, props placement

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 7.1 | `learn_07_hill` | 4 | Hill pad room=2; spawn room=1 (minimal multi-room) | **done** |
| 7.2 | `learn_28_hill_collision` | 4 | Room-1 floor quad mirrors hill cut-out (no void fall) | **done** |
| 7.3 | `learn_31_cover_points` | 0 | AI cover points emitted; bots use cover (visual N/A) | **done** |
| 7.4 | — (wiki) | — | Door props / multi-room custom seg (relinkPtr limits) | **pending** (not in pdmap JSON yet) |

---

## 8. Composite / fixture / registration (curriculum phase 2)

| # | Learn map | Scenario | Expected in-game test | Status |
|---|-----------|----------|----------------------|--------|
| 8.1 | `learn_10_full_arena` | 5 | my_arena-like composite | **done** |
| 8.2 | `learn_12_testarena_fixture` | 5 | Matches minimal_map.json fixture | **done** |
| 8.3 | `learn_13_fixture_compact` | 4 | Matches minimal_map 2.json compact fixture | **done** |
| 8.4 | `learn_16_my_arena_registered` | 5 | Matches registered my_arena module layout | **done** |

---

## 9. Learning engine / docs (non-map)

| # | Item | Status |
|---|------|--------|
| 9.1 | `pdmap learn run` probes → knowledge.json | **auto** (iteration 22) |
| 9.2 | MAP_DETERMINISTIC_SPEC.md emission | **auto** |
| 9.3 | gaps.md doc coverage 100% | **auto** |
| 9.4 | Curriculum 31/31 validate OK | **auto** (pipeline); **manual play 0–31 complete 2026-07-01** |
| 9.5 | Runtime smoke STAGE_TEST_UFF log hints | **pending** (CI hardening) |
| 9.6 | Live register --apply + make rebuild smoke | **pending** |

---

## Curriculum validation status

All **32 play steps (0–31)** manually confirmed in-game this session. No further curriculum play queue.

**Still open (outside curriculum maps):** §6.4 radar/KOTH pulse observation, §7.4 door props / custom multi-room seg in pdmap JSON, §9.5 runtime smoke CI, §9.6 live `register --apply` smoke.

---

## Commands

```bash
# Regenerate curriculum JSON + level modules
python3 tools/pdmap.py learn curriculum generate

# Validate all steps (0 errors)
python3 tools/pdmap.py learn curriculum validate

# Re-play any step (example: 31 cover points)
./scripts/play-learn-step.sh 31

# Learning engine iteration (writes runs/<timestamp>.json)
python3 tools/pdmap.py learn run
```
