#!/usr/bin/env python3
"""Generate StdObject model catalog from constants.h for Anim Lab prop museum.

Parses retail ``setup*.c`` stdobject(scale, MODEL_*, …) lines for per-model
extrascale (runtime multiplier = scale / 256). When a model appears at multiple
scales, the most frequent retail placement wins.

XZ footprint comes from ``MODELNODETYPE_BBOX`` rodata in
``src/assets/ntsc-final/files/props/*.bin`` (world units at extrascale 0x0100).

Output: tools/pdmap/data/stdobject_models.json (deterministic, committed).
"""

from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSTANTS_H = ROOT / "src" / "include" / "constants.h"
FILES_H = ROOT / "src" / "include" / "files.h"
GENERAL_C = ROOT / "src" / "game" / "modeldata" / "general.c"
LIST_C = ROOT / "src" / "assets" / "ntsc-final" / "files" / "list.c"
PROPS_DIR = ROOT / "src" / "assets" / "ntsc-final" / "files" / "props"
SETUPS_DIR = ROOT / "src" / "setups"
OUT_JSON = Path(__file__).resolve().parent / "data" / "stdobject_models.json"

_MODEL_VMA = 0x05000000
_BBOX_NODE_TYPE = 0x0A

_DEFINE_RE = re.compile(r"^#define\s+(MODEL_\w+)\s+(0x[0-9A-Fa-f]+)")
_STDOBJECT_RE = re.compile(r"stdobject\((0x[0-9A-Fa-f]+),\s*(MODEL_\w+)")

_SCALE_DEFAULT = 0x0100

# Title / logo StdObjects lack gameplay bbox rodata and are loaded only on the title screen.
_EXCLUDE_EXACT = frozenset({
    "MODEL_NINTENDOLOGO",
    "MODEL_NLOGO",
    "MODEL_NLOGO2",
    "MODEL_NLOGO3",
    "MODEL_PERFECTDARK",
    "MODEL_PDONE",
    "MODEL_PDTWO",
    "MODEL_PDTHREE",
    "MODEL_PDFOUR",
    "MODEL_RARELOGO",
    "MODEL_JPNLOGO",
    "MODEL_JPNPD",
})

# Exclude weapon pickups, chr attachments, and non-StdObject scenery.
_EXCLUDE_SUBSTR = (
    "GUN",
    "WEAPON",
    "CHR",
    "AMMO",
    "SHIELD",
    "PICKUP",
    "KEY",
    "CARD",
    "BOND",
    "DOORHAND",
    "HAND",
    "FIST",
    "KNIFE",
    "ROCKET",
    "GRENADE",
    "MINE",
    "PROXY",
    "BULLET",
    "SHELL",
    "CLIP",
    "MAGAZINE",
    "LASER",
    "REMOTE",
    "TIMED",
    "PROX",
    "COMBAT",
    "THROW",
)

_TAG_RULES: tuple[tuple[str, str], ...] = (
    ("A51_", "military"),
    ("LAB_", "lab"),
    ("CI_", "ci"),
    ("ELD_", "eld"),
    ("LIP_", "lip"),
    ("SK_", "skedar"),
    ("DESK", "furniture"),
    ("CHAIR", "furniture"),
    ("TABLE", "furniture"),
    ("CRATE", "military"),
    ("CONSOLE", "lab"),
    ("MAINFRAME", "lab"),
    ("TERMINAL", "lab"),
    ("DOOR", "architecture"),
    ("WINDOW", "architecture"),
    ("BED", "furniture"),
    ("TOILET", "furniture"),
    ("SINK", "furniture"),
    ("TV", "furniture"),
)


def _tag_for(name: str) -> str:
    for needle, tag in _TAG_RULES:
        if needle in name:
            return tag
    return "misc"


def _placable(name: str) -> bool:
    if name in _EXCLUDE_EXACT:
        return False
    upper = name.upper()
    for bad in _EXCLUDE_SUBSTR:
        if bad in upper:
            return False
    return True


def _parse_file_table() -> dict[int, str]:
    """Map file id → ROM asset name (e.g. 0x0100 → PtvscreenZ)."""
    text = LIST_C.read_text(encoding="utf-8", errors="replace")
    return {
        int(m.group(1), 16): m.group(2)
        for m in re.finditer(r"/\*0x([0-9A-Fa-f]+)\*/\s*\"([^\"]+)\"", text)
    }


def _parse_file_constants() -> dict[str, int]:
    text = FILES_H.read_text(encoding="utf-8", errors="replace")
    return {
        m.group(1): int(m.group(2), 16)
        for m in re.finditer(r"#define\s+(FILE_\w+)\s+(0x[0-9A-Fa-f]+)", text)
    }


def _parse_model_file_ids() -> dict[int, int]:
    """Map model id → prop file id from g_ModelStates (first table in general.c)."""
    text = GENERAL_C.read_text(encoding="utf-8", errors="replace")
    file_const = _parse_file_constants()
    out: dict[int, int] = {}
    for m in re.finditer(
        r"/\*0x([0-9A-Fa-f]+)\*/\s*\{\s*NULL,\s*(FILE_\w+)",
        text,
    ):
        model_id = int(m.group(1), 16)
        if model_id in out:
            continue
        file_name = m.group(2)
        if file_name in file_const:
            out[model_id] = file_const[file_name]
    return out


def _prop_bin_for_file_id(file_id: int, files: dict[int, str]) -> Path | None:
    """Resolve a prop ``.bin`` on disk for a ROM file id."""
    rom_name = files.get(file_id, "")
    if not (rom_name.startswith("P") and rom_name.endswith("Z")):
        return None
    stem = rom_name[1:-1].lower()
    direct = PROPS_DIR / f"{stem}.bin"
    if direct.is_file():
        return direct
    return None


def _bbox_from_prop_bin(path: Path) -> tuple[float, float, float, float, float, float] | None:
    """Read the first bbox node rodata from a prop model ``.bin``."""
    data = path.read_bytes()
    for offset in range(0, len(data) - 8, 2):
        if (struct.unpack(">H", data[offset : offset + 2])[0] & 0xFF) != _BBOX_NODE_TYPE:
            continue
        rodata_off = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        file_off = rodata_off - _MODEL_VMA
        if file_off < 0 or file_off + 28 > len(data):
            continue
        return struct.unpack(">6f", data[file_off + 4 : file_off + 28])
    return None


def _xz_footprint_from_bbox(
    bbox: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float]:
    """Return width, depth, halfX, halfZ at extrascale 0x0100."""
    xmin, xmax, ymin, ymax, zmin, zmax = bbox
    width = xmax - xmin
    depth = zmax - zmin
    height = ymax - ymin
    # Flat panels (windows, screens) store depth in Y when Z extent is ~0.
    if depth < 1.0:
        depth = max(depth, height)
    if width < 1.0:
        width = max(width, height)
    return width, depth, width / 2.0, depth / 2.0


def parse_model_footprints() -> dict[int, dict[str, object]]:
    """Map model id → bbox footprint fields sourced from props/*.bin."""
    files = _parse_file_table()
    model_files = _parse_model_file_ids()
    footprints: dict[int, dict[str, object]] = {}
    for model_id, file_id in sorted(model_files.items()):
        prop_bin = _prop_bin_for_file_id(file_id, files)
        if prop_bin is None:
            continue
        bbox = _bbox_from_prop_bin(prop_bin)
        if bbox is None:
            continue
        width, depth, half_x, half_z = _xz_footprint_from_bbox(bbox)
        footprints[model_id] = {
            "width": round(width, 2),
            "depth": round(depth, 2),
            "halfX": round(half_x, 2),
            "halfZ": round(half_z, 2),
            "bboxSource": str(prop_bin.relative_to(ROOT)),
        }
    return footprints


def parse_retail_scales() -> dict[str, tuple[int, str]]:
    """Map MODEL_* name → (scale, source hint) from all setup*.c stdobject lines."""
    counts: dict[str, Counter[int]] = defaultdict(Counter)
    sources: dict[str, set[str]] = defaultdict(set)

    for path in sorted(SETUPS_DIR.glob("setup*.c")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _STDOBJECT_RE.finditer(text):
            scale = int(m.group(1), 16)
            name = m.group(2)
            counts[name][scale] += 1
            sources[name].add(path.stem)

    resolved: dict[str, tuple[int, str]] = {}
    for name, counter in counts.items():
        scale, freq = counter.most_common(1)[0]
        src_list = sorted(sources[name])
        hint = src_list[0] if len(src_list) == 1 else f"{src_list[0]}+({freq} placements)"
        resolved[name] = (scale, hint)
    return resolved


def parse_models() -> list[dict]:
    retail = parse_retail_scales()
    footprints = parse_model_footprints()
    rows: list[dict] = []
    seen: set[int] = set()
    for line in CONSTANTS_H.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _DEFINE_RE.match(line.strip())
        if not m:
            continue
        name, hex_val = m.group(1), m.group(2)
        model_id = int(hex_val, 16)
        if model_id in seen:
            continue
        if not _placable(name):
            continue
        seen.add(model_id)
        label = name.replace("MODEL_", "").replace("_", " ").title()
        if name in retail:
            scale, scale_source = retail[name]
        else:
            scale, scale_source = _SCALE_DEFAULT, "default"
        row: dict[str, object] = {
            "name": name,
            "label": label,
            "model": model_id,
            "modelHex": hex_val,
            "tag": _tag_for(name),
            "scale": scale,
            "scaleHex": f"0x{scale:04X}",
            "scaleSource": scale_source,
        }
        if model_id in footprints:
            row.update(footprints[model_id])
        rows.append(row)
    rows.sort(key=lambda r: r["model"])
    return rows


def main() -> int:
    if not CONSTANTS_H.is_file():
        print(f"Missing {CONSTANTS_H}", file=sys.stderr)
        return 1
    rows = parse_models()
    non_default = sum(1 for r in rows if r["scale"] != _SCALE_DEFAULT)
    with_bbox = sum(1 for r in rows if "halfX" in r)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": str(CONSTANTS_H.relative_to(ROOT)),
        "bboxSource": str(PROPS_DIR.relative_to(ROOT)),
        "count": len(rows),
        "scaleDefault": f"0x{_SCALE_DEFAULT:04X}",
        "scaleNonDefault": non_default,
        "bboxCount": with_bbox,
        "models": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(rows)} models ({non_default} non-default scales, "
        f"{with_bbox} with bbox) → {OUT_JSON}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
