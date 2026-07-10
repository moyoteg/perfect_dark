"""Retail Carrington Institute (dish) door props extracted from ``setupdish.c``.

Doors are setup objects, not seg geometry. Custom MP setup packers that replace
``Ump_setup*`` must re-include these or corridors stay blocked.

Used by ``agent_office_ci`` (``STAGE_AGENT_OFFICE_CI`` / dish geometry).
"""

from __future__ import annotations

import os
import re

from .props import Door
from .retail_door_siblings import remap_door_siblings, retail_door_cmd_indices
from .setup_c_preprocess import iter_setup_c_lines

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SETUP_DISH = os.path.join(_ROOT, "src", "setups", "setupdish.c")
_CONSTANTS_H = os.path.join(_ROOT, "src", "include", "constants.h")

_DOOR_LINE = re.compile(
    r"^\tdoor\((.+)\)\s*$",
)

OBJFLAG_DEACTIVATED = 0x10000000
OBJFLAG_CANNOT_ACTIVATE = 0x02000000
OBJFLAG_DOOR_KEEPOPEN = 0x40000000
OBJFLAG2_LOCKEDFRONT = 0x08000000
OBJFLAG2_LOCKEDBACK = 0x10000000

DOORTYPE_SLIDING = 0
DOORTYPE_SWINGING = 5
DOORTYPE_LASER = 11
DOORTYPE_VERTICAL = 6


def _load_c_constants(path: str) -> dict[str, int]:
    """Parse ``#define NAME value`` lines from a C header."""
    consts: dict[str, int] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.split("//", 1)[0].strip()
            if not line.startswith("#define "):
                continue
            body = line[len("#define ") :]
            if "(" in body.split()[0]:
                continue
            parts = body.split(None, 1)
            if len(parts) != 2:
                continue
            name, expr = parts[0], parts[1].strip()
            try:
                consts[name] = _eval_c_int(expr, consts)
            except (ValueError, KeyError):
                continue
    return consts


def _eval_c_int(expr: str, consts: dict[str, int]) -> int:
    """Evaluate a simple C integer expression (hex, decimal, ``|``, ``-``)."""
    expr = expr.strip()
    if not expr:
        raise ValueError("empty expression")

    def replace_token(m: re.Match[str]) -> str:
        name = m.group(0)
        if name.startswith("0x") or name.startswith("0X"):
            return str(int(name, 16))
        if name.isdigit():
            return name
        if name.startswith("PAD_DISH_"):
            return str(int(name.rsplit("_", 1)[-1], 16))
        if name not in consts:
            raise KeyError(name)
        return str(consts[name])

    resolved = re.sub(r"0x[0-9a-fA-F]+|0X[0-9a-fA-F]+|\d+|[A-Za-z_][A-Za-z0-9_]*", replace_token, expr)
    if not re.fullmatch(r"[\d\s|+\-()]+", resolved):
        raise ValueError(f"unsupported expression: {expr!r} → {resolved!r}")
    return int(eval(resolved, {"__builtins__": {}}, {}))  # noqa: S307 — controlled input


def _parse_door_args(args: str, consts: dict[str, int]) -> dict:
    """Parse one ``door(...)`` argument list into Door constructor kwargs."""
    parts = [p.strip() for p in args.split(",")]
    if len(parts) != 19:
        raise ValueError(f"expected 19 door args, got {len(parts)}: {args!r}")

    keys = (
        "scale",
        "model",
        "pad",
        "flags",
        "flags2",
        "flags3",
        "maxdamage",
        "maxfrac",
        "perimfrac",
        "accel",
        "decel",
        "maxspeed",
        "doorflags",
        "doortype",
        "keyflags",
        "autoclosetime",
        "unk88",
        "sibling",
        "unkc4",
    )
    raw = {k: _eval_c_int(v, consts) for k, v in zip(keys, parts)}
    return {
        "scale": raw["scale"],
        "model": raw["model"],
        "pad": raw["pad"],
        "flags": raw["flags"],
        "flags2": raw["flags2"],
        "flags3": raw["flags3"],
        "maxdamage": raw["maxdamage"],
        "maxfrac": raw["maxfrac"],
        "perimfrac": raw["perimfrac"],
        "accel": raw["accel"],
        "decel": raw["decel"],
        "maxspeed": raw["maxspeed"],
        "doorflags": raw["doorflags"],
        "doortype": raw["doortype"],
        "keyflags": raw["keyflags"],
        "autoclosetime": raw["autoclosetime"],
        "unk88": raw["unk88"],
        "sibling": raw["sibling"],
        "unkc4": raw["unkc4"],
    }


def _mp_unlock_door_fields(fields: dict) -> dict:
    """Return a copy with MP-friendly door flags — all doors openable without mission scripts."""
    out = dict(fields)
    doortype = out["doortype"]

    out["flags"] &= ~(OBJFLAG_DEACTIVATED | OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
    out["flags2"] &= ~(OBJFLAG2_LOCKEDFRONT | OBJFLAG2_LOCKEDBACK)
    out["keyflags"] = 0

    if doortype == DOORTYPE_LASER:
        return out

    if doortype in (DOORTYPE_SLIDING, DOORTYPE_SWINGING, DOORTYPE_VERTICAL):
        return out

    return out


def parse_setupdish_doors(*, mp_unlock: bool = True) -> list[Door]:
    """Parse all ``door(...)`` entries from ``setupdish.c``."""
    from .ci_retail_lifts import lift_door_pads

    consts = _load_c_constants(_CONSTANTS_H)
    doors: list[Door] = []
    skip_pads = lift_door_pads()

    for line in iter_setup_c_lines(_SETUP_DISH):
        m = _DOOR_LINE.match(line.rstrip())
        if not m:
            continue
        fields = _parse_door_args(m.group(1), consts)
        if fields["pad"] in skip_pads:
            continue
        if mp_unlock:
            fields = _mp_unlock_door_fields(fields)
        doors.append(Door(**fields))
    return doors


def dish_door_inventory() -> list[dict]:
    """Human-readable door list for docs / validation output."""
    consts = _load_c_constants(_CONSTANTS_H)
    inv: list[dict] = []
    model_names = {v: k for k, v in consts.items() if k.startswith("MODEL_")}

    for line in iter_setup_c_lines(_SETUP_DISH):
        m = _DOOR_LINE.match(line.rstrip())
        if not m:
            continue
        fields = _parse_door_args(m.group(1), consts)
        inv.append(
            {
                "pad": fields["pad"],
                "padHex": f"0x{fields['pad']:04X}",
                "model": model_names.get(fields["model"], f"0x{fields['model']:04X}"),
                "doortype": fields["doortype"],
            }
        )
    return inv


def prepare_agent_office_doors(doors: list[Door]) -> list[Door]:
    """MP-unlocked retail doors with remapped sibling indices for door-only packs.

    Retail ``sibling`` offsets assume the full ``setupdish.c`` props[] layout; remap
    before pack so paired leaves stay in sync. Doors spawn closed and animate normally.
    """
    from .ci_retail_lifts import lift_door_pads

    consts = _load_c_constants(_CONSTANTS_H)
    skip_pads = lift_door_pads()
    cmd_indices = retail_door_cmd_indices(
        _SETUP_DISH,
        parse_door_args=_parse_door_args,
        consts=consts,
        skip_pad=lambda pad: pad in skip_pads,
    )
    return remap_door_siblings(doors, cmd_indices)


def agent_office_ci_doors() -> list[Door]:
    """All retail dish doors except lift-car doors (those ship in lift assemblies)."""
    return prepare_agent_office_doors(parse_setupdish_doors(mp_unlock=True))
