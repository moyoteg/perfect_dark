# War Colors (STAGE_EXTRA26 / bg_mp13) — Conker-correct Deathmatch setup.
#
# Golden Nintendo Maps replaced Villa seg/tiles with Conker BFD geometry but kept
# the retail mp13 pad graph. Retail Ump_setupmp13Z still references spawn pads 001C–0027
# and weapons 00BD–00C6; seven of those XY sit in void on Conker (extreme Villa -X).
#
# This overlay keeps retail pads + CTF/hill anchors, but points DM spawns and floor
# weapons at pad indices probed usable on Conker geometry (see docs/WAR_COLORS_LEVEL.md).
#
# Deploy: python3 tools/pdmap.py build war_colors_conker --deploy
# Play:   ./scripts/play-conker-war-sentry.sh

from tools.pdmap.builders import add_loadout_intro, _retail_multi_ammo_crate
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Case, CaseRespawn, Hill, Spawn
from tools.pdmap.props import Weapon
from tools.pdmap.retail import load_retail_pads
from tools.pdmap import weapons as W

DEPLOY_AS = "mp13"
RETAIL_STAGE = "mp13"
SKIP_TILES = True
SKIP_SEG = True
SKIP_PADS = True
RETAIL_GEOMETRY = True

# WEAPON_MPLOCATION00..09 (constants.h 240..249) — scenario assigns real weapons per slot.
_MPLOCATION00 = 240
_MPLOCATION01 = 241
_MPLOCATION02 = 242
_MPLOCATION03 = 243
_MPLOCATION04 = 244
_MPLOCATION05 = 245
_MPLOCATION06 = 246
_MPLOCATION07 = 247
_MPLOCATION08 = 248
_MPLOCATION09 = 249

# 12 Deathmatch spawns: 6 SHC fortress interior (+Z, z>1500), 6 Tediz tunnel interior
# (-Z, z<-2000). Zero bridge/contested pads (|z|<=500 excluded).
CONKER_SPAWN_PADS: tuple[int, ...] = (
    35, 116, 113, 0, 218, 108,   # SHC ridge interior (+Z)
    88, 80, 16, 82, 20, 89,       # Tediz deep tunnels (-Z)
)

# 5 floor weapons per faction — all probed usable, strictly inside each base.
# SHC: z>1200 fortress platforms. Tediz: z<-1200 (prefer z<-2000) tunnel floors.
CONKER_WEAPON_LAYOUT: list[tuple[int, list[int], int]] = [
    # SHC fortress interior (+Z ridge)
    (190, [201, 202], _MPLOCATION00),  # 00BE z=+1304
    (198, [129, 130], _MPLOCATION01),  # 00C6 z=+2092
    (192, [205, 206], _MPLOCATION02),  # 00C0 z=+1413
    (100, [101, 105], _MPLOCATION03),  # ridge z=+1990
    (35, [106, 107], _MPLOCATION04),   # far ridge z=+3043
    # Tediz deep tunnel interior (-Z)
    (16, [17, 84], _MPLOCATION05),     # z=-2722
    (80, [89, 95], _MPLOCATION06),     # z=-2973
    (88, [215], _MPLOCATION07),        # z=-3163 (deepest)
    (20, [83, 90], _MPLOCATION08),     # z=-2417
    (82, [176, 174], _MPLOCATION09),  # z=-2642
]


def _add_mplocation_weapon(g: MapDef, weapon_pad: int, slot_id: int) -> None:
    g.add_prop(Weapon(
        weapon=slot_id,
        scale=0x0100,
        model=0,
        chr_=weapon_pad,
        flags=W.OBJFLAG_FALL,
    ))


def _add_retail_scenarios(g: MapDef) -> None:
    """Mirror mp_setupmp13.c CTF/KOTH intro (pad indices unchanged)."""
    g.add_intro(Case(team=0, pad=6))
    for pad in (0, 1, 2, 3, 4, 5):
        g.add_intro(CaseRespawn(team=0, pad=pad))

    g.add_intro(Case(team=1, pad=13))
    for pad in (7, 8, 9, 10, 11, 12):
        g.add_intro(CaseRespawn(team=1, pad=pad))

    g.add_intro(Case(team=2, pad=19))
    for pad in (14, 15, 16, 17, 18, 20):
        g.add_intro(CaseRespawn(team=2, pad=pad))

    g.add_intro(Case(team=3, pad=27))
    for pad in (21, 22, 23, 24, 25, 26):
        g.add_intro(CaseRespawn(team=3, pad=pad))

    for pad in (76, 142, 170, 67):
        g.add_intro(Hill(pad=pad))


def build() -> MapDef:
    g = MapDef("war_colors_conker")

    load_retail_pads(g, RETAIL_STAGE, default_room=-1)

    for pad_idx in CONKER_SPAWN_PADS:
        g.add_intro(Spawn(pad=pad_idx))

    _add_retail_scenarios(g)

    for weapon_pad, ammo_pads, slot_id in CONKER_WEAPON_LAYOUT:
        _add_mplocation_weapon(g, weapon_pad, slot_id)
        for ammo_pad in ammo_pads:
            g.add_prop(_retail_multi_ammo_crate(ammo_pad))

    add_loadout_intro(g)
    return g
