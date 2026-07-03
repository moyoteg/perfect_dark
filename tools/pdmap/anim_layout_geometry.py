"""Export Animation Lab layout geometry for Map Editor 3D preview."""

from __future__ import annotations

from typing import Any


def animlab_preview_geometry() -> dict[str, Any]:
    """Box arena + tiles + pads + districts + walkable regions + props."""
    import importlib.util
    from pathlib import Path

    from .anim_catalog import parade_layout_payload, parade_special_marker
    from .anim_props import parade_all_prop_markers

    root = Path(__file__).resolve().parents[2]
    mod_path = root / "src" / "levels" / "animlab.py"
    spec = importlib.util.spec_from_file_location("animlab_level", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    layout = parade_layout_payload()
    tiles_json = mod.build_tiles_json()
    special = parade_special_marker()

    pads: list[dict[str, Any]] = [
        {
            "index": 0,
            "x": 0.0,
            "y": 10.0,
            "z": layout["playerSpawn"]["z"],
            "room": 1,
            "kind": "spawn",
        },
        {
            "index": special["pad"],
            "x": special["x"],
            "y": special.get("y", 10.0),
            "z": special["z"],
            "room": special.get("room", 1),
            "kind": "tour",
        },
    ]
    for slot in layout.get("slots") or []:
        pads.append(
            {
                "index": slot["pad"],
                "x": slot["x"],
                "y": slot.get("y", 10.0),
                "z": slot["z"],
                "room": slot.get("room", 1),
                "kind": "guard",
                "district": slot.get("district"),
                "animId": slot.get("animId"),
            }
        )
    for prop in parade_all_prop_markers():
        pads.append(
            {
                "index": prop["pad"],
                "x": prop["x"],
                "y": prop.get("y", 10.0),
                "z": prop["z"],
                "room": prop.get("room", 1),
                "kind": prop.get("kind", "prop"),
                "label": prop.get("label"),
                "modelHex": prop.get("modelHex"),
            }
        )

    # Flatten tile quads for Three.js wireframe overlay.
    tile_quads: list[dict[str, Any]] = []
    for room_key, tiles in (tiles_json.get("rooms") or {}).items():
        for tile in tiles:
            verts = tile.get("vertices") or []
            if len(verts) < 4:
                continue
            xs = [v["x"] for v in verts]
            zs = [v["z"] for v in verts]
            tile_quads.append(
                {
                    "room": room_key,
                    "x0": min(xs),
                    "z0": min(zs),
                    "x1": max(xs),
                    "z1": max(zs),
                    "y": verts[0].get("y", 0),
                    "floorcolour": tile.get("floorcolour"),
                    "floortype": tile.get("floortype"),
                }
            )

    return {
        "name": "animlab",
        "boxHalf": float(getattr(mod, "BOX_HALF", layout.get("arenaHalf", 8000))),
        "height": float(getattr(mod, "BOX_HEIGHT", 3000)),
        "segMode": getattr(mod, "SEG_MODE", "parade_districts"),
        "layout": layout,
        "tiles": tile_quads,
        "pads": pads,
        "districts": layout.get("districts") or [],
        "walkableRegions": layout.get("walkableRegions") or [],
        "props": parade_all_prop_markers(),
        "museum": layout.get("museumDistrict"),
        "vignettes": layout.get("vignetteProps"),
    }
