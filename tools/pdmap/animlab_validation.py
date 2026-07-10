"""Structured validation interface for STAGE_ANIMLAB (Animation Lab).

Pure-function audits consumed by CI, release gate, and ``pdmap validate animlab``.
See ``docs/ANIMLAB_SCENARIOS.md`` scenario ``animlab_build_and_audit_passes``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from importlib import import_module
from typing import Any

from .anim_characters import MAIN_CHARACTER_ENTRIES, _character_pad_first
from .anim_levels import megaworld_plan
from .anim_wayfinding import audit_spawn_collision_floor, audit_spawn_walk_paths
from .builders import PARADE_SEG_MARKER_Y_OFFSET

SCENARIO_BUILD_AND_AUDIT = "animlab_build_and_audit_passes"

_EXPECTED_CHARACTER_COUNT = 24
_EXPECTED_LEVEL_ISLAND_COUNT = 92
_EXPECTED_SOLO_COUNT = 26
_CHARACTER_PAD_FIRST = 924
_CHARACTER_PAD_LAST = 947
_CHARACTER_ROOM = 19


@dataclass(frozen=True)
class AnimLabValidationReport:
    """Typed result of ``run_animlab_validation()`` — one scenario, full evidence."""

    scenario_id: str
    collision_errors: list[str]
    walk_warnings: list[str]
    y4_tile_count_room1: int
    character_count: int
    level_island_count: int
    passed: bool
    evidence_lines: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"AnimLabValidationReport[{self.scenario_id}] {status}",
            f"  collision_errors={len(self.collision_errors)} "
            f"walk_warnings={len(self.walk_warnings)} "
            f"y4_tiles_room1={self.y4_tile_count_room1}",
            f"  characters={self.character_count} level_islands={self.level_island_count}",
            f"  marker_y_offset={PARADE_SEG_MARKER_Y_OFFSET}",
        ]
        for line in self.evidence_lines:
            lines.append(f"  {line}")
        for err in self.collision_errors[:5]:
            lines.append(f"  collision: {err}")
        for warn in self.walk_warnings[:5]:
            lines.append(f"  walk: {warn}")
        return "\n".join(lines)


def _room_tiles(tiles_data: dict[str, Any], room_index: int) -> list[dict]:
    for rname, tiles in tiles_data.get("rooms", {}).items():
        if int(rname.split("_")[-1]) == room_index:
            return tiles
    return []


def count_y4_tiles_room1(tiles_data: dict[str, Any] | None = None) -> int:
    """Count room-1 tile quads whose vertex Y rounds to 4 (legacy double-floor layer)."""
    if tiles_data is None:
        mod = import_module("src.levels.animlab")
        tiles_data = mod.build_tiles_json()
    room1 = _room_tiles(tiles_data, 1)
    return sum(1 for t in room1 if int(t["vertices"][0]["y"]) == 4)


def run_animlab_validation(
    *,
    scenario_id: str = SCENARIO_BUILD_AND_AUDIT,
    tiles_data: dict[str, Any] | None = None,
    name: str = "parade",
) -> AnimLabValidationReport:
    """Run Anim Lab layout audits and content baselines; return typed report."""
    if tiles_data is None:
        mod = import_module(f"src.levels.{name}")
        tiles_data = mod.build_tiles_json()

    collision_errors = audit_spawn_collision_floor(tiles_data)
    walk_warnings = audit_spawn_walk_paths()
    y4_count = count_y4_tiles_room1(tiles_data)

    collision_errors = list(collision_errors)
    from .core import load_level_module
    try:
        g = load_level_module(name).build()
        doors = [p for p in g.props if type(p).__name__ == "Door"]
        if len(doors) != 2:
            collision_errors.append(f"Expected exactly 2 double sliding doors in {name}, got {len(doors)}")
        else:
            d1, d2 = doors[0], doors[1]
            if d1.sibling != 1 or d2.sibling != -1:
                collision_errors.append(f"Invalid door sibling linkages: {d1.sibling}, {d2.sibling}")
            pad1 = next((p for p in g.pads if p.index == d1.pad), None)
            pad2 = next((p for p in g.pads if p.index == d2.pad), None)
            if not pad1 or not pad2:
                collision_errors.append("Could not find pads for door siblings")
            else:
                import math
                dist = math.hypot(pad1.x - pad2.x, pad1.z - pad2.z)
                if abs(dist - 218.0) > 1.0:
                    collision_errors.append(f"Unexpected door sibling pad distance: {dist:.2f} (expected ~218)")
                dot_prod = pad1.up_x * pad2.up_x + pad1.up_y * pad2.up_y + pad1.up_z * pad2.up_z
                if abs(dot_prod + 1.0) > 0.01:
                    collision_errors.append(f"Unexpected door sibling up vectors alignment: dot={dot_prod:.2f}")
    except Exception as e:
        collision_errors.append(f"Failed to statically verify doors: {e}")

    char_count = len(MAIN_CHARACTER_ENTRIES)
    pad_first = _character_pad_first()
    plan = megaworld_plan()
    island_count = int(plan["count"])

    evidence: list[str] = [
        f"PARADE_SEG_MARKER_Y_OFFSET={PARADE_SEG_MARKER_Y_OFFSET}",
        f"character_pads={pad_first}..{pad_first + char_count - 1} room={_CHARACTER_ROOM}",
        f"level_islands solo={plan['soloCount']} mp={plan['mpCount']} dev={plan['devCount']}",
        f"room1_tiles={len(_room_tiles(tiles_data, 1))}",
    ]

    passed = (
        len(collision_errors) == 0
        and len(walk_warnings) == 0
        and y4_count == 99
        and char_count == _EXPECTED_CHARACTER_COUNT
        and island_count == _EXPECTED_LEVEL_ISLAND_COUNT
        and pad_first == _CHARACTER_PAD_FIRST
        and PARADE_SEG_MARKER_Y_OFFSET == 4.0
    )

    return AnimLabValidationReport(
        scenario_id=scenario_id,
        collision_errors=collision_errors,
        walk_warnings=walk_warnings,
        y4_tile_count_room1=y4_count,
        character_count=char_count,
        level_island_count=island_count,
        passed=passed,
        evidence_lines=evidence,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: print JSON line + human summary; exit 0 when ``passed``."""
    report = run_animlab_validation()
    print(report.to_json())
    print(report, file=sys.stderr)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
