"""High-level helpers for common Combat Simulator map layouts."""

from __future__ import annotations

from .core import MapDef
from .intro import Spawn, Weapon, Ammo, Case, CaseRespawn, Hill
from .props import Weapon as WeaponProp, AmmoCrate
from .tiles import _DEFAULT_FLAGS
from . import weapons as W


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
    for pad in pads:
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
    for cx, cz, team, is_respawn in zones:
        arena_tiles.extend(
            hill_ring_tiles(cx, cz, zone_half, ring_width, y=y, floorcolour=ring_colour)
        )
        zone_colour = ctf_team_floor_colour(team)
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=y,
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
    yi = int(y)
    cut_outer = zone_half + ring_width
    cuts = [(cx, cz, cut_outer) for cx, cz, _, _ in zones]
    arena_tiles = _floor_tiles_minus_zones(half, y, cuts, floorcolour=4095)

    def _tile_to_face(tile: dict, colour_index: int) -> tuple:
        vs = tile["vertices"]
        return (
            (vs[0]["x"], yi, vs[0]["z"]),
            (vs[3]["x"], yi, vs[3]["z"]),
            (vs[2]["x"], yi, vs[2]["z"]),
            (vs[1]["x"], yi, vs[1]["z"]),
            colour_index,
        )

    faces = [_tile_to_face(t, 0) for t in arena_tiles]
    zone_colour_idx = 2
    for cx, cz, _team, _is_respawn in zones:
        for ring_tile in hill_ring_tiles(
            cx, cz, zone_half, ring_width, y=y, floorcolour=4095
        ):
            faces.append(_tile_to_face(ring_tile, 1))
        zone_tile = tile_quad(
            cx - zone_half,
            cz - zone_half,
            cx + zone_half,
            cz + zone_half,
            y=y,
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

    for cx, cz, team, is_respawn in zones:
        arena_tiles.extend(
            hill_ring_tiles(cx, cz, zone_half, ctf_ring_width, y=y, floorcolour=ctf_ring_colour)
        )
        zone_colour = ctf_team_floor_colour(team)
        arena_tiles.append(
            tile_quad(
                cx - zone_half,
                cz - zone_half,
                cx + zone_half,
                cz + zone_half,
                y=y,
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


def configure_animation_lab(*, half: float = 5000.0, pad_y: float = PAD_FLOOR_OFFSET) -> MapDef:
    """Animation parade arena — player south, twelve guards on a north line.

    Deploy with ``pdmap build animlab --deploy``; boot via ``--test-animlab`` (``STAGE_ANIMLAB``).
    the parade setup (``MapDef.anim_parade = True``).
    """
    from .anim_parade import NUM_SLOTS, PAD_PARADE_FIRST

    g = MapDef("animlab")
    g.anim_parade = True

    # Pad 0: player faces +Z toward the parade row.
    g.add_pad(index=0, x=0.0, y=pad_y, z=-2500.0, room=1)
    g.add_intro(Spawn(0))

    # Pads 1..N: guard line at z=+2800; spacing fits inside ±5000 box.
    span = min(9000.0, max(480.0 * (NUM_SLOTS - 1), 600.0))
    spacing = span / max(NUM_SLOTS - 1, 1)
    x0 = -span / 2.0
    for slot in range(NUM_SLOTS):
        g.add_pad(
            index=PAD_PARADE_FIRST + slot,
            x=x0 + slot * spacing,
            y=pad_y,
            z=2800.0,
            room=1,
        )

    add_loadout_intro(g)
    return g


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
