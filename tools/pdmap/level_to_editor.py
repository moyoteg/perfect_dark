"""Converter from procedural level MapDef to Map Editor JSON format.

Enables all 76+ custom level modules in src/levels/ to be imported, edited,
and playtested directly in the 3D Map Editor.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from .core import MapDef


def mapdef_to_editor_json(m: MapDef) -> dict[str, Any]:
    """Convert an in-memory MapDef instance into the canonical editor JSON schema."""
    spawn_pads: set[int] = set()
    scenario_pads: dict[int, str] = {}

    for cmd in m.intro:
        cmd_type = type(cmd).__name__
        if hasattr(cmd, "pad"):
            pad_idx = int(cmd.pad)
            if cmd_type == "Spawn":
                spawn_pads.add(pad_idx)
            elif cmd_type in ("Hill", "Case", "CaseRespawn"):
                scenario_pads[pad_idx] = cmd_type.lower()

    weapon_pads: dict[int, int] = {}
    for prop in m.props:
        if hasattr(prop, "pad") and hasattr(prop, "weapon") and prop.weapon:
            weapon_pads[int(prop.pad)] = int(prop.weapon)

    # Invariant: Must have at least one spawn pad
    if not spawn_pads and m.pads:
        spawn_pads.add(0)
        if len(m.pads) > 1:
            spawn_pads.add(1)

    pads_json: list[dict[str, Any]] = []
    max_x = 1000.0
    max_z = 1000.0

    for i, p in enumerate(m.pads):
        max_x = max(max_x, abs(float(p.x)))
        max_z = max(max_z, abs(float(p.z)))

        ptype = "other"
        extra: dict[str, Any] = {}
        if p.index in spawn_pads:
            ptype = "spawn"
        elif p.index in weapon_pads:
            ptype = "weapon"
            extra["weapon"] = weapon_pads[p.index]
        elif p.index in scenario_pads:
            ptype = "scenario"
            extra["scenario"] = scenario_pads[p.index]

        pad_entry: dict[str, Any] = {
            "index": i,
            "type": ptype,
            "x": float(p.x),
            "y": max(10.0, float(p.y)),
            "z": float(p.z),
            "room": int(p.room) if p.room > 0 else 1,
            "dir": [float(p.dir_x), float(p.dir_y), float(p.dir_z)],
            "up": [float(p.up_x), float(p.up_y), float(p.up_z)],
        }
        pad_entry.update(extra)
        pads_json.append(pad_entry)

    covers_json: list[dict[str, Any]] = []
    for c in m.covers:
        covers_json.append({
            "x": float(c.x),
            "y": float(c.y),
            "z": float(c.z),
            "dir": [float(c.dir_x), float(c.dir_y), float(c.dir_z)],
        })

    box_half = max(3000.0, max_x + 500.0, max_z + 500.0)
    box_half = min(32000.0, box_half)

    return {
        "name": m.name,
        "box_half": box_half,
        "box_height": 3000.0,
        "spawn_y": 10.0,
        "pads": pads_json,
        "covers": covers_json,
    }
