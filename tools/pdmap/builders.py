"""High-level helpers for common Combat Simulator map layouts."""

from __future__ import annotations

from .core import MapDef
from .intro import Spawn, Weapon, Ammo, Case, CaseRespawn, Hill
from .props import Weapon as WeaponProp, AmmoCrate, AmmoCrateMulti
from .tiles import _DEFAULT_FLAGS
from . import weapons as W
from .anim_catalog import PARADE_ZONE_HALF


def add_spawn_grid(
    g: MapDef,
    positions: list[tuple[float, float]],
    *,
    y: float = 0.0,
    room: int = 1,
    start_index: int = 0,
) -> list[int]:
    """Place spawn pads and matching intro Spawn commands. Returns pad indices."""
    indices: list[int] = []
    for offset, (x, z) in enumerate(positions):
        idx = start_index + offset
        g.add_pad(index=idx, x=x, y=y, z=z, room=room)
        g.add_intro(Spawn(pad=idx))
        indices.append(idx)
    return indices


def add_mp_scenarios(
    g: MapDef,
    *,
    cases: list[tuple[int, int, int]],
    hill_pads: list[int],
) -> None:
    """Register Capture-the-Case and King-of-the-Hill intro anchors.

    Each case entry is (team, case_pad, respawn_pad).
    """
    for team, case_pad, respawn_pad in cases:
        g.add_intro(Case(team=team, pad=case_pad))
        g.add_intro(CaseRespawn(team=team, pad=respawn_pad))
    for pad in hill_pads:
        g.add_intro(Hill(pad=pad))


def add_loadout_intro(
    g: MapDef,
    *,
    weapons: tuple[int, ...] = W.INTRO_WEAPONS,
    ammo: tuple[int, ...] = W.INTRO_AMMO,
    ammo_qty: int = 100,
) -> None:
    """Standard Combat Simulator starting weapons and ammo."""
    for weapon_id in weapons:
        g.add_intro(Weapon(weapon_id=weapon_id, dualweapon=-1))
    for ammotype in ammo:
        g.add_intro(Ammo(ammotype=ammotype, quantity=ammo_qty))


def add_floor_weapons(
    g: MapDef,
    pad_weapon_pairs: list[tuple[int, int]],
    *,
    scale: int = 0x0100,
) -> None:
    for pad, weapon_id in pad_weapon_pairs:
        g.add_prop(WeaponProp(
            weapon=weapon_id,
            scale=scale,
            model=W.WEAPON_FLOOR_MODEL.get(weapon_id, 0),
            chr_=pad,
            flags=W.OBJFLAG_FALL,
        ))


def add_ammo_row(
    g: MapDef,
    pads: list[int],
    *,
    ammotype: int = W.AMMOTYPE_PISTOL,
    scale: int = 0x0019,
    model: int = W.MODEL_MULTI_AMMO_CRATE,
) -> None:
    """Place floor ammo props. Multi-ammo crate model uses OBJTYPE_MULTIAMMOCRATE
    (retail HTM bank pads / ammocratemulti) so scenario code can find them."""
    for pad in pads:
        if model == W.MODEL_MULTI_AMMO_CRATE:
            g.add_prop(AmmoCrateMulti(
                scale=scale,
                model=model,
                pad=pad,
                flags=W.OBJFLAG_FALL,
                flags2=W.OBJFLAG2_IMMUNETOANTI,
                maxdamage=1000,
            ))
        else:
            g.add_prop(AmmoCrate(
                ammotype=ammotype,
                scale=scale,
                model=model,
                pad=pad,
                flags=W.OBJFLAG_FALL,
                flags2=W.OBJFLAG2_IMMUNETOANTI,
                maxdamage=1000,
            ))


def floor_box_tiles(
    name: str,
    *,
    half: float = 5000.0,
    y: float = 0.0,
    room_index: int = 1,
) -> dict:
    """Single-room floor collision matching a centred box arena."""
    room_key = f"ROOM_{name.upper()}_{room_index:04d}"
    return {
        "rooms": {
            f"ROOM_{name.upper()}_0000": [],
            room_key: [floor_tile(half=half, y=y)],
        }
    }


# Visible box seg faces are render-only; perimeter blocking uses vertical wall tiles
# (GEOFLAG_WALL via flag0004). Match stock wall tiles: no floor bits, block LOS/shoot.
_WALL_TILE_FLAGS = {
    "flag0001": False,
    "flag0002": False,
    "flag0004": True,
    "flag0008": True,
    "flag0010": True,
    "flag0020": False,
    "ladder": False,
    "flag0080": False,
    "flag0100": False,
    "underwater": False,
    "flag0400": False,
    "aibotcrouch": False,
    "aibotduck": False,
    "flag2000": False,
    "die": False,
    "climbableledge": False,
}


def wall_tile(
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
    v3: tuple[float, float, float],
    *,
    floorcolour: int = 4095,
    floortype: str = "default",
) -> dict:
    """Vertical collision quad (four corners, Y may vary)."""
    return {
        **_WALL_TILE_FLAGS,
        "floortype": floortype,
        "floorcolour": floorcolour,
        "vertices": [
            {"x": int(v0[0]), "y": int(v0[1]), "z": int(v0[2])},
            {"x": int(v1[0]), "y": int(v1[1]), "z": int(v1[2])},
            {"x": int(v2[0]), "y": int(v2[1]), "z": int(v2[2])},
            {"x": int(v3[0]), "y": int(v3[1]), "z": int(v3[2])},
        ],
    }


def box_perimeter_wall_tiles(
    *,
    half: float,
    height: float,
    y: float = 0.0,
) -> list[dict]:
    """Four vertical wall quads aligned with ``seg._faces`` wall indices 2..5."""
    h = int(half)
    t = int(height)
    yi = int(y)
    return [
        wall_tile((-h, yi, -h), (h, yi, -h), (h, t, -h), (-h, t, -h)),  # -Z
        wall_tile((h, yi, -h), (h, yi, h), (h, t, h), (h, t, -h)),      # +X
        wall_tile((h, yi, h), (-h, yi, h), (-h, t, h), (h, t, h)),      # +Z
        wall_tile((-h, yi, h), (-h, yi, -h), (-h, t, -h), (-h, t, h)),  # -X
    ]


def floor_box_with_walls(
    name: str,
    *,
    half: float = 5000.0,
    height: float = 3000.0,
    y: float = 0.0,
    room_index: int = 1,
) -> dict:
    """Floor plus perimeter wall collision for visible full/box seg arenas."""
    room_key = f"ROOM_{name.upper()}_{room_index:04d}"
    tiles = [floor_tile(half=half, y=y)]
    tiles.extend(box_perimeter_wall_tiles(half=half, height=height, y=y))
    return {
        "rooms": {
            f"ROOM_{name.upper()}_0000": [],
            room_key: tiles,
        }
    }


# Overlap-pad lesson marker — tiles carry collision; seg draws the visible square
# (tiles are collision-only — same pattern as KOTH/CTF zone markers).
CENTER_MARKER_HALF = 250.0
CENTER_MARKER_RING_WIDTH = 50.0
CENTER_MARKER_SEG_Y_OFFSET = 4.0
CENTER_MARKER_COLOUR = 1709  # green tint (same family as KOTH zone tiles)


def floor_box_with_center_marker(
    name: str,
    *,
    half: float = 5000.0,
    y: float = 0.0,
    room_index: int = 1,
    marker_half: float = CENTER_MARKER_HALF,
    marker_colour: int = CENTER_MARKER_COLOUR,
) -> dict:
    """Grey box floor with a contrasting square at the origin (overlap-pad demos)."""
    room_key = f"ROOM_{name.upper()}_{room_index:04d}"
    m = float(marker_half)
    tiles = _floor_tiles_minus_rect(half, y, 0.0, 0.0, m, floorcolour=4095)
    tiles.append(tile_quad(-m, -m, m, m, y=y, floorcolour=marker_colour))
    return {
        "rooms": {
            f"ROOM_{name.upper()}_0000": [],
            room_key: tiles,
        }
    }


def center_marker_all_floor_faces(
    half: float,
    *,
    center_x: float = 0.0,
    center_z: float = 0.0,
    marker_half: float = CENTER_MARKER_HALF,
    ring_width: float = CENTER_MARKER_RING_WIDTH,
    y: float = 0.0,
) -> list[tuple]:
    """Floor quads for seg room 1: grey arena shell, dark ring, green centre square.

    Returns faces as ``((x0,y,z0), (x1,y,z0), (x1,y,z1), (x0,y,z1), colour_index)``.
    Colour indices: 0=arena, 1=ring, 2=green marker (layered above ring to avoid z-fight).
    """
    cut_outer = marker_half + ring_width
    arena_tiles = _floor_tiles_minus_rect(
        half, y, center_x, center_z, cut_outer, floorcolour=4095
    )
    ring_y = y + CTF_SEG_RING_Y_OFFSET
    ring_tiles = hill_ring_tiles(
        center_x, center_z, marker_half, ring_width, y=ring_y, floorcolour=4095
    )
    arena_tiles.extend(ring_tiles)
    marker_y = y + CENTER_MARKER_SEG_Y_OFFSET
    marker_tile = tile_quad(
        center_x - marker_half,
        center_z - marker_half,
        center_x + marker_half,
        center_z + marker_half,
        y=marker_y,
    )

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        fy = int(vs[0]["y"])
        return (
            (vs[0]["x"], fy, vs[0]["z"]),
            (vs[3]["x"], fy, vs[3]["z"]),
            (vs[2]["x"], fy, vs[2]["z"]),
            (vs[1]["x"], fy, vs[1]["z"]),
            colour_index,
        )

    n_arena = len(arena_tiles) - len(ring_tiles)
    faces = [
        _tile_to_face(t, 1 if i >= n_arena else 0)
        for i, t in enumerate(arena_tiles)
    ]
    faces.append(_tile_to_face(marker_tile, 2))
    return faces


def center_marker_face_colours() -> list[int]:
    """Seg colour table for ``center_marker_all_floor_faces``."""
    return [HILL_SEG_ARENA_RGBA, HILL_SEG_RING_RGBA, HILL_SEG_ZONE_RGBA]


def cover_markers_from_mapdef(mapdef: MapDef) -> list[tuple[float, float]]:
    """Return (x, z) positions for visible cover-point floor markers."""
    return [(c.x, c.z) for c in mapdef.covers]


def marker_positions_all_floor_faces(
    half: float,
    positions: list[tuple[float, float]],
    *,
    marker_half: float = CENTER_MARKER_HALF,
    ring_width: float = CENTER_MARKER_RING_WIDTH,
    y: float = 0.0,
) -> list[tuple]:
    """Floor quads for seg room 1: grey arena, dark rings, green squares at each position."""
    if not positions:
        return center_marker_all_floor_faces(
            half,
            center_x=0.0,
            center_z=0.0,
            marker_half=marker_half,
            ring_width=ring_width,
            y=y,
        )

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        fy = int(vs[0]["y"])
        return (
            (vs[0]["x"], fy, vs[0]["z"]),
            (vs[3]["x"], fy, vs[3]["z"]),
            (vs[2]["x"], fy, vs[2]["z"]),
            (vs[1]["x"], fy, vs[1]["z"]),
            colour_index,
        )

    cut_outer = marker_half + ring_width
    cuts = [(cx, cz, cut_outer) for cx, cz in positions]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=4095)
    faces = [_tile_to_face(t, 0) for t in arena_tiles]

    seen_rings: set[tuple[int, int, int, int, int]] = set()
    for cx, cz in positions:
        ring_y = y + CTF_SEG_RING_Y_OFFSET
        for ring_tile in hill_ring_tiles(
            cx, cz, marker_half, ring_width, y=ring_y, floorcolour=4095
        ):
            key = _ctf_ring_quad_key(ring_tile, ring_y)
            if key in seen_rings:
                continue
            seen_rings.add(key)
            faces.append(_tile_to_face(ring_tile, 1))

    marker_y = y + CENTER_MARKER_SEG_Y_OFFSET
    for cx, cz in positions:
        marker_tile = tile_quad(
            cx - marker_half,
            cz - marker_half,
            cx + marker_half,
            cz + marker_half,
            y=marker_y,
        )
        faces.append(_tile_to_face(marker_tile, 2))
    return faces


def floor_box_with_cover_markers(
    name: str,
    *,
    half: float = 5000.0,
    y: float = 0.0,
    room_index: int = 1,
    markers: list[tuple[float, float]],
    marker_half: float = CENTER_MARKER_HALF,
    ring_width: float = CENTER_MARKER_RING_WIDTH,
    marker_colour: int = CENTER_MARKER_COLOUR,
) -> dict:
    """Grey box floor with green squares at AI cover positions (collision + seg markers)."""
    room_key = f"ROOM_{name.upper()}_{room_index:04d}"
    if not markers:
        return floor_box_tiles(name, half=half, y=y, room_index=room_index)
    cut_outer = marker_half + ring_width
    cuts = [(cx, cz, cut_outer) for cx, cz in markers]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=4095)
    seen_rings: set[tuple[int, int, int, int, int]] = set()
    m = float(marker_half)
    for cx, cz in markers:
        _append_unique_ctf_ring_tiles(
            arena_tiles,
            cx,
            cz,
            marker_half,
            ring_width,
            y=y,
            floorcolour=4095,
            seen=seen_rings,
        )
        arena_tiles.append(
            tile_quad(
                cx - m,
                cz - m,
                cx + m,
                cz + m,
                y=y,
                floorcolour=marker_colour,
            )
        )
    return {
        "rooms": {
            f"ROOM_{name.upper()}_0000": [],
            room_key: arena_tiles,
        }
    }


def floor_tile(*, half: float = 5000.0, y: float = 0.0) -> dict:
    h = int(half)
    yi = int(y)
    return {
        **_DEFAULT_FLAGS,
        "floortype": "default",
        "floorcolour": 4095,
        "vertices": [
            {"x": -h, "y": yi, "z": -h},
            {"x": -h, "y": yi, "z": h},
            {"x": h, "y": yi, "z": h},
            {"x": h, "y": yi, "z": -h},
        ],
    }


# KOTH capture zones are room-based (see kingofthehill.inc). A single-room box
# arena makes the entire floor the hill with no visible boundary. Use a dedicated
# hill room (typically room 2) plus contrasting floor tiles and a ring marker.
HILL_ZONE_HALF = 600.0
HILL_RING_WIDTH = 100.0
HILL_ZONE_COLOUR = 1709
HILL_RING_COLOUR = 818
HILL_ROOM_INDEX = 2

# Seg floor colours (RGBA8) for KOTH box arenas — tiles are collision-only; the
# engine tints *seg* room geometry green via kingofthehill.inc (room 2).
HILL_SEG_ARENA_RGBA = 0xD0D0D0FF
HILL_SEG_RING_RGBA = 0x303030FF
HILL_SEG_ZONE_RGBA = 0x40AA40FF


def tile_quad(
    x0: float,
    z0: float,
    x1: float,
    z1: float,
    *,
    y: float = 0.0,
    floorcolour: int = 4095,
    floortype: str = "default",
) -> dict:
    """Axis-aligned floor quad (4 vertices, Y-up)."""
    yi = int(y)
    return {
        **_DEFAULT_FLAGS,
        "floortype": floortype,
        "floorcolour": floorcolour,
        "vertices": [
            {"x": int(x0), "y": yi, "z": int(z0)},
            {"x": int(x0), "y": yi, "z": int(z1)},
            {"x": int(x1), "y": yi, "z": int(z1)},
            {"x": int(x1), "y": yi, "z": int(z0)},
        ],
    }


def _floor_tiles_minus_rect(
    half: float,
    y: float,
    cx: float,
    cz: float,
    cut_half: float,
    *,
    floorcolour: int = 4095,
) -> list[dict]:
    """Full box floor tiles with a square hole removed (room 1 arena shell)."""
    h = int(half)
    x0, x1 = int(cx - cut_half), int(cx + cut_half)
    z0, z1 = int(cz - cut_half), int(cz + cut_half)
    tiles: list[dict] = []
    if z0 > -h:
        tiles.append(tile_quad(-h, -h, h, z0, y=y, floorcolour=floorcolour))
    if z1 < h:
        tiles.append(tile_quad(-h, z1, h, h, y=y, floorcolour=floorcolour))
    tiles.append(tile_quad(-h, max(z0, -h), x0, min(z1, h), y=y, floorcolour=floorcolour))
    tiles.append(tile_quad(x1, max(z0, -h), h, min(z1, h), y=y, floorcolour=floorcolour))
    return tiles


def hill_ring_tiles(
    cx: float,
    cz: float,
    hill_half: float,
    ring_width: float,
    *,
    y: float = 0.0,
    floorcolour: int = HILL_RING_COLOUR,
) -> list[dict]:
    """Four strip tiles forming a visible ring outside the hill capture square."""
    r = int(hill_half)
    w = int(ring_width)
    outer = r + w
    return [
        tile_quad(cx - outer, cz + r, cx + outer, cz + outer, y=y, floorcolour=floorcolour),
        tile_quad(cx - outer, cz - outer, cx + outer, cz - r, y=y, floorcolour=floorcolour),
        tile_quad(cx - outer, cz - r, cx - r, cz + r, y=y, floorcolour=floorcolour),
        tile_quad(cx + r, cz - r, cx + outer, cz + r, y=y, floorcolour=floorcolour),
    ]


def floor_box_with_hill_zone(
    name: str,
    *,
    half: float,
    y: float = 0.0,
    hill_center_x: float,
    hill_center_z: float,
    hill_half: float = HILL_ZONE_HALF,
    ring_width: float = HILL_RING_WIDTH,
    arena_room_index: int = 1,
    hill_room_index: int = HILL_ROOM_INDEX,
    arena_colour: int = 4095,
    hill_colour: int = HILL_ZONE_COLOUR,
    ring_colour: int = HILL_RING_COLOUR,
) -> dict:
    """Box arena with a marked KOTH hill: ring tiles in room 1, capture floor in room 2.

    Hill capture scoring uses ``prop->rooms[0] == hill pad room`` on stock maps.
    pdmap box arenas keep players in seg room 1; the engine uses position bounds
    (``PDMAP_KOTH_HILL_HALF``) via ``kohPropInHill()`` instead.
    Room 1 therefore must include a collision quad over the hill square; room 2 keeps
    the same footprint for ``LIGHTOP_HIGHLIGHT`` / ``prop->rooms`` when seg room 2
    exists on stock maps.
    """
    cut_outer = hill_half + ring_width
    arena_tiles = _floor_tiles_minus_rect(
        half, y, hill_center_x, hill_center_z, cut_outer, floorcolour=arena_colour
    )
    arena_tiles.extend(
        hill_ring_tiles(
            hill_center_x,
            hill_center_z,
            hill_half,
            ring_width,
            y=y,
            floorcolour=ring_colour,
        )
    )
    hill_tile = tile_quad(
        hill_center_x - hill_half,
        hill_center_z - hill_half,
        hill_center_x + hill_half,
        hill_center_z + hill_half,
        y=y,
        floorcolour=hill_colour,
        floortype="carpet",
    )
    # Room 1 hill quad: collision under the green seg floor (see docstring above).
    arena_tiles.append(
        tile_quad(
            hill_center_x - hill_half,
            hill_center_z - hill_half,
            hill_center_x + hill_half,
            hill_center_z + hill_half,
            y=y,
            floorcolour=arena_colour,
        )
    )
    prefix = name.upper()
    return {
        "rooms": {
            f"ROOM_{prefix}_0000": [],
            f"ROOM_{prefix}_{arena_room_index:04d}": arena_tiles,
            f"ROOM_{prefix}_{hill_room_index:04d}": [hill_tile],
        }
    }


def hill_zone_floor_faces(
    half: float,
    hill_center_x: float,
    hill_center_z: float,
    *,
    hill_half: float = HILL_ZONE_HALF,
    ring_width: float = HILL_RING_WIDTH,
    y: float = 0.0,
) -> tuple[list[tuple], list[int]]:
    """Floor quads for seg room 1 (arena shell + dark ring) and room 2 (hill square).

    Returns ``(arena_faces, hill_faces)`` where each face is
    ``((x0,y,z0), (x1,y,z0), (x1,y,z1), (x0,y,z1), colour_index)``.
    """
    yi = int(y)
    cut_outer = hill_half + ring_width
    arena_tiles = _floor_tiles_minus_rect(
        half, y, hill_center_x, hill_center_z, cut_outer, floorcolour=4095
    )
    arena_tiles.extend(
        hill_ring_tiles(
            hill_center_x, hill_center_z, hill_half, ring_width, y=y, floorcolour=4095
        )
    )
    hill_tile = tile_quad(
        hill_center_x - hill_half,
        hill_center_z - hill_half,
        hill_center_x + hill_half,
        hill_center_z + hill_half,
        y=y,
    )

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        return (
            (vs[0]["x"], yi, vs[0]["z"]),
            (vs[3]["x"], yi, vs[3]["z"]),
            (vs[2]["x"], yi, vs[2]["z"]),
            (vs[1]["x"], yi, vs[1]["z"]),
            colour_index,
        )

    arena_faces = [
        _tile_to_face(t, 1 if i >= len(arena_tiles) - 4 else 0)
        for i, t in enumerate(arena_tiles)
    ]
    hill_faces = [_tile_to_face(hill_tile, 2)]
    return arena_faces, hill_faces


def hill_zone_all_floor_faces(
    half: float,
    hill_center_x: float,
    hill_center_z: float,
    *,
    hill_half: float = HILL_ZONE_HALF,
    ring_width: float = HILL_RING_WIDTH,
    y: float = 0.0,
) -> list[tuple]:
    """All KOTH floor quads for a single-room seg (arena + ring + hill square).

    Tile room 2 still owns KOTH highlight; room 1 carries matching collision quads
    via ``floor_box_with_hill_zone`` because pdmap box segs stay single-room.
    Seg draws every marker in room 1 so ``convertRoomGfxData`` stays on the
    proven single-room path (multi-room custom segs crash in relinkPtr).
    """
    arena_faces, hill_faces = hill_zone_floor_faces(
        half, hill_center_x, hill_center_z,
        hill_half=hill_half, ring_width=ring_width, y=y,
    )
    return arena_faces + hill_faces


def hill_zone_center_from_mapdef(mapdef: MapDef) -> tuple[float, float] | None:
    """Return (x, z) of the first Hill intro pad, or None if no hill anchors."""
    for cmd in mapdef.intro:
        if isinstance(cmd, Hill):
            pad = mapdef.pads[cmd.pad]
            return (pad.x, pad.z)
    return None


# CTF delivery / case pads — visible floor markers (ring + team-coloured square).
CTF_ZONE_HALF = 400.0
CTF_RING_WIDTH = 80.0
CTF_RING_COLOUR = HILL_RING_COLOUR
# Seg/tile marker Y offsets (arena collision stays at y=0). Case+respawn pairs on
# the testarena fixture sit 200 units apart while zone_half=400, so inner squares
# and shared-axis rings would coplanar z-fight at y=0 without layered markers.
CTF_SEG_RING_Y_OFFSET = 2.0
CTF_SEG_CASE_Y_OFFSET = 4.0
CTF_SEG_RESPAWN_Y_OFFSET = 6.0
# 12-bit floorcolour (RRRR GGGG BBBB) aligned with g_TeamColours RGB ordering.
CTF_TEAM_FLOOR_COLOUR = (0xF00, 0xFF0, 0x00F, 0xF0F)
# Seg floor RGBA8: arena grey, dark ring, then per-team zone tints.
CTF_SEG_ARENA_RGBA = HILL_SEG_ARENA_RGBA
CTF_SEG_RING_RGBA = HILL_SEG_RING_RGBA
CTF_TEAM_SEG_RGBA = (
    0xFF4040FF,  # team 0 red — delivery zone
    0xFFFF40FF,  # team 1 yellow
    0x4040FFFF,  # team 2 blue
    0xFF40FFFF,  # team 3 magenta
)
# Muted tint for Case (briefcase spawn) pads when both are marked.
CTF_CASE_SEG_RGBA = (
    0x804040FF,
    0x808040FF,
    0x404080FF,
    0x804080FF,
)


def ctf_team_floor_colour(team: int) -> int:
    """Tile floorcolour for a CTF team index (0–3)."""
    return CTF_TEAM_FLOOR_COLOUR[team % len(CTF_TEAM_FLOOR_COLOUR)]


def ctf_zone_marker_y(*, base_y: float, is_respawn: bool) -> float:
    """Y for a visible CTF zone square (case vs delivery respawn layering)."""
    offset = CTF_SEG_RESPAWN_Y_OFFSET if is_respawn else CTF_SEG_CASE_Y_OFFSET
    return base_y + offset


def _ctf_ring_quad_key(tile: dict, y: float) -> tuple[int, int, int, int, int]:
    """Hashable key for deduplicating identical ring strip quads."""
    vs = tile["vertices"]
    return (int(y), vs[0]["x"], vs[0]["z"], vs[2]["x"], vs[2]["z"])


def _append_unique_ctf_ring_tiles(
    out: list[dict],
    cx: float,
    cz: float,
    zone_half: float,
    ring_width: float,
    *,
    y: float,
    floorcolour: int,
    seen: set[tuple[int, int, int, int, int]],
) -> None:
    """Add ring strips once per unique footprint (shared-axis case pairs reuse rings)."""
    ring_y = y + CTF_SEG_RING_Y_OFFSET
    for ring_tile in hill_ring_tiles(
        cx, cz, zone_half, ring_width, y=ring_y, floorcolour=floorcolour
    ):
        key = _ctf_ring_quad_key(ring_tile, ring_y)
        if key in seen:
            continue
        seen.add(key)
        out.append(ring_tile)


def ctf_zones_from_mapdef(mapdef: MapDef) -> list[tuple[float, float, int, bool]]:
    """Return CTF marker zones as (center_x, center_z, team, is_respawn).

    ``is_respawn`` is True for CaseRespawn pads (delivery / score zone).
    """
    zones: list[tuple[float, float, int, bool]] = []
    for cmd in mapdef.intro:
        if isinstance(cmd, Case):
            pad = mapdef.pads[cmd.pad]
            zones.append((pad.x, pad.z, cmd.team, False))
        elif isinstance(cmd, CaseRespawn):
            pad = mapdef.pads[cmd.pad]
            zones.append((pad.x, pad.z, cmd.team, True))
    return zones


def _subtract_rect_from_quad(
    xmin: float,
    zmin: float,
    xmax: float,
    zmax: float,
    hx0: float,
    hz0: float,
    hx1: float,
    hz1: float,
    *,
    y: float,
    floorcolour: int,
) -> list[dict]:
    """Axis-aligned quad minus a rectangular hole (non-overlapping pieces)."""
    if hx1 <= xmin or hx0 >= xmax or hz1 <= zmin or hz0 >= zmax:
        return [tile_quad(xmin, zmin, xmax, zmax, y=y, floorcolour=floorcolour)]
    pieces: list[dict] = []
    if hz0 > zmin:
        pieces.append(tile_quad(xmin, zmin, xmax, hz0, y=y, floorcolour=floorcolour))
    if hz1 < zmax:
        pieces.append(tile_quad(xmin, hz1, xmax, zmax, y=y, floorcolour=floorcolour))
    pieces.append(
        tile_quad(xmin, max(hz0, zmin), min(hx0, xmax), min(hz1, zmax), y=y, floorcolour=floorcolour)
    )
    pieces.append(
        tile_quad(max(hx1, xmin), max(hz0, zmin), xmax, min(hz1, zmax), y=y, floorcolour=floorcolour)
    )
    out: list[dict] = []
    for piece in pieces:
        vs = piece["vertices"]
        if vs[2]["x"] > vs[0]["x"] and vs[1]["z"] > vs[0]["z"]:
            out.append(piece)
    return out


def _floor_tiles_minus_zones(
    half: float,
    y: float,
    cuts: list[tuple[float, float, float]],
    *,
    floorcolour: int = 4095,
) -> list[dict]:
    """Full box floor with square holes removed for each (cx, cz, cut_half)."""
    h = int(half)
    tiles = [tile_quad(-h, -h, h, h, y=y, floorcolour=floorcolour)]
    for cx, cz, cut_half in cuts:
        co = int(cut_half)
        hx0, hx1 = int(cx - co), int(cx + co)
        hz0, hz1 = int(cz - co), int(cz + co)
        new_tiles: list[dict] = []
        for tile in tiles:
            vs = tile["vertices"]
            new_tiles.extend(
                _subtract_rect_from_quad(
                    vs[0]["x"],
                    vs[0]["z"],
                    vs[2]["x"],
                    vs[2]["z"],
                    hx0,
                    hz0,
                    hx1,
                    hz1,
                    y=y,
                    floorcolour=floorcolour,
                )
            )
        tiles = new_tiles
    return tiles


def floor_box_with_ctf_zones(
    name: str,
    *,
    half: float,
    y: float = 0.0,
    zones: list[tuple[float, float, int, bool]],
    zone_half: float = CTF_ZONE_HALF,
    ring_width: float = CTF_RING_WIDTH,
    arena_room_index: int = 1,
    arena_colour: int = 4095,
    ring_colour: int = CTF_RING_COLOUR,
) -> dict:
    """Box arena with marked CTF pads: dark ring + team-coloured square per zone.

    Each zone entry is ``(center_x, center_z, team, is_respawn)``. CaseRespawn
    pads use full team ``floorcolour``; Case pads use the same hue at lower seg
    opacity (see ``ctf_zone_all_floor_faces``). Room 1 carries all collision quads.
    """
    cut_outer = zone_half + ring_width
    cuts = [(cx, cz, cut_outer) for cx, cz, _, _ in zones]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=arena_colour)
    seen_rings: set[tuple[int, int, int, int, int]] = set()
    for cx, cz, team, is_respawn in zones:
        _append_unique_ctf_ring_tiles(
            arena_tiles,
            cx,
            cz,
            zone_half,
            ring_width,
            y=y,
            floorcolour=ring_colour,
            seen=seen_rings,
        )
        zone_colour = ctf_team_floor_colour(team)
        marker_y = ctf_zone_marker_y(base_y=y, is_respawn=is_respawn)
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=marker_y,
                floorcolour=zone_colour,
                floortype="carpet" if is_respawn else "default",
            )
        )
        # Collision under the coloured seg marker (same pattern as KOTH hill quad).
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=y,
                floorcolour=arena_colour,
            )
        )
    prefix = name.upper()
    return {
        "rooms": {
            f"ROOM_{prefix}_0000": [],
            f"ROOM_{prefix}_{arena_room_index:04d}": arena_tiles,
        }
    }


def ctf_zone_all_floor_faces(
    half: float,
    zones: list[tuple[float, float, int, bool]],
    *,
    zone_half: float = CTF_ZONE_HALF,
    ring_width: float = CTF_RING_WIDTH,
    y: float = 0.0,
) -> list[tuple]:
    """All CTF floor quads for seg room 1 (arena shell, rings, team squares).

    Returns faces as ``((x0,y,z0), (x1,y,z0), (x1,y,z1), (x0,y,z1), colour_index)``.
    Colour indices: 0=arena, 1=ring, 2+ = one per zone (respawn bright, case muted).
    """
    cut_outer = zone_half + ring_width
    cuts = [(cx, cz, cut_outer) for cx, cz, _, _ in zones]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=4095)

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        fy = int(vs[0]["y"])
        return (
            (vs[0]["x"], fy, vs[0]["z"]),
            (vs[3]["x"], fy, vs[3]["z"]),
            (vs[2]["x"], fy, vs[2]["z"]),
            (vs[1]["x"], fy, vs[1]["z"]),
            colour_index,
        )

    faces = [_tile_to_face(t, 0) for t in arena_tiles]
    zone_colour_idx = 2
    seen_rings: set[tuple[int, int, int, int, int]] = set()
    for cx, cz, _team, is_respawn in zones:
        ring_y = y + CTF_SEG_RING_Y_OFFSET
        for ring_tile in hill_ring_tiles(
            cx, cz, zone_half, ring_width, y=ring_y, floorcolour=4095
        ):
            key = _ctf_ring_quad_key(ring_tile, ring_y)
            if key in seen_rings:
                continue
            seen_rings.add(key)
            faces.append(_tile_to_face(ring_tile, 1))
        marker_y = ctf_zone_marker_y(base_y=y, is_respawn=is_respawn)
        zone_tile = tile_quad(
            cx - zone_half,
            cz - zone_half,
            cx + zone_half,
            cz + zone_half,
            y=marker_y,
        )
        faces.append(_tile_to_face(zone_tile, zone_colour_idx))
        zone_colour_idx += 1
    return faces


def ctf_zone_face_colours(zones: list[tuple[float, float, int, bool]]) -> list[int]:
    """Seg colour table for ``ctf_zone_all_floor_faces`` (arena, ring, per-zone)."""
    colours = [CTF_SEG_ARENA_RGBA, CTF_SEG_RING_RGBA]
    for _, _, team, is_respawn in zones:
        palette = CTF_TEAM_SEG_RGBA if is_respawn else CTF_CASE_SEG_RGBA
        colours.append(palette[team % len(palette)])
    return colours


def floor_box_with_hill_and_ctf_zones(
    name: str,
    *,
    half: float,
    y: float = 0.0,
    hill_center_x: float,
    hill_center_z: float,
    zones: list[tuple[float, float, int, bool]],
    hill_half: float = HILL_ZONE_HALF,
    hill_ring_width: float = HILL_RING_WIDTH,
    zone_half: float = CTF_ZONE_HALF,
    ctf_ring_width: float = CTF_RING_WIDTH,
    arena_room_index: int = 1,
    hill_room_index: int = HILL_ROOM_INDEX,
    arena_colour: int = 4095,
    hill_colour: int = HILL_ZONE_COLOUR,
    hill_ring_colour: int = HILL_RING_COLOUR,
    ctf_ring_colour: int = CTF_RING_COLOUR,
) -> dict:
    """Box arena combining KOTH hill tiles (room 2) and CTF pad markers (room 1).

    Used by composite curriculum maps (e.g. learn_10): grey arena shell with square
    holes for hill + each CTF zone, dark rings, team-coloured CTF squares, and the
    usual hill capture quad in room 2 with matching room-1 collision.
    """
    cuts: list[tuple[float, float, float]] = [
        (hill_center_x, hill_center_z, hill_half + hill_ring_width),
    ]
    cuts.extend(
        (cx, cz, zone_half + ctf_ring_width) for cx, cz, _, _ in zones
    )
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=arena_colour)

    seen_rings: set[tuple[int, int, int, int, int]] = set()
    for cx, cz, team, is_respawn in zones:
        _append_unique_ctf_ring_tiles(
            arena_tiles,
            cx,
            cz,
            zone_half,
            ctf_ring_width,
            y=y,
            floorcolour=ctf_ring_colour,
            seen=seen_rings,
        )
        zone_colour = ctf_team_floor_colour(team)
        marker_y = ctf_zone_marker_y(base_y=y, is_respawn=is_respawn)
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=marker_y,
                floorcolour=zone_colour,
                floortype="carpet" if is_respawn else "default",
            )
        )
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=y,
                floorcolour=arena_colour,
            )
        )

    arena_tiles.extend(
        hill_ring_tiles(
            hill_center_x,
            hill_center_z,
            hill_half,
            hill_ring_width,
            y=y,
            floorcolour=hill_ring_colour,
        )
    )
    hill_tile = tile_quad(
        hill_center_x - hill_half,
        hill_center_z - hill_half,
        hill_center_x + hill_half,
        hill_center_z + hill_half,
        y=y,
        floorcolour=hill_colour,
        floortype="carpet",
    )
    arena_tiles.append(
        tile_quad(
            hill_center_x - hill_half,
            hill_center_z - hill_half,
            hill_center_x + hill_half,
            hill_center_z + hill_half,
            y=y,
            floorcolour=arena_colour,
        )
    )
    prefix = name.upper()
    return {
        "rooms": {
            f"ROOM_{prefix}_0000": [],
            f"ROOM_{prefix}_{arena_room_index:04d}": arena_tiles,
            f"ROOM_{prefix}_{hill_room_index:04d}": [hill_tile],
        }
    }


# Pads must sit slightly ABOVE the floor. The engine's ground search
# (cdFindGroundFromList) only accepts a floor whose Y is strictly less than the
# search cylinder's Y (`ground < pos.y`). If a spawn pad is exactly on the floor
# (Y == floor Y) the floor is rejected and the player falls into the void. The
# player is then placed exactly at the floor height, so this small offset does
# NOT cause fall damage. See docs/MAP_CREATION.md §11.1.
PAD_FLOOR_OFFSET = 10.0


def configure_matrix_test_room(half: float = 5000.0, pad_y: float = PAD_FLOOR_OFFSET) -> MapDef:
    """Matrix Test Room (uff) — a fully playable Combat Simulator box arena.

    All pads sit inside the [-half, +half] floor box (so players spawn on the
    visible, walled floor rather than in the void) and at ``pad_y`` just above
    the floor (so the ground search accepts the floor). The layout assumes
    ``half >= 4200`` (the outermost case pads sit at +/-4200).
    """
    g = MapDef("uff")

    spawn_positions = [
        (-4000, -4000), (4000, -4000), (-4000, 4000), (4000, 4000),
        (-2000, -2000), (2000, -2000), (-2000, 2000), (2000, 2000),
        (0, -3000), (0, 3000), (-3000, 0), (3000, 0),
        (-1000, -1000), (1000, -1000), (-1000, 1000), (1000, 1000),
    ]
    add_spawn_grid(g, spawn_positions, y=pad_y)

    weapon_layout = [
        (16, W.WEAPON_FALCON2), (17, W.WEAPON_MAGSEC4), (18, W.WEAPON_MAULER),
        (19, W.WEAPON_CMP150), (20, W.WEAPON_SUPERDRAGON), (21, W.WEAPON_LAPTOPGUN),
        (22, W.WEAPON_ROCKETLAUNCHER), (23, W.WEAPON_SNIPERRIFLE),
        (24, W.WEAPON_CROSSBOW), (25, W.WEAPON_TRANQUILIZER),
    ]
    for pad, _ in weapon_layout:
        x, z = _pad_xy_for_index(pad)
        g.add_pad(index=pad, x=x, y=pad_y, z=z, room=1)
    add_floor_weapons(g, weapon_layout)

    cases = [(0, 26, 27), (1, 28, 29), (2, 30, 31), (3, 32, 33)]
    for _, case_pad, respawn_pad in cases:
        for pad in (case_pad, respawn_pad):
            x, z = _pad_xy_for_index(pad)
            g.add_pad(index=pad, x=x, y=pad_y, z=z, room=1)

    hill_pads = [34, 35, 36, 37]
    for pad in hill_pads:
        x, z = _pad_xy_for_index(pad)
        g.add_pad(index=pad, x=x, y=pad_y, z=z, room=1)

    add_mp_scenarios(g, cases=cases, hill_pads=hill_pads)

    ammo_pads = list(range(38, 58))
    for pad in ammo_pads:
        x, z = _pad_xy_for_index(pad)
        g.add_pad(index=pad, x=x, y=pad_y, z=z, room=1)
    add_ammo_row(g, ammo_pads)

    add_loadout_intro(g)
    return g


def configure_animation_lab(*, half: float | None = None, pad_y: float = PAD_FLOOR_OFFSET) -> MapDef:
    """Animation parade arena — player south hub, category districts north, props west.

    Grid size, spacing, and arena extent come from ``anim_catalog`` (full named
    catalog). Deploy with ``pdmap build animlab --deploy``; boot via
    ``--test-animlab`` (``STAGE_ANIMLAB``). Uses ``MapDef.anim_parade = True``.
    """
    from .anim_catalog import (
        PARADE_PLAYER_SPAWN_Z,
        PARADE_SPECIAL_X,
        PARADE_SPECIAL_Z,
        parade_arena_half,
        parade_grid_xy,
        parade_slot_markers,
        parade_special_marker,
    )
    from .anim_parade import NUM_GRID_SLOTS, PAD_PARADE_FIRST, PAD_SPECIAL_TOUR
    from .anim_props import add_parade_props

    if half is None:
        half = parade_arena_half()

    slot_meta = {s["slot"]: s for s in parade_slot_markers()}
    g = MapDef("animlab")
    g.anim_parade = True

    # Pad 0: player faces +Z toward the district grid (room 1 south hub).
    g.add_pad(index=0, x=0.0, y=pad_y, z=PARADE_PLAYER_SPAWN_Z, room=1)
    g.add_intro(Spawn(0))

    # Pads 1..N: per-district sub-zone grids; each sub-zone uses its own tile room.
    for slot in range(NUM_GRID_SLOTS):
        meta = slot_meta[slot + 1]
        x, z = parade_grid_xy(slot + 1)
        g.add_pad(
            index=PAD_PARADE_FIRST + slot,
            x=x,
            y=pad_y,
            z=z,
            room=meta["room"],
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        )

    # Full-tour cycler — east of spawn hub (room 1).
    special = parade_special_marker()
    g.add_pad(
        index=PAD_SPECIAL_TOUR,
        x=PARADE_SPECIAL_X,
        y=pad_y,
        z=PARADE_SPECIAL_Z,
        room=special["room"],
        dir_x=-1.0,
        dir_y=0.0,
        dir_z=0.0,
    )

    # Static props — props yard west + computer-district vignette (pads after tour).
    add_parade_props(g, pad_y=pad_y)

    add_loadout_intro(g)
    return g


# Animation lab parade — category-coloured floor markers (visible with SEG_MODE=parade).
PARADE_SEG_MARKER_Y_OFFSET = 4.0
PARADE_SEG_ARENA_RGBA = HILL_SEG_ARENA_RGBA


def floor_box_with_parade_slots(
    name: str,
    *,
    half: float,
    y: float = 0.0,
    slots: list[dict],
    zone_half: float = PARADE_ZONE_HALF,
    arena_room_index: int = 1,
    arena_colour: int = 4095,
) -> dict:
    """Box arena with coloured floor squares under each parade guard cell."""
    cuts = [(s["x"], s["z"], zone_half) for s in slots]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=arena_colour)
    marker_y = y + PARADE_SEG_MARKER_Y_OFFSET
    for slot in slots:
        cx, cz = slot["x"], slot["z"]
        colour = slot["floorColour"]
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=marker_y,
                floorcolour=colour,
                floortype="carpet",
            )
        )
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=y,
                floorcolour=arena_colour,
            )
        )
    prefix = name.upper()
    return {
        "rooms": {
            f"ROOM_{prefix}_0000": [],
            f"ROOM_{prefix}_{arena_room_index:04d}": arena_tiles,
        }
    }


def floor_box_with_parade_zones(
    name: str,
    *,
    half: float,
    y: float = 0.0,
    slots: list[dict],
    zones: list[dict],
    districts: list[dict] | None = None,
    props_district: dict | None = None,
    museum_district: dict | None = None,
    vignette_props: dict | None = None,
    zone_half: float = PARADE_ZONE_HALF,
    arena_room_index: int = 1,
    arena_colour: int = 4095,
) -> dict:
    """Parade arena: room 1 hub + district boundary tiles; rooms 2+ per sub-zone.

    Guard pads use zone tile rooms (≤30 chr/room). District boundary markers use
    category colours on the hub floor (tiles only — avoids seg bgInflate crash).
    """
    base = floor_box_with_parade_slots(
        name,
        half=half,
        y=y,
        slots=slots,
        zone_half=zone_half,
        arena_room_index=arena_room_index,
        arena_colour=arena_colour,
    )
    rooms = dict(base["rooms"])
    prefix = name.upper()
    marker_y = y + PARADE_SEG_MARKER_Y_OFFSET
    hub_tiles = list(rooms.get(f"ROOM_{prefix}_{arena_room_index:04d}", []))

    # North walk spine — hub carpet from spawn toward district grid.
    from .anim_catalog import (
        PARADE_CORRIDOR_COLOUR,
        PARADE_CORRIDOR_END_Z,
        PARADE_PLAYER_SPAWN_Z,
        PARADE_PROPS_HALF,
        PARADE_SPECIAL_X,
        PARADE_SPECIAL_Z,
    )

    hub_tiles.append(
        tile_quad(
            -350.0,
            PARADE_PLAYER_SPAWN_Z + 80.0,
            350.0,
            PARADE_CORRIDOR_END_Z,
            y=marker_y,
            floorcolour=PARADE_CORRIDOR_COLOUR,
            floortype="carpet",
        )
    )
    # Full-tour pad marker (gold carpet east of spawn).
    tour_half = zone_half * 0.85
    hub_tiles.append(
        tile_quad(
            PARADE_SPECIAL_X - tour_half,
            PARADE_SPECIAL_Z - tour_half,
            PARADE_SPECIAL_X + tour_half,
            PARADE_SPECIAL_Z + tour_half,
            y=marker_y,
            floorcolour=_hex_to_floor_colour("#ffd166"),
            floortype="carpet",
        )
    )

    # Category district boundary markers on hub floor (subtle carpet overlay).
    from .anim_catalog import PARADE_DISTRICT_CELL_D, PARADE_DISTRICT_CELL_W

    for district in districts or []:
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        span_cols = int(district.get("spanCols", 1))
        span_rows = int(district.get("spanRows", 1))
        hw = span_cols * PARADE_DISTRICT_CELL_W / 2.0 + 80.0
        hd = span_rows * PARADE_DISTRICT_CELL_D / 2.0 + 80.0
        colour = _hex_to_floor_colour(str(district.get("color", "#505060")))
        hub_tiles.append(
            tile_quad(
                dcx - hw,
                dcz - hd,
                dcx + hw,
                dcz + hd,
                y=marker_y,
                floorcolour=colour,
                floortype="carpet",
            )
        )

    rooms[f"ROOM_{prefix}_{arena_room_index:04d}"] = hub_tiles

    # Props district carpet on hub floor (props pads use room 1).
    if props_district:
        pcx = float(props_district.get("centerX", 0))
        pcz = float(props_district.get("centerZ", 0))
        ph = PARADE_PROPS_HALF
        prop_colour = int(props_district.get("floorColour", 0x38B))
        hub_tiles.append(
            tile_quad(
                pcx - ph,
                pcz - ph,
                pcx + ph,
                pcz + ph,
                y=marker_y,
                floorcolour=prop_colour,
                floortype="carpet",
            )
        )
        rooms[f"ROOM_{prefix}_{arena_room_index:04d}"] = hub_tiles

    # Mirror guard category colours onto hub room 1 (always visible on hub floor).
    for slot in slots:
        if slot.get("isSpecialTour"):
            continue
        scx, scz = slot["x"], slot["z"]
        colour = int(slot.get("floorColour", arena_colour))
        hub_tiles.append(
            tile_quad(
                scx - zone_half,
                scz - zone_half,
                scx + zone_half,
                scz + zone_half,
                y=marker_y,
                floorcolour=colour,
                floortype="carpet",
            )
        )

    # Corridor district bands — coloured strips along the north walk spine.
    if districts:
        band_count = len(districts)
        z_start = PARADE_PLAYER_SPAWN_Z + 120.0
        z_end = PARADE_CORRIDOR_END_Z
        z_step = (z_end - z_start) / max(1, band_count)
        spine_half = 220.0
        for i, district in enumerate(districts):
            colour = _hex_to_floor_colour(str(district.get("color", "#505060")))
            z0 = z_start + i * z_step
            z1 = z_start + (i + 1) * z_step
            hub_tiles.append(
                tile_quad(
                    -spine_half,
                    z0,
                    spine_half,
                    z1,
                    y=marker_y,
                    floorcolour=colour,
                    floortype="carpet",
                )
            )

    # Prop museum wing carpet (far west, room 1).
    if museum_district:
        from .anim_catalog import PARADE_MUSEUM_HALF, PARADE_MUSEUM_CENTER_X, PARADE_PROPS_CENTER_X

        mcx = float(museum_district.get("centerX", 0))
        mcz = float(museum_district.get("centerZ", 0))
        mh = float(museum_district.get("half", PARADE_MUSEUM_HALF))
        museum_colour = int(museum_district.get("floorColour", _hex_to_floor_colour("#0ea5e9")))
        hub_tiles.append(
            tile_quad(
                mcx - mh,
                mcz - mh,
                mcx + mh,
                mcz + mh,
                y=marker_y,
                floorcolour=museum_colour,
                floortype="carpet",
            )
        )
        # Walk path props yard → museum.
        hub_tiles.append(
            tile_quad(
                PARADE_MUSEUM_CENTER_X + mh,
                mcz - 200.0,
                PARADE_PROPS_CENTER_X - PARADE_PROPS_HALF,
                mcz + 200.0,
                y=marker_y,
                floorcolour=PARADE_CORRIDOR_COLOUR,
                floortype="carpet",
            )
        )

    # District vignette entrance carpets at prop positions.
    if vignette_props:
        for prop in vignette_props.get("props") or []:
            px, pz = float(prop["x"]), float(prop["z"])
            colour = int(prop.get("floorColour", arena_colour))
            hub_tiles.append(
                tile_quad(
                    px - 90.0,
                    pz - 90.0,
                    px + 90.0,
                    pz + 90.0,
                    y=marker_y,
                    floorcolour=colour,
                    floortype="carpet",
                )
            )

    rooms[f"ROOM_{prefix}_{arena_room_index:04d}"] = hub_tiles

    margin = zone_half + 40.0
    for zone in zones:
        room_idx = int(zone["room"])
        zslots = zone.get("slots") or []
        if not zslots:
            continue
        xs = [s["x"] for s in zslots]
        zs = [s["z"] for s in zslots]
        xmin, xmax = min(xs) - margin, max(xs) + margin
        zmin, zmax = min(zs) - margin, max(zs) + margin
        zone_tiles = [
            tile_quad(xmin, zmin, xmax, zmax, y=y, floorcolour=arena_colour)
        ]
        # Per-guard category colour markers inside each sub-zone room.
        for slot in zslots:
            scx, scz = slot["x"], slot["z"]
            colour = int(slot.get("floorColour", arena_colour))
            zone_tiles.append(
                tile_quad(
                    scx - zone_half,
                    scz - zone_half,
                    scx + zone_half,
                    scz + zone_half,
                    y=marker_y,
                    floorcolour=colour,
                    floortype="carpet",
                )
            )
            zone_tiles.append(
                tile_quad(
                    scx - zone_half,
                    scz - zone_half,
                    scx + zone_half,
                    scz + zone_half,
                    y=y,
                    floorcolour=arena_colour,
                )
            )
        rooms[f"ROOM_{prefix}_{room_idx:04d}"] = zone_tiles
    return {"rooms": rooms}


def _hex_to_floor_colour(hex_color: str) -> int:
    """12-bit floor colour from ``#RRGGBB``."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) >> 4
    g = int(h[2:4], 16) >> 4
    b = int(h[4:6], 16) >> 4
    return (r << 8) | (g << 4) | b


def _parade_seg_colour_table(slots: list[dict]) -> tuple[list[int], dict[str, int]]:
    """Map slot categories to seg colour indices (vertex byte = (index+1)*4, max ~63)."""
    face_colours = [PARADE_SEG_ARENA_RGBA]
    cat_to_idx: dict[str, int] = {}
    for slot in slots:
        cat = slot.get("category") or "other"
        if cat not in cat_to_idx:
            cat_to_idx[cat] = len(face_colours)
            face_colours.append(slot["segRgba"])
    return face_colours, cat_to_idx


def parade_slot_all_floor_faces(
    half: float,
    slots: list[dict],
    *,
    zone_half: float = PARADE_ZONE_HALF,
    y: float = 0.0,
) -> list[tuple]:
    """All parade floor quads for seg room 1 (arena shell + per-slot coloured squares)."""
    _, cat_to_idx = _parade_seg_colour_table(slots)
    cuts = [(s["x"], s["z"], zone_half) for s in slots]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=4095)

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        fy = int(vs[0]["y"])
        return (
            (vs[0]["x"], fy, vs[0]["z"]),
            (vs[3]["x"], fy, vs[3]["z"]),
            (vs[2]["x"], fy, vs[2]["z"]),
            (vs[1]["x"], fy, vs[1]["z"]),
            colour_index,
        )

    faces = [_tile_to_face(t, 0) for t in arena_tiles]
    marker_y = y + PARADE_SEG_MARKER_Y_OFFSET
    for slot in slots:
        cx, cz = slot["x"], slot["z"]
        cat = slot.get("category") or "other"
        colour_index = cat_to_idx[cat]
        zone_tile = tile_quad(
            cx - zone_half,
            cz - zone_half,
            cx + zone_half,
            cz + zone_half,
            y=marker_y,
        )
        faces.append(_tile_to_face(zone_tile, colour_index))
    return faces


def parade_slot_face_colours(slots: list[dict]) -> list[int]:
    """Seg colour table for ``parade_slot_all_floor_faces`` (arena + per-category)."""
    return _parade_seg_colour_table(slots)[0]


def parade_district_seg_faces(
    half: float,
    districts: list[dict],
    *,
    props_district: dict | None = None,
    museum_district: dict | None = None,
    special: dict | None = None,
    zone_half: float = PARADE_ZONE_HALF,
    y: float = 0.0,
) -> tuple[list[tuple], list[int]]:
    """Arena + district/props/tour raised markers (~12 faces — safe for bgInflate)."""
    from .anim_catalog import (
        PARADE_DISTRICT_CELL_D,
        PARADE_DISTRICT_CELL_W,
        PARADE_PROPS_HALF,
        PARADE_SPECIAL_X,
        PARADE_SPECIAL_Z,
    )

    marker_y = y + PARADE_SEG_MARKER_Y_OFFSET
    arena_tiles = _floor_tiles_minus_zones(half, y, [], floorcolour=4095)
    face_colours: list[int] = [PARADE_SEG_ARENA_RGBA]

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        fy = int(vs[0]["y"])
        return (
            (vs[0]["x"], fy, vs[0]["z"]),
            (vs[3]["x"], fy, vs[3]["z"]),
            (vs[2]["x"], fy, vs[2]["z"]),
            (vs[1]["x"], fy, vs[1]["z"]),
            colour_index,
        )

    faces = [_tile_to_face(t, 0) for t in arena_tiles]

    for district in districts:
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        span_cols = int(district.get("spanCols", 1))
        span_rows = int(district.get("spanRows", 1))
        hw = span_cols * PARADE_DISTRICT_CELL_W / 2.0 + 40.0
        hd = span_rows * PARADE_DISTRICT_CELL_D / 2.0 + 40.0
        rgba = _hex_to_seg_rgba(str(district.get("color", "#505060")))
        face_colours.append(rgba)
        zone_tile = tile_quad(dcx - hw, dcz - hd, dcx + hw, dcz + hd, y=marker_y)
        faces.append(_tile_to_face(zone_tile, len(face_colours) - 1))

    if props_district:
        pcx = float(props_district.get("centerX", 0))
        pcz = float(props_district.get("centerZ", 0))
        ph = PARADE_PROPS_HALF
        rgba = _hex_to_seg_rgba("#38bdf8")
        face_colours.append(rgba)
        zone_tile = tile_quad(pcx - ph, pcz - ph, pcx + ph, pcz + ph, y=marker_y)
        faces.append(_tile_to_face(zone_tile, len(face_colours) - 1))

    if museum_district:
        from .anim_catalog import PARADE_MUSEUM_HALF

        mcx = float(museum_district.get("centerX", 0))
        mcz = float(museum_district.get("centerZ", 0))
        mh = float(museum_district.get("half", PARADE_MUSEUM_HALF))
        rgba = _hex_to_seg_rgba("#0ea5e9")
        face_colours.append(rgba)
        zone_tile = tile_quad(mcx - mh, mcz - mh, mcx + mh, mcz + mh, y=marker_y)
        faces.append(_tile_to_face(zone_tile, len(face_colours) - 1))

    if special:
        sx = float(special.get("x", PARADE_SPECIAL_X))
        sz = float(special.get("z", PARADE_SPECIAL_Z))
        sh = zone_half * 0.85
        rgba = _hex_to_seg_rgba("#ffd166")
        face_colours.append(rgba)
        zone_tile = tile_quad(sx - sh, sz - sh, sx + sh, sz + sh, y=marker_y)
        faces.append(_tile_to_face(zone_tile, len(face_colours) - 1))

    return faces, face_colours


def _hex_to_seg_rgba(hex_color: str, *, alpha: int = 0xFF) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r << 24) | (g << 16) | (b << 8) | alpha


def _pad_xy_for_index(pad: int) -> tuple[float, float]:
    """Pad positions from mods/uff_pads.json (scaled game units / 6)."""
    table: dict[int, tuple[float, float]] = {
        16: (0, 0), 17: (0, -1500), 18: (0, 1500), 19: (-1500, 0), 20: (1500, 0),
        21: (-3500, -3500), 22: (3500, -3500), 23: (-3500, 3500), 24: (3500, 3500),
        25: (-4500, 0),
        26: (-4200, -4200), 27: (-4200, -4000),
        28: (4200, -4200), 29: (4200, -4000),
        30: (-4200, 4200), 31: (-4200, 4000),
        32: (4200, 4200), 33: (4200, 4000),
        34: (0, 500), 35: (0, -500), 36: (-500, 0), 37: (500, 0),
    }
    if pad in table:
        return table[pad]
    if 38 <= pad <= 57:
        row = (pad - 38) // 5
        col = (pad - 38) % 5
        return (-3000 + col * 1500, -3000 + row * 1500)
    return (0.0, 0.0)
