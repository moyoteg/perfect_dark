# Matrix Test Room — two-sided 64-spawn battle layout (32 pads per flank).
# Deploy with: python3 tools/pdmap.py build matrix_battle_64 --seg --deploy
# Play with:   ./build/pd.arm64 --test-map --moddir mods/mod_allinone --scenario-0 --num-sims 63 --teams-battle
# PC port supports up to 64 fighters (1 human + 63 bots); stock u32 chrslots caps N64 at 32.

from tools.pdmap.builders import add_ammo_row, add_floor_weapons, add_loadout_intro, floor_box_tiles
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap import weapons as W

# Matrix Test Room dimensions (matches uff / STAGE_TEST_UFF env: grey floor, black sky).
BOX_HALF = 5000.0
BOX_HEIGHT = 3000.0
SPAWN_Y = 10.0

# Empty seg — in-box camera; collision from tiles only (MAP_CREATION.md §11.12).
SEG_MODE = "empty"

# Deploy into the uff test slot so --test-map loads this arena without stage registration.
DEPLOY_AS = "uff"

# Grid: 8 columns × 4 rows = 32 spawns per team.
_TEAM_COLS = 8
_TEAM_ROWS = 4
_X0 = -3500.0
_X_STEP = 1000.0
_TEAM0_Z = (-3600.0, -3800.0, -4000.0, -4200.0)
_TEAM1_Z = (3600.0, 3800.0, 4000.0, 4200.0)


def _team_spawn_positions(team: int) -> list[tuple[float, float]]:
    """Return (x, z) spawn positions for one flank (team 0 = -Z, team 1 = +Z)."""
    z_rows = _TEAM0_Z if team == 0 else _TEAM1_Z
    positions: list[tuple[float, float]] = []
    for z in z_rows:
        for col in range(_TEAM_COLS):
            positions.append((_X0 + col * _X_STEP, z))
    return positions


def build() -> MapDef:
    g = MapDef("matrix_battle_64")

    pad_index = 0
    for team in (0, 1):
        face_z = 1.0 if team == 0 else -1.0  # teams face each other across the arena
        for x, z in _team_spawn_positions(team):
            g.add_pad(
                index=pad_index,
                x=x,
                y=SPAWN_Y,
                z=z,
                room=1,
                dir_x=0.0,
                dir_y=0.0,
                dir_z=face_z,
            )
            g.add_intro(Spawn(pad=pad_index))
            pad_index += 1

    # Center-zone resupply between flanks (teams at Z ≈ ±3600–4200).
    # 12 floor weapons + 7 ammo crates — enough pickup diversity for 50+ bots.
    weapon_pads: list[tuple[int, float, float, int]] = [
        (64, -2800.0, 0.0, W.WEAPON_AR34),
        (65, -1400.0, 0.0, W.WEAPON_CMP150),
        (66, 0.0, 0.0, W.WEAPON_SHOTGUN),
        (67, 1400.0, 0.0, W.WEAPON_FALCON2),
        (68, 2800.0, 0.0, W.WEAPON_MAGSEC4),
        (69, -2000.0, -1000.0, W.WEAPON_SNIPERRIFLE),
        (70, 2000.0, -1000.0, W.WEAPON_SUPERDRAGON),
        (71, -2000.0, 1000.0, W.WEAPON_ROCKETLAUNCHER),
        (72, 2000.0, 1000.0, W.WEAPON_CROSSBOW),
        (73, -1000.0, -1600.0, W.WEAPON_LAPTOPGUN),
        (74, 1000.0, -1600.0, W.WEAPON_MAULER),
        (75, -1000.0, 1600.0, W.WEAPON_TRANQUILIZER),
    ]
    for pad, x, z, _ in weapon_pads:
        g.add_pad(index=pad, x=x, y=SPAWN_Y, z=z, room=1)
    add_floor_weapons(g, [(pad, wid) for pad, _, _, wid in weapon_pads])

    ammo_pads: list[tuple[int, float, float]] = [
        (76, 0.0, 0.0),          # center multi-ammo (overlaps shotgun pad — OK)
        (77, -1800.0, -600.0),   # rifle flank
        (78, 1800.0, -600.0),
        (79, -1800.0, 600.0),    # shotgun flank
        (80, 1800.0, 600.0),
        (81, 0.0, -2000.0),      # mid-lane toward team 0
        (82, 0.0, 2000.0),       # mid-lane toward team 1
    ]
    for pad, x, z in ammo_pads:
        g.add_pad(index=pad, x=x, y=SPAWN_Y, z=z, room=1)
    add_ammo_row(g, [76, 81, 82])
    add_ammo_row(g, [77, 78], ammotype=W.AMMOTYPE_RIFLE, model=0)
    add_ammo_row(g, [79, 80], ammotype=W.AMMOTYPE_SHOTGUN, model=0)

    add_loadout_intro(g)
    return g


def build_tiles_json():
    return floor_box_tiles("matrix_battle_64", half=BOX_HALF, y=0.0, room_index=1)
