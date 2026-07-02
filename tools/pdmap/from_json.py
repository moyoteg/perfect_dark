"""Canonical editor JSON → MapDef conversion.

Single source of truth for turning Map Editor export JSON into a ``MapDef``
plus box-arena dimensions. Used by ``pdmap from-json``, ``test_map.py``, and
optional level-module export (``--write-level``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .builders import (
    CENTER_MARKER_HALF,
    HILL_ROOM_INDEX,
    PAD_FLOOR_OFFSET,
    add_ammo_row,
    add_floor_weapons,
    add_loadout_intro,
    cover_markers_from_mapdef,
    ctf_zones_from_mapdef,
    floor_box_tiles,
    floor_box_with_center_marker,
    floor_box_with_cover_markers,
    floor_box_with_ctf_zones,
    floor_box_with_hill_zone,
    floor_box_with_walls,
    hill_zone_center_from_mapdef,
)
from .core import MapDef
from .intro import Case, CaseRespawn, Hill, Spawn
from . import weapons as W

_VALID_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# Seg draw modes that show perimeter walls — collision must mirror them in tiles.
_VISIBLE_WALL_SEG_MODES = frozenset({"full", "walls", "box", "debug", "rainbow"})

# Editor weapon IDs → weapons.py constants (fallback to hex literal).
_WEAPON_CONST: dict[int, str] = {
    W.WEAPON_FALCON2: "W.WEAPON_FALCON2",
    W.WEAPON_MAGSEC4: "W.WEAPON_MAGSEC4",
    W.WEAPON_MAULER: "W.WEAPON_MAULER",
    W.WEAPON_CMP150: "W.WEAPON_CMP150",
    W.WEAPON_LAPTOPGUN: "W.WEAPON_LAPTOPGUN",
    W.WEAPON_SUPERDRAGON: "W.WEAPON_SUPERDRAGON",
    W.WEAPON_SNIPERRIFLE: "W.WEAPON_SNIPERRIFLE",
    W.WEAPON_ROCKETLAUNCHER: "W.WEAPON_ROCKETLAUNCHER",
    W.WEAPON_CROSSBOW: "W.WEAPON_CROSSBOW",
    W.WEAPON_TRANQUILIZER: "W.WEAPON_TRANQUILIZER",
}

_AMMO_CONST: dict[int, str] = {
    W.AMMOTYPE_PISTOL: "W.AMMOTYPE_PISTOL",
    W.AMMOTYPE_RIFLE: "W.AMMOTYPE_RIFLE",
    W.AMMOTYPE_SHOTGUN: "W.AMMOTYPE_SHOTGUN",
    W.AMMOTYPE_ROCKET: "W.AMMOTYPE_ROCKET",
}


def validate_level_name(name: str) -> str:
    """Normalize and validate a level / asset name."""
    name = (name or "map").strip().lower()
    if not _VALID_NAME.match(name):
        raise ValueError(
            f"Invalid level name {name!r}; use lowercase letters, digits, underscore "
            "(must start with a letter)."
        )
    return name


def _weapon_id(raw: int) -> int:
    return int(raw)


def _ammo_id(raw: int) -> int:
    return int(raw)


@dataclass(frozen=True)
class EditorMapSpec:
    """Validated editor export: MapDef + box arena parameters."""

    name: str
    box_half: float
    box_height: float
    spawn_y: float
    mapdef: MapDef
    # Pads whose Y was auto-corrected from at/below floor to spawn_y.
    y_corrected_pads: tuple[int, ...] = ()
    # Optional green square at origin (overlap-pad lessons under empty seg).
    center_marker: bool = False
    center_marker_half: float = CENTER_MARKER_HALF
    # Visible floor markers at AI cover positions (step 31).
    cover_markers: bool = False

    @classmethod
    def from_json(
        cls,
        data: dict[str, Any],
        *,
        deploy_name: str | None = None,
        spawn_y: float | None = None,
    ) -> EditorMapSpec:
        """Parse editor JSON into a fully wired ``MapDef`` with all MP invariants."""
        name = validate_level_name(deploy_name or str(data.get("name", "map")))
        half = float(data.get("box_half", 5000))
        height = float(data.get("box_height", 3000))
        floor_y = spawn_y if spawn_y is not None else float(
            data.get("spawn_y", PAD_FLOOR_OFFSET)
        )

        pads: list[dict[str, Any]] = list(data.get("pads") or [])
        if not pads:
            raise ValueError("Refusing to build an empty map — add at least one pad.")

        g = MapDef(name)
        y_corrected: list[int] = []

        spawn_indices: list[int] = []
        weapon_rows: list[tuple[int, int]] = []
        ammo_by_type: dict[int, list[int]] = {}
        scenario_cmds: list[tuple[str, int, int]] = []  # kind, pad, team

        for i, p in enumerate(pads):
            idx = int(p.get("index", i))
            if idx != i:
                raise ValueError(
                    f"Pad at array position {i} has index={idx}; "
                    "indices must be contiguous 0..N-1."
                )

            x = float(p.get("x", 0))
            z = float(p.get("z", 0))
            y = float(p.get("y", floor_y))
            if y <= 0.0:
                y_corrected.append(i)
                y = floor_y
            room = int(p.get("room", 1))
            kind = p.get("type", "other")

            pad_kwargs: dict[str, float | int] = {"room": room}
            if "dir" in p:
                d = p["dir"]
                pad_kwargs.update(dir_x=float(d[0]), dir_y=float(d[1]), dir_z=float(d[2]))
            if "up" in p:
                u = p["up"]
                pad_kwargs.update(up_x=float(u[0]), up_y=float(u[1]), up_z=float(u[2]))

            g.add_pad(index=i, x=x, y=y, z=z, **pad_kwargs)

            if kind == "spawn":
                spawn_indices.append(i)
            elif kind == "weapon":
                if "weapon" not in p:
                    raise ValueError(f"Weapon pad {i} missing 'weapon' id.")
                weapon_rows.append((i, _weapon_id(int(p["weapon"]))))
            elif kind == "ammo":
                aid = _ammo_id(int(p.get("ammoType", W.AMMOTYPE_SHOTGUN)))
                ammo_by_type.setdefault(aid, []).append(i)
            elif kind == "scenario":
                sc = str(p.get("scenario", "hill"))
                team = int(p.get("team", 0))
                scenario_cmds.append((sc, i, team))

        if not spawn_indices:
            raise ValueError("Map has no spawn pads — add at least one pad with type 'spawn'.")

        for i in spawn_indices:
            g.add_intro(Spawn(pad=i))

        if weapon_rows:
            add_floor_weapons(g, weapon_rows)

        for aid, indices in sorted(ammo_by_type.items()):
            add_ammo_row(g, indices, ammotype=aid)

        for sc, pad, team in scenario_cmds:
            if sc == "case":
                g.add_intro(Case(team=team, pad=pad))
            elif sc == "case_respawn":
                g.add_intro(CaseRespawn(team=team, pad=pad))
            else:
                g.add_intro(Hill(pad=pad))

        add_loadout_intro(g)

        for cover in data.get("covers") or []:
            g.add_cover(
                x=float(cover.get("x", 0)),
                z=float(cover.get("z", 0)),
                y=float(cover.get("y", floor_y)),
            )

        return cls(
            name=name,
            box_half=half,
            box_height=height,
            spawn_y=floor_y,
            mapdef=g,
            y_corrected_pads=tuple(y_corrected),
            center_marker=bool(data.get("center_marker", False)),
            center_marker_half=float(
                data.get("center_marker_half", CENTER_MARKER_HALF)
            ),
            cover_markers=bool(data.get("cover_markers", False)),
        )

    def tiles_json(self, *, seg_mode: str | None = None) -> dict:
        """Collision floor matching the box arena (hill / CTF zone tiles when anchored)."""
        center = hill_zone_center_from_mapdef(self.mapdef)
        if center is not None:
            return floor_box_with_hill_zone(
                self.name,
                half=self.box_half,
                y=0.0,
                hill_center_x=center[0],
                hill_center_z=center[1],
            )
        ctf_zones = ctf_zones_from_mapdef(self.mapdef)
        if ctf_zones:
            return floor_box_with_ctf_zones(
                self.name,
                half=self.box_half,
                y=0.0,
                zones=ctf_zones,
            )
        if self.center_marker:
            return floor_box_with_center_marker(
                self.name,
                half=self.box_half,
                y=0.0,
                room_index=1,
                marker_half=self.center_marker_half,
            )
        if self.cover_markers and self.mapdef.covers:
            return floor_box_with_cover_markers(
                self.name,
                half=self.box_half,
                y=0.0,
                room_index=1,
                markers=cover_markers_from_mapdef(self.mapdef),
            )
        if seg_mode in _VISIBLE_WALL_SEG_MODES:
            return floor_box_with_walls(
                self.name,
                half=self.box_half,
                height=self.box_height,
                y=0.0,
                room_index=1,
            )
        return floor_box_tiles(self.name, half=self.box_half, y=0.0, room_index=1)

    def tiles_room_count(self) -> int:
        """Number of tile rooms (room 0 + arena + optional hill room)."""
        return HILL_ROOM_INDEX + 1 if hill_zone_center_from_mapdef(self.mapdef) else 2


def load_editor_json(path: str | None) -> dict[str, Any]:
    """Load editor JSON from a file path or stdin (``path`` is ``None`` or ``'-'``)."""
    import json
    import sys

    if path in (None, "-"):
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)
