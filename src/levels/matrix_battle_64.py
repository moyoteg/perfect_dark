# Matrix Test Room — two-sided 64-spawn battle layout (32 pads per flank).
# Deploy with: python3 tools/pdmap.py build matrix_battle_64 --seg --deploy
# Play with:   ./scripts/play-matrix-battle.sh
# Or:          ./build/pd.arm64 --test-map --moddir mods/mod_allinone --scenario-0 --num-sims 50 --teams-battle --sim-difficulty 5
# PC port supports up to 64 fighters (1 human + 63 bots); stock u32 chrslots caps N64 at 32.

from tools.pdmap.builders import add_loadout_intro, add_weapon_ammo_pair, floor_box_tiles
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
# 400-unit row spacing (was 200) — reduces spawn-line overlap with 25+ bots per flank.
_TEAM0_Z = (-3400.0, -3800.0, -4200.0, -4600.0)
_TEAM1_Z = (3400.0, 3800.0, 4200.0, 4600.0)

# Retail Combat Simulator weapon→ammo pad offset (mp1 ≈130 units on X).
_AMMO_OFFSET_X = W.RETAIL_AMMO_PAIR_OFFSET_X


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

    # --- Weapon + large retail ammo pairs (48) — Combat Simulator layout ---
    # Each station: weapon pad at (x, z), large multiammocrate at (x + offset, z).
    weapon_layout: list[tuple[float, float, int]] = [
        # Center belt (12).
        (-2800.0, 0.0, W.WEAPON_AR34),
        (-1400.0, 0.0, W.WEAPON_CMP150),
        (0.0, 0.0, W.WEAPON_SHOTGUN),
        (1400.0, 0.0, W.WEAPON_FALCON2),
        (2800.0, 0.0, W.WEAPON_MAGSEC4),
        (-2000.0, -1000.0, W.WEAPON_SNIPERRIFLE),
        (2000.0, -1000.0, W.WEAPON_SUPERDRAGON),
        (-2000.0, 1000.0, W.WEAPON_ROCKETLAUNCHER),
        (2000.0, 1000.0, W.WEAPON_CROSSBOW),
        (-1000.0, -1600.0, W.WEAPON_LAPTOPGUN),
        (1000.0, -1600.0, W.WEAPON_MAULER),
        (-1000.0, 1600.0, W.WEAPON_TRANQUILIZER),
        # Team 0 advance rows (13).
        (-3200.0, -2600.0, W.WEAPON_FALCON2),
        (-2400.0, -2600.0, W.WEAPON_CMP150),
        (-1600.0, -2600.0, W.WEAPON_AR34),
        (-800.0, -2600.0, W.WEAPON_SHOTGUN),
        (800.0, -2600.0, W.WEAPON_MAGSEC4),
        (1600.0, -2600.0, W.WEAPON_FALCON2),
        (2400.0, -2600.0, W.WEAPON_AR34),
        (3200.0, -2600.0, W.WEAPON_CMP150),
        (-3200.0, -1800.0, W.WEAPON_MAGSEC4),
        (-1600.0, -1800.0, W.WEAPON_SHOTGUN),
        (0.0, -1800.0, W.WEAPON_FALCON2),
        (1600.0, -1800.0, W.WEAPON_CMP150),
        (3200.0, -1800.0, W.WEAPON_AR34),
        # Team 1 advance rows (13).
        (-3200.0, 2600.0, W.WEAPON_FALCON2),
        (-2400.0, 2600.0, W.WEAPON_CMP150),
        (-1600.0, 2600.0, W.WEAPON_AR34),
        (-800.0, 2600.0, W.WEAPON_SHOTGUN),
        (800.0, 2600.0, W.WEAPON_MAGSEC4),
        (1600.0, 2600.0, W.WEAPON_FALCON2),
        (2400.0, 2600.0, W.WEAPON_AR34),
        (3200.0, 2600.0, W.WEAPON_CMP150),
        (-3200.0, 1800.0, W.WEAPON_MAGSEC4),
        (-1600.0, 1800.0, W.WEAPON_SHOTGUN),
        (0.0, 1800.0, W.WEAPON_FALCON2),
        (1600.0, 1800.0, W.WEAPON_CMP150),
        (3200.0, 1800.0, W.WEAPON_AR34),
        # Just forward of front spawn lines (10).
        (-2800.0, -3200.0, W.WEAPON_FALCON2),
        (0.0, -3200.0, W.WEAPON_SHOTGUN),
        (2800.0, -3200.0, W.WEAPON_AR34),
        (-1400.0, -3200.0, W.WEAPON_MAGSEC4),
        (1400.0, -3200.0, W.WEAPON_CMP150),
        (-2800.0, 3200.0, W.WEAPON_FALCON2),
        (0.0, 3200.0, W.WEAPON_SHOTGUN),
        (2800.0, 3200.0, W.WEAPON_AR34),
        (-1400.0, 3200.0, W.WEAPON_MAGSEC4),
        (1400.0, 3200.0, W.WEAPON_CMP150),
    ]

    for x, z, weapon_id in weapon_layout:
        weapon_pad = pad_index
        g.add_pad(index=weapon_pad, x=x, y=SPAWN_Y, z=z, room=1)
        pad_index += 1
        ammo_pad = pad_index
        g.add_pad(
            index=ammo_pad,
            x=x + _AMMO_OFFSET_X,
            y=SPAWN_Y,
            z=z,
            room=1,
        )
        pad_index += 1
        add_weapon_ammo_pair(g, weapon_pad, weapon_id, [ammo_pad])

    add_loadout_intro(g)
    return g


def build_tiles_json():
    return floor_box_tiles("matrix_battle_64", half=BOX_HALF, y=0.0, room_index=1)
