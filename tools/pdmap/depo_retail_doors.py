"""Retail depo door props extracted from ``setupdepo.c``.

Doors are **setup objects** (OBJTYPE door / 0x01), not seg geometry. Retail-overlay
maps that replace ``Ump_setup*`` with a custom packer must re-include these or door
frames appear empty and corridors stay blocked.

Used by ``agent_office`` (``STAGE_AGENT_OFFICE`` / depo geometry).
"""

from __future__ import annotations

import os
import re

from .props import Door

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SETUP_DEPO = os.path.join(_ROOT, "src", "setups", "setupdepo.c")
_CONSTANTS_H = os.path.join(_ROOT, "src", "include", "constants.h")

_DOOR_LINE = re.compile(
    r"^\tdoor\((.+)\)\s*$",
)

# MP free-roam: activate sliding/swinging doors and drop mission locks/keys.
OBJFLAG_DEACTIVATED = 0x10000000
OBJFLAG_CANNOT_ACTIVATE = 0x02000000
OBJFLAG_DOOR_KEEPOPEN = 0x40000000
OBJFLAG2_LOCKEDFRONT = 0x08000000
OBJFLAG2_LOCKEDBACK = 0x10000000

DOORTYPE_SLIDING = 0
DOORTYPE_SWINGING = 5
DOORTYPE_LASER = 11

# Mission-only doors — keep retail flags (deactivated / scripted).
MODEL_G5SAFEDOOR = 0x009D
MODEL_G5_ESCDOORUP = 0x00A8
MODEL_G5_ESCDOORDOWN = 0x00AA

# Holograph meeting-room north corridor (retail tag 0x3a; PAD_DEPO_00B5/00B6).
MODEL_DOOR4A_G5 = 0x009A
MODEL_DOOR4B_G5 = 0x009B
PAD_MEETING_ROOM_ENTRY_A = 0x00B5
PAD_MEETING_ROOM_ENTRY_B = 0x00B6

# South briefing doorway pair — retail keeps these deactivated; reactivating blocks
# the PAD_DEPO_008F corridor into the holograph room (double-door symptom).
PAD_MEETING_ROOM_SOUTH_A = 0x00AA
PAD_MEETING_ROOM_SOUTH_B = 0x00AB

# Laser grid pads on lobby → meeting-room corridor (retail OBJ_LASER_* tags).
_LASER_GRID_PADS = frozenset(range(0x00D1, 0x00E1))

_MEETING_ROOM_ENTRY_MODELS = frozenset({MODEL_DOOR4A_G5, MODEL_DOOR4B_G5})
_MEETING_ROOM_ENTRY_PADS = frozenset({PAD_MEETING_ROOM_ENTRY_A, PAD_MEETING_ROOM_ENTRY_B})
_MEETING_ROOM_SOUTH_ENTRY_PADS = frozenset(
    {PAD_MEETING_ROOM_SOUTH_A, PAD_MEETING_ROOM_SOUTH_B}
)

_MISSION_ONLY_MODELS = frozenset(
    {
        MODEL_G5SAFEDOOR,
        MODEL_G5_ESCDOORUP,
        MODEL_G5_ESCDOORDOWN,
    }
)


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
                continue  # function-like macro
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
        if name.startswith("PAD_DEPO_"):
            # PAD_DEPO_009C → 156 (pad index in retail depo graph).
            return str(int(name.rsplit("_", 1)[-1], 16))
        if name not in consts:
            raise KeyError(name)
        return str(consts[name])

    resolved = re.sub(r"0x[0-9a-fA-F]+|0X[0-9a-fA-F]+|\d+|[A-Za-z_][A-Za-z0-9_]*", replace_token, expr)
    # Only allow safe arithmetic/bitwise tokens after substitution.
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
    """Return a copy with MP-friendly door flags (openable without mission scripts).

    Retail depo blocks the meeting-room corridor with:
    - 16 ``DOORTYPE_LASER`` beams (pads 0x00D1–0x00E0) that stay closed until
      laser-switch ailists call ``open_door(OBJ_LASER_*)``;
    - ``MODEL_DOOR4A/B_G5`` at pads 0x00B5/0x00B6 (tag 0x3a) and ``MODEL_DOOR2_G5``
      at pads 0x00AA/0x00AB on the south briefing doorway — all scripted in
      retail; MP free-roam deactivates them so the player can enter the room.
    """
    out = dict(fields)
    doortype = out["doortype"]
    model = out["model"]
    pad = out["pad"]

    # Escape / safe doors stay scripted.
    if model in _MISSION_ONLY_MODELS:
        return out

    if doortype == DOORTYPE_LASER:
        # Deactivate laser beams — retail KEEPOPEN + CANNOT_ACTIVATE blocks passage
        # and cannot be opened without mission laser-switch scripts.
        out["flags"] |= OBJFLAG_DEACTIVATED
        out["flags"] &= ~(OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
        return out

    # South briefing doorway — retail already deactivated; do not reactivate.
    if pad in _MEETING_ROOM_SOUTH_ENTRY_PADS:
        out["flags"] |= OBJFLAG_DEACTIVATED
        out["flags"] &= ~(OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
        return out

    # North corridor DOOR4 pair — remove collision for MP briefing free-roam.
    if model in _MEETING_ROOM_ENTRY_MODELS or pad in _MEETING_ROOM_ENTRY_PADS:
        out["flags"] |= OBJFLAG_DEACTIVATED
        out["flags"] &= ~(OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
        out["flags2"] &= ~(OBJFLAG2_LOCKEDFRONT | OBJFLAG2_LOCKEDBACK)
        out["keyflags"] = 0
        return out

    if doortype in (DOORTYPE_SLIDING, DOORTYPE_SWINGING):
        out["flags"] &= ~OBJFLAG_DEACTIVATED
        out["flags2"] &= ~(OBJFLAG2_LOCKEDFRONT | OBJFLAG2_LOCKEDBACK)
        out["keyflags"] = 0
    return out


def parse_setupdepo_doors(*, mp_unlock: bool = True) -> list[Door]:
    """Parse all ``door(...)`` entries from ``setupdepo.c``."""
    consts = _load_c_constants(_CONSTANTS_H)
    doors: list[Door] = []

    with open(_SETUP_DEPO, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _DOOR_LINE.match(line.rstrip())
            if not m:
                continue
            fields = _parse_door_args(m.group(1), consts)
            if mp_unlock:
                fields = _mp_unlock_door_fields(fields)
            doors.append(Door(**fields))
    return doors


def depo_door_inventory() -> list[dict]:
    """Human-readable door list for docs / validation output."""
    consts = _load_c_constants(_CONSTANTS_H)
    inv: list[dict] = []
    model_names = {v: k for k, v in consts.items() if k.startswith("MODEL_")}

    with open(_SETUP_DEPO, encoding="utf-8", errors="replace") as fh:
        for line in fh:
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
    """Prepare retail door props for agent-office MP setups.

    Agent office packs ``door(...)`` props only (no tags/chrs between pairs). Retail
    ``sibling`` offsets assume the full ``setup*.c`` props[] layout and can corrupt
    ``doorsCalcFrac`` sibling walks. Clear them — paired leaves still render.

    Do **not** MP-unlock here: ``mp_unlock=True`` activates dozens of automatic doors
    whose ``doorTick``/``doorsCalcFrac`` work pegs CPU and freezes the game. Deactivated
    doors keep collision; the briefing rooms are already open in retail layouts.
    """
    for door in doors:
        door.sibling = 0
        # Briefing rooms are open in retail layouts; keep every door static.
        door.flags |= OBJFLAG_DEACTIVATED
        door.flags &= ~(OBJFLAG_CANNOT_ACTIVATE | OBJFLAG_DOOR_KEEPOPEN)
    return doors


def agent_office_depo_doors() -> list[Door]:
    """All retail depo doors — static/deactivated (no ``doorTick`` CPU load)."""
    return prepare_agent_office_doors(parse_setupdepo_doors(mp_unlock=False))
