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

    Deploy with ``DEPLOY_AS = \"uff\"`` so ``--test-map`` loads this geometry and
    the parade setup (``MapDef.anim_parade = True``).
    """
    from .anim_parade import NUM_SLOTS, PAD_PARADE_FIRST

    g = MapDef("animlab")
    g.anim_parade = True

    # Pad 0: player faces +Z toward the parade row.
    g.add_pad(index=0, x=0.0, y=pad_y, z=-2500.0, room=1)
    g.add_intro(Spawn(0))

    # Pads 1..12: guard line at z=+2800, spaced 600 units on X.
    span = 600.0 * (NUM_SLOTS - 1)
    x0 = -span / 2.0
    for slot in range(NUM_SLOTS):
        g.add_pad(
            index=PAD_PARADE_FIRST + slot,
            x=x0 + slot * 600.0,
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
