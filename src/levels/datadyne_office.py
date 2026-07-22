# dataDyne office — Virtual Agent Simulation Map (L0 foundation)
#
# The first world for the LLM-agent simulation described in
# ../../llm-play/VISION.md. Not an arena: an OFFICE FLOOR. Simulants
# (LLM-controlled bots, bridge `bot_mask`) spawn at workstations and — once
# the behavior + conversation layers land (L1–L3) — sit at their desks, work
# at their computers, and respond when the player walks up and speaks.
#
# This module is the L0 substrate: a legible office floor plan (desks, chairs,
# computers, cubicle rows), agent home spawns, a player entry spawn, and named
# interaction anchors. Authored in the same deterministic style as
# uff_masonic.py so it builds through the exact same pdmap pipeline.
#
# Build & deploy (see docs/DETERMINISTIC_MAP_CREATION.md):
#   python3 scripts/ensure-llm-office-map-assets.py
#   # or: tools/pdmap.py build datadyne_office --deploy, then mirror → bg_uff.*
# Launch: LLM Play → Office (office_sim) → Start (--test-map / STAGE_TEST_UFF)
#
# Empty tiles-only seg (SEG_MODE="empty") keeps in-box first-person clean — no
# phantom wall / near-plane sheet (MAP_CREATION §11.11–11.12). Props render from
# the setup binary; full desk *collision* is an L1+ refinement (needs seg geometry
# or per-prop collision), so early agents/player may pass through furniture.

from tools.pdmap.builders import add_loadout_intro, floor_box_tiles
from tools.pdmap.core import MapDef
from tools.pdmap.intro import Spawn
from tools.pdmap.props import StdObject, SingleMonitor

# ── Office model ids (verified against src/include/constants.h) ────────────────
MODEL_DD_OFFICEDOOR = 0x003B  # constants.h:1875
MODEL_DD_DESK       = 0x0046  # constants.h:1886
MODEL_DD_CHAIR      = 0x0047  # constants.h:1887
MODEL_PD_CONSOLE    = 0x00B2  # constants.h:1994  (desktop computer / terminal)
MODEL_DOORCONSOLE   = 0x0018  # constants.h:1840  (wall panel / lab console)

# ── Simulant roster (dataDyne staff) ──────────────────────────────────────────
# body ids from constants.h (MPBODY_*). Bound to LLM brains by the Simulation
# Director at runtime; the map only fixes WHERE each agent starts (its home desk).
#   Cassandra De Vries  MPBODY_CASSANDRA   0x11   corner office, cold/political
#   Lab tech ×2         MPBODY_DD_LABTECH  0x2c   cubicle row, heads-down
#   Shock trooper       MPBODY_DDSHOCK     0x17   desk near lab, twitchy
#   Security guard      MPBODY_DD_GUARD    0x1a   patrol / reception
# (Runtime binding lives in the sidecar roster, not the level module — a
#  character is a folder under assets/characters/<slug>/, per VISION §5.)

BOX_HALF = 6000.0     # office footprint half-extent (±6000 floor)
BOX_HEIGHT = 2600.0   # ceiling clearance
SEG_MODE = "empty"    # tiles-only collision; in-box FPS safe
SPAWN_Y = 10.0        # PAD_FLOOR_OFFSET — spawn / prop pads just above floor (pad_y_at_floor)
# Furniture pads must use the same small positive Y as spawns — Y≤0 fails pdmap
# validation (ground search rejects the floor). Visual sit-on-floor is engine-side.

# ── Floor plan ────────────────────────────────────────────────────────────────
# Two cubicle rows of workstations facing a central aisle, a corner executive
# office, and a reception/entry. Coordinates in world units (+Y up, +X east,
# +Z south). Each workstation = one desk + chair + computer, with a spawn pad at
# the chair so its assigned agent starts seated at its own terminal.
#
#   facing: yaw the seated agent looks toward its monitor (degrees, 0 = +Z).
WORKSTATIONS = [
    # slug,           desk_x,  desk_z,  facing,  body,               role
    ("cassandra",    -4200.0, -4200.0,   135.0, "MPBODY_CASSANDRA", "CEO — corner office"),
    ("labtech_1",    -1500.0, -3800.0,     0.0, "MPBODY_DD_LABTECH", "Research — cubicle A1"),
    ("labtech_2",       0.0,  -3800.0,     0.0, "MPBODY_DD_LABTECH", "Research — cubicle A2"),
    ("analyst",      1500.0,  -3800.0,     0.0, "MPBODY_DD_LABTECH", "Data — cubicle A3"),
    ("shock",       -1500.0,   3800.0,   180.0, "MPBODY_DDSHOCK",    "Security desk — row B1"),
    ("engineer",        0.0,   3800.0,   180.0, "MPBODY_DD_LABTECH", "Systems — row B2"),
    ("guard",        4200.0,   4200.0,   225.0, "MPBODY_DD_GUARD",   "Reception / patrol"),
]

# Player enters at reception, facing the floor (north, into the office).
PLAYER_SPAWN = (5200.0, 4600.0)   # (x, z)

# Named interaction anchors — where the player is meant to walk to talk to
# someone. Consumed by the Simulation Director's proximity layer (VISION §5),
# not by the engine. Kept here so the world and its social geography live in one
# file. dist = approach radius in world units.
INTERACTION_ANCHORS = [
    ("cassandra_office_door", -3400.0, -3400.0, 500.0),
    ("cubicle_row_a",             0.0, -3200.0, 700.0),
    ("cubicle_row_b",             0.0,  3200.0, 700.0),
    ("reception",              4400.0,  4200.0, 500.0),
    ("water_cooler",          -4400.0,  4400.0, 400.0),  # a natural gathering spot
]

# Offsets of a workstation's chair and computer relative to the desk origin.
CHAIR_DZ = 300.0      # chair sits "in front" (aisle side) of the desk
COMPUTER_DZ = -120.0  # monitor sits on the far edge of the desk


def build() -> MapDef:
    g = MapDef("datadyne_office")

    # Pad index plan (contiguous, room 1 — hard invariant):
    #   0                    → player spawn (reception)
    #   1 .. N               → one agent home spawn per workstation (at its chair)
    # Furniture props are anchored to their own pads placed after the spawns.
    g.add_pad(index=0, x=PLAYER_SPAWN[0], y=SPAWN_Y, z=PLAYER_SPAWN[1], room=1)
    g.add_intro(Spawn(pad=0))

    pad = 1
    agent_home_pads = {}
    furniture_pad = {}
    for slug, dx, dz, facing, body, role in WORKSTATIONS:
        # Agent home spawn — at the chair, so the simulant starts seated.
        chair_z = dz + CHAIR_DZ
        g.add_pad(index=pad, x=dx, y=SPAWN_Y, z=chair_z, room=1)
        g.add_intro(Spawn(pad=pad))
        agent_home_pads[slug] = pad
        pad += 1

    # Furniture pads (desks, chairs, computers) come after all spawn pads so the
    # spawn block stays contiguous and low-indexed.
    for slug, dx, dz, facing, body, role in WORKSTATIONS:
        desk_pad = pad
        g.add_pad(index=desk_pad, x=dx, y=SPAWN_Y, z=dz, room=1)
        pad += 1
        chair_pad = pad
        g.add_pad(index=chair_pad, x=dx, y=SPAWN_Y, z=dz + CHAIR_DZ, room=1)
        pad += 1
        comp_pad = pad
        g.add_pad(index=comp_pad, x=dx, y=SPAWN_Y, z=dz + COMPUTER_DZ, room=1)
        pad += 1
        furniture_pad[slug] = (desk_pad, chair_pad, comp_pad)

        g.add_prop(StdObject(model=MODEL_DD_DESK, pad=desk_pad))
        g.add_prop(StdObject(model=MODEL_DD_CHAIR, pad=chair_pad))
        # The "computer" the agent works on. SingleMonitor gives an on-screen
        # image; image id is a placeholder to tune when texture ids are wired.
        # Fallback that always builds: StdObject(model=MODEL_PD_CONSOLE, ...).
        g.add_prop(SingleMonitor(image=0x00, model=MODEL_PD_CONSOLE, pad=comp_pad))

    # Unarmed office loadout (no weapons on the floor — this is a workplace, not
    # an arena). Intro still needs a loadout block; keep it minimal.
    add_loadout_intro(g)

    # Stash the social geography on the MapDef for the deploy/inspect tooling and
    # the Simulation Director to read back (home desks + interaction anchors).
    g.agent_home_pads = agent_home_pads          # slug -> spawn pad index
    g.furniture_pad = furniture_pad              # slug -> (desk, chair, computer) pads
    g.interaction_anchors = INTERACTION_ANCHORS  # named approach zones
    return g


def build_tiles_json():
    # Floor-only box tiles (room 1). Walls/cubicle partitions are an L1 pass:
    # either box-tile inner walls or, on Path B, real dataDyne geometry.
    return floor_box_tiles("datadyne_office", half=BOX_HALF, y=0.0, room_index=1)
