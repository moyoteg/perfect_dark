"""Dimension-aware prop museum packing for Anim Lab.

Uses per-model XZ half-extents from ``stdobject_models.json`` (bbox rodata in
``src/assets/ntsc-final/files/props/*.bin`` at extrascale 0x0100). Placement is
greedy row packing with clearance between AABBs.
"""

from __future__ import annotations

import math
from typing import Any

# Clearance between model footprints (world units).
PARADE_MUSEUM_PACK_MARGIN = 80.0
# Carpet padding beyond outermost prop edge.
PARADE_MUSEUM_GRID_MARGIN = 600.0
# Soft cap on row length before wrapping to the next aisle (world units).
PARADE_MUSEUM_ROW_MAX_X = 26000.0
# Max XZ half-extent for museum showcase (larger bboxes shrink uniformly for display + packing).
PARADE_MUSEUM_SHOWCASE_MAX_HALF = 450.0
# Engine seg box faces use s16 vertex coords — arena half cannot exceed ~32767.
PARADE_ARENA_HALF_S16_MAX = 32000.0

# Conservative XZ half-extent when bbox rodata is missing (at scale 0x0100).
_TAG_FALLBACK_HALF: dict[str, float] = {
    "architecture": 320.0,
    "furniture": 110.0,
    "military": 90.0,
    "lab": 140.0,
    "ci": 130.0,
    "eld": 120.0,
    "lip": 120.0,
    "skedar": 150.0,
    "misc": 100.0,
}
_DEFAULT_FALLBACK_HALF = 100.0


def model_half_extents(row: dict[str, Any], *, scale: int | None = None) -> tuple[float, float]:
    """XZ half-extents in world units for a catalog row at its retail extrascale."""
    extrascale = int(scale if scale is not None else row.get("scale", 0x0100))
    factor = extrascale / 256.0
    tag = str(row.get("tag", "misc"))
    base_hx = float(row.get("halfX") or row.get("halfx") or 0.0)
    base_hz = float(row.get("halfZ") or row.get("halfz") or 0.0)
    if base_hx <= 0.0 or base_hz <= 0.0:
        fb = _TAG_FALLBACK_HALF.get(tag, _DEFAULT_FALLBACK_HALF)
        base_hx = base_hx if base_hx > 0.0 else fb
        base_hz = base_hz if base_hz > 0.0 else fb
    return base_hx * factor, base_hz * factor


def model_showcase_extents(
    row: dict[str, Any], *, scale: int | None = None
) -> tuple[float, float, float]:
    """XZ half-extents and uniform scale factor for museum placement (fits arena)."""
    hx, hz = model_half_extents(row, scale=scale)
    peak = max(hx, hz)
    cap = PARADE_MUSEUM_SHOWCASE_MAX_HALF
    if peak <= cap:
        return hx, hz, 1.0
    shrink = cap / peak
    return hx * shrink, hz * shrink, shrink


def _pack_rows_at_center(
    items: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    margin: float,
    row_max_x: float,
) -> list[dict[str, Any]]:
    """Greedy row pack for pre-sized items; shift block centroid to (*center_x*, *center_z*)."""
    if not items:
        return []

    pack: list[dict[str, Any]] = []
    cursor_x = 0.0
    row_z = 0.0
    row_depth = 0.0

    for it in items:
        hx, hz = it["hx"], it["hz"]
        if pack and cursor_x > 0.0 and cursor_x + hx > row_max_x:
            row_z += row_depth + margin
            cursor_x = 0.0
            row_depth = 0.0

        cx = cursor_x + hx
        cz = row_z + hz
        pack.append({**it, "packX": cx, "packZ": cz})
        cursor_x += 2.0 * hx + margin
        row_depth = max(row_depth, 2.0 * hz)

    min_x = min(p["packX"] - p["hx"] for p in pack)
    max_x = max(p["packX"] + p["hx"] for p in pack)
    min_z = min(p["packZ"] - p["hz"] for p in pack)
    max_z = max(p["packZ"] + p["hz"] for p in pack)
    block_cx = (min_x + max_x) / 2.0
    block_cz = (min_z + max_z) / 2.0
    shift_x = center_x - block_cx
    shift_z = center_z - block_cz

    for p in pack:
        p["x"] = p["packX"] + shift_x
        p["z"] = p["packZ"] + shift_z
    return pack


def pack_museum_rows(
    rows: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    margin: float = PARADE_MUSEUM_PACK_MARGIN,
    row_max_x: float = PARADE_MUSEUM_ROW_MAX_X,
) -> list[dict[str, Any]]:
    """Pack catalog rows into non-overlapping (x, z) centres; largest props first."""
    if not rows:
        return []

    items: list[dict[str, Any]] = []
    for row in rows:
        hx, hz, scale_factor = model_showcase_extents(row)
        items.append(
            {
                "row": row,
                "hx": hx,
                "hz": hz,
                "scaleFactor": scale_factor,
                "sort": max(hx, hz),
            }
        )
    items.sort(key=lambda it: (-it["sort"], int(it["row"]["model"])))
    return _pack_rows_at_center(
        items,
        center_x=center_x,
        center_z=center_z,
        margin=margin,
        row_max_x=row_max_x,
    )


# True-scale gallery — retail extrascale only; bbox from prop bin rodata (no showcase shrink).
PARADE_TRUE_SCALE_MEGA_PEAK_HALF = PARADE_MUSEUM_SHOWCASE_MAX_HALF
PARADE_TRUE_SCALE_MEGA_ROW_MAX_X = 50000.0


def pack_true_scale_rows(
    rows: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    margin: float = PARADE_MUSEUM_PACK_MARGIN,
    row_max_x: float = PARADE_MUSEUM_ROW_MAX_X,
    allow_tag_fallback: bool = False,
) -> list[dict[str, Any]]:
    """Pack rows at **actual** retail bbox half-extents (``scaleFactor`` always 1.0).

    Dimensions come from ``MODELNODETYPE_BBOX`` rodata in ``props/*.bin`` via
    ``stdobject_models.json`` — not heuristics. Tag fallbacks apply only when
    *allow_tag_fallback* is True and bbox rodata is missing.
    """
    if not rows:
        return []

    items: list[dict[str, Any]] = []
    for row in rows:
        if allow_tag_fallback:
            hx, hz = model_half_extents(row)
        else:
            base_hx = float(row.get("halfX") or row.get("halfx") or 0.0)
            base_hz = float(row.get("halfZ") or row.get("halfz") or 0.0)
            if base_hx <= 0.0 or base_hz <= 0.0:
                raise ValueError(
                    f"true-scale pack missing bbox for model 0x{int(row['model']):04X} "
                    f"({row.get('label', row.get('name', '?'))})"
                )
            extrascale = int(row.get("scale", 0x0100))
            factor = extrascale / 256.0
            hx, hz = base_hx * factor, base_hz * factor
        items.append(
            {
                "row": row,
                "hx": hx,
                "hz": hz,
                "scaleFactor": 1.0,
                "sort": max(hx, hz),
            }
        )
    items.sort(key=lambda it: (-it["sort"], int(it["row"]["model"])))
    return _pack_rows_at_center(
        items,
        center_x=center_x,
        center_z=center_z,
        margin=margin,
        row_max_x=row_max_x,
    )


def largest_placement_footprints(
    placements: list[dict[str, Any]], *, limit: int = 10
) -> list[dict[str, Any]]:
    """Top *limit* models by peak XZ half-extent (for layout payload / docs)."""
    ranked = sorted(placements, key=lambda p: (-max(p["hx"], p["hz"]), int(p["row"]["model"])))
    out: list[dict[str, Any]] = []
    for place in ranked[:limit]:
        row = place["row"]
        out.append(
            {
                "model": int(row["model"]),
                "modelHex": f"0x{int(row['model']):04X}",
                "label": str(row.get("label", row.get("name", "Model"))),
                "tag": str(row.get("tag", "misc")),
                "halfX": float(place["hx"]),
                "halfZ": float(place["hz"]),
                "peakHalf": max(float(place["hx"]), float(place["hz"])),
                "width": 2.0 * float(place["hx"]),
                "depth": 2.0 * float(place["hz"]),
            }
        )
    return out


def museum_s16_half_cap(*, center_x: float, center_z: float) -> float:
    """Max half-extent for tile/seg coords (vertices pack as u16/s16)."""
    return float(max(1200, 32767 - int(max(abs(center_x), abs(center_z)))))


def museum_footprint_half(
    placements: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    margin: float = PARADE_MUSEUM_GRID_MARGIN,
) -> float:
    """Axis-aligned half-extent of the museum from packed placements."""
    if not placements:
        return 1200.0
    half_x = max(abs(p["x"] - center_x) + p["hx"] for p in placements)
    half_z = max(abs(p["z"] - center_z) + p["hz"] for p in placements)
    return max(half_x, half_z, 1200.0) + margin


def museum_carpet_half(
    placements: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    margin: float = PARADE_MUSEUM_GRID_MARGIN,
) -> float:
    """Walkable carpet half — full footprint clamped to tile coordinate limits."""
    raw = museum_footprint_half(placements, center_x=center_x, center_z=center_z, margin=margin)
    return min(raw, museum_s16_half_cap(center_x=center_x, center_z=center_z))


def museum_layout_metrics(
    placements: list[dict[str, Any]],
    *,
    center_x: float,
    center_z: float,
    count: int,
) -> dict[str, float]:
    """Footprint summary for builders and layout payload."""
    if not placements:
        return {
            "count": float(count),
            "half": 1200.0,
            "carpetHalf": 1200.0,
            "centerX": center_x,
            "centerZ": center_z,
            "layout": "dimension_packed",
            "margin": PARADE_MUSEUM_PACK_MARGIN,
        }
    min_x = min(p["x"] - p["hx"] for p in placements)
    max_x = max(p["x"] + p["hx"] for p in placements)
    min_z = min(p["z"] - p["hz"] for p in placements)
    max_z = max(p["z"] + p["hz"] for p in placements)
    full_half = museum_footprint_half(placements, center_x=center_x, center_z=center_z)
    carpet_half = museum_carpet_half(placements, center_x=center_x, center_z=center_z)
    return {
        "count": float(count),
        "half": carpet_half,
        "fullHalf": full_half,
        "carpetHalf": carpet_half,
        "centerX": center_x,
        "centerZ": center_z,
        "layout": "dimension_packed",
        "margin": PARADE_MUSEUM_PACK_MARGIN,
        "width": max_x - min_x,
        "depth": max_z - min_z,
        "maxHalfX": max(p["hx"] for p in placements),
        "maxHalfZ": max(p["hz"] for p in placements),
    }


def verify_museum_placements(
    placements: list[dict[str, Any]],
    *,
    margin: float = 0.0,
) -> list[tuple[int, int]]:
    """Return pairs of indices with overlapping XZ AABBs (empty = success)."""
    overlaps: list[tuple[int, int]] = []
    n = len(placements)
    for i in range(n):
        a = placements[i]
        for j in range(i + 1, n):
            b = placements[j]
            dx = abs(a["x"] - b["x"])
            dz = abs(a["z"] - b["z"])
            need_x = a["hx"] + b["hx"] + margin
            need_z = a["hz"] + b["hz"] + margin
            if dx < need_x and dz < need_z:
                overlaps.append((i, j))
    return overlaps


# --- Object catalog tag districts (showcase museum split by stdobject_models tag) ---

OBJECT_TAG_ORDER: tuple[str, ...] = (
    "furniture",
    "military",
    "lab",
    "architecture",
    "ci",
    "skedar",
    "misc",
    "eld",
    "lip",
)

OBJECT_TAG_META: dict[str, dict[str, str]] = {
    "furniture": {"label": "Furniture", "color": "#eab308", "icon": "🪑"},
    "military": {"label": "Military", "color": "#94a3b8", "icon": "🎖"},
    "lab": {"label": "Lab", "color": "#22d3ee", "icon": "🔬"},
    "architecture": {"label": "Architecture", "color": "#a78bfa", "icon": "🏛"},
    "ci": {"label": "CI", "color": "#f472b6", "icon": "🏢"},
    "skedar": {"label": "Skedar", "color": "#ef4444", "icon": "👽"},
    "misc": {"label": "Misc", "color": "#64748b", "icon": "📦"},
    "eld": {"label": "Eld", "color": "#84cc16", "icon": "🌲"},
    "lip": {"label": "Lip", "color": "#fb923c", "icon": "💋"},
}

# Southwest object-catalog megazone — far from spawn, connected by labelled corridors.
OBJECT_CATALOG_HUB_X = -21000.0
OBJECT_CATALOG_HUB_Z = -26500.0
# Orbit radius for non-misc tag districts around the hub (misc sits at hub centre).
OBJECT_TAG_ORBIT_RADIUS = 8500.0


def tag_district_offset(tag: str) -> tuple[float, float]:
    """XZ offset from catalog hub for *tag* (misc at centre; others on compass ring)."""
    r = OBJECT_TAG_ORBIT_RADIUS
    compass: dict[str, tuple[float, float]] = {
        "misc": (0.0, 0.0),
        "architecture": (0.0, r),
        "lab": (-r * 0.87, r * 0.5),
        "ci": (r * 0.87, r * 0.5),
        "military": (-r, -r * 0.25),
        "furniture": (0.0, -r * 0.85),
        "skedar": (r, -r * 0.25),
        "eld": (-r * 0.5, r * 0.75),
        "lip": (r * 0.5, r * 0.75),
    }
    return compass.get(tag, (0.0, 0.0))


def tag_district_center(tag: str) -> tuple[float, float]:
    """World (x, z) centre for a tag district cluster."""
    ox, oz = tag_district_offset(tag)
    return OBJECT_CATALOG_HUB_X + ox, OBJECT_CATALOG_HUB_Z + oz


def group_rows_by_tag(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Bucket catalog rows by ``tag`` field (stable sort within tag)."""
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        tag = str(row.get("tag", "misc"))
        by_tag.setdefault(tag, []).append(row)
    for tag_rows in by_tag.values():
        tag_rows.sort(key=lambda r: int(r["model"]))
    return by_tag


def pack_tag_districts(
    rows: list[dict[str, Any]],
    *,
    margin: float = PARADE_MUSEUM_PACK_MARGIN,
    row_max_x: float = PARADE_MUSEUM_ROW_MAX_X,
) -> dict[str, list[dict[str, Any]]]:
    """Pack each tag into its own dimension-aware cluster; return tag → placements."""
    by_tag = group_rows_by_tag(rows)
    packed: dict[str, list[dict[str, Any]]] = {}
    for tag in OBJECT_TAG_ORDER:
        tag_rows = by_tag.pop(tag, [])
        if not tag_rows:
            continue
        cx, cz = tag_district_center(tag)
        packed[tag] = pack_museum_rows(
            tag_rows,
            center_x=cx,
            center_z=cz,
            margin=margin,
            row_max_x=row_max_x,
        )
    # Any unexpected tags still land in misc orbit.
    for tag, tag_rows in sorted(by_tag.items()):
        cx, cz = tag_district_center("misc")
        packed[tag] = pack_museum_rows(
            tag_rows,
            center_x=cx,
            center_z=cz,
            margin=margin,
            row_max_x=row_max_x,
        )
    return packed


def flatten_tag_placements(packed: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """All placements in OBJECT_TAG_ORDER (for overlap checks / flat spec lists)."""
    out: list[dict[str, Any]] = []
    seen_tags = set(packed.keys())
    for tag in OBJECT_TAG_ORDER:
        if tag in packed:
            for p in packed[tag]:
                out.append({**p, "tag": tag})
            seen_tags.discard(tag)
    for tag in sorted(seen_tags):
        for p in packed[tag]:
            out.append({**p, "tag": tag})
    return out


def catalog_megazone_metrics(
    packed: dict[str, list[dict[str, Any]]],
    *,
    count: int,
) -> dict[str, float]:
    """Bounding half-extent of the full tag-district megazone from packed placements."""
    flat = flatten_tag_placements(packed)
    if not flat:
        return {
            "count": float(count),
            "half": 1200.0,
            "carpetHalf": 1200.0,
            "centerX": OBJECT_CATALOG_HUB_X,
            "centerZ": OBJECT_CATALOG_HUB_Z,
            "layout": "tag_districts",
        }
    min_x = min(p["x"] - p["hx"] for p in flat)
    max_x = max(p["x"] + p["hx"] for p in flat)
    min_z = min(p["z"] - p["hz"] for p in flat)
    max_z = max(p["z"] + p["hz"] for p in flat)
    cx = (min_x + max_x) / 2.0
    cz = (min_z + max_z) / 2.0
    half_x = max(abs(min_x - cx), abs(max_x - cx)) + PARADE_MUSEUM_GRID_MARGIN
    half_z = max(abs(min_z - cz), abs(max_z - cz)) + PARADE_MUSEUM_GRID_MARGIN
    raw_half = max(half_x, half_z, 1200.0)
    cap = museum_s16_half_cap(center_x=cx, center_z=cz)
    carpet_half = min(raw_half, cap)
    return {
        "count": float(count),
        "half": carpet_half,
        "fullHalf": raw_half,
        "carpetHalf": carpet_half,
        "centerX": cx,
        "centerZ": cz,
        "hubX": OBJECT_CATALOG_HUB_X,
        "hubZ": OBJECT_CATALOG_HUB_Z,
        "layout": "tag_districts",
        "margin": PARADE_MUSEUM_PACK_MARGIN,
        "width": max_x - min_x,
        "depth": max_z - min_z,
    }


def tag_district_metrics(
    tag: str,
    placements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-tag footprint summary for builders and UI."""
    cx, cz = tag_district_center(tag)
    meta = OBJECT_TAG_META.get(tag, OBJECT_TAG_META["misc"])
    carpet_half = museum_carpet_half(placements, center_x=cx, center_z=cz)
    return {
        "tag": tag,
        "label": meta["label"],
        "icon": meta.get("icon", ""),
        "color": meta["color"],
        "centerX": cx,
        "centerZ": cz,
        "half": carpet_half,
        "carpetHalf": carpet_half,
        "count": len(placements),
    }
