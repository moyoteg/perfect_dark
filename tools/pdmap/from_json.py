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
    floor_box_with_hill_and_ctf_zones,
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


_CLASS_DEFAULTS: dict[str, dict[str, Any]] = {
    "Door": {
        "maxfrac": 0x018c0000,
        "perimfrac": 0x018c0000,
        "accel": 0x0006a000,
        "decel": 0x00035000,
        "maxspeed": 0x006a0000,
        "doorflags": 0x000000c0,
        "doortype": 0x01,
        "keyflags": 0,
        "autoclosetime": 0,
        "unk88": 0,
        "sibling": 0,
        "unkc4": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0x10008,
        "flags2": 0x1a0,
        "flags3": 0x40,
        "maxdamage": 1000,
    },
    "Key": {
        "lockbits": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
    },
    "Camera": {
        "targetpad": 0,
        "yaw": 0,
        "ymaxspeed": 0,
        "maxdist": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "AmmoCrate": {
        "ammotype": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Chr": {
        "spawnflags": 0,
        "chrnum": 0,
        "pad": 0,
        "body": 0,
        "head": 0,
        "function": 0,
        "padpreset": 0,
        "chrpreset": 0,
        "hear_scale": 0,
        "view_dist": 0,
        "flags": 0,
        "flags2": 0,
        "team": 0,
        "squadron": 0,
        "chair": 0,
        "convtalk": 0,
        "tude": 0,
        "naturalanim": 0,
        "yvisang": 0,
        "teamscandist": 0,
    },
    "SingleMonitor": {
        "image": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "MultiMonitor": {
        "image1": 0,
        "image2": 0,
        "image3": 0,
        "image4": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Autogun": {
        "targetpad": 0,
        "unk64": 0,
        "unk68": 0,
        "unk80": 0,
        "unk84": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "LinkGuns": {
        "gun1offset": 0,
        "gun2offset": 0,
    },
    "Debris": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Hat": {
        "scale": 0x0100,
        "model": 0,
        "chr_": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "LiftDoor": {
        "dooroffset": 0,
        "liftoffset": 0,
        "stopnum": 0,
    },
    "Shield": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Tag": {
        "id": 0,
        "value": 0,
    },
    "BeginObjective": {
        "value": 0,
        "text": 0,
        "diffbit": 0,
    },
    "EndObjective": {},
    "RequireObjectDestroyed": {
        "object_": 0,
    },
    "CompleteFlags": {
        "stageflag": 0,
    },
    "FailFlags": {
        "stageflag": 0,
    },
    "RequireObjectCollected": {
        "object_": 0,
    },
    "RequireObjectThrown": {
        "object_": 0,
    },
    "RequireObjectHolographed": {
        "object_": 0,
    },
    "RequireRoomEntered": {
        "room": 0,
    },
    "RequireObjectThrownInRoom": {
        "object_": 0,
        "pad": 0,
    },
    "Briefing": {
        "value": 0,
        "text": 0,
    },
    "GasBottle": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "RenameObject": {
        "objoffset": 0,
        "weapon": 0,
        "text": 0,
        "text2": 0,
        "text3": 0,
        "text4": 0,
        "text5": 0,
    },
    "PadlockedDoor": {
        "dooroffset": 0,
        "lockoffset": 0,
    },
    "Glass": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Safe": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "SafeItem": {
        "item": 0,
        "safe": 0,
        "door": 0,
    },
    "CameraPos": {
        "scale": 0x0100,
        "u1": 0,
        "u2": 0,
        "u3": 0,
        "u4": 0,
        "u5": 0,
        "pad": 0,
    },
    "TintedGlass": {
        "unk5c": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "Lift": {
        "pad1": 0,
        "pad2": 0,
        "pad3": 0,
        "pad4": 0,
        "door1": 0,
        "door2": 0,
        "door3": 0,
        "door4": 0,
        "accel": 0,
        "maxspeed": 0,
        "unk84": 0,
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
    "StdObject": {
        "scale": 0x0100,
        "model": 0,
        "pad": 0,
        "flags": 0,
        "flags2": 0,
        "flags3": 0,
        "maxdamage": 1000,
    },
}


def _parse_custom_objects(g: MapDef, data: dict[str, Any], pad_indices: dict[str, int]) -> None:
    """Parse unified objects array and inline door/prop pads to add setup props to MapDef."""
    raw_objects: list[dict[str, Any]] = []

    # Parse inline props/doors from pads
    for i, p in enumerate(data.get("pads") or []):
        kind = p.get("type", "other")
        if kind in ("prop", "door"):
            obj = dict(p)
            obj["class"] = "StdObject" if kind == "prop" else "Door"
            obj["pad"] = i
            raw_objects.append(obj)

    # Parse root-level objects
    for obj in data.get("objects") or []:
        raw_objects.append(dict(obj))

    # Build mapping from friendly object ID to unified index in raw_objects list
    obj_indices: dict[str, int] = {}
    for idx, obj in enumerate(raw_objects):
        obj_id = obj.get("id")
        if obj_id:
            obj_indices[str(obj_id)] = idx

    from . import props as P

    for idx, obj in enumerate(raw_objects):
        class_name = obj.get("class")
        if not class_name:
            continue

        cls = getattr(P, class_name, None)
        if cls is None:
            raise ValueError(f"Unknown setup object class: {class_name}")

        defaults = _CLASS_DEFAULTS.get(class_name, {})
        params = dict(defaults)

        # Merge JSON fields
        for k, v in obj.items():
            if k in ("id", "class", "type", "x", "y", "z", "room", "index"):
                continue
            params[k] = v

        # Resolve pad references and relative object offsets
        resolved_params = {}
        for k, v in params.items():
            if k in ("pad", "targetpad", "pad1", "pad2", "pad3", "pad4"):
                resolved_params[k] = pad_indices.get(str(v), v)
            elif k == "sibling" and isinstance(v, str):
                if v in obj_indices:
                    resolved_params[k] = obj_indices[v] - idx
                else:
                    resolved_params[k] = v
            elif k in ("object_", "dooroffset", "liftoffset", "objoffset", "item", "safe", "door", "door1", "door2", "door3", "door4", "lockoffset"):
                if str(v) in obj_indices:
                    resolved_params[k] = obj_indices[str(v)]
                else:
                    resolved_params[k] = v
            else:
                resolved_params[k] = v

        try:
            inst = cls(**resolved_params)
        except TypeError as exc:
            raise TypeError(f"Failed to instantiate {class_name} with params {resolved_params}: {exc}") from exc

        g.add_prop(inst)


@dataclass(frozen=True)
class EditorMapSpec:
    """Validated editor export: MapDef + box arena parameters."""

    name: str
    box_half: float
    box_height: float
    spawn_y: float
    mapdef: MapDef
    level_module: str = "uff"
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
        level_module = validate_level_name(str(data.get("level_module") or data.get("name") or "uff"))
        half = float(data.get("box_half", 5000))
        height = float(data.get("box_height", 3000))
        floor_y = spawn_y if spawn_y is not None else float(
            data.get("spawn_y", PAD_FLOOR_OFFSET)
        )

        pads: list[dict[str, Any]] = list(data.get("pads") or [])
        if not pads:
            raise ValueError("Refusing to build an empty map — add at least one pad.")

        g = MapDef(name)
        if name == "parade" or name.startswith("parade_") or level_module == "parade":
            g.anim_parade = True
        y_corrected: list[int] = []

        pad_indices: dict[str, int] = {}
        for i, p in enumerate(pads):
            idx = int(p.get("index", i))
            pad_id = p.get("id")
            if pad_id:
                pad_indices[str(pad_id)] = idx
            pad_indices[str(idx)] = idx

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

        _parse_custom_objects(g, data, pad_indices)

        for cover in data.get("covers") or []:
            g.add_cover(
                x=float(cover.get("x", 0)),
                z=float(cover.get("z", 0)),
                y=float(cover.get("y", floor_y)),
            )

        g.custom_waypoints = data.get("waypoints", [])

        return cls(
            name=name,
            level_module=level_module,
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
        try:
            from .core import load_level_module
            mod = load_level_module(self.level_module)
            if mod and hasattr(mod, "build_tiles_json"):
                return mod.build_tiles_json()
        except Exception:
            pass

        center = hill_zone_center_from_mapdef(self.mapdef)
        ctf_zones = ctf_zones_from_mapdef(self.mapdef)
        if center is not None and ctf_zones:
            return floor_box_with_hill_and_ctf_zones(
                self.name,
                half=self.box_half,
                y=0.0,
                hill_center_x=center[0],
                hill_center_z=center[1],
                zones=ctf_zones,
            )
        if center is not None:
            return floor_box_with_hill_zone(
                self.name,
                half=self.box_half,
                y=0.0,
                hill_center_x=center[0],
                hill_center_z=center[1],
            )
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

    def tiles_room_count(self) -> int | None:
        """Number of tile rooms (room 0 + arena + optional hill room)."""
        try:
            from .core import load_level_module
            mod = load_level_module(self.level_module)
            if mod and getattr(mod, "RETAIL_GEOMETRY", False):
                return None
        except Exception:
            pass
        return HILL_ROOM_INDEX + 1 if hill_zone_center_from_mapdef(self.mapdef) else 2


def load_editor_json(path: str | None) -> dict[str, Any]:
    """Load editor JSON from a file path or stdin (``path`` is ``None`` or ``'-'``)."""
    import json
    import sys

    if path in (None, "-"):
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)
