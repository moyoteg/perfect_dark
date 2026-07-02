# Matrix Test Room — 64-spawn battle layout with Laptop Gun emphasis.
# Engine: --laptop-sentry-infinite-ammo (255 = no drain) + --unlimited-sentries.
# Deploy: python3 tools/pdmap.py build matrix_battle_sentry_inf --seg --deploy
# Play:   ./scripts/play-matrix-sentry-unlimited.sh
# Or:     ./build/pd.arm64 --test-map --moddir mods/mod_allinone --laptop-sentry-infinite-ammo
#         --unlimited-sentries --scenario-0 --num-sims 50 --teams-battle --sim-difficulty 5

from tools.pdmap.builders import (
    _retail_multi_ammo_crate,
    add_floor_weapons,
    add_loadout_intro,
    add_weapon_ammo_pair,
    floor_box_tiles,
)
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap import weapons as W

BOX_HALF = 5000.0
BOX_HEIGHT = 3000.0
SPAWN_Y = 10.0
SEG_MODE = "empty"
DEPLOY_AS = "uff"

_TEAM_COLS = 8
_TEAM_ROWS = 4
_X0 = -3500.0
_X_STEP = 1000.0
_TEAM0_Z = (-3400.0, -3800.0, -4200.0, -4600.0)
_TEAM1_Z = (3400.0, 3800.0, 4200.0, 4600.0)
_AMMO_OFFSET_X = W.RETAIL_AMMO_PAIR_OFFSET_X

# Generous SMG resupply for repeated sentry deploys (retail laptop crate = 150).
_LAPTOP_AMMO_SLOTS = {W.AMMOTYPE_SMG: 600}


def _team_spawn_positions(team: int) -> list[tuple[float, float]]:
    z_rows = _TEAM0_Z if team == 0 else _TEAM1_Z
    positions: list[tuple[float, float]] = []
    for z in z_rows:
        for col in range(_TEAM_COLS):
            positions.append((_X0 + col * _X_STEP, z))
    return positions


def _add_laptop_pair(g: MapDef, pad_index: int, x: float, z: float) -> int:
    """Weapon + boosted ammo crate; returns next free pad index."""
    weapon_pad = pad_index
    g.add_pad(index=weapon_pad, x=x, y=SPAWN_Y, z=z, room=1)
    pad_index += 1
    ammo_pad = pad_index
    g.add_pad(index=ammo_pad, x=x + _AMMO_OFFSET_X, y=SPAWN_Y, z=z, room=1)
    pad_index += 1
    add_floor_weapons(g, [(weapon_pad, W.WEAPON_LAPTOPGUN)])
    g.add_prop(
        _retail_multi_ammo_crate(
            ammo_pad,
            scale=0x0100,
            model=W.MODEL_MULTI_AMMO_CRATE,
            slots=_LAPTOP_AMMO_SLOTS,
        )
    )
    return pad_index


def build() -> MapDef:
    g = MapDef("matrix_battle_sentry_inf")

    pad_index = 0
    for team in (0, 1):
        face_z = 1.0 if team == 0 else -1.0
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

    # Same 48-pair battle layout as matrix_battle_64, with laptops replacing several rifles.
    weapon_layout: list[tuple[float, float, int]] = [
        (-2800.0, 0.0, W.WEAPON_AR34),
        (-1400.0, 0.0, W.WEAPON_CMP150),
        (0.0, 0.0, W.WEAPON_LAPTOPGUN),
        (1400.0, 0.0, W.WEAPON_FALCON2),
        (2800.0, 0.0, W.WEAPON_MAGSEC4),
        (-2000.0, -1000.0, W.WEAPON_LAPTOPGUN),
        (2000.0, -1000.0, W.WEAPON_SUPERDRAGON),
        (-2000.0, 1000.0, W.WEAPON_ROCKETLAUNCHER),
        (2000.0, 1000.0, W.WEAPON_LAPTOPGUN),
        (-1000.0, -1600.0, W.WEAPON_LAPTOPGUN),
        (1000.0, -1600.0, W.WEAPON_MAULER),
        (-1000.0, 1600.0, W.WEAPON_LAPTOPGUN),
        (-3200.0, -2600.0, W.WEAPON_FALCON2),
        (-2400.0, -2600.0, W.WEAPON_LAPTOPGUN),
        (-1600.0, -2600.0, W.WEAPON_AR34),
        (-800.0, -2600.0, W.WEAPON_SHOTGUN),
        (800.0, -2600.0, W.WEAPON_MAGSEC4),
        (1600.0, -2600.0, W.WEAPON_LAPTOPGUN),
        (2400.0, -2600.0, W.WEAPON_AR34),
        (3200.0, -2600.0, W.WEAPON_CMP150),
        (-3200.0, -1800.0, W.WEAPON_MAGSEC4),
        (-1600.0, -1800.0, W.WEAPON_LAPTOPGUN),
        (0.0, -1800.0, W.WEAPON_FALCON2),
        (1600.0, -1800.0, W.WEAPON_CMP150),
        (3200.0, -1800.0, W.WEAPON_AR34),
        (-3200.0, 2600.0, W.WEAPON_FALCON2),
        (-2400.0, 2600.0, W.WEAPON_LAPTOPGUN),
        (-1600.0, 2600.0, W.WEAPON_AR34),
        (-800.0, 2600.0, W.WEAPON_SHOTGUN),
        (800.0, 2600.0, W.WEAPON_MAGSEC4),
        (1600.0, 2600.0, W.WEAPON_LAPTOPGUN),
        (2400.0, 2600.0, W.WEAPON_AR34),
        (3200.0, 2600.0, W.WEAPON_CMP150),
        (-3200.0, 1800.0, W.WEAPON_MAGSEC4),
        (-1600.0, 1800.0, W.WEAPON_LAPTOPGUN),
        (0.0, 1800.0, W.WEAPON_FALCON2),
        (1600.0, 1800.0, W.WEAPON_CMP150),
        (3200.0, 1800.0, W.WEAPON_AR34),
        (-2800.0, -3200.0, W.WEAPON_LAPTOPGUN),
        (0.0, -3200.0, W.WEAPON_SHOTGUN),
        (2800.0, -3200.0, W.WEAPON_AR34),
        (-1400.0, -3200.0, W.WEAPON_MAGSEC4),
        (1400.0, -3200.0, W.WEAPON_LAPTOPGUN),
        (-2800.0, 3200.0, W.WEAPON_LAPTOPGUN),
        (0.0, 3200.0, W.WEAPON_SHOTGUN),
        (2800.0, 3200.0, W.WEAPON_AR34),
        (-1400.0, 3200.0, W.WEAPON_MAGSEC4),
        (1400.0, 3200.0, W.WEAPON_LAPTOPGUN),
    ]

    for x, z, weapon_id in weapon_layout:
        if weapon_id == W.WEAPON_LAPTOPGUN:
            pad_index = _add_laptop_pair(g, pad_index, x, z)
            continue
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

    # Extra laptop sentry lanes (boosted ammo crates).
    for x in (-2800.0, -1400.0, 0.0, 1400.0, 2800.0):
        pad_index = _add_laptop_pair(g, pad_index, x, -600.0)
        pad_index = _add_laptop_pair(g, pad_index, x, 600.0)

    add_loadout_intro(g)
    return g


def build_tiles_json():
    return floor_box_tiles("matrix_battle_sentry_inf", half=BOX_HALF, y=0.0, room_index=1)
