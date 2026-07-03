"""Retail Carrington Institute (dish) lift assemblies from ``setupdish.c``.

Each assembly is a self-contained prop sequence (``lift`` + four ``door`` +
four ``lift_door``) whose relative command offsets must stay intact. Used by
``agent_office_ci`` for visual elevator presence in the lobby hub.
"""

from __future__ import annotations

import os
import re

from .ci_retail_doors import (
    OBJFLAG_CANNOT_ACTIVATE,
    OBJFLAG_DEACTIVATED,
    OBJFLAG_DOOR_KEEPOPEN,
    _eval_c_int,
    _load_c_constants,
    _parse_door_args,
)
from .props import Door, Lift, LiftDoor, Prop

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SETUP_DISH = os.path.join(_ROOT, "src", "setups", "setupdish.c")
_CONSTANTS_H = os.path.join(_ROOT, "src", "include", "constants.h")

_LIFT_LINE = re.compile(r"^\tlift\((.+)\)\s*$")
_DOOR_LINE = re.compile(r"^\tdoor\((.+)\)\s*$")
_LIFT_DOOR_LINE = re.compile(r"^\tlift_door\((.+)\)\s*$")

# Lift-car door pads — also emitted inside lift assemblies; exclude from flat door list.
_LIFT_DOOR_PADS = frozenset({0x015E, 0x015F, 0x0160, 0x0161, 0x0162, 0x0163, 0x0164, 0x0165})


def lift_door_pads() -> frozenset[int]:
    """Pads owned by lift assemblies (avoid duplicate flat doors)."""
    return _LIFT_DOOR_PADS


def _parse_lift_args(args: str, consts: dict[str, int]) -> dict:
    parts = [p.strip() for p in args.split(",")]
    if len(parts) != 18:
        raise ValueError(f"expected 18 lift args, got {len(parts)}: {args!r}")

    keys = (
        "scale",
        "model",
        "pad",
        "flags",
        "flags2",
        "flags3",
        "maxdamage",
        "pad1",
        "pad2",
        "pad3",
        "pad4",
        "door1",
        "door2",
        "door3",
        "door4",
        "accel",
        "maxspeed",
        "unk84",
    )
    raw = {k: _eval_c_int(v, consts) for k, v in zip(keys, parts)}
    return raw


def _parse_lift_door_args(args: str, consts: dict[str, int]) -> dict:
    parts = [p.strip() for p in args.split(",")]
    if len(parts) != 3:
        raise ValueError(f"expected 3 lift_door args, got {len(parts)}: {args!r}")
    return {
        "dooroffset": _eval_c_int(parts[0], consts),
        "liftoffset": _eval_c_int(parts[1], consts),
        "stopnum": _eval_c_int(parts[2], consts),
    }


def parse_setupdish_lift_assemblies() -> list[list[Prop]]:
    """Parse retail lift blocks preserving internal relative offsets."""
    consts = _load_c_constants(_CONSTANTS_H)
    assemblies: list[list[Prop]] = []
    current: list[Prop] | None = None
    doors_needed = 0
    lift_doors_needed = 0

    with open(_SETUP_DISH, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.rstrip()
            lift_m = _LIFT_LINE.match(stripped)
            if lift_m:
                fields = _parse_lift_args(lift_m.group(1), consts)
                current = [
                    Lift(
                        scale=fields["scale"],
                        model=fields["model"],
                        pad=fields["pad"],
                        flags=fields["flags"],
                        flags2=fields["flags2"],
                        flags3=fields["flags3"],
                        maxdamage=fields["maxdamage"],
                        pad1=fields["pad1"],
                        pad2=fields["pad2"],
                        pad3=fields["pad3"],
                        pad4=fields["pad4"],
                        door1=fields["door1"],
                        door2=fields["door2"],
                        door3=fields["door3"],
                        door4=fields["door4"],
                        accel=fields["accel"],
                        maxspeed=fields["maxspeed"],
                        unk84=fields["unk84"],
                    )
                ]
                doors_needed = 4
                lift_doors_needed = 0
                continue

            if current is None:
                continue

            door_m = _DOOR_LINE.match(stripped)
            if door_m and doors_needed > 0:
                current.append(Door(**_parse_door_args(door_m.group(1), consts)))
                doors_needed -= 1
                if doors_needed == 0:
                    lift_doors_needed = 4
                continue

            lift_door_m = _LIFT_DOOR_LINE.match(stripped)
            if lift_door_m and lift_doors_needed > 0:
                args = _parse_lift_door_args(lift_door_m.group(1), consts)
                current.append(LiftDoor(**args))
                lift_doors_needed -= 1
                if lift_doors_needed == 0:
                    assemblies.append(current)
                    current = None
                continue

    if current is not None:
        raise ValueError("incomplete lift assembly at end of setupdish.c")

    return assemblies


def prepare_agent_office_lifts(assemblies: list[list[Prop]]) -> list[Prop]:
    """Static retail lifts — deactivate car doors so ``doorTick`` stays idle."""
    flat: list[Prop] = []
    for block in assemblies:
        for prop in block:
            if isinstance(prop, Door):
                prop.sibling = 0
                prop.flags |= OBJFLAG_DEACTIVATED
                prop.flags &= ~(OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
            flat.append(prop)
    return flat


def agent_office_ci_lifts() -> list[Prop]:
    """Two retail CI lift assemblies (visual + collision; doors deactivated)."""
    return prepare_agent_office_lifts(parse_setupdish_lift_assemblies())
