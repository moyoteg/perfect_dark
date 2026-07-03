# Virtual Agent Office — Carrington Institute (retail dish geometry).
#
# Pre-mission lobby hub: player spawns on PAD_DISH_000E (Y=35, room 0x0014),
# eight virtual agents ring the open CI foyer, Z-target for status lines, and use
# (Z) on the CI hub console in the north lobby (PAD_DISH_0017) for a room overview.
#
# Geometry: retail bg_dish seg/tiles/pads from ROM (SKIP_* flags).
# Setup: dedicated STAGE_AGENT_OFFICE_CI (0x84) → Ump_setupagent_office_ciZ.
# Doors/lifts: retail dish props (deactivated/static; ci_retail_doors / ci_retail_lifts).
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

    # Player spawns — CI lobby hub (Y≈35); agents reachable without opening doors.
    g.add_intro(Spawn(pad=PAD_BRIEFING_ENTRY))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_ALT))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_LOBBY))

    return g
