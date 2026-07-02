---
name: perfect-dark-map-creation
description: >-
  Author, build, deploy, and validate Perfect Dark multiplayer maps via pdmap
  (MapDef, JSON, tiles, pads, seg modes, scenarios). Use when creating or editing
  learn curriculum maps, my_arena, testarena, uff test slot, box arenas, CTF/KOTH
  pads, or when the user mentions pdmap, map JSON, deploy-as uff, or play-learn-step.
---

# Perfect Dark Map Creation

**Build / compile / generic launch:** see [perfect-dark-workflow](../perfect-dark-workflow/SKILL.md).  
**Deep reference:** [`docs/MAP_MAKING_WIKI.md`](../../docs/MAP_MAKING_WIKI.md), [`docs/MAP_CREATION.md`](../../docs/MAP_CREATION.md).  
**31-step curriculum:** [`journal/map_learn/CURRICULUM.md`](../../journal/map_learn/CURRICULUM.md).

---

## When to use this skill

| Task | Path |
|------|------|
| New box arena from JSON | `from-json` → `--deploy-as uff` |
| Edit level module | `src/levels/<name>.py` → `pdmap build` |
| Learn / regression map | `journal/map_learn/maps/learn_XX_*.json` |
| Registered arenas | `my_arena`, `testarena` (boot-stage, not `--test-map`) |
| Map Editor workflow | `journal/uff_viewer/` → export JSON → test_map.py or from-json |

Always pass `--moddir mods/mod_allinone`. Rebuild + deploy after every edit.

---

## Coordinate system

| Axis | Direction |
|------|-----------|
| **X+** | East (right) |
| **Y+** | Up |
| **Z+** | South |

- **Units:** ~1 unit ≈ 1 cm. `box_half: 5000` → ~100 m floor.
- **Floor tiles:** `Y=0` in tiles JSON (collision plane).
- **Pads (spawn, weapon, ammo, scenario):** **`Y=10`** (`SPAWN_Y`). Ground search requires `floor_y < pad_y`; `Y=0` pads fall through. Avoid `Y≥20` (fall damage on spawn).
- **Pad up vector:** floor props and terminals need **`up=[0,1,0]`** (+Y). Wrong up → props lie flat (HTM terminal in scenario 2).
- **Tiles vs pads:** tiles JSON coords are ×6 at compile; **pad JSON uses raw game coords** (not ×6).

### Room numbers

| Room | Role |
|------|------|
| **0** | Void — **must be empty** in tiles (no collision) |
| **1** | Standard playable room (spawns, main floor) |
| **2** | Hill capture room (KOTH hill pad `room=2`; tiles in room 2 for scoring) |

KOTH in box maps: hill pad in room 2 + **room-1 collision mirror** of hill quad (or players fall through green seg marker). Use `floor_box_with_hill_zone()` or curriculum steps 7/13/28.

---

## MapDef / JSON / Python workflow

### Five deployed assets per stage

| File | Role |
|------|------|
| `bg_<name>.seg` | Visible geometry (optional for gameplay) |
| `bg_<name>_tilesZ` | **Collision** (authoritative for floor/walls) |
| `bg_<name>_padsZ` | Pad anchors + symmetric waypoint graph |
| `Ump_setup<name>Z` | MP setup: intro, props, ailists |

**Collision comes from tiles, not seg.** Seg is visual; walkable perimeter needs tile quads.

### Authoring paths

**1. JSON (canonical for learn maps / editor export)**

```bash
python3 tools/pdmap.py from-json map.json --deploy-as uff --deploy --play --scenario-0
```

Pipeline: `EditorMapSpec.from_json` → `build_from_spec` → pads/tiles/setup/seg → mod deploy.

**2. Level module (`src/levels/<name>.py`)**

```python
from tools.pdmap.core import MapDef
from tools.pdmap.builders import (
    add_spawn_grid, add_loadout_intro, add_mp_scenarios,
    add_floor_weapons, add_ammo_row, floor_box_tiles,
)
from tools.pdmap import weapons as W

BOX_HALF = 5000.0
BOX_HEIGHT = 3000.0
SPAWN_Y = 10.0

def build() -> MapDef:
    g = MapDef("mymap")
    add_spawn_grid(g, [(-2000, -2000), (2000, 2000)], y=SPAWN_Y)
    add_loadout_intro(g)  # ailist 0x1000 — required for bots
    return g

def build_tiles_json():
    return floor_box_tiles("mymap", half=BOX_HALF, y=0.0, room_index=1)
```

```bash
PDMAP_SEG_MODE=empty python3 tools/pdmap.py build mymap --seg --deploy
python3 tools/pdmap.py validate mymap
```

**3. Scaffold new map**

```bash
python3 tools/pdmap.py init mymap
```

### Pad index rule (silent footgun)

`add_pad(index=k)` / JSON `"index"` **must equal array position** `0..N-1` contiguous. `mkpads` numbers by position; intro/props reference position. Gaps break weapons/spawns with no build error. `pdmap validate` catches this.

### Builder helpers (`tools/pdmap/builders.py`)

| Function | Purpose |
|----------|---------|
| `add_spawn_grid(g, positions, y=SPAWN_Y)` | Spawn pads + `Intro(Spawn)` |
| `add_loadout_intro(g)` | Starting weapons + **ailist 0x1000** (bots) |
| `add_mp_scenarios(g, cases=[…], hill_pads=[…])` | CTF Case/CaseRespawn + Hill intro |
| `add_floor_weapons(g, [(pad, W.WEAPON_*), …])` | Floor weapon props |
| `add_ammo_row(g, [pad, …], ammotype=…)` | Ammo crate props |
| `floor_box_tiles` / `floor_box_with_hill_zone` | Collision JSON |
| `g.add_cover(x, z, y=SPAWN_Y)` | AI cover points (step 31) |

---

## Pads

| Type | JSON `"type"` | Intro / props |
|------|---------------|---------------|
| Spawn | `spawn` | `Intro(Spawn(pad=…))` |
| Floor weapon | `weapon` | `Weapon` prop on pad (`weaponnum` id) |
| Ammo crate | `ammo` | `AmmoCrate` prop (`ammoType`, `quantity`) |
| Scenario | `scenario` | `hill`, `case`, `case_respawn` → Hill/Case/CaseRespawn intro |

### Overlap rules

| OK | Not OK |
|----|--------|
| spawn + weapon + ammo same XZ (step 20) | two **spawn** same spot |
| center AR34 + shotgun ammo at `(0,10,0)` | two **weapon** same spot |

Cross-type overlap is stock uff pattern; same-type overlap warns in editor.

### Waypoints

`MapDef.pack_pads_json()` builds **symmetric** k-nearest graph (K=6). Asymmetric one-way edges crash `waypointFindRoute`. Do not hand-edit without mirroring edges.

### Two weapon ID namespaces (never mix)

| Context | Enum | AR34 example |
|---------|------|--------------|
| Floor props, intro `Weapon()` | **weaponnum** / `W.WEAPON_*` | `0x11` |
| `--loadout`, Combat Sim menu | **MPWEAPON_*** | `0x10` |

Default Test/Play loadout: `--loadout 1,9,16,4,0,37` (Falcon2, CMP150, AR34, MagSec4, None, Shield).

---

## Seg modes (`PDMAP_SEG_MODE` / `--seg-mode`)

Procedural box: `tools/pdmap/seg.py`. **Collision is always from tiles.**

| Mode | Draws | Use when |
|------|-------|----------|
| **`empty`** | No faces (setup GDL only) | **Default Test/Play** — no viewport sheet |
| **`full`** | Ceiling + 4 walls | Visible shell; may near-clip in FPS |
| **`hill`** | Arena floor + dark ring + green hill square (room 1 seg) | KOTH steps 7, 13, 28 |
| **`ctf`** | Coloured squares at Case/CaseRespawn pads | CTF steps 8, 10, 12, 16, 25, 26 |
| **`marker`** | Grey floor + green centre/overlap markers | Steps 20, 31 |
| **`box`** | Ceiling + 2 walls | Minimal shell |
| **`floor`** | Floor quad only | Debug — causes viewport artifact |

```bash
PDMAP_SEG_MODE=empty python3 tools/pdmap.py build uff --seg --deploy
python3 tools/pdmap.py from-json map.json --deploy-as uff --seg-mode hill --deploy
```

### G_VTX rule

Max **16 verts per `G_VTX`**. Use **`G_VTX(4)` per face**, never one `G_VTX(24)` — causes phantom collidable wall at origin. Deploy refuses bad segs.

### Custom seg

Set `SEG_SCRIPT` in level module → script writes `bg_<name>.seg` (step 29). Multi-room custom segs can crash `relinkPtr`; box segs stay single-room.

---

## Scenarios and launch flags

| ID | Name | Intro needed | Notes |
|----|------|--------------|-------|
| **0** | Combat | Spawns (+ loadout for bots) | Default |
| **1** | Hold the Briefcase | — | Green 30s timer while holding; **no** Case pads |
| **2** | Hacker Central | — | **Two multi-ammo crates** (`AmmoCrateMulti`) for HTM bank |
| **3** | Pop a Cap | Spawns only | Solo `--num-sims 0`: victim survival timer |
| **4** | King of the Hill | `Hill(pad=…)`, hill tiles | Launch `--scenario-4` |
| **5** | Capture the Case | **`Case` + `CaseRespawn` per team** | Instant score at home; launch `--scenario-5` |

### CLI flags (`title.c` / play scripts)

```bash
./build/pd.arm64 --test-map \
  --moddir mods/mod_allinone \
  --scenario-5 \
  --num-sims 4 \
  --sim-difficulty 2 \
  --loadout 1,9,16,4,0,37 \
  --mp-options 0
```

| Flag | Meaning |
|------|---------|
| `--test-map` | Always **`STAGE_TEST_UFF`** → loads **`bg_uff.*`** (uff test slot) |
| `--boot-stage STAGE_MY_ARENA` | Registered stage → **`bg_my_arena.*`** (not uff) |
| `--scenario-N` | Match mode 0–5 (CTF = **5**, KOTH = **4**) |
| `--num-sims N` | Bot count; stock cap **4** without `MPFEATURE_8BOTS` |
| `--loadout W0,…,W5` | **MPWEAPON** ids (not weaponnum) |
| `--skip-intro` | Skip intro cinematics (boot-stage launches) |

**`--test-map` vs `--boot-stage`:** test-map ignores which level module you edited unless you **`--deploy-as uff`**. Registered `my_arena` / `testarena` need build + deploy + `--boot-stage` (step 25).

---

## Deploy paths

### Uff test slot (fast iteration)

```bash
# Curriculum step N
./scripts/play-learn-step.sh 7          # KOTH hill
./scripts/play-learn-step.sh 10 --no-play   # deploy only

# Direct
python3 tools/pdmap.py from-json journal/map_learn/maps/learn_01_spawn.json \
  --deploy-as uff --deploy --play --scenario-0
```

`play-learn-step.sh` sets scenario, seg-mode, and extra flags per step (matches `tools/pdmap/learn/curriculum.py`).

### Registered arenas

```bash
python3 tools/pdmap.py build my_arena --seg --deploy
./build/pd.arm64 --boot-stage STAGE_MY_ARENA --skip-intro \
  --moddir mods/mod_allinone --scenario-5
```

Registration (four wiring points): `files.h`, `list.c`, `stagetable.c`, `setup.c` — see wiki §12. Until registered, use **`--deploy-as uff`**.

### Deploy-as naming

| Concept | Example |
|---------|---------|
| Level module name | `learn_07_hill` |
| Deploy asset name | `uff` (test slot) or `my_arena` (registered) |

Editor: **Deploy → uff (test-map slot)** overwrites `bg_uff.*` in mod.

### Mod hygiene (step 30)

After deploy, log must show:

```
file … (bgdata/bg_uff.seg) loaded externally
file … (bgdata/bg_uff_tilesZ) loaded externally
file … (Ump_setupuffZ) loaded externally
```

Missing → ROM embedded data; add `--moddir` and redeploy. Stale seg (editor Seg unchecked) causes silent regressions.

---

## Bots and setup (map author checklist)

Three requirements (detail in workflow skill §6):

1. **`add_loadout_intro(g)`** → ailist **id `0x1000`** (`mp_init_simulants`). Without it: bots at Y≈−99900.
2. **`--test-map`** sets `g_MpSetup.chrslots = 0x01` only — do not pre-set simulant bits in setup.
3. **Multiple spawns + symmetric waypoints** (pdmap default).

---

## Common pitfalls (curriculum-validated)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Fall through floor | Pad `Y=0` or missing tiles room 1 | `Y=10`; `floor_box_tiles` |
| Fall through hill edge | No room-1 hill collision mirror | `floor_box_with_hill_zone` (step 28) |
| CTF does not score | Wrong scenario or missing CaseRespawn | **`--scenario-5`**; both `case` + `case_respawn` per team |
| Hold timer instead of CTF capture | Used scenario 1 | CTF = scenario **5**, not 1 |
| HTM / Hacker broken | Single ammo crate | **Two multi-ammo crates** at bank pads (step 21) |
| Wrong map loads | `--test-map` always uff | `--deploy-as uff` or `--boot-stage` for registered |
| `--boot-stage` wrong mode | Scenario flag separate | Pass **`--scenario-5`** (or 4) with boot-stage |
| Phantom wall at origin | `G_VTX(24)` stale seg | Rebuild `--seg`; per-face `G_VTX(4)` |
| Dark sheet on screen | Seg floor behind near plane | `PDMAP_SEG_MODE=empty` |
| Wall collision missing | Relied on seg geometry | Add **tile quads** for perimeter |
| Props flat on ground | Pad up not +Y | **`up=[0,1,0]`** on floor pads |
| Wrong starting guns | Mixed weaponnum / MPWEAPON | Props = weaponnum; `--loadout` = MPWEAPON |
| Only 4 bots | Stock cap | Normal; step 23 |
| Changes ignored | No redeploy / wrong moddir | `--seg --deploy --moddir mods/mod_allinone` |

---

## Validation

### Pipeline validate (no game launch)

```bash
python3 tools/pdmap.py learn curriculum validate   # all 31 steps, 0 errors
python3 tools/pdmap.py validate uff
python3 tools/pdmap.py learn curriculum generate   # refresh JSON + level modules
```

Checks: contiguous pad indices, `Y>0`, spawn present, CTF/Hill intro, pad room < tile rooms, G_VTX ≤16, ailist 0x1000 via loadout intro.

### In-game validation

```bash
./scripts/play-learn-step.sh N              # deploy-as uff + launch
./scripts/validate-maps.sh status           # validation queue state
./scripts/validate-maps.sh step 0           # my_arena boot-stage
./scripts/validate-maps.sh next             # advance manual checklist
```

State file: `journal/map_learn/.validation_step`. Full manual checklist: [`journal/map_learn/LEARN_PLAN.md`](../../journal/map_learn/LEARN_PLAN.md).

### Pre-flight (before declaring done)

- [ ] `pdmap validate` — zero errors
- [ ] `build --seg --deploy` completed
- [ ] Box FPS: `PDMAP_SEG_MODE=empty` (or step-appropriate seg mode)
- [ ] Pads `Y=10`, contiguous indices
- [ ] CTF: Case + CaseRespawn per team; launch **`--scenario-5`**
- [ ] KOTH: hill room 2 + room-1 collision; launch **`--scenario-4`**
- [ ] `add_loadout_intro` if bots needed
- [ ] Log: `bg_*.* loaded externally`

---

## Curriculum quick index (31 steps)

Regenerate: `python3 tools/pdmap.py learn curriculum generate`.

| Steps | Topic |
|-------|-------|
| 1–2 | Spawn Y=10, four spawns |
| 3–4 | Weapon pickup, ammo crate |
| 5–6 | Loadout / ailist 0x1000, waypoints + bots |
| 7–8 | KOTH hill, CTF Case+CaseRespawn |
| 9 | Deploy-as uff / `--test-map` |
| 10 | Full composite (my_arena-like) |
| 11 | Y autocorrect 0→10 |
| 12–13 | testarena / compact fixtures |
| 14–15 | seg full vs empty |
| 16 | my_arena registered layout |
| 17–18 | from-json CLI, register probe |
| 19–22 | Scenarios 1–3 (Hold, Hacker, Pop a Cap) |
| 20 | Cross-type pad overlap |
| 23–24 | Bot cap, MPWEAPON loadout |
| 25 | Boot-stage my_arena |
| 26–27 | Solo CTF, multi weaponnum pickups |
| 28 | Hill collision mirror |
| 29 | Custom SEG_SCRIPT |
| 30 | Mod deploy hygiene |
| 31 | AI cover points |

Artifacts: `journal/map_learn/maps/learn_XX_*.json`, `src/levels/learn_XX_*.py`.

---

## Command cheat sheet

```bash
# Init / build / deploy
python3 tools/pdmap.py init mymap
PDMAP_SEG_MODE=empty python3 tools/pdmap.py build uff --seg --deploy
python3 tools/pdmap.py from-json map.json --deploy-as uff --deploy --play --scenario-5

# Curriculum
python3 tools/pdmap.py learn curriculum generate
python3 tools/pdmap.py learn curriculum validate
./scripts/play-learn-step.sh 10

# Editor backend
python3 journal/uff_viewer/test_map.py map.json --level uff --deploy-as uff \
  --mod mod_allinone --seg --deploy --play

# Registered stage
./build/pd.arm64 --boot-stage STAGE_MY_ARENA --skip-intro \
  --moddir mods/mod_allinone --scenario-5
```

---

## Related files

| Path | Role |
|------|------|
| [`tools/pdmap/learn/curriculum.py`](../../tools/pdmap/learn/curriculum.py) | 31-step registry + generate/validate |
| [`scripts/play-learn-step.sh`](../../scripts/play-learn-step.sh) | Deploy-as uff + scenario/seg per step |
| [`scripts/validate-maps.sh`](../../scripts/validate-maps.sh) | Manual validation launcher |
| [`journal/uff_viewer/test_map.py`](../../journal/uff_viewer/test_map.py) | Map Editor Test/Play backend |
| [`src/levels/uff.py`](../../src/levels/uff.py) | Reference box arena |
| [`docs/MAP_DETERMINISTIC_SPEC.md`](../../docs/MAP_DETERMINISTIC_SPEC.md) | Machine-verified facts |
