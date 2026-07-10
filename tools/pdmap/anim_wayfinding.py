"""Animation Lab in-world wayfinding — colored spines, compass rose, gate/beacon metadata.

Used by ``builders.floor_box_with_parade_zones`` (carpet tiles), ``anim_props``
(sign/gate/beacon StdObjects), ``anim_lab.html`` (In-game guide panel), and
``validate`` (spawn walk-path audit).
"""

from __future__ import annotations

import math
from typing import Any

from .anim_catalog import (
    OBJECT_CATALOG_HUB_X,
    OBJECT_CATALOG_HUB_Z,
    PARADE_CHARACTERS_CENTER_X,
    PARADE_CHARACTERS_CENTER_Z,
    PARADE_CHARACTERS_COLOUR,
    PARADE_CHARACTERS_HALF,
    PARADE_CORRIDOR_END_Z,
    PARADE_CORRIDOR_HALF_WIDTH,
    PARADE_DISTRICT_ORIGIN_X,
    PARADE_DISTRICT_ORIGIN_Z,
    PARADE_MUSEUM_COLOUR,
    PARADE_PLAYER_SPAWN_Z,
    PARADE_PROPS_CENTER_X,
    PARADE_PROPS_CENTER_Z,
    PARADE_PROPS_HALF,
    PARADE_TRUE_SCALE_MEGA_CENTER_X,
    PARADE_TRUE_SCALE_MEGA_CENTER_Z,
    PARADE_TRUE_SCALE_MEGA_COLOUR,
    PARADE_TRUE_SCALE_NORMAL_CENTER_X,
    PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
    PARADE_TRUE_SCALE_COLOUR,
    _hex_to_floor_colour,
    hub_signpost_entries,
    parade_museum_grid_metrics,
    parade_museum_half,
    parade_true_scale_normal_half,
)

# Distance markers along routes longer than this (world units).
BEACON_INTERVAL = 2000.0
BEACON_MIN_ROUTE_LEN = 3000.0

# Compass rose wedges at spawn plaza (room 1 marker_y carpet).
COMPASS_ROSE_RADIUS = 170.0
COMPASS_ROSE_INNER = 28.0  # keep pad 0 clear


def spawn_corridor_routes() -> list[dict[str, Any]]:
    """Colored carpet rects from spawn hub to each major wing (room 1 spines).

    Returned in paint priority order — callers should apply after wing interiors
    so disjoint clipping keeps wing colours on top.
    """
    hw = PARADE_CORRIDOR_HALF_WIDTH
    spawn_z = PARADE_PLAYER_SPAWN_Z
    routes: list[dict[str, Any]] = []

    def _route(
        rid: str,
        label: str,
        compass: str,
        x0: float,
        z0: float,
        x1: float,
        z1: float,
        color: str,
    ) -> None:
        routes.append(
            {
                "id": rid,
                "label": label,
                "compass": compass,
                "kind": "corridor",
                "x0": x0,
                "z0": z0,
                "x1": x1,
                "z1": z1,
                "color": color,
                "floorColour": _hex_to_floor_colour(color),
            }
        )

    # North spine — animation districts (purple); extend past legacy corridor end to grid mouth.
    north_z_end = PARADE_DISTRICT_ORIGIN_Z - 280.0
    _route(
        "route_north_districts",
        "Animation districts",
        "N",
        -hw,
        spawn_z + 80.0,
        hw,
        north_z_end,
        "#a78bfa",
    )

    # Southwest — props gallery approach (cyan).
    gallery_west = PARADE_PROPS_CENTER_X - PARADE_PROPS_HALF
    _route(
        "route_props_approach",
        "Props gallery approach",
        "SW",
        gallery_west,
        spawn_z - 220.0,
        120.0,
        PARADE_PROPS_CENTER_Z + PARADE_PROPS_HALF,
        "#38bdf8",
    )

    # Catalog megazone — dynamic footprint from packed tag districts.
    cat_metrics = parade_museum_grid_metrics()
    cat_cx = float(cat_metrics.get("centerX", OBJECT_CATALOG_HUB_X))
    cat_cz = float(cat_metrics.get("centerZ", OBJECT_CATALOG_HUB_Z))
    cat_half = float(cat_metrics.get("half", parade_museum_half()))
    catalog_east = cat_cx + cat_half
    path_z_lo = min(PARADE_PROPS_CENTER_Z, cat_cz) - 500.0
    path_z_hi = max(PARADE_PROPS_CENTER_Z, cat_cz) + 500.0
    _route(
        "route_catalog_cross",
        "Props gallery → object catalog",
        "W",
        catalog_east,
        path_z_lo,
        gallery_west,
        path_z_hi,
        PARADE_MUSEUM_COLOUR,
    )
    # Vertical spine along gallery west face — connects props approach to catalog cross.
    _route(
        "route_catalog_spine_z",
        "Catalog approach spine",
        "W",
        gallery_west - hw,
        min(spawn_z - 220.0, path_z_lo),
        gallery_west + hw,
        max(path_z_hi, cat_cz + cat_half),
        PARADE_MUSEUM_COLOUR,
    )
    # East-west strip at catalog latitude — joins spine to megazone hub centre.
    _route(
        "route_catalog_east_spine",
        "Catalog east spine",
        "W",
        gallery_west,
        cat_cz - hw * 0.5,
        cat_cx + cat_half,
        cat_cz + hw * 0.5,
        PARADE_MUSEUM_COLOUR,
    )

    # Shared east hub strip — links spawn to character + true-scale L routes.
    _route(
        "route_east_hub_strip",
        "East hub strip",
        "E",
        80.0,
        spawn_z - 220.0,
        160.0,
        spawn_z + 120.0,
        "#64748b",
    )

    # True-scale normal wing — east spine then west approach (teal L-path).
    ts_half = parade_true_scale_normal_half()
    ts_cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X
    ts_cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
    _route(
        "route_true_scale_east_spine",
        "True-scale east spine",
        "NW",
        120.0 - hw * 0.4,
        spawn_z - 200.0,
        120.0 + hw * 0.4,
        ts_cz,
        PARADE_TRUE_SCALE_COLOUR,
    )
    _route(
        "route_true_scale_approach",
        "True-scale gallery",
        "NW",
        120.0,
        ts_cz - ts_half,
        ts_cx - ts_half,
        ts_cz + ts_half,
        PARADE_TRUE_SCALE_COLOUR,
    )

    # Character gallery (purple-pink).
    # Character gallery (purple-pink) — vertical spine then horizontal approach (L-path).
    ccx = PARADE_CHARACTERS_CENTER_X
    ccz = PARADE_CHARACTERS_CENTER_Z
    ch = PARADE_CHARACTERS_HALF
    _route(
        "route_characters_east_spine",
        "Character gallery east spine",
        "SE",
        120.0 - hw * 0.4,
        spawn_z - 200.0,
        120.0 + hw * 0.4,
        ccz,
        PARADE_CHARACTERS_COLOUR,
    )
    _route(
        "route_characters_approach",
        "Character gallery approach",
        "SE",
        120.0,
        ccz - ch,
        ccx - ch,
        ccz + ch,
        PARADE_CHARACTERS_COLOUR,
    )

    # Megaworld hub spines are painted by ``append_megaworld_hub_tiles`` (wing colours).
    return routes


def append_compass_rose_tiles(
    hub_tiles: list[dict],
    occupied: list[tuple[float, float, float, float]],
    *,
    marker_y: float,
    spawn_x: float = 0.0,
    spawn_z: float = PARADE_PLAYER_SPAWN_Z,
) -> None:
    """Four coloured wedges at spawn — E/W/+Z/-Z matching signpost compass colours."""
    from .builders import _append_disjoint_carpet

    r = COMPASS_ROSE_RADIUS
    inner = COMPASS_ROSE_INNER
    wedges: tuple[tuple[float, float, float, float, str], ...] = (
        # +X east — MP world crimson.
        (spawn_x + inner, spawn_z - r, spawn_x + r, spawn_z + r, "#dc2626"),
        # -X west — object catalog blue.
        (spawn_x - r, spawn_z - r, spawn_x - inner, spawn_z + r, "#0ea5e9"),
        # +Z toward districts — animation purple.
        (spawn_x - r, spawn_z + inner, spawn_x + r, spawn_z + r, "#a78bfa"),
        # -Z back rim — props cyan.
        (spawn_x - r, spawn_z - r, spawn_x + r, spawn_z - inner, "#38bdf8"),
    )
    for x0, z0, x1, z1, colour in wedges:
        _append_disjoint_carpet(
            hub_tiles,
            occupied,
            x0,
            z0,
            x1,
            z1,
            y=marker_y,
            floorcolour=_hex_to_floor_colour(colour),
            floortype="carpet",
        )


def wing_gate_entries() -> list[dict[str, Any]]:
    """Wing entrance gate markers — one prop cluster per major district mouth."""
    from .anim_levels import world_gate_entries

    gates: list[dict[str, Any]] = [
        {
            "id": "gate_districts",
            "label": "Animation districts",
            "compass": "N",
            "x": 0.0,
            "z": PARADE_CORRIDOR_END_Z - 60.0,
            "color": "#a78bfa",
            "hint": "North gate — category animation grids ahead",
            "kind": "gate",
        },
        {
            "id": "gate_props",
            "label": "Props gallery",
            "compass": "SW",
            "x": PARADE_PROPS_CENTER_X,
            "z": PARADE_PROPS_CENTER_Z - PARADE_PROPS_HALF - 100.0,
            "color": "#38bdf8",
            "hint": "Southwest gate — furniture & scenery props",
            "kind": "gate",
        },
        {
            "id": "gate_catalog",
            "label": "Object catalog",
            "compass": "W",
            "x": OBJECT_CATALOG_HUB_X + parade_museum_half() + 80.0,
            "z": OBJECT_CATALOG_HUB_Z,
            "color": PARADE_MUSEUM_COLOUR,
            "hint": "West gate — tag-coloured StdObject catalog districts",
            "kind": "gate",
        },
        {
            "id": "gate_characters",
            "label": "Character gallery",
            "compass": "SE",
            "x": PARADE_CHARACTERS_CENTER_X - PARADE_CHARACTERS_HALF - 80.0,
            "z": PARADE_CHARACTERS_CENTER_Z,
            "color": PARADE_CHARACTERS_COLOUR,
            "hint": "Southeast gate — playable character bodies",
            "kind": "gate",
        },
        {
            "id": "gate_true_scale_normal",
            "label": "True scale (normal)",
            "compass": "NW",
            "x": PARADE_TRUE_SCALE_NORMAL_CENTER_X - parade_true_scale_normal_half() - 80.0,
            "z": PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
            "color": PARADE_TRUE_SCALE_COLOUR,
            "hint": "Northwest gate — retail-scale object sizes",
            "kind": "gate",
        },
        {
            "id": "gate_true_scale_mega",
            "label": "True scale (mega yard)",
            "compass": "NW",
            "x": PARADE_TRUE_SCALE_MEGA_CENTER_X,
            "z": PARADE_TRUE_SCALE_MEGA_CENTER_Z + 1200.0,
            "color": PARADE_TRUE_SCALE_MEGA_COLOUR,
            "hint": "Far northwest — megastructure true-scale yard",
            "kind": "gate",
        },
    ]

    for wg in world_gate_entries():
        gates.append(
            {
                "id": f"gate_{wg['world']}_world",
                "label": wg["label"],
                "compass": wg["compass"],
                "x": float(wg["gateX"]),
                "z": float(wg["gateZ"]),
                "color": wg["color"],
                "hint": wg["walkHint"],
                "kind": "world_gate",
                "world": wg["world"],
            }
        )
    return gates


def _sample_line(x0: float, z0: float, x1: float, z1: float, step: float) -> list[tuple[float, float]]:
    """Sample centreline from (x0,z0) toward (x1,z1) every *step* units."""
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    if length < step:
        return [(x0, z0), (x1, z1)]
    n = max(1, int(math.ceil(length / step)))
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        pts.append((x0 + dx * t, z0 + dz * t))
    return pts


def distance_beacon_placements() -> list[dict[str, Any]]:
    """Periodic marker positions along long spawn→wing routes (every 2000 u)."""
    spawn_x, spawn_z = 0.0, PARADE_PLAYER_SPAWN_Z
    beacons: list[dict[str, Any]] = []

    spine_targets: list[tuple[str, str, float, float, str]] = [
        ("solo", "S", -4200.0, -5200.0, "#f59e0b"),
        ("mp", "E", 9200.0, -2800.0, "#dc2626"),
        ("dev", "NE", 5200.0, 3600.0, "#64748b"),
        ("props", "SW", PARADE_PROPS_CENTER_X, PARADE_PROPS_CENTER_Z, "#38bdf8"),
        ("catalog", "W", OBJECT_CATALOG_HUB_X, OBJECT_CATALOG_HUB_Z, PARADE_MUSEUM_COLOUR),
        ("characters", "SE", PARADE_CHARACTERS_CENTER_X, PARADE_CHARACTERS_CENTER_Z, PARADE_CHARACTERS_COLOUR),
        (
            "true_scale",
            "NW",
            PARADE_TRUE_SCALE_NORMAL_CENTER_X,
            PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
            PARADE_TRUE_SCALE_COLOUR,
        ),
        (
            "true_scale_mega",
            "NW",
            PARADE_TRUE_SCALE_MEGA_CENTER_X,
            PARADE_TRUE_SCALE_MEGA_CENTER_Z,
            PARADE_TRUE_SCALE_MEGA_COLOUR,
        ),
        ("districts", "N", PARADE_DISTRICT_ORIGIN_X, PARADE_DISTRICT_ORIGIN_Z, "#a78bfa"),
    ]

    for wing_id, compass, tx, tz, colour in spine_targets:
        length = math.hypot(tx - spawn_x, tz - spawn_z)
        if length < BEACON_MIN_ROUTE_LEN:
            continue
        samples = _sample_line(spawn_x, spawn_z, tx, tz, BEACON_INTERVAL)
        # Skip spawn (index 0) and final gate (last) — gates have dedicated markers.
        for i, (bx, bz) in enumerate(samples[1:-1], start=1):
            beacons.append(
                {
                    "id": f"beacon_{wing_id}_{i}",
                    "wing": wing_id,
                    "compass": compass,
                    "label": f"{compass} · {wing_id.replace('_', ' ')} ({i * int(BEACON_INTERVAL)} u)",
                    "x": bx,
                    "z": bz,
                    "color": colour,
                    "distance": int(round(math.hypot(bx - spawn_x, bz - spawn_z))),
                    "kind": "beacon",
                }
            )
    return beacons


def in_game_guide_payload() -> dict[str, Any]:
    """Spawn signpost ring + gates + beacons for anim_lab.html In-game guide panel."""
    from .anim_levels import megaworld_plan

    plan = megaworld_plan()
    signs = hub_signpost_entries()
    gates = wing_gate_entries()
    beacons = distance_beacon_placements()
    routes = spawn_corridor_routes()
    return {
        "id": "in_game_guide",
        "label": "In-game guide",
        "spawn": {"x": 0.0, "z": PARADE_PLAYER_SPAWN_Z},
        "corridorHalfWidth": PARADE_CORRIDOR_HALF_WIDTH,
        "beaconInterval": BEACON_INTERVAL,
        "signposts": signs,
        "gates": gates,
        "beacons": beacons,
        "routes": routes,
        "compassRose": {
            "radius": COMPASS_ROSE_RADIUS,
            "wedges": [
                {"axis": "E", "color": "#dc2626", "label": "MP world"},
                {"axis": "W", "color": "#0ea5e9", "label": "Object catalog"},
                {"axis": "+Z", "color": "#a78bfa", "label": "Animation districts"},
                {"axis": "-Z", "color": "#38bdf8", "label": "Props gallery"},
            ],
        },
        "walkHint": (
            "Stand on spawn pad 0 (0, -2200). Eight PORTAL arches at 1500 u mark each wing. "
            f"Follow coloured carpets: gold S solo ({plan['soloCount']} islands), "
            f"crimson east MP ({plan['mpCount']}), "
            f"northeast slate dev ({plan['devCount']}), "
            "cyan SW props, blue W catalog, teal NW true-scale, purple SE characters, "
            "lavender north animation districts."
        ),
    }


def _point_in_rect(px: float, pz: float, x0: float, z0: float, x1: float, z1: float) -> bool:
    return x0 <= px <= x1 and z0 <= pz <= z1


def _path_waypoints_for_wing(wing_id: str) -> list[tuple[float, float]]:
    """Polyline centrelines matching painted corridor geometry (not straight shortcuts)."""
    spawn_x, spawn_z = 0.0, PARADE_PLAYER_SPAWN_Z
    hw = PARADE_CORRIDOR_HALF_WIDTH
    gallery_west = PARADE_PROPS_CENTER_X - PARADE_PROPS_HALF

    if wing_id == "districts":
        return [
            (spawn_x, spawn_z),
            (spawn_x, PARADE_DISTRICT_ORIGIN_Z - 280.0),
        ]
    if wing_id == "props":
        return [
            (spawn_x, spawn_z),
            (120.0, spawn_z),
            (gallery_west, spawn_z),
            (gallery_west, PARADE_PROPS_CENTER_Z),
            (PARADE_PROPS_CENTER_X, PARADE_PROPS_CENTER_Z),
        ]
    if wing_id == "catalog":
        cat_metrics = parade_museum_grid_metrics()
        cat_cx = float(cat_metrics.get("centerX", OBJECT_CATALOG_HUB_X))
        cat_cz = float(cat_metrics.get("centerZ", OBJECT_CATALOG_HUB_Z))
        return [
            (spawn_x, spawn_z),
            (120.0, spawn_z),
            (gallery_west, spawn_z),
            (gallery_west, cat_cz),
            (cat_cx, cat_cz),
        ]
    if wing_id == "characters":
        return [
            (spawn_x, spawn_z),
            (120.0, spawn_z),
            (120.0, PARADE_CHARACTERS_CENTER_Z),
            (PARADE_CHARACTERS_CENTER_X, PARADE_CHARACTERS_CENTER_Z),
        ]
    if wing_id == "true_scale":
        ts_half = parade_true_scale_normal_half()
        ts_cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X
        ts_cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
        return [
            (spawn_x, spawn_z),
            (120.0, spawn_z),
            (120.0, ts_cz),
            (ts_cx - ts_half, ts_cz),
        ]
    if wing_id == "solo":
        return [(spawn_x, spawn_z), (-4200.0, -5200.0)]
    if wing_id == "mp":
        return [(spawn_x, spawn_z), (9200.0, -2800.0)]
    if wing_id == "dev":
        return [(spawn_x, spawn_z), (5200.0, 3600.0)]
    return [(spawn_x, spawn_z)]


def _collision_quads_at_y(tiles: list[dict], y: float = 0.0) -> list[tuple[float, float, float, float]]:
    """Axis-aligned collision rects from tile quads at *y*."""
    target_y = int(y)
    quads: list[tuple[float, float, float, float]] = []
    for tile in tiles:
        vs = tile["vertices"]
        if int(vs[0]["y"]) != target_y:
            continue
        x0, z0 = float(vs[0]["x"]), float(vs[0]["z"])
        x1, z1 = float(vs[2]["x"]), float(vs[2]["z"])
        quads.append((min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)))
    return quads


def _point_has_collision(px: float, pz: float, quads: list[tuple[float, float, float, float]]) -> bool:
    for x0, z0, x1, z1 in quads:
        if x0 <= px <= x1 and z0 <= pz <= z1:
            return True
    return False


def audit_hub_carpet_collision_floor(
    tiles_data: dict | None = None,
    *,
    player_room: int = 1,
    collision_y: float = 0.0,
) -> list[str]:
    """Warn when a room-1 hub carpet tile lacks Y=0 collision underneath."""
    if tiles_data is None:
        from importlib import import_module

        mod = import_module("src.levels.animlab")
        tiles_data = mod.build_tiles_json()

    room_tiles: list[dict] = []
    for rname, tiles in tiles_data.get("rooms", {}).items():
        if int(rname.split("_")[-1]) == player_room:
            room_tiles = tiles
            break

    quads = _collision_quads_at_y(room_tiles, y=collision_y)
    missing: list[tuple[float, float]] = []
    for tile in room_tiles:
        if tile.get("floortype") != "carpet":
            continue
        vs = tile["vertices"]
        x0, z0 = float(vs[0]["x"]), float(vs[0]["z"])
        x1, z1 = float(vs[2]["x"]), float(vs[2]["z"])
        cx, cz = (x0 + x1) * 0.5, (z0 + z1) * 0.5
        if not _point_has_collision(cx, cz, quads):
            missing.append((cx, cz))

    if not missing:
        return []
    sx0, sz0 = missing[0]
    return [
        f"spawn collision audit: {len(missing)} hub carpet cells missing room-{player_room} "
        f"Y={collision_y:.0f} floor (e.g. {sx0:.0f},{sz0:.0f})"
    ]


def audit_spawn_collision_floor(
    tiles_data: dict | None = None,
    *,
    sample_step: float = 250.0,
    player_room: int = 1,
    collision_y: float = 0.0,
    scale_factor: float = 1.0,
) -> list[str]:
    """Sample spawn→wing polylines; warn when room *player_room* lacks Y=0 floor."""
    if tiles_data is None:
        from importlib import import_module

        mod = import_module("src.levels.animlab")
        tiles_data = mod.build_tiles_json()

    room_tiles: list[dict] = []
    for rname, tiles in tiles_data.get("rooms", {}).items():
        if int(rname.split("_")[-1]) == player_room:
            room_tiles = tiles
            break

    quads = _collision_quads_at_y(room_tiles, y=collision_y)
    wing_ids = [
        "districts",
        "props",
        "catalog",
        "characters",
        "true_scale",
        "solo",
        "mp",
        "dev",
    ]

    warnings: list[str] = []
    for wing_id in wing_ids:
        waypoints = _path_waypoints_for_wing(wing_id)
        scaled_waypoints = [(wx * scale_factor, wz * scale_factor) for wx, wz in waypoints]
        samples: list[tuple[float, float]] = []
        for i in range(len(scaled_waypoints) - 1):
            x0, z0 = scaled_waypoints[i]
            x1, z1 = scaled_waypoints[i + 1]
            samples.extend(_sample_line(x0, z0, x1, z1, sample_step * scale_factor))

        missing = [
            (sx, sz)
            for sx, sz in samples
            if not _point_has_collision(sx, sz, quads)
        ]
        if missing:
            sx0, sz0 = missing[0]
            warnings.append(
                f"spawn collision audit: {wing_id} route missing room-{player_room} "
                f"floor at {len(missing)}/{len(samples)} samples "
                f"(step={sample_step:.0f} u; e.g. {sx0:.0f},{sz0:.0f})"
            )
    warnings.extend(audit_hub_carpet_collision_floor(tiles_data, player_room=player_room, collision_y=collision_y))
    return warnings


def audit_spawn_walk_paths(*, sample_step: float = 500.0, scale_factor: float = 1.0) -> list[str]:
    """Sample spawn→wing polylines; warn when no corridor region covers a sample point."""
    from .anim_levels import megaworld_plan

    scale = scale_factor
    regions: list[tuple[str, float, float, float, float]] = []

    for route in spawn_corridor_routes():
        regions.append(
            (route["id"], route["x0"] * scale, route["z0"] * scale, route["x1"] * scale, route["z1"] * scale)
        )

    # Wing interior carpets count as covered (corridors clip into them in builders).
    cat_metrics = parade_museum_grid_metrics()
    cat_cx = float(cat_metrics.get("centerX", OBJECT_CATALOG_HUB_X)) * scale
    cat_cz = float(cat_metrics.get("centerZ", OBJECT_CATALOG_HUB_Z)) * scale
    cat_half = float(cat_metrics.get("half", parade_museum_half())) * scale
    regions.append(("catalog_wing", cat_cx - cat_half, cat_cz - cat_half, cat_cx + cat_half, cat_cz + cat_half))
    ch = PARADE_CHARACTERS_HALF * scale
    ccx, ccz = PARADE_CHARACTERS_CENTER_X * scale, PARADE_CHARACTERS_CENTER_Z * scale
    regions.append(("characters_wing", ccx - ch, ccz - ch, ccx + ch, ccz + ch))
    ts_half = parade_true_scale_normal_half() * scale
    ts_cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X * scale
    ts_cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z * scale
    regions.append(("true_scale_wing", ts_cx - ts_half, ts_cz - ts_half, ts_cx + ts_half, ts_cz + ts_half))
    regions.append(
        (
            "props_wing",
            (PARADE_PROPS_CENTER_X - PARADE_PROPS_HALF) * scale,
            (PARADE_PROPS_CENTER_Z - PARADE_PROPS_HALF) * scale,
            (PARADE_PROPS_CENTER_X + PARADE_PROPS_HALF) * scale,
            (PARADE_PROPS_CENTER_Z + PARADE_PROPS_HALF) * scale,
        )
    )
    regions.append(
        (
            "districts_wing",
            (PARADE_DISTRICT_ORIGIN_X - 3500.0) * scale,
            (PARADE_DISTRICT_ORIGIN_Z - 3500.0) * scale,
            (PARADE_DISTRICT_ORIGIN_X + 3500.0) * scale,
            (PARADE_DISTRICT_ORIGIN_Z + 3500.0) * scale,
        )
    )

    plan = megaworld_plan()
    for spine in plan["hubSpines"]:
        regions.append(
            (
                f"megaworld_spine_{spine.world}",
                spine.x0 * scale,
                spine.z0 * scale,
                spine.x1 * scale,
                spine.z1 * scale,
            )
        )

    wing_ids = [
        "districts",
        "props",
        "catalog",
        "characters",
        "true_scale",
        "solo",
        "mp",
        "dev",
    ]

    warnings: list[str] = []
    hw = PARADE_CORRIDOR_HALF_WIDTH * scale

    for wing_id in wing_ids:
        waypoints = _path_waypoints_for_wing(wing_id)
        scaled_waypoints = [(wx * scale, wz * scale) for wx, wz in waypoints]
        samples: list[tuple[float, float]] = []
        for i in range(len(scaled_waypoints) - 1):
            x0, z0 = scaled_waypoints[i]
            x1, z1 = scaled_waypoints[i + 1]
            samples.extend(_sample_line(x0, z0, x1, z1, sample_step * scale)[1:])

        uncovered = 0
        for sx, sz in samples:
            covered = False
            for _rid, x0, z0, x1, z1 in regions:
                if _point_in_rect(
                    sx,
                    sz,
                    min(x0, x1) - hw,
                    min(z0, z1) - hw,
                    max(x0, x1) + hw,
                    max(z0, z1) + hw,
                ):
                    covered = True
                    break
            if not covered:
                uncovered += 1
        if uncovered:
            warnings.append(
                f"spawn walk audit: {wing_id} route has {uncovered}/{len(samples)} "
                f"sample points outside corridor carpets (step={sample_step * scale:.0f} u)"
            )
    return warnings
