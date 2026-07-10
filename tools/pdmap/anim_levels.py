"""Level worlds for Animation Lab — solo campaign, Combat Simulator, and dev strips.

Layout strategy (two-world + dev annex):
  - **Solo Campaign World** (WSW): every story mission as a coloured footprint island.
  - **Combat Simulator World** (E): every ``STAGE_MP_*`` plus ``STAGE_TEST_MP*`` arena.
  - **Dev / extras annex** (NE): test/dev, GoldenEye X extras, internal placeholders, mod arenas.
  - 500 u bridge corridors between islands and from spawn hub gates.
  - Island size from retail pad bounding boxes (``level_footprints``) — min 400×400 u,
    capped at 1200×1200 u for packing; one tall door-console name marker per island.

Metadata source: ``src/game/stagetable.c`` row order + ``STAGE_*`` symbols in
``src/include/constants.h``. Display labels from ``_LABEL_OVERRIDES`` + symbol parsing.

Does **not** embed real bg geometry — one bg file per Anim Lab stage only.
In-game stage warp is not wired; boot real levels via ``--boot-stage <hex>`` from CLI.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .anim_catalog import (
    PARADE_MEGAWORLD_ROOM,
    PARADE_PLAYER_SPAWN_Z,
    _hex_to_floor_colour,
)
from .core import MapDef
from .props import StdObject

# --- World placement (disjoint from props SW, catalog far WSW, true-scale E, chars SE) ---
SOLO_WORLD_ORIGIN_X = -15800.0
SOLO_WORLD_ORIGIN_Z = -8800.0
SOLO_WORLD_GATE_X = -4200.0
SOLO_WORLD_GATE_Z = -5200.0
SOLO_WORLD_COLS = 6
SOLO_WORLD_PITCH = 1500.0

MP_WORLD_ORIGIN_X = 21800.0
MP_WORLD_ORIGIN_Z = -3200.0
MP_WORLD_GATE_X = 9200.0
MP_WORLD_GATE_Z = -2800.0
MP_WORLD_COLS = 6
MP_WORLD_PITCH = 1500.0

DEV_WORLD_ORIGIN_X = 15200.0
DEV_WORLD_ORIGIN_Z = 11800.0
DEV_WORLD_GATE_X = 5200.0
DEV_WORLD_GATE_Z = 3600.0
DEV_WORLD_COLS = 7
DEV_WORLD_PITCH = 1400.0

MEGAWORLD_BRIDGE_HALF_WIDTH = 250.0  # 500 u walkable corridor
MEGAWORLD_ROOM = PARADE_MEGAWORLD_ROOM

# Legacy aliases (dev gate — northeast annex entry).
MEGAWORLD_ENTRY_X = DEV_WORLD_GATE_X
MEGAWORLD_ENTRY_Z = DEV_WORLD_GATE_Z
MEGAWORLD_GRID_ORIGIN_X = DEV_WORLD_ORIGIN_X
MEGAWORLD_GRID_ORIGIN_Z = DEV_WORLD_ORIGIN_Z
MEGAWORLD_COLOUR = "#f59e0b"  # solo gold default for UI accent

# Island name marker — tall door console (visible arch at world scale).
MODEL_DOORCONSOLE = 0x0018
_MUSEUM_OBJECT_FLAGS = (
    0x00000001  # OBJFLAG_FALL
    | 0x00000020  # OBJFLAG_XTOPADBOUNDS
    | 0x00000040  # OBJFLAG_YTOPADBOUNDS
    | 0x00000080  # OBJFLAG_ZTOPADBOUNDS
    | 0x00000400  # OBJFLAG_IGNOREFLOORCOLOUR
)
_PARADE_OBJ_FLAGS2 = 0x04000000 | 0x00020000 | 0x00000100  # CANFILLVIEWPORT | DONTPAUSE | NOFALL
_ISLAND_NAME_PROP_SCALE = 0x0380  # tall portal-style name marker per level island

_STAGETABLE_PATH = Path(__file__).resolve().parents[2] / "src" / "game" / "stagetable.c"

# Stages omitted from all worlds (menu / self).
_EXCLUDE_SYMBOLS = frozenset({"STAGE_ANIMLAB", "STAGE_PARADE"})

# Category palette — UI + floor carpet tints.
CATEGORY_META: dict[str, dict[str, str]] = {
    "solo": {"label": "Story / solo", "color": "#f59e0b"},
    "mp": {"label": "Multiplayer", "color": "#dc2626"},
    "test": {"label": "Test / dev", "color": "#64748b"},
    "extra": {"label": "GoldenEye X extras", "color": "#eab308"},
    "mod": {"label": "Mod / custom", "color": "#ec4899"},
    "internal": {"label": "Internal / placeholder", "color": "#475569"},
}

WORLD_META: dict[str, dict[str, Any]] = {
    "solo": {
        "id": "solo",
        "label": "Solo Campaign World",
        "shortLabel": "Solo world",
        "compass": "WSW",
        "color": "#f59e0b",
        "corridorColor": "#b45309",
        "originX": SOLO_WORLD_ORIGIN_X,
        "originZ": SOLO_WORLD_ORIGIN_Z,
        "gateX": SOLO_WORLD_GATE_X,
        "gateZ": SOLO_WORLD_GATE_Z,
        "cols": SOLO_WORLD_COLS,
        "pitch": SOLO_WORLD_PITCH,
        "walkHint": "From spawn walk WSW along the gold carpet to the Solo Campaign gate, then follow bridges through every story mission island.",
    },
    "mp": {
        "id": "mp",
        "label": "Combat Simulator World",
        "shortLabel": "MP world",
        "compass": "E",
        "color": "#dc2626",
        "corridorColor": "#991b1b",
        "originX": MP_WORLD_ORIGIN_X,
        "originZ": MP_WORLD_ORIGIN_Z,
        "gateX": MP_WORLD_GATE_X,
        "gateZ": MP_WORLD_GATE_Z,
        "cols": MP_WORLD_COLS,
        "pitch": MP_WORLD_PITCH,
        "walkHint": "From spawn walk east along the crimson carpet to the Combat Simulator gate, then follow bridges through every MP map island.",
    },
    "dev": {
        "id": "dev",
        "label": "Dev & extras annex",
        "shortLabel": "Dev annex",
        "compass": "NE",
        "color": "#64748b",
        "corridorColor": "#475569",
        "originX": DEV_WORLD_ORIGIN_X,
        "originZ": DEV_WORLD_ORIGIN_Z,
        "gateX": DEV_WORLD_GATE_X,
        "gateZ": DEV_WORLD_GATE_Z,
        "cols": DEV_WORLD_COLS,
        "pitch": DEV_WORLD_PITCH,
        "walkHint": "From spawn walk northeast along the slate carpet to the dev annex gate — test maps, GoldenEye X extras, mod arenas, and internal placeholders.",
    },
}

# Retail-friendly labels (override symbol-derived titles).
_LABEL_OVERRIDES: dict[str, str] = {
    "STAGE_MAIANSOS": "Maian SOS",
    "STAGE_DEFECTION": "Defection",
    "STAGE_INVESTIGATION": "Investigation",
    "STAGE_EXTRACTION": "Extraction",
    "STAGE_VILLA": "Carrington Villa",
    "STAGE_CHICAGO": "Chicago",
    "STAGE_G5BUILDING": "G5 Building",
    "STAGE_INFILTRATION": "A51 Infiltration",
    "STAGE_RESCUE": "A51 Rescue",
    "STAGE_ESCAPE": "A51 Escape",
    "STAGE_AIRBASE": "Air Base",
    "STAGE_AIRFORCEONE": "Air Force One",
    "STAGE_CRASHSITE": "Crash Site",
    "STAGE_PELAGIC": "Pelagic II",
    "STAGE_DEEPSEA": "Deep Sea",
    "STAGE_DEFENSE": "Institute Defense",
    "STAGE_ATTACKSHIP": "Attack Ship",
    "STAGE_SKEDARRUINS": "Skedar Ruins",
    "STAGE_MBR": "MBR",
    "STAGE_WAR": "War!",
    "STAGE_DUEL": "Duel",
    "STAGE_CITRAINING": "CI Training",
    "STAGE_RETAKING": "Retaking",
    "STAGE_MP_COMPLEX": "Complex",
    "STAGE_MP_G5BUILDING": "G5 Building (MP)",
    "STAGE_MP_TEMPLE": "Temple",
    "STAGE_MP_PIPES": "Pipes",
    "STAGE_MP_SKEDAR": "Skedar",
    "STAGE_MP_BASE": "Base",
    "STAGE_MP_AREA52": "Area 52",
    "STAGE_MP_WAREHOUSE": "Warehouse",
    "STAGE_MP_CARPARK": "Carpark",
    "STAGE_MP_RUINS": "Ruins",
    "STAGE_MP_SEWERS": "Sewers",
    "STAGE_MP_FELICITY": "Felicity",
    "STAGE_MP_FORTRESS": "Fortress",
    "STAGE_MP_VILLA": "Villa (MP)",
    "STAGE_MP_GRID": "Grid",
    "STAGE_MP_RAVINE": "Ravine",
    "STAGE_MY_ARENA": "My Arena",
    "STAGE_TESTARENA": "Test Arena",
    "STAGE_TEST_UFF": "UFF Test",
    "STAGE_EXTRA1": "Frigate (GEX)",
    "STAGE_EXTRA2": "Complex (GEX)",
    "STAGE_EXTRA3": "Train (GEX)",
    "STAGE_EXTRA4": "Archives (GEX)",
    "STAGE_EXTRA5": "Aztec (GEX)",
    "STAGE_EXTRA6": "Temple (GEX)",
    "STAGE_EXTRA7": "Icicle Pyramid (GEX)",
    "STAGE_EXTRA8": "Caves (GEX)",
    "STAGE_EXTRA9": "Library (GEX)",
    "STAGE_EXTRA10": "Facility (GEX)",
    "STAGE_EXTRA11": "Bunker (GEX)",
    "STAGE_EXTRA12": "Caverns (GEX)",
    "STAGE_EXTRA13": "Basement (GEX)",
    "STAGE_EXTRA14": "Egyptian (GEX)",
    "STAGE_EXTRA15": "Stack (GEX)",
    "STAGE_EXTRA16": "Runway (mod)",
    "STAGE_EXTRA17": "Control (mod)",
    "STAGE_EXTRA18": "Tawfret Ruins (mod)",
    "STAGE_EXTRA19": "Targitzan Temple (mod)",
    "STAGE_EXTRA20": "Junkyard (mod)",
    "STAGE_EXTRA21": "Steel Mill (mod)",
    "STAGE_EXTRA22": "Mall (mod)",
    "STAGE_EXTRA23": "Tunnels (mod)",
    "STAGE_EXTRA24": "Paradox (mod)",
    "STAGE_EXTRA25": "Rogue (mod)",
    "STAGE_EXTRA26": "War Colors (mod)",
}

@dataclass(frozen=True)
class StageIsland:
    """One placable stage island in a level world."""

    order: int
    world: str
    world_order: int
    symbol: str
    stage_hex: str
    label: str
    category: str
    x: float
    z: float
    half: float
    half_x: float
    half_z: float
    footprint_width: float
    footprint_depth: float
    pads_stem: str
    grid_row: int
    grid_col: int
    floor_colour: int
    colour_hex: str


@dataclass(frozen=True)
class BridgeSegment:
    """Axis-aligned walkable corridor between two graph nodes."""

    x0: float
    z0: float
    x1: float
    z1: float
    kind: str  # island_link | entry_tunnel | hub_spine
    world: str


def _symbol_category(symbol: str) -> str:
    if symbol in ("STAGE_MY_ARENA", "STAGE_TESTARENA"):
        return "mod"
    if symbol == "STAGE_EXTRACTION":
        return "solo"
    if symbol.startswith("STAGE_MP_"):
        return "mp"
    if symbol.startswith("STAGE_TEST_MP"):
        return "mp"
    if symbol.startswith("STAGE_TEST_") or symbol.startswith("STAGE_TEST"):
        return "test"
    if symbol.startswith("STAGE_EXTRA"):
        return "extra"
    if symbol in ("STAGE_24", "STAGE_28", "STAGE_2B"):
        return "internal"
    if symbol.startswith("STAGE_") and symbol[6:].isdigit():
        return "internal"
    return "solo"


def _world_for_stage(symbol: str, category: str) -> str:
    if category == "solo":
        return "solo"
    if category == "mp":
        return "mp"
    return "dev"


def _symbol_label(symbol: str) -> str:
    if symbol in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[symbol]
    core = symbol.removeprefix("STAGE_")
    if core.startswith("MP_"):
        core = core[3:]
    if core.startswith("TEST_"):
        core = core[5:]
    return core.replace("_", " ").title()


def _parse_stagetable_symbols() -> list[tuple[str, str]]:
    """Return [(hex_id, STAGE_SYMBOL), …] in ``g_Stages[]`` order."""
    text = _STAGETABLE_PATH.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"/\*(0x[0-9a-fA-F]+)\*/\s*(STAGE_\w+)", text)


def _grid_col_for_index(index: int, row: int, cols: int) -> int:
    """Serpentine column — even rows L→R, odd rows R→L."""
    col = index % cols
    if row % 2 == 1:
        col = cols - 1 - col
    return col


def _bridge_rects(
    ax: float,
    az: float,
    bx: float,
    bz: float,
    *,
    half_w: float,
    kind: str,
    world: str,
) -> list[BridgeSegment]:
    """Axis-aligned walkable corridors between graph nodes."""
    if kind in ("entry_tunnel", "hub_spine"):
        return [
            BridgeSegment(
                min(ax, bx) - half_w,
                min(az, bz) - half_w,
                max(ax, bx) + half_w,
                max(az, bz) + half_w,
                kind,
                world,
            )
        ]

    rects: list[BridgeSegment] = []
    if abs(ax - bx) > 1.0:
        rects.append(
            BridgeSegment(
                min(ax, bx) - half_w,
                az - half_w,
                max(ax, bx) + half_w,
                az + half_w,
                kind,
                world,
            )
        )
    if abs(az - bz) > 1.0:
        rects.append(
            BridgeSegment(
                bx - half_w,
                min(az, bz) - half_w,
                bx + half_w,
                max(az, bz) + half_w,
                kind,
                world,
            )
        )
    if not rects:
        rects.append(
            BridgeSegment(
                ax - half_w,
                az - half_w,
                bx + half_w,
                bz + half_w,
                kind,
                world,
            )
        )
    return rects


def _layout_world_grid(
    world_id: str,
    entries: list[tuple[str, str, str]],
    *,
    origin_x: float,
    origin_z: float,
    cols: int,
    pitch: float,
    gate_x: float,
    gate_z: float,
    global_order_start: int,
) -> tuple[list[StageIsland], list[BridgeSegment], int]:
    """Place islands + intra-world bridges for one world district."""
    islands: list[StageIsland] = []
    bridges: list[BridgeSegment] = []
    half_w = MEGAWORLD_BRIDGE_HALF_WIDTH

    from .level_footprints import (
        island_half_extents_for_stage,
        island_layout_half_for_stage,
        pads_stem_for_stage,
        raw_footprint_for_stage,
    )

    for idx, (stage_hex, symbol, category) in enumerate(entries):
        meta = CATEGORY_META.get(category, CATEGORY_META["internal"])
        half_x, half_z = island_half_extents_for_stage(symbol)
        half = island_layout_half_for_stage(symbol)
        fp = raw_footprint_for_stage(symbol)
        row = idx // cols
        col = _grid_col_for_index(idx, row, cols)
        cx = origin_x + col * pitch
        cz = origin_z + row * pitch
        colour_hex = meta["color"]
        islands.append(
            StageIsland(
                order=global_order_start + idx,
                world=world_id,
                world_order=idx,
                symbol=symbol,
                stage_hex=stage_hex.lower(),
                label=_symbol_label(symbol),
                category=category,
                x=cx,
                z=cz,
                half=half,
                half_x=half_x,
                half_z=half_z,
                footprint_width=float(fp.get("width", half_x * 2.0)),
                footprint_depth=float(fp.get("depth", half_z * 2.0)),
                pads_stem=str(pads_stem_for_stage(symbol) or ""),
                grid_row=row,
                grid_col=col,
                floor_colour=_hex_to_floor_colour(colour_hex),
                colour_hex=colour_hex,
            )
        )

    for i in range(len(islands) - 1):
        a, b = islands[i], islands[i + 1]
        bridges.extend(
            _bridge_rects(
                a.x,
                a.z,
                b.x,
                b.z,
                half_w=half_w,
                kind="island_link",
                world=world_id,
            )
        )

    if islands:
        first = islands[0]
        bridges.extend(
            _bridge_rects(
                gate_x,
                gate_z,
                first.x,
                first.z,
                half_w=half_w,
                kind="entry_tunnel",
                world=world_id,
            )
        )

    return islands, bridges, global_order_start + len(entries)


def _hub_spines() -> list[BridgeSegment]:
    """Spawn plaza → each world gate (room-1 carpet spines)."""
    spawn_x, spawn_z = 0.0, PARADE_PLAYER_SPAWN_Z
    half_w = MEGAWORLD_BRIDGE_HALF_WIDTH
    spines: list[BridgeSegment] = []

    spines.extend(
        _bridge_rects(
            spawn_x,
            spawn_z,
            SOLO_WORLD_GATE_X,
            SOLO_WORLD_GATE_Z,
            half_w=half_w,
            kind="hub_spine",
            world="solo",
        )
    )
    spines.extend(
        _bridge_rects(
            spawn_x,
            spawn_z,
            MP_WORLD_GATE_X,
            MP_WORLD_GATE_Z,
            half_w=half_w,
            kind="hub_spine",
            world="mp",
        )
    )
    spines.extend(
        _bridge_rects(
            spawn_x,
            spawn_z,
            DEV_WORLD_GATE_X,
            DEV_WORLD_GATE_Z,
            half_w=half_w,
            kind="hub_spine",
            world="dev",
        )
    )
    return spines


@lru_cache(maxsize=1)
def megaworld_plan() -> dict[str, Any]:
    """Full layout graph: worlds, islands, bridges, bounds (deterministic)."""
    raw = _parse_stagetable_symbols()
    by_world: dict[str, list[tuple[str, str, str]]] = {
        "solo": [],
        "mp": [],
        "dev": [],
    }
    for stage_hex, symbol in raw:
        if symbol in _EXCLUDE_SYMBOLS:
            continue
        category = _symbol_category(symbol)
        world_id = _world_for_stage(symbol, category)
        by_world[world_id].append((stage_hex, symbol, category))

    all_islands: list[StageIsland] = []
    all_bridges: list[BridgeSegment] = []
    order = 0
    world_summaries: dict[str, dict[str, Any]] = {}

    world_specs = [
        ("solo", SOLO_WORLD_ORIGIN_X, SOLO_WORLD_ORIGIN_Z, SOLO_WORLD_COLS, SOLO_WORLD_PITCH, SOLO_WORLD_GATE_X, SOLO_WORLD_GATE_Z),
        ("mp", MP_WORLD_ORIGIN_X, MP_WORLD_ORIGIN_Z, MP_WORLD_COLS, MP_WORLD_PITCH, MP_WORLD_GATE_X, MP_WORLD_GATE_Z),
        ("dev", DEV_WORLD_ORIGIN_X, DEV_WORLD_ORIGIN_Z, DEV_WORLD_COLS, DEV_WORLD_PITCH, DEV_WORLD_GATE_X, DEV_WORLD_GATE_Z),
    ]

    for world_id, ox, oz, cols, pitch, gx, gz in world_specs:
        entries = by_world[world_id]
        islands, bridges, next_order = _layout_world_grid(
            world_id,
            entries,
            origin_x=ox,
            origin_z=oz,
            cols=cols,
            pitch=pitch,
            gate_x=gx,
            gate_z=gz,
            global_order_start=order,
        )
        all_islands.extend(islands)
        all_bridges.extend(bridges)
        order = next_order
        rows = max(1, math.ceil(len(entries) / cols)) if entries else 0
        meta = WORLD_META[world_id]
        world_summaries[world_id] = {
            **meta,
            "count": len(entries),
            "cols": cols,
            "rows": rows,
            "originX": ox,
            "originZ": oz,
            "gateX": gx,
            "gateZ": gz,
            "pitch": pitch,
            "bridgeCount": len(bridges),
            "floorColour": _hex_to_floor_colour(str(meta["color"])),
            "corridorColour": _hex_to_floor_colour(str(meta["corridorColor"])),
        }

    hub_spines = _hub_spines()

    xs: list[float] = [0.0, SOLO_WORLD_GATE_X, MP_WORLD_GATE_X, DEV_WORLD_GATE_X]
    zs: list[float] = [PARADE_PLAYER_SPAWN_Z, SOLO_WORLD_GATE_Z, MP_WORLD_GATE_Z, DEV_WORLD_GATE_Z]
    for isl in all_islands:
        xs.extend((isl.x - isl.half_x, isl.x + isl.half_x))
        zs.extend((isl.z - isl.half_z, isl.z + isl.half_z))
    for b in all_bridges + hub_spines:
        xs.extend((b.x0, b.x1))
        zs.extend((b.z0, b.z1))

    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    cx = (min_x + max_x) / 2.0
    cz = (min_z + max_z) / 2.0
    half_extent = max(max_x - cx, max_z - cz) + 500.0

    by_category: dict[str, list[dict[str, Any]]] = {}
    for isl in all_islands:
        by_category.setdefault(isl.category, []).append(
            {
                "symbol": isl.symbol,
                "label": isl.label,
                "stageHex": isl.stage_hex,
                "world": isl.world,
                "x": isl.x,
                "z": isl.z,
            }
        )

    return {
        "islands": all_islands,
        "bridges": all_bridges,
        "hubSpines": hub_spines,
        "worlds": world_summaries,
        "count": len(all_islands),
        "bridgeCount": len(all_bridges),
        "soloCount": len(by_world["solo"]),
        "mpCount": len(by_world["mp"]),
        "devCount": len(by_world["dev"]),
        "centerX": cx,
        "centerZ": cz,
        "half": half_extent,
        "minX": min_x,
        "maxX": max_x,
        "minZ": min_z,
        "maxZ": max_z,
        "byCategory": by_category,
        "categoryMeta": CATEGORY_META,
        "worldMeta": WORLD_META,
        "source": "src/game/stagetable.c",
        # Legacy single-grid fields (dev annex).
        "originX": DEV_WORLD_ORIGIN_X,
        "originZ": DEV_WORLD_ORIGIN_Z,
        "entryX": DEV_WORLD_GATE_X,
        "entryZ": DEV_WORLD_GATE_Z,
        "cols": DEV_WORLD_COLS,
        "rows": world_summaries["dev"]["rows"],
    }


def megaworld_half() -> float:
    return float(megaworld_plan()["half"])


def megaworld_bounds() -> dict[str, float]:
    p = megaworld_plan()
    return {
        "centerX": float(p["centerX"]),
        "centerZ": float(p["centerZ"]),
        "half": float(p["half"]),
        "minX": float(p["minX"]),
        "maxX": float(p["maxX"]),
        "minZ": float(p["minZ"]),
        "maxZ": float(p["maxZ"]),
    }


def world_gate_entries() -> list[dict[str, Any]]:
    """Spawn signpost targets — one per playable world district."""
    plan = megaworld_plan()
    entries: list[dict[str, Any]] = []
    for world_id in ("solo", "mp", "dev"):
        w = plan["worlds"][world_id]
        entries.append(
            {
                "world": world_id,
                "compass": w["compass"],
                "label": w["label"],
                "shortLabel": w["shortLabel"],
                "count": w["count"],
                "gateX": w["gateX"],
                "gateZ": w["gateZ"],
                "originX": w["originX"],
                "originZ": w["originZ"],
                "color": w["color"],
                "floorColour": w["floorColour"],
                "walkHint": w["walkHint"],
            }
        )
    return entries


def _level_pad_first() -> int:
    """First pad after parade tour + props + character gallery."""
    from .anim_characters import MAIN_CHARACTER_ENTRIES, _character_pad_first

    return _character_pad_first() + len(MAIN_CHARACTER_ENTRIES)


def level_megaworld_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    pad = _level_pad_first()
    rows: list[dict[str, Any]] = []
    for i, isl in enumerate(megaworld_plan()["islands"]):
        world_meta = WORLD_META[isl.world]
        rows.append(
            {
                "pad": pad + i,
                "label": isl.label,
                "symbol": isl.symbol,
                "stageHex": isl.stage_hex,
                "category": isl.category,
                "world": isl.world,
                "worldLabel": world_meta["label"],
                "categoryLabel": CATEGORY_META.get(isl.category, {}).get("label", isl.category),
                "x": isl.x,
                "z": isl.z,
                "y": pad_y,
                "room": MEGAWORLD_ROOM,
                "half": isl.half,
                "halfX": isl.half_x,
                "halfZ": isl.half_z,
                "footprintWidth": isl.footprint_width,
                "footprintDepth": isl.footprint_depth,
                "padsStem": isl.pads_stem,
                "gridRow": isl.grid_row,
                "gridCol": isl.grid_col,
                "order": isl.order,
                "worldOrder": isl.world_order,
                "colour": isl.colour_hex,
                "floorColour": isl.floor_colour,
                "hint": f"Stage {isl.stage_hex} — {isl.symbol} ({isl.category}, {isl.world})",
                "kind": "level_island",
            }
        )
    return rows


def level_megaworld_layout_payload() -> dict[str, Any]:
    plan = megaworld_plan()
    markers = level_megaworld_markers()
    worlds = plan["worlds"]
    return {
        "id": "level_megaworld",
        "label": "Level worlds",
        "colour": MEGAWORLD_COLOUR,
        "floorColour": _hex_to_floor_colour(MEGAWORLD_COLOUR),
        "centerX": plan["centerX"],
        "centerZ": plan["centerZ"],
        "half": plan["half"],
        "count": plan["count"],
        "soloCount": plan["soloCount"],
        "mpCount": plan["mpCount"],
        "devCount": plan["devCount"],
        "bridgeCount": plan["bridgeCount"],
        "worlds": worlds,
        "worldGates": world_gate_entries(),
        "cols": plan["cols"],
        "rows": plan["rows"],
        "originX": plan["originX"],
        "originZ": plan["originZ"],
        "entryX": plan["entryX"],
        "entryZ": plan["entryZ"],
        "islands": markers,
        "byCategory": plan["byCategory"],
        "categoryMeta": plan["categoryMeta"],
        "worldMeta": plan["worldMeta"],
        "padFirst": _level_pad_first(),
        "graphPolicy": "three_world_districts_pad_footprints_serpentine",
        "metadataSource": "src/game/stagetable.c + retail pads JSON (level_footprints.py)",
        "footprintSource": "src/assets/ntsc-final/pads/*.json pad position bbox",
        "portalSupport": False,
        "portalNote": (
            "Walk onto coloured islands to preview level size. "
            "Boot the real stage from CLI: pd.arm64 --boot-stage <hex> --moddir mods/mod_allinone"
        ),
        "walkHint": (
            "Stand at spawn — eight coloured PORTALS at 800 u mark each wing. "
            f"WSW gold bridge → Solo Campaign ({plan['soloCount']} pad-sized islands); "
            f"east crimson → Combat Simulator ({plan['mpCount']} maps); "
            f"northeast slate → dev annex ({plan['devCount']} test/extras)."
        ),
    }


def _world_corridor_colour(world_id: str) -> int:
    return int(megaworld_plan()["worlds"][world_id]["corridorColour"])


def megaworld_district_room_tiles(
    *,
    y: float,
    marker_y: float,
    arena_colour: int,
) -> list[dict[str, Any]]:
    """Collision + carpet tiles for the level megaworld prop district room."""
    from .builders import tile_large_floor, _append_disjoint_carpet

    plan = megaworld_plan()
    bounds = megaworld_bounds()
    tiles: list[dict[str, Any]] = tile_large_floor(
        bounds["minX"],
        bounds["minZ"],
        bounds["maxX"],
        bounds["maxZ"],
        y=y,
        floorcolour=arena_colour,
    )

    occupied: list[tuple[float, float, float, float]] = []

    for isl in plan["islands"]:
        _append_disjoint_carpet(
            tiles,
            occupied,
            isl.x - isl.half_x,
            isl.z - isl.half_z,
            isl.x + isl.half_x,
            isl.z + isl.half_z,
            y=marker_y,
            floorcolour=isl.floor_colour,
            floortype="carpet",
        )

    for bridge in plan["bridges"]:
        _append_disjoint_carpet(
            tiles,
            occupied,
            bridge.x0,
            bridge.z0,
            bridge.x1,
            bridge.z1,
            y=marker_y,
            floorcolour=_world_corridor_colour(bridge.world),
            floortype="carpet",
        )
    return tiles


def append_megaworld_hub_tiles(
    hub_tiles: list[dict[str, Any]],
    *,
    marker_y: float,
    occupied: list[tuple[float, float, float, float]] | None = None,
) -> None:
    """Append level-world carpet tiles (islands + bridges + hub spines) to room-1 hub."""
    from .builders import _append_disjoint_carpet

    plan = megaworld_plan()
    occ = occupied if occupied is not None else []

    for isl in plan["islands"]:
        _append_disjoint_carpet(
            hub_tiles,
            occ,
            isl.x - isl.half_x,
            isl.z - isl.half_z,
            isl.x + isl.half_x,
            isl.z + isl.half_z,
            y=marker_y,
            floorcolour=isl.floor_colour,
            floortype="carpet",
        )

    def _corridor(x0: float, z0: float, x1: float, z1: float, colour: int) -> None:
        _append_disjoint_carpet(
            hub_tiles,
            occ,
            x0,
            z0,
            x1,
            z1,
            y=marker_y,
            floorcolour=colour,
            floortype="carpet",
        )

    for spine in plan["hubSpines"]:
        _corridor(spine.x0, spine.z0, spine.x1, spine.z1, _world_corridor_colour(spine.world))

    for bridge in plan["bridges"]:
        _corridor(
            bridge.x0,
            bridge.z0,
            bridge.x1,
            bridge.z1,
            _world_corridor_colour(bridge.world),
        )


def megaworld_walkable_regions() -> list[dict[str, Any]]:
    """Walkable overlay quads for anim_lab.html / Map Editor preview."""
    plan = megaworld_plan()
    regions: list[dict[str, Any]] = []

    for world_id, w in plan["worlds"].items():
        if w["count"] <= 0:
            continue
        cols, rows, pitch = w["cols"], w["rows"], w["pitch"]
        pad = 600.0
        x0 = w["originX"] - pad
        z0 = w["originZ"] - pad
        x1 = w["originX"] + (cols - 1) * pitch + pad
        z1 = w["originZ"] + (rows - 1) * pitch + pad
        regions.append(
            {
                "id": f"world_{world_id}_bounds",
                "label": w["label"],
                "kind": "world_bounds",
                "world": world_id,
                "x0": x0,
                "z0": z0,
                "x1": x1,
                "z1": z1,
                "color": w["color"],
                "count": w["count"],
            }
        )

    for spine in plan["hubSpines"]:
        regions.append(
            {
                "id": f"megaworld_spine_{spine.world}",
                "label": f"{WORLD_META[spine.world]['shortLabel']} approach",
                "kind": "corridor",
                "world": spine.world,
                "x0": spine.x0,
                "z0": spine.z0,
                "x1": spine.x1,
                "z1": spine.z1,
                "color": WORLD_META[spine.world]["corridorColor"],
            }
        )

    for i, bridge in enumerate(plan["bridges"]):
        regions.append(
            {
                "id": f"megaworld_bridge_{i}",
                "label": f"Bridge {i + 1}",
                "kind": "corridor",
                "world": bridge.world,
                "x0": bridge.x0,
                "z0": bridge.z0,
                "x1": bridge.x1,
                "z1": bridge.z1,
                "color": WORLD_META[bridge.world]["corridorColor"],
            }
        )

    for isl in plan["islands"]:
        regions.append(
            {
                "id": f"megaworld_{isl.symbol.lower()}",
                "label": isl.label,
                "kind": "level_island",
                "category": isl.category,
                "world": isl.world,
                "stageHex": isl.stage_hex,
                "x0": isl.x - isl.half_x,
                "z0": isl.z - isl.half_z,
                "x1": isl.x + isl.half_x,
                "z1": isl.z + isl.half_z,
                "color": isl.colour_hex,
            }
        )

    b = megaworld_bounds()
    regions.append(
        {
            "id": "megaworld_bounds",
            "label": "All level worlds",
            "kind": "megaworld",
            "x0": b["minX"],
            "z0": b["minZ"],
            "x1": b["maxX"],
            "z1": b["maxZ"],
            "color": MEGAWORLD_COLOUR,
        }
    )
    return regions


def add_level_megaworld_pads(mapdef: MapDef, *, pad_y: float = 10.0) -> None:
    """Register level-island pads + tall door-console name markers (after character gallery)."""
    pad_first = _level_pad_first()
    for i, marker in enumerate(level_megaworld_markers(pad_y=pad_y)):
        pad = pad_first + i
        mapdef.add_pad(
            index=pad,
            x=float(marker["x"]),
            y=pad_y,
            z=float(marker["z"]),
            room=MEGAWORLD_ROOM,
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        )
        mapdef.add_prop(
            StdObject(
                scale=_ISLAND_NAME_PROP_SCALE,
                model=MODEL_DOORCONSOLE,
                pad=pad,
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_PARADE_OBJ_FLAGS2,
                flags3=0x00000001,
            )
        )
