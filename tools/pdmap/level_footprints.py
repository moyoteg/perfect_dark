"""Retail pad bounding boxes for Anim Lab level-island footprints.

Maps each ``STAGE_*`` row in ``stagetable.c`` to its ``FILE_BG_*_PADS`` asset,
loads the corresponding ``src/assets/ntsc-final/pads/<stem>.json``, and derives
walkable island half-extents from pad positions (XZ span). Used by
``anim_levels`` to size coloured footprint floors — not full level geometry.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_STAGETABLE_PATH = _ROOT / "src" / "game" / "stagetable.c"
_FILES_H_PATH = _ROOT / "src" / "include" / "files.h"
_LIST_C_PATH = _ROOT / "src" / "assets" / "ntsc-final" / "files" / "list.c"
_PADS_DIR = _ROOT / "src" / "assets" / "ntsc-final" / "pads"

# Walkable island sizing (world units).
FOOTPRINT_MIN_HALF = 200.0  # 400×400 u minimum footprint
FOOTPRINT_MAX_HALF = 600.0  # cap so 89 islands fit in one bg file
FOOTPRINT_DEFAULT_HALF = 300.0  # 600×600 u when pads missing or empty


@lru_cache(maxsize=1)
def _file_id_to_path() -> dict[int, str]:
    text = _LIST_C_PATH.read_text(encoding="utf-8", errors="replace")
    out: dict[int, str] = {}
    for match in re.finditer(r"/\*(0x[0-9a-fA-F]+)\*/\s*\"([^\"]+)\"", text):
        out[int(match.group(1), 16)] = match.group(2)
    return out


@lru_cache(maxsize=1)
def _pads_const_to_file_id() -> dict[str, int]:
    text = _FILES_H_PATH.read_text(encoding="utf-8", errors="replace")
    out: dict[str, int] = {}
    for match in re.finditer(r"#define\s+(FILE_BG_\w+_PADS)\s+(0x[0-9A-Fa-f]+)", text):
        out[match.group(1)] = int(match.group(2), 16)
    return out


def _stem_from_pads_path(path: str) -> str:
    """``bgdata/bg_ref_padsZ`` → ``ref``."""
    name = path.removeprefix("bgdata/bg_").removesuffix("_padsZ")
    return name.lower()


@lru_cache(maxsize=1)
def stage_pads_stem_by_symbol() -> dict[str, str]:
    """``STAGE_SYMBOL`` → pads JSON stem (``ref``, ``sev``, ``mp11``, …)."""
    text = _STAGETABLE_PATH.read_text(encoding="utf-8", errors="replace")
    id_to_path = _file_id_to_path()
    const_to_id = _pads_const_to_file_id()
    mapping: dict[str, str] = {}
    for _hex, symbol, pads_const in re.findall(
        r"/\*(0x[0-9a-fA-F]+)\*/\s*(STAGE_\w+).*?(FILE_BG_\w+_PADS)", text
    ):
        _ = _hex
        file_id = const_to_id.get(pads_const)
        if file_id is None:
            continue
        path = id_to_path.get(file_id)
        if not path or "_pads" not in path:
            continue
        mapping[symbol] = _stem_from_pads_path(path)
    return mapping


def pads_json_path(stem: str) -> Path:
    return _PADS_DIR / f"{stem}.json"


@lru_cache(maxsize=1)
def pad_footprint_by_stem() -> dict[str, dict[str, Any]]:
    """Pad JSON stem → bbox summary from retail pad positions."""
    summaries: dict[str, dict[str, Any]] = {}
    for stem in set(stage_pads_stem_by_symbol().values()):
        path = pads_json_path(stem)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pads = data.get("pads") or []
        if not pads:
            summaries[stem] = {
                "stem": stem,
                "padCount": 0,
                "source": "empty",
            }
            continue
        xs = [float(p["pos"][0]) for p in pads]
        ys = [float(p["pos"][1]) for p in pads]
        zs = [float(p["pos"][2]) for p in pads]
        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)
        width = max_x - min_x
        depth = max_z - min_z
        half_x = width / 2.0
        half_z = depth / 2.0
        half = max(half_x, half_z)
        summaries[stem] = {
            "stem": stem,
            "padCount": len(pads),
            "minX": min_x,
            "maxX": max_x,
            "minY": min(ys),
            "maxY": max(ys),
            "minZ": min_z,
            "maxZ": max_z,
            "width": width,
            "depth": depth,
            "halfX": half_x,
            "halfZ": half_z,
            "half": half,
            "source": "pads",
        }
    return summaries


def pads_stem_for_stage(symbol: str) -> str | None:
    return stage_pads_stem_by_symbol().get(symbol)


def raw_footprint_for_stage(symbol: str) -> dict[str, Any]:
    """Unclamped pad bbox for a stage, or empty/default metadata."""
    stem = pads_stem_for_stage(symbol)
    if not stem:
        return {"symbol": symbol, "source": "missing"}
    cached = pad_footprint_by_stem().get(stem)
    if not cached:
        return {"symbol": symbol, "stem": stem, "source": "missing"}
    return {"symbol": symbol, **cached}


def clamp_island_half(raw_half: float) -> float:
    return max(FOOTPRINT_MIN_HALF, min(FOOTPRINT_MAX_HALF, raw_half))


def island_half_extents_for_stage(symbol: str) -> tuple[float, float]:
    """Return (half_x, half_z) for walkable island carpet — clamped per axis."""
    fp = raw_footprint_for_stage(symbol)
    if fp.get("source") not in ("pads",):
        half = FOOTPRINT_DEFAULT_HALF
        return half, half
    hx = clamp_island_half(float(fp.get("halfX", FOOTPRINT_DEFAULT_HALF)))
    hz = clamp_island_half(float(fp.get("halfZ", FOOTPRINT_DEFAULT_HALF)))
    return hx, hz


def island_layout_half_for_stage(symbol: str) -> float:
    """Grid spacing uses max axis half so serpentine bridges stay walkable."""
    hx, hz = island_half_extents_for_stage(symbol)
    return max(hx, hz)


def footprint_layout_payload() -> dict[str, Any]:
    """Summary for anim_lab.html / validation."""
    stems = stage_pads_stem_by_symbol()
    rows: list[dict[str, Any]] = []
    for symbol in sorted(stems):
        fp = raw_footprint_for_stage(symbol)
        hx, hz = island_half_extents_for_stage(symbol)
        rows.append(
            {
                "symbol": symbol,
                "stem": stems[symbol],
                "padCount": fp.get("padCount", 0),
                "width": fp.get("width"),
                "depth": fp.get("depth"),
                "halfX": hx,
                "halfZ": hz,
                "source": fp.get("source"),
            }
        )
    from_pads = sum(1 for r in rows if r["source"] == "pads")
    return {
        "count": len(rows),
        "fromPads": from_pads,
        "emptyOrMissing": len(rows) - from_pads,
        "minHalf": FOOTPRINT_MIN_HALF,
        "maxHalf": FOOTPRINT_MAX_HALF,
        "defaultHalf": FOOTPRINT_DEFAULT_HALF,
        "stages": rows,
    }
