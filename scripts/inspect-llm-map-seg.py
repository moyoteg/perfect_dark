#!/usr/bin/env python3
"""Inspect mod_allinone bg_uff seg/tiles for LLM Play (JSON on stdout).

Quick test (--test-map) requires tiles-only play seg (no face G_VTX loads).
See docs/MAP_CREATION.md §11.11–11.12.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_SEG = ROOT / "mods" / "mod_allinone" / "files" / "bgdata" / "bg_uff.seg"
MOD_TILES = ROOT / "mods" / "mod_allinone" / "files" / "bgdata" / "bg_uff_tilesZ"
EMPTY_PLAY_SEG_MAX_BYTES = 350


def inspect() -> dict:
    tiles_size = MOD_TILES.stat().st_size if MOD_TILES.is_file() else 0
    tiles_ok = MOD_TILES.is_file() and tiles_size > 0

    if not MOD_SEG.is_file():
        return {
            "ok": False,
            "size": 0,
            "tilesSize": tiles_size,
            "tilesOk": tiles_ok,
            "emptyPlaySeg": False,
            "errors": [f"missing {MOD_SEG}"],
        }

    data = MOD_SEG.read_bytes()
    sys.path.insert(0, str(ROOT))
    from tools.pdmap.seg import validate_seg_g_vtx

    errors = validate_seg_g_vtx(data)
    empty_play_seg = not errors and len(data) <= EMPTY_PLAY_SEG_MAX_BYTES

    if len(data) > EMPTY_PLAY_SEG_MAX_BYTES and not errors:
        errors.append(
            f"bg_uff.seg is {len(data)} B (> {EMPTY_PLAY_SEG_MAX_BYTES} B) — "
            "likely wall/checkerboard seg; Stop game and redeploy empty seg"
        )
        empty_play_seg = False

    if not tiles_ok:
        errors.append(f"missing or empty {MOD_TILES}")

    return {
        "ok": True,
        "size": len(data),
        "tilesSize": tiles_size,
        "tilesOk": tiles_ok,
        "emptyPlaySeg": empty_play_seg,
        "errors": errors,
    }


def main() -> int:
    payload = inspect()
    print(json.dumps(payload))
    if not payload.get("ok"):
        return 1
    if not payload.get("emptyPlaySeg") or not payload.get("tilesOk"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
