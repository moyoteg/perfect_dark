# Conker BFD Total War (War Colors / bg_mp13) — 64-spawn teams battle on retail geometry.
# Stage: STAGE_EXTRA26 (0x5b) → bg_mp13.* (same seg/tiles/pads slot as mp13).
# Engine: --laptop-sentry-infinite-ammo + --unlimited-sentries.
# Optional deploy (NOT default): python3 tools/pdmap.py build conker_war_sentry_inf --deploy
# Play (retail layout): ./scripts/play-conker-war-sentry.sh
# Play (custom overlay): ./scripts/play-conker-war-sentry.sh --deploy-custom
# Launch: ./build/pd.arm64 --boot-stage 0x5b --skip-intro --moddir mods/mod_allinone ...

from tools.pdmap.builders import (
    _retail_multi_ammo_crate,
    add_floor_weapons,
    add_loadout_intro,
    add_weapon_ammo_pair,
)
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap import weapons as W
from tools.pdmap.retail import (
    load_retail_pads,
    pick_team_spawn_pad_indices,
)

# Overlay custom setup/pads onto the retail mp13 asset slot (War Colors uses mp13 files).
DEPLOY_AS = "mp13"
RETAIL_STAGE = "mp13"
RETAIL_TILES = "mp13"
RETAIL_GEOMETRY = True
SKIP_TILES = True
SKIP_SEG = True

_AMMO_OFFSET_X = W.RETAIL_AMMO_PAIR_OFFSET_X
_LAPTOP_AMMO_SLOTS = {W.AMMOTYPE_SMG: 600}

# Extra weapon pads appended after retail mp13 pad graph (219 pads → index 219+).
# Coordinates are real War Colors / mp13 world space (SHC +Z ridge, Tediz -Z tunnels, center bridge).
_EXTRA_WEAPONS: list[tuple[float, float, float, int]] = [
    # SHC fortress (+Z, upper ridge y≈184).
    (-2800.0, 184.0, 2100.0, W.WEAPON_LAPTOPGUN),
    (-1400.0, 184.0, 2050.0, W.WEAPON_ROCKETLAUNCHER),
    (0.0, 184.0, 2000.0, W.WEAPON_LAPTOPGUN),
    (1400.0, 184.0, 2050.0, W.WEAPON_SUPERDRAGON),
    (2800.0, 184.0, 2100.0, W.WEAPON_LAPTOPGUN),
    (-3200.0, 184.0, 1750.0, W.WEAPON_FALCON2),
    (-1600.0, 184.0, 1700.0, W.WEAPON_LAPTOPGUN),
    (1600.0, 184.0, 1700.0, W.WEAPON_AR34),
    (3200.0, 184.0, 1750.0, W.WEAPON_LAPTOPGUN),
    # SHC outer platforms (y≈84).
    (-3800.0, 84.0, 2800.0, W.WEAPON_CMP150),
    (-2000.0, 84.0, 2900.0, W.WEAPON_LAPTOPGUN),
    (0.0, 84.0, 2950.0, W.WEAPON_SHOTGUN),
    (2000.0, 84.0, 2900.0, W.WEAPON_LAPTOPGUN),
    (3800.0, 84.0, 2800.0, W.WEAPON_MAGSEC4),
    # Tediz tunnels (-Z, y≈-516 / -316).
    (-2800.0, -516.0, -3100.0, W.WEAPON_LAPTOPGUN),
    (-1400.0, -516.0, -3000.0, W.WEAPON_ROCKETLAUNCHER),
    (0.0, -516.0, -2900.0, W.WEAPON_LAPTOPGUN),
    (1400.0, -516.0, -3000.0, W.WEAPON_SUPERDRAGON),
    (2800.0, -516.0, -3100.0, W.WEAPON_LAPTOPGUN),
    (-3200.0, -516.0, -1200.0, W.WEAPON_FALCON2),
    (-1600.0, -516.0, -900.0, W.WEAPON_LAPTOPGUN),
    (1600.0, -516.0, -900.0, W.WEAPON_AR34),
    (3200.0, -516.0, -1200.0, W.WEAPON_LAPTOPGUN),
    (-4500.0, -516.0, -2200.0, W.WEAPON_CMP150),
    (-2500.0, -316.0, -1800.0, W.WEAPON_LAPTOPGUN),
    (2500.0, -316.0, -1800.0, W.WEAPON_SHOTGUN),
    (4500.0, -516.0, -2200.0, W.WEAPON_LAPTOPGUN),
    # Center bridge / contested low ground (y≈-316).
    (-1200.0, -316.0, 200.0, W.WEAPON_AR34),
    (-400.0, -316.0, 150.0, W.WEAPON_LAPTOPGUN),
    (400.0, -316.0, 150.0, W.WEAPON_CMP150),
    (1200.0, -316.0, 200.0, W.WEAPON_LAPTOPGUN),
    (0.0, -316.0, -200.0, W.WEAPON_SNIPERRIFLE),
    (-800.0, -316.0, 600.0, W.WEAPON_LAPTOPGUN),
    (800.0, -316.0, 600.0, W.WEAPON_FALCON2),
    # Bridge laptop sentry lanes.
    (-1000.0, -316.0, 0.0, W.WEAPON_LAPTOPGUN),
    (1000.0, -316.0, 0.0, W.WEAPON_LAPTOPGUN),
    (-500.0, -316.0, -400.0, W.WEAPON_LAPTOPGUN),
    (500.0, -316.0, -400.0, W.WEAPON_LAPTOPGUN),
]


def _add_laptop_pair(g: MapDef, pad_index: int, x: float, y: float, z: float) -> int:
    # room=-1: let setupPreparePads resolve floor room from Conker geometry (same as retail mp13).
    weapon_pad = pad_index
    g.add_pad(index=weapon_pad, x=x, y=y, z=z, room=-1)
    pad_index += 1
    ammo_pad = pad_index
    g.add_pad(index=ammo_pad, x=x + _AMMO_OFFSET_X, y=y, z=z, room=-1)
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


def _add_weapon_pair(
    g: MapDef, pad_index: int, x: float, y: float, z: float, weapon_id: int
) -> int:
    weapon_pad = pad_index
    g.add_pad(index=weapon_pad, x=x, y=y, z=z, room=-1)
    pad_index += 1
    ammo_pad = pad_index
    g.add_pad(index=ammo_pad, x=x + _AMMO_OFFSET_X, y=y, z=z, room=-1)
    pad_index += 1
    add_weapon_ammo_pair(g, weapon_pad, weapon_id, [ammo_pad])
    return pad_index


def build() -> MapDef:
    g = MapDef("conker_war_sentry_inf")

    # Retail mp13 pads omit room (binary room=-1); setupPreparePads auto-binds floor room.
    retail_count = load_retail_pads(g, RETAIL_STAGE, default_room=-1)
    pad_index = retail_count

    for team in (0, 1):
        for pad_idx in pick_team_spawn_pad_indices(RETAIL_STAGE, team=team, count=32):
            g.add_intro(Spawn(pad=pad_idx))

    for x, y, z, weapon_id in _EXTRA_WEAPONS:
        if weapon_id == W.WEAPON_LAPTOPGUN:
            pad_index = _add_laptop_pair(g, pad_index, x, y, z)
        else:
            pad_index = _add_weapon_pair(g, pad_index, x, y, z, weapon_id)

    add_loadout_intro(g)
    return g
