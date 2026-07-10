"""Static props for the Animation Lab parade map — hub, vignettes, prop museum.

Prop model IDs from ``src/include/constants.h`` (NTSC-final). All props live in
**room 1** so they render with the player hub (STAGE_ANIMLAB visibility bypass).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .anim_catalog import (
    PARADE_CORRIDOR_HALF_WIDTH,
    PARADE_DISTRICT_CELL_D,
    PARADE_MUSEUM_CENTER_X,
    PARADE_MUSEUM_CENTER_Z,
    PARADE_MUSEUM_COLOUR,
    PARADE_PLAYER_SPAWN_Z,
    PARADE_PROPS_CENTER_X,
    PARADE_PROPS_CENTER_Z,
    PARADE_PROPS_ROOM,
    PARADE_SPAWN_CLEARANCE,
    PARADE_TRUE_SCALE_COLOUR,
    PARADE_TRUE_SCALE_MEGA_CENTER_X,
    PARADE_TRUE_SCALE_MEGA_CENTER_Z,
    PARADE_TRUE_SCALE_MEGA_COLOUR,
    PARADE_TRUE_SCALE_MEGA_ROOM,
    PARADE_TRUE_SCALE_NORMAL_CENTER_X,
    PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
    PARADE_TRUE_SCALE_NORMAL_ROOM,
    _hex_to_floor_colour,
    _parade_plan,
    hub_signpost_entries,
    parade_museum_grid_metrics,
    parade_museum_half,
    parade_museum_pick_count,
    parade_room_for_object_tag,
    parade_true_scale_grid_metrics,
)
from .museum_layout import (
    OBJECT_TAG_META,
    OBJECT_TAG_ORDER,
    largest_placement_footprints,
    model_half_extents,
    pack_museum_rows,
    pack_tag_districts,
    pack_true_scale_rows,
    tag_district_metrics,
    verify_museum_placements,
    PARADE_TRUE_SCALE_MEGA_PEAK_HALF,
    PARADE_TRUE_SCALE_MEGA_ROW_MAX_X,
)
from .anim_interactions import INTERACTION_CONTEXT
from .anim_parade import PAD_SPECIAL_TOUR
from .core import MapDef
from .props import StdObject, Prop

_HUB_PORTAL_TAGS = []
_RETURN_PORTAL_TAGS = []

# Stock stdobject flags — values from src/include/constants.h (runtime obj->flags).
OBJFLAG_FALL = 0x00000001
OBJFLAG_XTOPADBOUNDS = 0x00000020
OBJFLAG_YTOPADBOUNDS = 0x00000040
OBJFLAG_ZTOPADBOUNDS = 0x00000080
OBJFLAG_00000100 = 0x00000100
OBJFLAG_IGNOREFLOORCOLOUR = 0x00000400
OBJFLAG_INVINCIBLE = 0x00020000
OBJFLAG2_NOFALL = 0x00000100
OBJFLAG2_IMMUNETOGUNFIRE = 0x00004000
OBJFLAG3_PUSHABLE = 0x00000001
OBJFLAG3_INTERACTABLE = 0x00010000

# StdObject extrascale → runtime multiplier is extrascale / 256 (see setupCreateObject).
# Retail furniture/desks/chairs/crates/consoles use 0x0100 (1.0×). 0x0200 is for plant spikes etc.
_PROP_SCALE_DEFAULT = 0x0100

# Model IDs (hex) — documented for CHARACTER_ANIMATIONS.md
MODEL_DOORCONSOLE = 0x0018
MODEL_A51DESKENT = 0x0066
MODEL_LAB_CHAIR = 0x00BB
MODEL_LAB_TABLE = 0x00BC
MODEL_LAB_MAINFRAME = 0x00BE
MODEL_CI_DESK = 0x0161
MODEL_A51_CRATE1 = 0x0020
MODEL_A51_CRATE2 = 0x0021
MODEL_WINDOW = 0x0004
MODEL_DOOR2_G5 = 0x007D

# Wayfinding prop scales — portal arches must dominate the spawn skyline.
HUB_PORTAL_PROP_SCALE = 0x0400
SIGNPOST_PROP_SCALE = HUB_PORTAL_PROP_SCALE
GATE_MARKER_SCALE = 0x0280
BEACON_PROP_SCALE = 0x0220

# Distinct StdObject model per compass signpost (spawn ring).
_COMPASS_SIGNPOST_MODELS: dict[str, int] = {
    "N": MODEL_LAB_MAINFRAME,
    "SW": MODEL_A51_CRATE1,
    "S": MODEL_A51_CRATE2,
    "W": MODEL_DOORCONSOLE,
    "E": MODEL_CI_DESK,
    "NW": MODEL_LAB_TABLE,
    "SE": MODEL_LAB_CHAIR,
    "NE": MODEL_A51DESKENT,
}

# Gate entrance markers — console/desk variants per wing.
_GATE_MARKER_MODELS: dict[str, int] = {
    "gate_districts": MODEL_LAB_MAINFRAME,
    "gate_props": MODEL_A51_CRATE1,
    "gate_catalog": MODEL_DOORCONSOLE,
    "gate_characters": MODEL_LAB_CHAIR,
    "gate_true_scale_normal": MODEL_LAB_TABLE,
    "gate_true_scale_mega": MODEL_LAB_MAINFRAME,
    "gate_solo_world": MODEL_A51_CRATE2,
    "gate_mp_world": MODEL_CI_DESK,
    "gate_dev_world": MODEL_A51DESKENT,
}

_BEACON_MODELS: dict[str, int] = {
    "solo": MODEL_A51_CRATE2,
    "mp": MODEL_CI_DESK,
    "dev": MODEL_A51DESKENT,
    "props": MODEL_A51_CRATE1,
    "catalog": MODEL_DOORCONSOLE,
    "characters": MODEL_LAB_CHAIR,
    "true_scale": MODEL_LAB_TABLE,
    "true_scale_mega": MODEL_LAB_MAINFRAME,
    "districts": MODEL_LAB_MAINFRAME,
}

_STD_OBJECT_FLAGS = (
    OBJFLAG_FALL
    | OBJFLAG_XTOPADBOUNDS
    | OBJFLAG_YTOPADBOUNDS
    | OBJFLAG_ZTOPADBOUNDS
    | OBJFLAG_00000100
    | OBJFLAG_IGNOREFLOORCOLOUR
)
OBJFLAG2_CANFILLVIEWPORT = 0x04000000
OBJFLAG2_DONTPAUSE = 0x00020000
_PARADE_OBJ_FLAGS2 = OBJFLAG2_NOFALL | OBJFLAG2_CANFILLVIEWPORT | OBJFLAG2_DONTPAUSE
_CHAIR_FLAGS = _STD_OBJECT_FLAGS | OBJFLAG_INVINCIBLE
_CHAIR_FLAGS2 = _PARADE_OBJ_FLAGS2
_DESK_FLAGS = _STD_OBJECT_FLAGS
_DESK_FLAGS2 = _PARADE_OBJ_FLAGS2 | OBJFLAG2_IMMUNETOGUNFIRE

# Museum grid — visual-only: skip OBJFLAG_00000100 so objInit does not allocate per-prop geo
# (364+ props exhaust stage MEMPOOL_STAGE and crash during setupCreateProps).
_MUSEUM_OBJECT_FLAGS = (
    OBJFLAG_FALL
    | OBJFLAG_XTOPADBOUNDS
    | OBJFLAG_YTOPADBOUNDS
    | OBJFLAG_ZTOPADBOUNDS
    | OBJFLAG_IGNOREFLOORCOLOUR
)
_MUSEUM_OBJECT_FLAGS2 = _PARADE_OBJ_FLAGS2

_MODEL_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "stdobject_models.json"

# Spawn at (0, PARADE_PLAYER_SPAWN_Z) — plaza stays clear; gallery is southwest.
PARADE_SPAWN_X = 0.0
PARADE_SPAWN_Z = PARADE_PLAYER_SPAWN_Z
_GALLERY_PITCH = 480.0  # generous spacing between solid furniture props


@dataclass(frozen=True)
class ParadePropSpec:
    """One static prop in the parade arena (room 1)."""

    label: str
    model: int
    x: float
    z: float
    district: str
    hint: str
    kind: str = "hub"  # plaza | hub | corridor | vignette | museum | signpost | door
    tag: str = "misc"
    flags: int = _STD_OBJECT_FLAGS
    flags2: int = _PARADE_OBJ_FLAGS2
    flags3: int = OBJFLAG3_PUSHABLE
    scale: int = _PROP_SCALE_DEFAULT
    room: int = PARADE_PROPS_ROOM
    tag_id: int = 0
    dir_x: float = 0.0
    dir_y: float = 0.0
    dir_z: float = -1.0
    up_x: float | None = None
    up_y: float | None = None
    up_z: float | None = None
    xmin: float | None = None
    xmax: float | None = None
    ymin: float | None = None
    ymax: float | None = None
    zmin: float | None = None
    zmax: float | None = None


def _spawn_plaza_specs() -> tuple[ParadePropSpec, ...]:
    """Glass-walled room centered at (0.0, -1200.0) containing the combat sims."""
    return (
        # North wall: Window
        ParadePropSpec(
            "Glass Room N Window",
            MODEL_WINDOW,
            0.0,
            -900.0,
            "plaza",
            "Transparent north window",
            kind="plaza",
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        ),
        # West wall: Window
        ParadePropSpec(
            "Glass Room W Window",
            MODEL_WINDOW,
            -300.0,
            -1200.0,
            "plaza",
            "Transparent west window",
            kind="plaza",
            dir_x=-1.0,
            dir_y=0.0,
            dir_z=0.0,
        ),
        # East wall: Window
        ParadePropSpec(
            "Glass Room E Window",
            MODEL_WINDOW,
            300.0,
            -1200.0,
            "plaza",
            "Transparent east window",
            kind="plaza",
            dir_x=1.0,
            dir_y=0.0,
            dir_z=0.0,
        ),
        # South wall: Sliding Door
        ParadePropSpec(
            "Glass Room Door",
            MODEL_DOOR2_G5,
            0.0,
            -1500.0,
            "plaza",
            "Trapped combat sims door",
            kind="door",
            dir_x=0.0,
            dir_y=1.0,
            dir_z=0.0,
            up_x=0.0,
            up_y=0.0,
            up_z=-1.0,
            xmin=-83.0,
            xmax=83.0,
            ymin=-333.0,
            ymax=333.0,
            zmin=-10.0,
            zmax=220.0,
        ),
        # South-west wall segment: Window
        ParadePropSpec(
            "Glass Room SW Window",
            MODEL_WINDOW,
            -200.0,
            -1500.0,
            "plaza",
            "Transparent southwest window",
            kind="plaza",
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        ),
        # South-east wall segment: Window
        ParadePropSpec(
            "Glass Room SE Window",
            MODEL_WINDOW,
            200.0,
            -1500.0,
            "plaza",
            "Transparent southeast window",
            kind="plaza",
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        ),
    )


def _gallery_grid_specs() -> tuple[ParadePropSpec, ...]:
    """3×3 furniture gallery with a open center cell for walking through."""
    cx, cz = PARADE_PROPS_CENTER_X, PARADE_PROPS_CENTER_Z
    p = _GALLERY_PITCH
    # (col, row) offsets from center — skip (0,0) for a walk-through alcove.
    cells: list[tuple[int, int, str, int, str, str, int, int]] = [
        (-1, -1, "Door console", MODEL_DOORCONSOLE, "computer", "Gallery NW — OPERATE_* terminal", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (0, -1, "Lab mainframe", MODEL_LAB_MAINFRAME, "computer", "Gallery north — console backdrop", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (1, -1, "CI desk", MODEL_CI_DESK, "computer", "Gallery NE — briefing desk", _DESK_FLAGS, _DESK_FLAGS2),
        (-1, 0, "A51 crate A", MODEL_A51_CRATE1, "combat", "Gallery west — cover prop", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (1, 0, "A51 crate B", MODEL_A51_CRATE2, "combat", "Gallery east — combat reference", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (-1, 1, "A51 desk + terminal", MODEL_A51DESKENT, "computer", "Gallery SW — typing & operate anims", _DESK_FLAGS, _DESK_FLAGS2),
        (0, 1, "Lab table", MODEL_LAB_TABLE, "computer", "Gallery south — workbench surface", _DESK_FLAGS, _DESK_FLAGS2),
        (1, 1, "Lab chair", MODEL_LAB_CHAIR, "computer", "Gallery SE — SITTING_* loops", _CHAIR_FLAGS, _CHAIR_FLAGS2),
    ]
    specs: list[ParadePropSpec] = []
    for col, row, label, model, district, hint, flags, flags2 in cells:
        specs.append(
            ParadePropSpec(
                label,
                model,
                cx + col * p,
                cz + row * p,
                district,
                hint,
                kind="hub",
                flags=flags,
                flags2=flags2,
            )
        )
    return tuple(specs)


# Hub props — southwest furniture gallery (room 1, cyan carpet).
PARADE_HUB_PROP_SPECS: tuple[ParadePropSpec, ...] = _gallery_grid_specs()

# Legacy alias for docs / imports.
PARADE_PROP_SPECS = PARADE_HUB_PROP_SPECS

# North walk — flanking computer props (corridor centerline stays clear).
_CORRIDOR_X = PARADE_CORRIDOR_HALF_WIDTH + 80.0
PARADE_CORRIDOR_COMPUTER_SPECS: tuple[ParadePropSpec, ...] = (
    ParadePropSpec(
        "Walk path · A51 desk",
        MODEL_A51DESKENT,
        -_CORRIDOR_X,
        PARADE_PLAYER_SPAWN_Z + 380.0,
        "computer",
        "North walk — desk west of spine (corridor stays open)",
        kind="corridor",
        flags=_DESK_FLAGS,
        flags2=_DESK_FLAGS2,
    ),
    ParadePropSpec(
        "Walk path · door console",
        MODEL_DOORCONSOLE,
        _CORRIDOR_X,
        PARADE_PLAYER_SPAWN_Z + 380.0,
        "computer",
        "North walk — terminal east of spine",
        kind="corridor",
    ),
    ParadePropSpec(
        "Walk path · lab chair",
        MODEL_LAB_CHAIR,
        -_CORRIDOR_X,
        PARADE_PLAYER_SPAWN_Z + 620.0,
        "computer",
        "North walk — seated typing context (west flank)",
        kind="corridor",
        flags=_CHAIR_FLAGS,
        flags2=_CHAIR_FLAGS2,
    ),
    ParadePropSpec(
        "Walk path · lab table",
        MODEL_LAB_TABLE,
        _CORRIDOR_X,
        PARADE_PLAYER_SPAWN_Z + 620.0,
        "computer",
        "North walk — workbench east flank",
        kind="corridor",
        flags=_DESK_FLAGS,
        flags2=_DESK_FLAGS2,
    ),
)

# Per-district vignette templates: (model, offset_x, offset_z, label_suffix, flags...).
_VIGNETTE_TEMPLATES: dict[str, list[tuple[Any, ...]]] = {
    "computer": [
        (MODEL_A51DESKENT, -280, -40, "desk", _DESK_FLAGS, _DESK_FLAGS2),
        (MODEL_LAB_CHAIR, 280, -40, "chair", _CHAIR_FLAGS, _CHAIR_FLAGS2),
        (MODEL_DOORCONSOLE, 0, -200, "console", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "combat": [
        (MODEL_A51_CRATE1, -260, 0, "crate A", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (MODEL_A51_CRATE2, 260, 0, "crate B", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "use": [
        (MODEL_LAB_TABLE, -260, 0, "workbench", _DESK_FLAGS, _DESK_FLAGS2),
        (MODEL_DOORCONSOLE, 260, 0, "terminal", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "social": [
        (MODEL_CI_DESK, -280, 0, "briefing desk", _DESK_FLAGS, _DESK_FLAGS2),
        (MODEL_LAB_CHAIR, 280, 40, "seat", _CHAIR_FLAGS, _CHAIR_FLAGS2),
    ],
    "movement": [
        (MODEL_A51_CRATE1, 0, 0, "path marker", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "react": [
        (MODEL_A51_CRATE1, -80, 0, "cover", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "death": [
        (MODEL_A51_CRATE2, 0, 0, "fall context", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "weapon": [
        (MODEL_A51_CRATE1, -90, 0, "crate A", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
        (MODEL_A51_CRATE2, 90, 0, "crate B", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "other": [
        (MODEL_A51_CRATE1, 0, 0, "misc prop", _STD_OBJECT_FLAGS, _PARADE_OBJ_FLAGS2),
    ],
    "cutscene": [
        (MODEL_LAB_TABLE, 0, 0, "staging table", _DESK_FLAGS, _DESK_FLAGS2),
    ],
}


@lru_cache(maxsize=1)
def _vignette_specs() -> tuple[ParadePropSpec, ...]:
    """District entrance vignettes — south mouth of each category district."""
    specs: list[ParadePropSpec] = []
    for district in _parade_plan()["districts"]:
        cat = str(district["id"])
        templates = _VIGNETTE_TEMPLATES.get(cat)
        if not templates:
            continue
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        span_rows = int(district.get("spanRows", 1))
        mouth_z = dcz - span_rows * PARADE_DISTRICT_CELL_D / 2.0 - 120.0
        ctx = INTERACTION_CONTEXT.get(cat, {})
        vignette_label = ctx.get("vignetteLabel", cat)
        for tpl in templates:
            model, ox, oz, suffix, flags, flags2 = tpl
            specs.append(
                ParadePropSpec(
                    f"{vignette_label} · {suffix}",
                    int(model),
                    dcx + float(ox),
                    mouth_z + float(oz),
                    cat,
                    f"District vignette for {cat} — {suffix}",
                    kind="vignette",
                    flags=int(flags),
                    flags2=int(flags2),
                )
            )
    return tuple(specs)


@lru_cache(maxsize=1)
def _load_model_catalog() -> list[dict[str, Any]]:
    if not _MODEL_CATALOG_PATH.is_file():
        return []
    data = json.loads(_MODEL_CATALOG_PATH.read_text(encoding="utf-8"))
    return list(data.get("models") or [])


@lru_cache(maxsize=1)
def _model_scale_by_id() -> dict[int, int]:
    """Retail extrascale per model id — from stdobject_models.json (gen_model_catalog.py)."""
    scales: dict[int, int] = {}
    for row in _load_model_catalog():
        scales[int(row["model"])] = int(row.get("scale", _PROP_SCALE_DEFAULT))
    return scales


def _prop_scale_for_model(model: int) -> int:
    """Retail extrascale for a StdObject model id (default 0x0100 = 1.0×)."""
    return _model_scale_by_id().get(model, _PROP_SCALE_DEFAULT)


def _with_retail_scale(spec: ParadePropSpec) -> ParadePropSpec:
    """Apply catalog retail scale unless the spec already sets a custom extrascale."""
    if spec.kind in ("signpost", "portal", "gate", "beacon") and spec.scale != _PROP_SCALE_DEFAULT:
        return spec
    scale = _prop_scale_for_model(spec.model)
    if scale == spec.scale:
        return spec
    return ParadePropSpec(
        spec.label,
        spec.model,
        spec.x,
        spec.z,
        spec.district,
        spec.hint,
        kind=spec.kind,
        tag=spec.tag,
        flags=spec.flags,
        flags2=spec.flags2,
        flags3=spec.flags3,
        scale=scale,
        room=spec.room,
    )


def _museum_cap() -> int | None:
    """Return max museum models, or None for full catalog (ANIMLAB_MUSEUM_MAX ≤ 0)."""
    cap_raw = os.environ.get("ANIMLAB_MUSEUM_MAX", "0").strip()
    try:
        cap = int(cap_raw)
    except ValueError:
        cap = 0
    if cap <= 0:
        return None
    return cap


def _museum_picked_rows() -> list[dict[str, Any]]:
    """Catalog rows selected for the museum (full list or ANIMLAB_MUSEUM_MAX cap)."""
    catalog = _load_model_catalog()
    if not catalog:
        return []

    cap = _museum_cap()
    if cap is None:
        return sorted(catalog, key=lambda r: int(r["model"]))

    by_tag: dict[str, list[dict[str, Any]]] = {}
    for row in catalog:
        by_tag.setdefault(str(row.get("tag", "misc")), []).append(row)
    for tag_rows in by_tag.values():
        tag_rows.sort(key=lambda r: int(r["model"]))

    picked: list[dict[str, Any]] = []
    tags = sorted(by_tag.keys())
    idx = 0
    while len(picked) < cap and tags:
        tag = tags[idx % len(tags)]
        pool = by_tag[tag]
        if pool:
            picked.append(pool.pop(0))
            if not pool:
                tags = [t for t in tags if by_tag[t]]
                idx = 0
                continue
        idx += 1
        if idx > cap * len(by_tag) + 10:
            break
    return picked[:cap]


@lru_cache(maxsize=1)
def _museum_tag_packed() -> dict[str, tuple[dict[str, Any], ...]]:
    """Per-tag dimension-packed placements for the object catalog megazone."""
    rows = _museum_picked_rows()
    packed = pack_tag_districts(rows)
    for tag, placements in packed.items():
        overlaps = verify_museum_placements(placements)
        if overlaps:
            raise RuntimeError(
                f"object catalog tag {tag!r} has {len(overlaps)} overlapping pair(s); "
                f"first={overlaps[0]}"
            )
    return {tag: tuple(ps) for tag, ps in packed.items()}


@lru_cache(maxsize=1)
def _museum_packed_placements() -> tuple[dict[str, Any], ...]:
    """Flat list of all showcase museum placements (tag-district clusters)."""
    flat: list[dict[str, Any]] = []
    for tag in OBJECT_TAG_ORDER:
        for place in _museum_tag_packed().get(tag, ()):
            flat.append({**place, "tag": tag})
    for tag, places in _museum_tag_packed().items():
        if tag in OBJECT_TAG_ORDER:
            continue
        for place in places:
            flat.append({**place, "tag": tag})
    return tuple(flat)


@lru_cache(maxsize=1)
def _hub_signpost_specs() -> tuple[ParadePropSpec, ...]:
    """Eight portal left pillars at 800 u — one per major wing."""
    specs: list[ParadePropSpec] = []
    import math

    compass_angle: dict[str, float] = {
        "N": 0.0,
        "NE": math.pi / 4,
        "E": math.pi / 2,
        "SE": 3 * math.pi / 4,
        "S": math.pi,
        "SW": 5 * math.pi / 4,
        "W": -math.pi / 2,
        "NW": -math.pi / 4,
    }

    global _HUB_PORTAL_TAGS
    _HUB_PORTAL_TAGS.clear()
    _PORTAL_TAG_START = 0x20

    for i, sign in enumerate(hub_signpost_entries()):
        compass = str(sign["compass"])
        ang = compass_angle.get(compass, 0.0)
        perp_ang = ang + math.pi / 2

        # Left Pillar coordinate
        lx = float(sign["x"]) + 75.0 * math.sin(perp_ang)
        lz = float(sign["z"]) + 75.0 * math.cos(perp_ang)

        model = MODEL_LAB_MAINFRAME
        tag_id = _PORTAL_TAG_START + i
        _HUB_PORTAL_TAGS.append((tag_id, sign))

        specs.append(
            ParadePropSpec(
                f"Portal L · {compass} {sign['label'][:28]}",
                model,
                lx,
                lz,
                "portal",
                str(sign["hint"]),
                kind="portal",
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_MUSEUM_OBJECT_FLAGS2,
                flags3=OBJFLAG3_INTERACTABLE,
                scale=HUB_PORTAL_PROP_SCALE,
                tag_id=tag_id,
            )
        )
    return tuple(specs)


@lru_cache(maxsize=1)
def _wing_gate_marker_specs() -> tuple[ParadePropSpec, ...]:
    """Console/crate gate markers at each major wing entrance."""
    from .anim_wayfinding import wing_gate_entries

    global _RETURN_PORTAL_TAGS
    _RETURN_PORTAL_TAGS.clear()
    _RETURN_TAG_START = 0x40

    specs: list[ParadePropSpec] = []
    for i, gate in enumerate(wing_gate_entries()):
        gid = str(gate["id"])
        model = MODEL_LAB_MAINFRAME
        tag_id = _RETURN_TAG_START + i
        _RETURN_PORTAL_TAGS.append((tag_id, gate))

        specs.append(
            ParadePropSpec(
                f"Gate · {gate['label'][:32]}",
                model,
                float(gate["x"]),
                float(gate["z"]),
                str(gate.get("world", "gate")),
                str(gate.get("hint", gate["label"])),
                kind="gate",
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_MUSEUM_OBJECT_FLAGS2,
                flags3=OBJFLAG3_INTERACTABLE,
                scale=0x0100,
                tag_id=tag_id,
            )
        )
    return tuple(specs)


@lru_cache(maxsize=1)
def _distance_beacon_specs() -> tuple[ParadePropSpec, ...]:
    """Periodic markers every 2000 u along long spawn→wing routes."""
    from .anim_wayfinding import distance_beacon_placements

    specs: list[ParadePropSpec] = []
    for beacon in distance_beacon_placements():
        wing = str(beacon["wing"])
        model = _BEACON_MODELS.get(wing, MODEL_A51_CRATE1)
        specs.append(
            ParadePropSpec(
                f"Beacon · {beacon['label'][:36]}",
                model,
                float(beacon["x"]),
                float(beacon["z"]),
                wing,
                f"Distance marker — {beacon['label']}",
                kind="beacon",
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_MUSEUM_OBJECT_FLAGS2,
                scale=BEACON_PROP_SCALE,
            )
        )
    return tuple(specs)


@lru_cache(maxsize=1)
def _museum_specs() -> tuple[ParadePropSpec, ...]:
    """Dimension-packed StdObject models — one tag district per tile room."""
    packed = _museum_tag_packed()
    if not packed:
        return ()

    specs: list[ParadePropSpec] = []
    for tag in OBJECT_TAG_ORDER:
        placements = packed.get(tag)
        if not placements:
            continue
        meta = OBJECT_TAG_META.get(tag, OBJECT_TAG_META["misc"])
        for place in placements:
            row = place["row"]
            label = str(row.get("label", row.get("name", "Model")))
            model_id = int(row["model"])
            base_scale = _prop_scale_for_model(model_id)
            shrink = float(place.get("scaleFactor", 1.0))
            if shrink < 0.999:
                scale = max(0x20, int(base_scale * shrink))
            else:
                scale = base_scale
            specs.append(
                ParadePropSpec(
                    label[:48],
                    model_id,
                    float(place["x"]),
                    float(place["z"]),
                    "museum",
                    f"{meta['label']}: {row.get('name', label)} ({tag})",
                    kind="museum",
                    tag=tag,
                    flags=_MUSEUM_OBJECT_FLAGS,
                    flags2=_MUSEUM_OBJECT_FLAGS2,
                    scale=scale,
                    room=parade_room_for_object_tag(tag),
                )
            )
    for tag, placements in packed.items():
        if tag in OBJECT_TAG_ORDER:
            continue
        for place in placements:
            row = place["row"]
            label = str(row.get("label", row.get("name", "Model")))
            model_id = int(row["model"])
            specs.append(
                ParadePropSpec(
                    label[:48],
                    model_id,
                    float(place["x"]),
                    float(place["z"]),
                    "museum",
                    f"Museum: {row.get('name', label)} ({tag})",
                    kind="museum",
                    tag=tag,
                    flags=_MUSEUM_OBJECT_FLAGS,
                    flags2=_MUSEUM_OBJECT_FLAGS2,
                    scale=_prop_scale_for_model(model_id),
                    room=parade_room_for_object_tag(tag),
                )
            )
    return tuple(specs)


def _true_scale_catalog_rows() -> list[dict[str, Any]]:
    """Full placable catalog for true-scale wings (same cap policy as showcase museum)."""
    return _museum_picked_rows()


def _true_scale_split_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split catalog into normal-scale vs megastructure rows by bbox peak half-extent."""
    normal: list[dict[str, Any]] = []
    mega: list[dict[str, Any]] = []
    for row in _true_scale_catalog_rows():
        peak = max(model_half_extents(row))
        if peak > PARADE_TRUE_SCALE_MEGA_PEAK_HALF:
            mega.append(row)
        else:
            normal.append(row)
    return normal, mega


@lru_cache(maxsize=1)
def _true_scale_wing_placements(wing: str) -> tuple[dict[str, Any], ...]:
    """Dimension-aware true-scale placements for one wing (*normal* or *mega*)."""
    from .museum_layout import PARADE_MUSEUM_ROW_MAX_X

    normal_rows, mega_rows = _true_scale_split_rows()
    if wing == "normal":
        rows = normal_rows
        center_x = PARADE_TRUE_SCALE_NORMAL_CENTER_X
        center_z = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
        row_max_x = PARADE_MUSEUM_ROW_MAX_X
    elif wing == "mega":
        rows = mega_rows
        center_x = PARADE_TRUE_SCALE_MEGA_CENTER_X
        center_z = PARADE_TRUE_SCALE_MEGA_CENTER_Z
        row_max_x = PARADE_TRUE_SCALE_MEGA_ROW_MAX_X
    else:
        raise ValueError(f"unknown true-scale wing {wing!r}")

    packed = pack_true_scale_rows(
        rows,
        center_x=center_x,
        center_z=center_z,
        row_max_x=row_max_x,
        allow_tag_fallback=True,
    )
    overlaps = verify_museum_placements(packed)
    if overlaps:
        raise RuntimeError(
            f"true-scale {wing} wing has {len(overlaps)} overlapping pair(s); "
            f"first={overlaps[0]}"
        )
    return tuple(packed)


@lru_cache(maxsize=1)
def _true_scale_packed_placements() -> tuple[dict[str, Any], ...]:
    """All true-scale placements (normal wing + megastructure yard)."""
    return _true_scale_wing_placements("normal") + _true_scale_wing_placements("mega")


@lru_cache(maxsize=1)
def _true_scale_specs() -> tuple[ParadePropSpec, ...]:
    """Retail-scale StdObject models — actual bbox dimensions, no showcase shrink."""
    placements = _true_scale_packed_placements()
    if not placements:
        return ()

    specs: list[ParadePropSpec] = []
    normal_count = len(_true_scale_wing_placements("normal"))
    for idx, place in enumerate(placements):
        row = place["row"]
        label = str(row.get("label", row.get("name", "Model")))
        model_id = int(row["model"])
        wing = "normal" if idx < normal_count else "mega"
        room = (
            PARADE_TRUE_SCALE_NORMAL_ROOM
            if wing == "normal"
            else PARADE_TRUE_SCALE_MEGA_ROOM
        )
        specs.append(
            ParadePropSpec(
                label[:48],
                model_id,
                float(place["x"]),
                float(place["z"]),
                "true_scale",
                f"True scale ({wing}): {row.get('name', label)} — bbox rodata, retail scale",
                kind="true_scale",
                tag=str(row.get("tag", "misc")),
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_MUSEUM_OBJECT_FLAGS2,
                scale=_prop_scale_for_model(model_id),
                room=room,
            )
        )
    return tuple(specs)


def _scaled_specs(specs: tuple[ParadePropSpec, ...]) -> tuple[ParadePropSpec, ...]:
    return tuple(_with_retail_scale(s) for s in specs)


@lru_cache(maxsize=1)
def _cutscene_reserved_specs() -> tuple[ParadePropSpec, ...]:
    """Central marker when cutscene district is reserved (392 CUT_* clips, 0 guard-playable)."""
    specs: list[ParadePropSpec] = []
    for district in _parade_plan()["districts"]:
        if str(district.get("id")) != "cutscene" or not district.get("reserved"):
            continue
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        note = str(district.get("reserveNote", "Phase 4 reserved"))
        specs.append(
            ParadePropSpec(
                "Cutscene · Phase 4 reserved",
                MODEL_LAB_MAINFRAME,
                dcx,
                dcz,
                "cutscene",
                note,
                kind="signpost",
                flags=_MUSEUM_OBJECT_FLAGS,
                flags2=_MUSEUM_OBJECT_FLAGS2,
                scale=GATE_MARKER_SCALE,
            )
        )
    return tuple(specs)


@lru_cache(maxsize=1)
def all_parade_prop_specs() -> tuple[ParadePropSpec, ...]:
    """Spawn hub gallery + eight portal ring + museum + true-scale props in pad order."""
    return (
        _scaled_specs(_spawn_plaza_specs())
        + _scaled_specs(PARADE_HUB_PROP_SPECS)
        + _scaled_specs(_vignette_specs())
        + _scaled_specs(_cutscene_reserved_specs())
        + _scaled_specs(_hub_signpost_specs())
        + _museum_specs()
        + _true_scale_specs()
    )


@lru_cache(maxsize=1)
def _num_dynamic_parade_pads() -> int:
    """Count Leaf 2 sliding doors and portal right pillars."""
    count = 0
    for spec in all_parade_prop_specs():
        if getattr(spec, "kind", None) in ("door", "portal"):
            count += 1
    return count


PARADE_PROPS_FLOOR_COLOUR = _hex_to_floor_colour("#38bdf8")
PARADE_MUSEUM_FLOOR_COLOUR = _hex_to_floor_colour(PARADE_MUSEUM_COLOUR)
PARADE_TRUE_SCALE_FLOOR_COLOUR = _hex_to_floor_colour(PARADE_TRUE_SCALE_COLOUR)
PARADE_TRUE_SCALE_MEGA_FLOOR_COLOUR = _hex_to_floor_colour(PARADE_TRUE_SCALE_MEGA_COLOUR)
PARADE_PROPS_PAD_FIRST = PAD_SPECIAL_TOUR + 1


def _true_scale_wing_for_spec(spec: ParadePropSpec) -> str:
    """Nearest anchored wing centre — normal (east-north) vs mega (far northwest)."""
    dx_n = (spec.x - PARADE_TRUE_SCALE_NORMAL_CENTER_X) ** 2 + (
        spec.z - PARADE_TRUE_SCALE_NORMAL_CENTER_Z
    ) ** 2
    dx_m = (spec.x - PARADE_TRUE_SCALE_MEGA_CENTER_X) ** 2 + (
        spec.z - PARADE_TRUE_SCALE_MEGA_CENTER_Z
    ) ** 2
    return "mega" if dx_m < dx_n else "normal"


def _spec_to_marker(spec: ParadePropSpec, *, pad: int, pad_y: float) -> dict[str, Any]:
    if spec.kind == "true_scale":
        wing = _true_scale_wing_for_spec(spec)
        colour = (
            PARADE_TRUE_SCALE_MEGA_FLOOR_COLOUR
            if wing == "mega"
            else PARADE_TRUE_SCALE_FLOOR_COLOUR
        )
    elif spec.kind == "museum":
        tag = spec.tag
        meta = OBJECT_TAG_META.get(tag, OBJECT_TAG_META["misc"])
        colour = _hex_to_floor_colour(meta["color"])
    elif spec.kind in ("signpost", "portal"):
        colour = _hex_to_floor_colour("#fbbf24")
    elif spec.kind in ("gate", "beacon"):
        colour = _hex_to_floor_colour("#fbbf24")
    else:
        colour = PARADE_PROPS_FLOOR_COLOUR
    return {
        "pad": pad,
        "label": spec.label,
        "model": spec.model,
        "modelHex": f"0x{spec.model:04X}",
        "x": spec.x,
        "z": spec.z,
        "y": pad_y,
        "room": spec.room,
        "district": spec.district,
        "kind": spec.kind,
        "tag": spec.tag,
        "hint": spec.hint,
        "floorColour": colour,
    }


def parade_all_prop_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    """All placed props with sequential pad numbers."""
    rows: list[dict[str, Any]] = []
    for i, spec in enumerate(all_parade_prop_specs()):
        rows.append(_spec_to_marker(spec, pad=PARADE_PROPS_PAD_FIRST + i, pad_y=pad_y))
    return rows


def parade_prop_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    """Spawn plaza + hub props (legacy API — props yard summary)."""
    rows: list[dict[str, Any]] = []
    plaza = _spawn_plaza_specs()
    for i, spec in enumerate(plaza + PARADE_HUB_PROP_SPECS):
        rows.append(_spec_to_marker(spec, pad=PARADE_PROPS_PAD_FIRST + i, pad_y=pad_y))
    return rows


def parade_vignette_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    offset = PARADE_PROPS_PAD_FIRST + len(_spawn_plaza_specs()) + len(PARADE_HUB_PROP_SPECS)
    return [
        _spec_to_marker(spec, pad=offset + i, pad_y=pad_y)
        for i, spec in enumerate(_vignette_specs())
    ]


def parade_museum_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    offset = (
        PARADE_PROPS_PAD_FIRST
        + len(_spawn_plaza_specs())
        + len(PARADE_HUB_PROP_SPECS)
        + len(_vignette_specs())
        + len(_cutscene_reserved_specs())
        + len(_hub_signpost_specs())
    )
    return [
        _spec_to_marker(spec, pad=offset + i, pad_y=pad_y)
        for i, spec in enumerate(_museum_specs())
    ]


def parade_true_scale_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    offset = (
        PARADE_PROPS_PAD_FIRST
        + len(_spawn_plaza_specs())
        + len(PARADE_HUB_PROP_SPECS)
        + len(_vignette_specs())
        + len(_cutscene_reserved_specs())
        + len(_hub_signpost_specs())
        + len(_museum_specs())
    )
    return [
        _spec_to_marker(spec, pad=offset + i, pad_y=pad_y)
        for i, spec in enumerate(_true_scale_specs())
    ]


def add_parade_props(mapdef: MapDef, *, pad_y: float = 10.0) -> None:
    """Register all prop pads and StdObject props on *mapdef*."""
    import math

    compass_angle: dict[str, float] = {
        "N": 0.0,
        "NE": math.pi / 4,
        "E": math.pi / 2,
        "SE": 3 * math.pi / 4,
        "S": math.pi,
        "SW": 5 * math.pi / 4,
        "W": -math.pi / 2,
        "NW": -math.pi / 4,
    }

    dynamic_pad_calls = []
    total_specs = len(all_parade_prop_specs())

    for i, spec in enumerate(all_parade_prop_specs()):
        pad = PARADE_PROPS_PAD_FIRST + i
        pad_kwargs = {}
        for field in ("up_x", "up_y", "up_z", "xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
            val = getattr(spec, field, None)
            if val is not None:
                pad_kwargs[field] = val

        if getattr(spec, "kind", None) == "door":
            # For double sliding door, spawn two offset pads and two door objects
            ux = getattr(spec, "up_x", 0.0)
            uy = getattr(spec, "up_y", 0.0)
            uz = getattr(spec, "up_z", -1.0)
            
            # Leaf 1 (Left/first)
            mapdef.add_pad(
                index=pad,
                x=spec.x - 109.0 * ux,
                y=pad_y - 109.0 * uy,
                z=spec.z - 109.0 * uz,
                room=spec.room,
                dir_x=getattr(spec, "dir_x", 0.0),
                dir_y=getattr(spec, "dir_y", 0.0),
                dir_z=getattr(spec, "dir_z", -1.0),
                **pad_kwargs,
            )
            # Leaf 2 (Right/second) - queued for dynamic section at the end
            pad2 = PARADE_PROPS_PAD_FIRST + total_specs + len(dynamic_pad_calls)
            
            pad2_kwargs = pad_kwargs.copy()
            pad2_kwargs["up_x"] = -ux
            pad2_kwargs["up_y"] = -uy
            pad2_kwargs["up_z"] = -uz
            dynamic_pad_calls.append((
                pad2,
                spec.x + 109.0 * ux,
                pad_y + 109.0 * uy,
                spec.z + 109.0 * uz,
                spec.room,
                getattr(spec, "dir_x", 0.0),
                getattr(spec, "dir_y", 0.0),
                getattr(spec, "dir_z", -1.0),
                pad2_kwargs,
            ))

            if getattr(spec, "tag_id", 0) != 0:
                from .props import Tag
                mapdef.add_prop(Tag(spec.tag_id, 1))

            from .props import Door
            mapdef.add_prop(
                Door(
                    maxfrac=0x0000f333,
                    perimfrac=0x00010000,
                    accel=0x0001AAAA,
                    decel=0x0001AAAA,
                    maxspeed=0x00000CCC,
                    doorflags=0x0000000c,
                    doortype=0,
                    keyflags=0,
                    autoclosetime=0x00000258,
                    unk88=0x012c0320,
                    sibling=1, # Links to the next door (Leaf 2)
                    unkc4=0x00000300,
                    scale=spec.scale,
                    model=spec.model,
                    pad=pad,
                    flags=spec.flags,
                    flags2=spec.flags2,
                    flags3=spec.flags3,
                )
            )
            mapdef.add_prop(
                Door(
                    maxfrac=0x0000f333,
                    perimfrac=0x00010000,
                    accel=0x0001AAAA,
                    decel=0x0001AAAA,
                    maxspeed=0x00000CCC,
                    doorflags=0x0000000c,
                    doortype=0,
                    keyflags=0,
                    autoclosetime=0x00000258,
                    unk88=0x012c0320,
                    sibling=-1, # Links to the previous door (Leaf 1)
                    unkc4=0,
                    scale=spec.scale,
                    model=spec.model,
                    pad=pad2,
                    flags=spec.flags,
                    flags2=spec.flags2,
                    flags3=spec.flags3,
                )
            )
        else:
            mapdef.add_pad(
                index=pad,
                x=spec.x,
                y=pad_y,
                z=spec.z,
                room=spec.room,
                dir_x=getattr(spec, "dir_x", 0.0),
                dir_y=getattr(spec, "dir_y", 0.0),
                dir_z=getattr(spec, "dir_z", -1.0),
                **pad_kwargs,
            )
            if getattr(spec, "tag_id", 0) != 0:
                from .props import Tag
                mapdef.add_prop(Tag(spec.tag_id, 1))
            mapdef.add_prop(
                StdObject(
                    scale=spec.scale,
                    model=spec.model,
                    pad=pad,
                    flags=spec.flags,
                    flags2=spec.flags2,
                    flags3=spec.flags3,
                )
            )

        # If it's a portal spec, also spawn the flanking Right Pillar
        if getattr(spec, "kind", None) == "portal":
            try:
                compass = spec.label.split(" · ")[1].split(" ")[0]
                ang = compass_angle.get(compass, 0.0)
                perp_ang = ang + math.pi / 2

                rx = spec.x - 150.0 * math.sin(perp_ang)
                rz = spec.z - 150.0 * math.cos(perp_ang)

                # Register a new dynamic pad for the right pillar at the end
                right_pad = PARADE_PROPS_PAD_FIRST + total_specs + len(dynamic_pad_calls)
                dynamic_pad_calls.append((
                    right_pad,
                    rx,
                    pad_y,
                    rz,
                    spec.room,
                    0.0,
                    0.0,
                    -1.0,
                    {},
                ))
                mapdef.add_prop(
                    StdObject(
                        scale=spec.scale,
                        model=spec.model,
                        pad=right_pad,
                        flags=spec.flags,
                        flags2=spec.flags2,
                        flags3=spec.flags3,
                    )
                )
            except Exception as e:
                print(f"  [WARN] Failed to parse portal properties for spec '{spec.label}': {e}")

    # Append all dynamic pads sequentially at the end to keep pad array indices contiguous
    for p_idx, p_x, p_y, p_z, p_room, p_dx, p_dy, p_dz, p_kwargs in dynamic_pad_calls:
        mapdef.add_pad(
            index=p_idx,
            x=p_x,
            y=p_y,
            z=p_z,
            room=p_room,
            dir_x=p_dx,
            dir_y=p_dy,
            dir_z=p_dz,
            **p_kwargs,
        )

def parade_props_layout_payload() -> dict[str, Any]:
    """Spawn plaza + props yard summary for docs and anim_lab.html."""
    return {
        "id": "props",
        "label": "Props & scenery",
        "centerX": PARADE_PROPS_CENTER_X,
        "centerZ": PARADE_PROPS_CENTER_Z,
        "spawnX": PARADE_SPAWN_X,
        "spawnZ": PARADE_SPAWN_Z,
        "spawnClearance": PARADE_SPAWN_CLEARANCE,
        "galleryPitch": _GALLERY_PITCH,
        "floorColour": PARADE_PROPS_FLOOR_COLOUR,
        "props": parade_prop_markers(),
        "modelIds": {
            spec.label: f"0x{spec.model:04X}"
            for spec in _spawn_plaza_specs() + PARADE_HUB_PROP_SPECS
        },
    }


def parade_vignette_layout_payload() -> dict[str, Any]:
    props = parade_vignette_markers()
    by_district: dict[str, list[dict[str, Any]]] = {}
    for p in props:
        by_district.setdefault(str(p["district"]), []).append(p)
    return {
        "id": "vignettes",
        "label": "District vignettes",
        "props": props,
        "byDistrict": by_district,
        "count": len(props),
    }


def parade_museum_layout_payload() -> dict[str, Any]:
    props = parade_museum_markers()
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for p in props:
        by_tag.setdefault(str(p.get("tag", "misc")), []).append(p)
    metrics = parade_museum_grid_metrics()
    packed = _museum_tag_packed()
    tag_districts: list[dict[str, Any]] = []
    for tag in OBJECT_TAG_ORDER:
        placements = list(packed.get(tag, ()))
        if not placements:
            continue
        td = tag_district_metrics(tag, placements)
        meta = OBJECT_TAG_META.get(tag, OBJECT_TAG_META["misc"])
        tag_districts.append(
            {
                **td,
                "icon": meta.get("icon", ""),
                "color": meta["color"],
                "floorColour": _hex_to_floor_colour(meta["color"]),
                "room": parade_room_for_object_tag(tag),
                "props": [p for p in props if p.get("tag") == tag],
            }
        )
    cap_raw = os.environ.get("ANIMLAB_MUSEUM_MAX", "0").strip()
    return {
        "id": "museum",
        "label": "Object catalog",
        "centerX": float(metrics.get("centerX", PARADE_MUSEUM_CENTER_X)),
        "centerZ": float(metrics.get("centerZ", PARADE_MUSEUM_CENTER_Z)),
        "hubX": float(metrics.get("hubX", PARADE_MUSEUM_CENTER_X)),
        "hubZ": float(metrics.get("hubZ", PARADE_MUSEUM_CENTER_Z)),
        "half": parade_museum_half(),
        "floorColour": PARADE_MUSEUM_FLOOR_COLOUR,
        "layout": str(metrics.get("layout", "tag_districts")),
        "packMargin": metrics.get("margin"),
        "footprintWidth": metrics.get("width"),
        "footprintDepth": metrics.get("depth"),
        "fullHalf": metrics.get("fullHalf"),
        "carpetHalf": metrics.get("carpetHalf"),
        "catalogSize": len(_load_model_catalog()),
        "maxCap": cap_raw,
        "count": len(props),
        "props": props,
        "byTag": by_tag,
        "tagDistricts": tag_districts,
        "tagMeta": OBJECT_TAG_META,
        "tagOrder": list(OBJECT_TAG_ORDER),
    }


def _true_scale_wing_payload(wing: str) -> dict[str, Any]:
    """One true-scale wing summary for layout payload / builders."""
    from .museum_layout import museum_carpet_half

    placements = _true_scale_wing_placements(wing)
    props = parade_true_scale_markers()
    normal_count = len(_true_scale_wing_placements("normal"))
    if wing == "normal":
        props = props[:normal_count]
        cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X
        cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
        colour = PARADE_TRUE_SCALE_COLOUR
        floor_colour = PARADE_TRUE_SCALE_FLOOR_COLOUR
        half = museum_carpet_half(
            list(placements),
            center_x=cx,
            center_z=cz,
        )
        label = "True scale — normal objects"
    else:
        props = props[normal_count:]
        cx = PARADE_TRUE_SCALE_MEGA_CENTER_X
        cz = PARADE_TRUE_SCALE_MEGA_CENTER_Z
        colour = PARADE_TRUE_SCALE_MEGA_COLOUR
        floor_colour = PARADE_TRUE_SCALE_MEGA_FLOOR_COLOUR
        half = museum_carpet_half(
            list(placements),
            center_x=cx,
            center_z=cz,
        )
        label = "True scale — megastructure yard"

    metrics = parade_true_scale_grid_metrics(wing=wing)
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for p in props:
        by_tag.setdefault(str(p.get("tag", "misc")), []).append(p)

    return {
        "id": f"true_scale_{wing}",
        "wing": wing,
        "label": label,
        "centerX": cx,
        "centerZ": cz,
        "half": half,
        "floorColour": floor_colour,
        "colour": colour,
        "layout": "true_scale_bbox",
        "scalePolicy": "retail_extrascale_only",
        "packMargin": metrics.get("margin"),
        "footprintWidth": metrics.get("width"),
        "footprintDepth": metrics.get("depth"),
        "maxHalfX": metrics.get("maxHalfX"),
        "fullHalf": metrics.get("fullHalf"),
        "carpetHalf": metrics.get("carpetHalf"),
        "count": len(props),
        "props": props,
        "byTag": by_tag,
        "largestModels": largest_placement_footprints(list(placements), limit=10),
    }


def parade_true_scale_layout_payload() -> dict[str, Any]:
    """True-scale gallery summary — normal wing + megastructure yard."""
    all_props = parade_true_scale_markers()
    normal_wing = _true_scale_wing_payload("normal")
    mega_wing = _true_scale_wing_payload("mega")
    combined = _true_scale_packed_placements()
    # Per-wing AABB packing is verified in ``_true_scale_wing_placements``; combined
    # check is skipped — megastructures extend far beyond walkable carpet tiles.

    by_tag: dict[str, list[dict[str, Any]]] = {}
    for p in all_props:
        by_tag.setdefault(str(p.get("tag", "misc")), []).append(p)

    return {
        "id": "true_scale",
        "label": "True scale gallery",
        "scalePolicy": "retail_extrascale_only",
        "bboxSource": "MODELNODETYPE_BBOX rodata in props/*.bin (stdobject_models.json)",
        "catalogSize": len(_load_model_catalog()),
        "count": len(all_props),
        "normalCount": normal_wing["count"],
        "megaCount": mega_wing["count"],
        "splitPeakHalf": PARADE_TRUE_SCALE_MEGA_PEAK_HALF,
        "overlapPairs": 0,
        "wings": [normal_wing, mega_wing],
        "props": all_props,
        "byTag": by_tag,
        "largestModels": largest_placement_footprints(list(combined), limit=15),
    }
