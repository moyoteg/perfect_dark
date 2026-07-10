# Virtual Agent Office — dataDyne G5 Building (retail depo geometry).
#
# Player spawns on meeting-room corridor pads (PAD_DEPO_003D primary, alts 003E/008F,
# Y≈27); eight virtual agents in the holograph meeting room. Z-target for status lines;
# (Z) on PD console.
#
# Geometry: retail bg_depo seg/tiles/pads from ROM (SKIP_* flags).
# Setup: dedicated STAGE_AGENT_OFFICE (0x83) → Ump_setupagent_officeZ.
# Doors: retail depo doors (mp_unlock + sibling remapped; tools/pdmap/depo_retail_doors.py).
#
# Deploy:  python3 tools/pdmap.py build agent_office --deploy
# Play:    ./scripts/play-agent-office.sh

from tools.pdmap.agent_office import (
    PAD_BRIEFING_ENTRY,
    PAD_PLAYER_SPAWN,
    PAD_PLAYER_SPAWN_ALT,
    PAD_PLAYER_SPAWN_LOBBY,
)
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap.retail import load_retail_pads

# Retail depo collision + visible geometry; only custom MP setup is deployed.
RETAIL_STAGE = "depo"
RETAIL_TILES = "depo"
RETAIL_GEOMETRY = True

# Keep retail collision + visible geometry; only replace MP setup binary.
SKIP_TILES = True
SKIP_SEG = True
SKIP_PADS = True


def build() -> MapDef:
    g = MapDef("agent_office")
    g.agent_office = True

    # Full retail pad graph (indices match setupdepo / bg_depo_padsZ).
    load_retail_pads(g, RETAIL_STAGE, default_room=-1)

    # Player spawns — meeting-room corridor (PAD_DEPO_003D primary; alts 003E, 008F).
    g.add_intro(Spawn(pad=PAD_BRIEFING_ENTRY))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_ALT))
    g.add_intro(Spawn(pad=PAD_PLAYER_SPAWN_LOBBY))

    # mp_init ailist 0x1000 is emitted by pack_agent_office_setup (for --with-bots only).
    return g
