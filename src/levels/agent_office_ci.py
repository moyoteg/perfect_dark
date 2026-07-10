# Virtual Agent Office — Carrington Institute (retail dish geometry).
#
# Player spawns at retail intro pad (PAD_DISH_00F5, Jo's office); eight virtual
# agents at retail desk/chair chr pads. Z-target for status; (Z) on CI hub console.
#
# Geometry: retail bg_dish seg/tiles/pads from ROM (SKIP_* flags).
# Setup: dedicated STAGE_AGENT_OFFICE_CI (0x84) → Ump_setupagent_office_ciZ.
# Doors/lifts: retail dish props (mp_unlock + sibling remap; ci_retail_doors / ci_retail_lifts).
#
# Deploy:  python3 tools/pdmap.py build agent_office_ci --deploy
# Play:    ./scripts/play-agent-office-ci.sh

from tools.pdmap.agent_office_ci import (
    PAD_BRIEFING_ENTRY,
    PAD_PLAYER_SPAWN_ALT,
    PAD_PLAYER_SPAWN_LOBBY,
)
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap.retail import load_retail_pads

RETAIL_STAGE = "dish"
RETAIL_TILES = "dish"
RETAIL_GEOMETRY = True

SKIP_TILES = True
SKIP_SEG = True
SKIP_PADS = True


def build() -> MapDef:
    g = MapDef("agent_office_ci")
    g.agent_office_ci = True

    load_retail_pads(g, RETAIL_STAGE, default_room=-1)

    # Player spawns — retail intro office (setupdish.c intro[] → PAD_DISH_00F5).
    g.add_intro(Spawn(pad=PAD_BRIEFING_ENTRY))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_ALT))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_LOBBY))

    return g
