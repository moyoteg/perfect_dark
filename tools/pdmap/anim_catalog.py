"""Curated Perfect Dark animation catalog — study sections, parade set, auto-labels.

Used by the Animation Lab UI (``serve_animlab.py``) and the in-game parade
(``anim_parade.py``). Numeric indices are NTSC-final ``animations.json`` order.
"""

from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .core import ROOT, ROMID

_HEX_STUB = re.compile(r"^ANIM_[0-9A-F]{4}$")

# Category styling for the lab UI (icon + color + short blurb).
CATEGORY_META: dict[str, dict[str, str]] = {
    "idle": {"icon": "🧍", "color": "#6b8cff", "title": "Idle & hold", "blurb": "Looping stands — simulant default poses"},
    "social": {"icon": "💬", "color": "#a78bfa", "title": "Social & idle fidgets", "blurb": "Yawn, sneeze, talk — Cass / guard intros"},
    "movement": {"icon": "🚶", "color": "#4fd1a5", "title": "Movement", "blurb": "Walk, run — chrGoPos / GOPOSFLAG picks"},
    "combat": {"icon": "🔫", "color": "#ff6b6b", "title": "Combat", "blurb": "Draw, shoot, reload, grenades"},
    "react": {"icon": "💥", "color": "#ffb347", "title": "Reactions", "blurb": "Hit, cower, surrender"},
    "death": {"icon": "☠️", "color": "#888899", "title": "Death", "blurb": "g_DeathAnimations[] pool"},
    "computer": {
        "icon": "💻",
        "color": "#38bdf8",
        "title": "Computer / console",
        "blurb": "Terminals, typing, seated desk work — OPERATE_* & SITTING_*",
    },
    "use": {"icon": "🎯", "color": "#56cfe1", "title": "Use / operate", "blurb": "Sniping setup, prone sequences, misc object use"},
    "preset": {"icon": "🎭", "color": "#f472b6", "title": "AI presets", "blurb": "do_preset_animation(PRESETANIM_*)"},
    "cutscene": {"icon": "🎬", "color": "#94a3b8", "title": "Cutscene (CUT_*)", "blurb": "Mission cinematics — rarely used in MP"},
    "weapon": {"icon": "🔧", "color": "#c4b5fd", "title": "Weapon-specific", "blurb": "Per-gun equip / reload cycles"},
    "other": {"icon": "📎", "color": "#9090a8", "title": "Other named", "blurb": "Misc gameplay animations"},
    "stub": {"icon": "⬡", "color": "#505060", "title": "Hex stub", "blurb": "ANIM_00XX placeholder names"},
}

# Study-guide step labels (matches docs/CHARACTER_ANIMATIONS.md).
STUDY_STEPS: dict[int, str] = {
    1: "Assets & IDs",
    2: "Load / cache (anim.c)",
    3: "modelSetAnimation",
    4: "chrStartAnim / ACT_ANIM",
    5: "chr_do_animation (AI)",
    6: "Preset anims",
    7: "Combat / movement auto",
    8: "Player / bond",
    9: "Mod overrides",
    10: "Add new anims",
}

# Curated entries: (anim_id, label, hint, usage, category, study_step, in_parade)
# ``parade`` slot numbers are legacy UI hints only — the in-game grid uses every
# named, playable animation from ``animations.json`` via ``parade_showcase()``.
CURATED: list[dict[str, Any]] = [
    # --- Step 3: stand loops -------------------------------------------------
    {
        "id": "ANIM_TWO_GUN_HOLD",
        "label": "Two-gun hold",
        "hint": "Default sim idle — both hands, subtle sway",
        "usage": "chrChooseStandAnimation; Counter-Op bots",
        "category": "idle",
        "step": 3,
        "parade": 1,
    },
    {
        "id": "ANIM_006A",
        "label": "Stand variant 006A",
        "hint": "Alt rifle idle — second common stand pose",
        "usage": "chrChooseStandAnimation fallback",
        "category": "idle",
        "step": 3,
        "parade": 2,
    },
    # --- Step 4–5: social / AI one-shots --------------------------------------
    {
        "id": "ANIM_YAWN",
        "label": "Yawn",
        "hint": "Slow stretch — lab cycle starter",
        "usage": "setup ailists; chr_do_animation",
        "category": "social",
        "step": 5,
        "parade": 3,
    },
    {
        "id": "ANIM_SNEEZE",
        "label": "Sneeze",
        "hint": "SFX at frame 42 in chrTickAnim",
        "usage": "Guard fidget; chr_do_animation",
        "category": "social",
        "step": 4,
        "parade": 4,
    },
    {
        "id": "ANIM_SCRATCH_HEAD",
        "label": "Scratch head",
        "hint": "Hand to head — casual guard",
        "usage": "Ambient NPC fidget",
        "category": "social",
        "step": 5,
        "parade": 5,
    },
    {
        "id": "ANIM_TALKING_00A0",
        "label": "Talking (long)",
        "hint": "Cass office loop — frames 0–193",
        "usage": "setupwax.c Cass intro",
        "category": "social",
        "step": 4,
        "parade": 6,
    },
    {
        "id": "ANIM_TALKING_003D",
        "label": "Talking (short)",
        "hint": "Quick gesture — preset talk table",
        "usage": "PRESETANIM_TALK* pool",
        "category": "preset",
        "step": 6,
        "parade": 7,
    },
    {
        "id": "ANIM_SURRENDER_002E",
        "label": "Surrender",
        "hint": "Hands up — captive / yield",
        "usage": "Mission scripts; chr_do_animation",
        "category": "react",
        "step": 5,
        "parade": 8,
    },
    # --- Movement -------------------------------------------------------------
    {
        "id": "ANIM_WALK_BACKWARDS",
        "label": "Walk backwards",
        "hint": "Retreat while facing player",
        "usage": "setupwax.c; CHRANIMFLAG_SLOWUPDATE",
        "category": "movement",
        "step": 5,
        "parade": 9,
    },
    {
        "id": "ANIM_RUNNING_ONEHANDGUN",
        "label": "Run (one-hand gun)",
        "hint": "Light weapon run cycle",
        "usage": "chrGoPosChooseAnimation",
        "category": "movement",
        "step": 7,
        "parade": 10,
    },
    {
        "id": "ANIM_RUNNING_TWOHANDGUN",
        "label": "Run (two-hand gun)",
        "hint": "Heavy weapon run cycle",
        "usage": "chrGoPosChooseAnimation",
        "category": "movement",
        "step": 7,
        "parade": None,
    },
    # --- Combat ---------------------------------------------------------------
    {
        "id": "ANIM_DRAW_PISTOL_0245",
        "label": "Draw pistol",
        "hint": "Holster → aim — Cass before combat",
        "usage": "setupwax.c draw transition",
        "category": "combat",
        "step": 4,
        "parade": 11,
    },
    {
        "id": "ANIM_KNEEL_SHOOT_RIGHT_HAND",
        "label": "Kneel shoot (RH)",
        "hint": "One knee, fire right-hand weapon",
        "usage": "chrAttackChooseAnimation",
        "category": "combat",
        "step": 7,
        "parade": 12,
    },
    {
        "id": "ANIM_RELOAD_0209",
        "label": "Reload (generic)",
        "hint": "Mag swap — disarm at end frame",
        "usage": "chrTickAnim special case",
        "category": "combat",
        "step": 4,
        "parade": 13,
    },
    {
        "id": "ANIM_THROWGRENADE_STANDING",
        "label": "Throw grenade",
        "hint": "Overhand toss — standing",
        "usage": "chrThrowGrenade / AI",
        "category": "combat",
        "step": 7,
        "parade": 14,
    },
    {
        "id": "ANIM_FIX_GUN_JAM_EASY",
        "label": "Fix jam (easy)",
        "hint": "Tap weapon — PRESETANIM_GUNJAM",
        "usage": "do_preset_animation gun jam",
        "category": "preset",
        "step": 6,
        "parade": 15,
    },
    {
        "id": "ANIM_FIX_GUN_JAM_HARD",
        "label": "Fix jam (hard)",
        "hint": "Longer clear — harder jam preset",
        "usage": "PRESETANIM_GUNJAM variant",
        "category": "preset",
        "step": 6,
        "parade": None,
    },
    # --- Computer / console interact ------------------------------------------
    {
        "id": "ANIM_OPERATE_0204",
        "label": "Operate terminal (A)",
        "hint": "Standing — hands on panel / keypad (188 fr)",
        "usage": "Transportation, Dam, Pelagic II, Area 51; random with 0205/0206",
        "category": "computer",
        "step": 5,
        "parade": 16,
    },
    {
        "id": "ANIM_OPERATE_0205",
        "label": "Operate terminal (B)",
        "hint": "Alt standing console gesture — longer cycle (223 fr)",
        "usage": "BioTech guards (setuplip func0431); Dam/PAM/ARK terminals",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_OPERATE_0206",
        "label": "Operate terminal (C)",
        "hint": "Third standing operate variant (210 fr)",
        "usage": "Jonathan planting explosives (setuptra); terminal scripts",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_OPERATE_0221",
        "label": "Console tap (A)",
        "hint": "Short standing tap — biotech consoles (43 fr)",
        "usage": "LIP BioTech2 (func0430); RIT cyclone guards; CI terminals",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_OPERATE_0222",
        "label": "Console tap (B)",
        "hint": "Short press variant (37 fr)",
        "usage": "LIP BioTech2 random pool with 0221/0223",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_OPERATE_0223",
        "label": "Console swipe",
        "hint": "Horizontal swipe on panel (58 fr); often CHRANIMFLAG_FLIP",
        "usage": "LIP/LEE terminal guards; left-side consoles",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_SITTING_TYPING",
        "label": "Sitting typing",
        "hint": "Laptop / keyboard loop — abs-trans root (134 fr)",
        "usage": "RIT Air Base pilots (func0411_typing_guy); ELD lab",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_SITTING_DORMANT",
        "label": "Sitting idle",
        "hint": "Seated at desk — minimal motion (45 fr)",
        "usage": "RIT pilots (func0412); LIP/CAVE guard rooms",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_SITTING_0265",
        "label": "Sitting (variant)",
        "hint": "Alt seated chair idle (86 fr)",
        "usage": "CAVE Skedar ruins; DISH defection guards",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_STAND_UP_FROM_SITTING",
        "label": "Stand from sitting",
        "hint": "Rise from chair — pair with SITTING_* wake (17 fr)",
        "usage": "Transition out of seated desk poses",
        "category": "computer",
        "step": 5,
        "parade": None,
    },
    # --- Use / operate (non-computer) -----------------------------------------
    {
        "id": "ANIM_SNIPING_GETDOWN",
        "label": "Sniping get-down",
        "hint": "Drop to prone for sniper",
        "usage": "Sniper chr setup",
        "category": "use",
        "step": 7,
        "parade": 17,
    },
    # --- Reactions / death ----------------------------------------------------
    {
        "id": "ANIM_COWER_01F5",
        "label": "Cower",
        "hint": "Duck & cover — under fire",
        "usage": "Morale / suppress reactions",
        "category": "react",
        "step": 7,
        "parade": 18,
    },
    {
        "id": "ANIM_LOOK_AROUND_025B",
        "label": "Look around",
        "hint": "Head sweep — patrol idle",
        "usage": "Guard search behavior",
        "category": "react",
        "step": 5,
        "parade": 19,
    },
    {
        "id": "ANIM_DEATH_001A",
        "label": "Death 001A",
        "hint": "Standard death pool entry",
        "usage": "g_DeathAnimations[0]",
        "category": "death",
        "step": 7,
        "parade": 20,
    },
    {
        "id": "ANIM_DEATH_0021",
        "label": "Death 0021",
        "hint": "Longer collapse variant",
        "usage": "g_DeathAnimations pool",
        "category": "death",
        "step": 7,
        "parade": None,
    },
    # --- Extra reference (catalog only, not in parade) ------------------------
    {
        "id": "ANIM_IDLE",
        "label": "IDLE (placeholder)",
        "hint": "0 frames — never play",
        "usage": "Index 0 sentinel only",
        "category": "idle",
        "step": 1,
        "parade": None,
    },
    {
        "id": "ANIM_RELOAD",
        "label": "Reload (long)",
        "hint": "174 frames — generic reload",
        "usage": "Older reload path",
        "category": "combat",
        "step": 7,
        "parade": None,
    },
    {
        "id": "ANIM_GUN_FALCON2_RELOAD",
        "label": "Falcon 2 reload",
        "hint": "Example weapon-specific reload",
        "usage": "bgun / chr weapon tables",
        "category": "weapon",
        "step": 8,
        "parade": None,
    },
    {
        "id": "ANIM_GUN_CMP150_RELOAD",
        "label": "CMP150 reload",
        "hint": "Starter SMG reload cycle",
        "usage": "Loadout default weapon",
        "category": "weapon",
        "step": 8,
        "parade": None,
    },
    {
        "id": "ANIM_LOOK_AROUND_FRANTIC",
        "label": "Look around (frantic)",
        "hint": "Fast panic scan",
        "usage": "Alarm state NPCs",
        "category": "react",
        "step": 5,
        "parade": None,
    },
    {
        "id": "ANIM_DEATH_STOMACH_LONG",
        "label": "Death (stomach long)",
        "hint": "Slow slump forward",
        "usage": "Special death selection",
        "category": "death",
        "step": 7,
        "parade": None,
    },
]

# Prefix rules for auto-classifying any named ANIM_* (longest match first).
_PREFIX_RULES: list[tuple[str, str, str]] = [
    ("CUT_", "cutscene", "Cinematic / mission cutscene clip"),
    ("GUN_", "weapon", "Weapon equip, reload, or fire cycle"),
    ("DEATH_", "death", "Death / collapse sequence"),
    ("TALKING_", "social", "Dialogue gesture"),
    ("OPERATE_", "computer", "Standing console / terminal interact"),
    ("THROWGRENADE", "combat", "Grenade throw"),
    ("KNEEL_", "combat", "Kneeling combat pose"),
    ("RELOAD", "combat", "Reload cycle"),
    ("DRAW_", "combat", "Draw weapon from holster"),
    ("FIX_GUN", "preset", "Clear gun jam preset"),
    ("SURRENDER", "react", "Yield / hands up"),
    ("COWER", "react", "Cower under fire"),
    ("LOOK_", "react", "Look / scan environment"),
    ("SNIPING_", "use", "Sniper prone sequence"),
    ("SITTING_", "computer", "Seated desk / typing activity"),
    ("RUNNING_", "movement", "Run cycle"),
    ("WALK_", "movement", "Walk cycle"),
    ("SKEDAR_", "other", "Skedar chr specific"),
    ("ONBIKE_", "movement", "Bike mount / ride"),
    ("YAWN", "social", "Yawn fidget"),
    ("SNEEZE", "social", "Sneeze fidget"),
    ("SCRATCH", "social", "Scratch fidget"),
    ("GRAB_", "combat", "Grab / melee"),
    ("SPECIALDIE", "death", "Special death"),
]


@lru_cache(maxsize=1)
def _load_anims() -> list[dict[str, Any]]:
    path = os.path.join(ROOT, "src", "assets", ROMID, "animations.json")
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


@lru_cache(maxsize=1)
def _index_by_id() -> dict[str, int]:
    return {row["id"]: i for i, row in enumerate(_load_anims())}


def _flags_summary(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if row.get("flag01"):
        flags.append("loop")
    if row.get("flag02"):
        flags.append("abs-trans")
    if row.get("flag04"):
        flags.append("repeat")
    if row.get("flag08"):
        flags.append("cutskip")
    return flags


def parade_guard_playable(row: dict[str, Any]) -> bool:
    """True when *row* is safe to play on a pad-locked Area51 guard in Anim Lab.

    Cutscene clips (``CUT_*``, camera/dropship/vehicle rigs) use absolute world
    translation and smear chr geometry across the map when forced onto a guard.
    """
    anim_id = row["id"]
    body = anim_id.replace("ANIM_", "")
    if body.startswith("CUT_"):
        return False
    if "DROPSHIP" in anim_id or "_CAM_" in anim_id or "VEHICLE" in anim_id:
        return False
    if row.get("flag08"):
        return False
    if body.startswith("SKEDAR_") or body.startswith("ONBIKE_"):
        return False
    return True


def _auto_classify(anim_id: str) -> tuple[str, str]:
    """Return (category, one-line hint) from ANIM_* name."""
    if _HEX_STUB.match(anim_id):
        return "stub", "Unnamed stub — use index number in scripts"
    body = anim_id.replace("ANIM_", "")
    for prefix, category, hint in _PREFIX_RULES:
        if body.startswith(prefix) or prefix.rstrip("_") in body:
            return category, hint
    return "other", "Named gameplay animation"


def _humanize_id(anim_id: str) -> str:
    body = anim_id.replace("ANIM_", "").replace("_", " ").title()
    return body


def enrich_entry(
    anim_id: str,
    *,
    curated: dict[str, Any] | None = None,
    parade_slot: int | None = None,
    is_special_tour: bool = False,
) -> dict[str, Any]:
    """Build a UI-ready record for one animation."""
    by_id = _index_by_id()
    index = by_id.get(anim_id)
    row = _load_anims()[index] if index is not None else None

    if curated:
        category = curated["category"]
        label = curated["label"]
        hint = curated["hint"]
        usage = curated.get("usage", "")
        step = curated.get("step")
        if parade_slot is None:
            parade_slot = curated.get("parade")
    else:
        category, auto_hint = _auto_classify(anim_id)
        label = _humanize_id(anim_id)
        hint = auto_hint
        usage = ""
        step = None
        if parade_slot is None:
            parade_slot = None

    meta = CATEGORY_META.get(category, CATEGORY_META["other"])
    flags = _flags_summary(row) if row else []
    chr_ref = None
    pad_ref = None
    if parade_slot is not None and not is_special_tour:
        pad_ref = parade_slot
        chr_ref = f"0x{0x50 + parade_slot - 1:02X}"

    return {
        "id": anim_id,
        "index": index,
        "indexHex": f"0x{index:04X}" if index is not None else None,
        "file": row["file"] if row else None,
        "numframes": row["numframes"] if row else None,
        "bytesperframe": row["bytesperframe"] if row else None,
        "flags": flags,
        "label": label,
        "hint": hint,
        "usage": usage,
        "category": category,
        "categoryTitle": meta["title"],
        "categoryIcon": meta["icon"],
        "categoryColor": meta["color"],
        "studyStep": step,
        "studyStepTitle": STUDY_STEPS.get(step) if step else None,
        "paradeSlot": parade_slot,
        "inParade": parade_slot is not None,
        "isSpecialTour": is_special_tour,
        "chrRef": chr_ref,
        "padRef": pad_ref,
    }


# In-game parade grid — category **districts** with sub-zones (≤30 chr/room).
#
# ``cdCollectGeoForCyl`` (collision.c) keeps ``s16 propnums[256]`` and
# ``roomGetProps`` writes past *len* with no bounds check. Each sub-zone uses
# its own tile room; room 1 holds spawn, full-tour cycler, and static props.
PARADE_MAX_CHR_PER_ZONE = 30
PARADE_ZONE_ROOM_BASE = 2  # room 1 = player spawn + full-tour + props
PARADE_ZONE_COLS = 6
PARADE_ZONE_ROWS = 5  # 6×5 = 30 guards per sub-zone
PARADE_ZONE_SPACING_X = 200.0
PARADE_ZONE_SPACING_Z = 200.0
PARADE_ZONE_HALF = 90.0  # floor marker half-size (~half cell spacing)
# Legacy aliases — per-zone grid spacing.
PARADE_PREFERRED_COLS = PARADE_ZONE_COLS
PARADE_SPACING_X = PARADE_ZONE_SPACING_X
PARADE_SPACING_Z = PARADE_ZONE_SPACING_Z
PARADE_ZONE_GAP_Z = 350.0  # walk corridor between sub-zone blocks (legacy ref)
PARADE_ZONE_ORIGIN_Z = -600.0  # legacy — use district layout instead
PARADE_GRID_ORIGIN_Z = PARADE_ZONE_ORIGIN_Z

# --- South hub & walk spine ---------------------------------------------------
PARADE_PLAYER_SPAWN_Z = -2200.0
PARADE_HUB_Z = -1950.0  # north edge of spawn plaza (room 1 corridor start)
PARADE_CORRIDOR_END_Z = -1500.0  # where district grid begins (short walk from spawn)

# --- Category district grid (north of corridor) -------------------------------
# Each category gets a spatial district; large categories span multiple sub-zones.
PARADE_DISTRICT_ORDER: tuple[str, ...] = (
    "movement",
    "social",
    "combat",
    "react",
    "death",
    "computer",
    "use",
    "other",
    "weapon",
    "cutscene",
)

# Per-district placement on the district grid (col, row, span). Cutscene spans
# the full row width; weapon spans two columns for its four sub-zones.
PARADE_DISTRICT_LAYOUT: dict[str, dict[str, int]] = {
    "movement": {"gridCol": 0, "gridRow": 0, "spanCols": 1, "spanRows": 1},
    "social": {"gridCol": 1, "gridRow": 0, "spanCols": 1, "spanRows": 1},
    "combat": {"gridCol": 2, "gridRow": 0, "spanCols": 1, "spanRows": 1},
    "react": {"gridCol": 3, "gridRow": 0, "spanCols": 1, "spanRows": 1},
    "death": {"gridCol": 0, "gridRow": 1, "spanCols": 1, "spanRows": 1},
    "computer": {"gridCol": 1, "gridRow": 1, "spanCols": 1, "spanRows": 1},
    "use": {"gridCol": 2, "gridRow": 1, "spanCols": 1, "spanRows": 1},
    "other": {"gridCol": 3, "gridRow": 1, "spanCols": 1, "spanRows": 1},
    "weapon": {"gridCol": 0, "gridRow": 2, "spanCols": 2, "spanRows": 1},
    "cutscene": {"gridCol": 0, "gridRow": 3, "spanCols": 4, "spanRows": 2},
}

PARADE_DISTRICT_COLS = 4
PARADE_DISTRICT_CELL_W = 1500.0
PARADE_DISTRICT_CELL_D = 1200.0
PARADE_DISTRICT_ORIGIN_X = -2250.0  # centre of grid col 0
PARADE_DISTRICT_ORIGIN_Z = -900.0  # centre of grid row 0 — short walk north of spawn
PARADE_SUBZONE_PITCH_X = 1150.0  # sub-zone centres within a district
PARADE_SUBZONE_PITCH_Z = 1000.0
PARADE_SUBZONE_COLS = 4  # max sub-zones per row inside a district

# Props district — hub furniture gallery only (room 1). Bulk StdObject wings use
# dedicated tile rooms ≥ PARADE_PROP_ROOM_BASE so cdCollectGeoForCyl never sees
# 256+ props in one room (stack propnums[256] in collision.c).
PARADE_PROP_MAX_PER_ROOM = 200
PARADE_PROP_ROOM_BASE = 14  # rooms 2–13 = parade guard sub-zones
PARADE_PROPS_ROOM = 1
PARADE_OBJECT_TAG_ROOM_BASE = 20  # default for unknown tags
# Explicit room map — must stay ≤24 (engine allocates 25 tile rooms, 0..24).
OBJECT_TAG_ROOMS: dict[str, int] = {
    "furniture": 14,
    "military": 15,
    "lab": 20,
    "architecture": 21,
    "ci": 22,
    "skedar": 23,
    "misc": 24,
}
PARADE_TRUE_SCALE_NORMAL_ROOM = 16
PARADE_TRUE_SCALE_MEGA_ROOM = 17
PARADE_MEGAWORLD_ROOM = 18
PARADE_CHARACTERS_ROOM = 19
PARADE_PROPS_CENTER_X = -2200.0  # southwest furniture gallery
PARADE_PROPS_CENTER_Z = -3000.0
PARADE_PROPS_HALF = 750.0
PARADE_SPAWN_CLEARANCE = 500.0  # no solid props within this radius of spawn
PARADE_SPAWN_PLAZA_RADIUS = PARADE_SPAWN_CLEARANCE  # legacy alias — clearance, not a prop ring


def spawn_plaza_bounds() -> dict[str, float]:
    """Axis-aligned room-1 spawn plaza (pad 0 ± clearance) — never carve away."""
    sr = PARADE_SPAWN_CLEARANCE
    return {
        "x0": -sr,
        "z0": PARADE_PLAYER_SPAWN_Z - sr,
        "x1": sr,
        "z1": PARADE_PLAYER_SPAWN_Z + sr,
    }
PARADE_CORRIDOR_HALF_WIDTH = 250.0  # 500 u total — main route walk width
PARADE_CORRIDOR_COLOUR = 0x888  # fallback hub spine tint (12-bit; routes use wing colours)

# Object catalog megazone — tag-district clusters southwest (see museum_layout.py).
from .museum_layout import (  # noqa: E402 — layout constants
    OBJECT_CATALOG_HUB_X,
    OBJECT_CATALOG_HUB_Z,
    OBJECT_TAG_META,
    OBJECT_TAG_ORDER,
)

PARADE_MUSEUM_CENTER_X = OBJECT_CATALOG_HUB_X  # megazone centroid alias
PARADE_MUSEUM_CENTER_Z = OBJECT_CATALOG_HUB_Z
PARADE_MUSEUM_HALF = 1200.0  # fallback; use parade_museum_half() when sized
PARADE_MUSEUM_COLOUR = "#0ea5e9"  # megazone approach corridor tint
# Legacy grid constants (uniform pitch); layout now uses museum_layout.pack_museum_rows.
PARADE_MUSEUM_GRID_COLS = 0
PARADE_MUSEUM_GRID_SPACING = 520.0
PARADE_MUSEUM_GRID_MARGIN = 600.0  # carpet padding beyond outer props


def parade_museum_pick_count() -> int:
    """How many catalog models the museum will place (respects ANIMLAB_MUSEUM_MAX)."""
    import os

    from .anim_props import _load_model_catalog

    catalog = _load_model_catalog()
    if not catalog:
        return 0
    cap_raw = os.environ.get("ANIMLAB_MUSEUM_MAX", "0").strip()
    try:
        cap = int(cap_raw)
    except ValueError:
        cap = 0
    if cap <= 0:
        return len(catalog)
    return min(cap, len(catalog))


def parade_museum_grid_metrics(*, count: int | None = None) -> dict[str, float]:
    """Tag-district megazone footprint from per-tag bbox packing."""
    from .anim_props import _museum_tag_packed
    from .museum_layout import catalog_megazone_metrics

    packed = _museum_tag_packed()
    flat = [p for ps in packed.values() for p in ps]
    if count is None:
        count = len(flat)
    return catalog_megazone_metrics(packed, count=count)


def parade_museum_half() -> float:
    """Half-extent of the museum carpet from packed prop footprints."""
    return float(parade_museum_grid_metrics()["half"])


# True-scale prop gallery — retail extrascale only (bbox rodata, no showcase shrink).
# Split into two anchored wings so 352 models fit without AABB overlap:
#   normal objects (peak half ≤ 450 u) east-north of spawn;
#   megastructures (peak half > 450 u) far northwest yard.
PARADE_TRUE_SCALE_NORMAL_CENTER_X = 15000.0
PARADE_TRUE_SCALE_NORMAL_CENTER_Z = -20000.0
# s16 tile coords must stay within ±32767 — anchor megastructures in far NW corner.
PARADE_TRUE_SCALE_MEGA_CENTER_X = -29000.0
PARADE_TRUE_SCALE_MEGA_CENTER_Z = -29000.0
PARADE_TRUE_SCALE_COLOUR = "#14b8a6"  # teal — distinct from showcase museum (#0ea5e9)
PARADE_TRUE_SCALE_MEGA_COLOUR = "#0d9488"  # darker teal for megastructure yard carpet


def parade_true_scale_grid_metrics(*, wing: str = "combined") -> dict[str, float]:
    """Footprint summary for true-scale wing(s) — actual bbox packing, no shrink."""
    from .anim_props import _true_scale_packed_placements, _true_scale_wing_placements
    from .museum_layout import museum_layout_metrics

    if wing == "normal":
        placements = _true_scale_wing_placements("normal")
        cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X
        cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
    elif wing == "mega":
        placements = _true_scale_wing_placements("mega")
        cx = PARADE_TRUE_SCALE_MEGA_CENTER_X
        cz = PARADE_TRUE_SCALE_MEGA_CENTER_Z
    else:
        placements = _true_scale_packed_placements()
        cx = PARADE_TRUE_SCALE_NORMAL_CENTER_X
        cz = PARADE_TRUE_SCALE_NORMAL_CENTER_Z
    return museum_layout_metrics(
        placements,
        center_x=cx,
        center_z=cz,
        count=len(placements),
    )


def parade_true_scale_normal_half() -> float:
    from .anim_props import _true_scale_wing_placements
    from .museum_layout import museum_carpet_half

    placements = _true_scale_wing_placements("normal")
    return museum_carpet_half(
        placements,
        center_x=PARADE_TRUE_SCALE_NORMAL_CENTER_X,
        center_z=PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
    )


def parade_true_scale_mega_half() -> float:
    from .anim_props import _true_scale_wing_placements
    from .museum_layout import museum_carpet_half

    placements = _true_scale_wing_placements("mega")
    return museum_carpet_half(
        placements,
        center_x=PARADE_TRUE_SCALE_MEGA_CENTER_X,
        center_z=PARADE_TRUE_SCALE_MEGA_CENTER_Z,
    )


# Full-tour cycler — east of spawn plaza (room 1).
PARADE_SPECIAL_X = 600.0
PARADE_SPECIAL_Z = -2200.0
PARADE_SPECIAL_COLOUR = "#ffd166"
PARADE_SPECIAL_LABEL = "Full tour"
PARADE_SPECIAL_HINT = (
    "East of spawn — cycles every named animation. "
    "Use the eight coloured PORTALS at spawn (800 u ring) for directions. "
    "Walk southwest (cyan) for the props gallery; far southwest (W) for the object catalog "
    "(tag-coloured districts); northwest (teal) for true-scale yards (normal + mega gates); "
    "southeast (purple) for main characters; WSW gold solo world, east crimson MP world, "
    "northeast slate dev annex for test/extras."
)

# Hub portal ring — eight coloured arches at 800 u from spawn (room 1 wayfinding).
PARADE_HUB_SIGNPOST_RADIUS = 800.0
PARADE_HUB_PORTAL_RADIUS = PARADE_HUB_SIGNPOST_RADIUS
PARADE_HUB_SIGNPOST_COLOUR = "#fbbf24"

# Main-character gallery — southeast wing (dedicated tile room; distinct bodies vs parade guards).
PARADE_CHARACTERS_CENTER_X = 5500.0
PARADE_CHARACTERS_CENTER_Z = -4500.0
PARADE_CHARACTERS_HALF = 950.0
PARADE_CHARACTERS_COLOUR = "#c084fc"
PARADE_CHARACTERS_COLS = 6
PARADE_CHARACTERS_PITCH = 380.0


def parade_room_for_object_tag(tag: str) -> int:
    """Tile room for one object-catalog tag district (≤200 props per tag)."""
    return int(OBJECT_TAG_ROOMS.get(tag, PARADE_OBJECT_TAG_ROOM_BASE))


def parade_room_for_museum_prop(prop_index: int) -> int:
    """Legacy — tag districts use ``parade_room_for_object_tag`` instead."""
    _ = prop_index
    return PARADE_OBJECT_TAG_ROOM_BASE


def _cutscene_rom_count() -> int:
    """Named CUT_* clips in ROM (none are guard-playable on parade pads today)."""
    n = 0
    for row in _load_anims():
        if row.get("numframes", 0) <= 0:
            continue
        if _auto_classify(row["id"])[0] == "cutscene":
            n += 1
    return n


_STDOBJECT_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "stdobject_models.json"


@lru_cache(maxsize=1)
def _true_scale_wing_counts() -> tuple[int, int]:
    """Normal vs mega true-scale counts for hub labels (no anim_props import — avoids cycles)."""
    from .museum_layout import PARADE_TRUE_SCALE_MEGA_PEAK_HALF, model_half_extents

    if not _STDOBJECT_CATALOG_PATH.is_file():
        return 0, 0
    catalog = list(json.loads(_STDOBJECT_CATALOG_PATH.read_text(encoding="utf-8")).get("models") or [])
    normal = mega = 0
    for row in catalog:
        peak = max(model_half_extents(row))
        if peak > PARADE_TRUE_SCALE_MEGA_PEAK_HALF:
            mega += 1
        else:
            normal += 1
    return normal, mega


def hub_signpost_entries() -> list[dict[str, Any]]:
    """Spawn-plaza portal ring — direction, label, target wing, distance from spawn."""
    from .anim_levels import world_gate_entries

    spawn_x, spawn_z = 0.0, PARADE_PLAYER_SPAWN_Z
    r = PARADE_HUB_SIGNPOST_RADIUS

    def _dist(tx: float, tz: float) -> int:
        return int(round(math.hypot(tx - spawn_x, tz - spawn_z)))

    level_gates = {g["compass"]: g for g in world_gate_entries()}
    solo_g = level_gates["WSW"]
    mp_g = level_gates["E"]
    dev_g = level_gates["NE"]
    ts_normal, ts_mega = _true_scale_wing_counts()
    ts_label = f"True scale · {ts_normal} normal + {ts_mega} mega"
    ts_hint_dir = (
        f"northwest — NW-N normal yard (~{_dist(PARADE_TRUE_SCALE_NORMAL_CENTER_X, PARADE_TRUE_SCALE_NORMAL_CENTER_Z)} u); "
        f"NW-W mega yard (~{_dist(PARADE_TRUE_SCALE_MEGA_CENTER_X, PARADE_TRUE_SCALE_MEGA_CENTER_Z)} u)"
    )

    wings: list[tuple[str, str, float, float, str, str]] = [
        ("N", "Animation districts", PARADE_DISTRICT_ORIGIN_X, PARADE_DISTRICT_ORIGIN_Z, "#a78bfa", "north"),
        ("SW", "Props gallery", PARADE_PROPS_CENTER_X, PARADE_PROPS_CENTER_Z, "#38bdf8", "southwest"),
        ("WSW", f"Solo world · {solo_g['count']} levels", solo_g["gateX"], solo_g["gateZ"], solo_g["color"], "west-southwest"),
        ("W", "Object catalog", OBJECT_CATALOG_HUB_X, OBJECT_CATALOG_HUB_Z, "#0ea5e9", "far southwest"),
        ("E", f"MP world · {mp_g['count']} maps", mp_g["gateX"], mp_g["gateZ"], mp_g["color"], "east"),
        ("NW", ts_label, PARADE_TRUE_SCALE_NORMAL_CENTER_X, PARADE_TRUE_SCALE_NORMAL_CENTER_Z, PARADE_TRUE_SCALE_COLOUR, ts_hint_dir),
        ("SE", "Character gallery", PARADE_CHARACTERS_CENTER_X, PARADE_CHARACTERS_CENTER_Z, PARADE_CHARACTERS_COLOUR, "southeast"),
        ("NE", f"Dev annex · {dev_g['count']} stages", dev_g["gateX"], dev_g["gateZ"], dev_g["color"], "northeast"),
    ]
    compass_angle: dict[str, float] = {
        "N": 0.0,
        "NE": math.pi / 4,
        "E": math.pi / 2,
        "SE": 3 * math.pi / 4,
        "SW": 5 * math.pi / 4,
        "WSW": 7 * math.pi / 8,
        "W": -math.pi / 2,
        "NW": -3 * math.pi / 4,
    }
    entries: list[dict[str, Any]] = []
    for compass, label, tx, tz, colour, hint_dir in wings:
        ang = compass_angle.get(compass, 0.0)
        sx = spawn_x + r * math.sin(ang)
        sz = spawn_z + r * math.cos(ang)
        entry: dict[str, Any] = {
            "compass": compass,
            "label": label,
            "hint": f"{compass} → {label} ({hint_dir}, ~{_dist(tx, tz)} u)",
            "x": sx,
            "z": sz,
            "targetX": tx,
            "targetZ": tz,
            "distance": _dist(tx, tz),
            "color": colour,
            "floorColour": _hex_to_floor_colour(colour),
        }
        if compass == "NW":
            entry["subTargets"] = [
                {
                    "id": "gate_true_scale_normal",
                    "compass": "NW-N",
                    "label": f"True scale (normal) · {ts_normal}",
                    "x": PARADE_TRUE_SCALE_NORMAL_CENTER_X,
                    "z": PARADE_TRUE_SCALE_NORMAL_CENTER_Z,
                    "distance": _dist(PARADE_TRUE_SCALE_NORMAL_CENTER_X, PARADE_TRUE_SCALE_NORMAL_CENTER_Z),
                    "color": PARADE_TRUE_SCALE_COLOUR,
                },
                {
                    "id": "gate_true_scale_mega",
                    "compass": "NW-W",
                    "label": f"True scale (mega yard) · {ts_mega}",
                    "x": PARADE_TRUE_SCALE_MEGA_CENTER_X,
                    "z": PARADE_TRUE_SCALE_MEGA_CENTER_Z,
                    "distance": _dist(PARADE_TRUE_SCALE_MEGA_CENTER_X, PARADE_TRUE_SCALE_MEGA_CENTER_Z),
                    "color": PARADE_TRUE_SCALE_MEGA_COLOUR,
                },
            ]
        entries.append(entry)
    return entries


def hub_signpost_layout_payload() -> dict[str, Any]:
    """Hub compass ring metadata for tiles, props, and anim_lab.html overlay."""
    signs = hub_signpost_entries()
    return {
        "id": "hub_signposts",
        "label": "Spawn portal ring",
        "radius": PARADE_HUB_SIGNPOST_RADIUS,
        "color": PARADE_HUB_SIGNPOST_COLOUR,
        "signs": signs,
        "count": len(signs),
    }


from .anim_interactions import COMPUTER_INTERACTION_IDS  # noqa: E402 — re-export

# Max anims per tour ailist chunk (u8 label budget in unrolled wait/next pairs).
PARADE_TOUR_CHUNK_SIZE = 100


def parade_usable_rows() -> list[dict[str, Any]]:
    """Named, non-stub gameplay animations with frames > 0, sorted by ROM index."""
    rows: list[dict[str, Any]] = []
    for row in _load_anims():
        anim_id = row["id"]
        if _HEX_STUB.match(anim_id):
            continue
        if row.get("numframes", 0) <= 0:
            continue
        if not parade_guard_playable(row):
            continue
        rows.append(row)
    rows.sort(key=lambda r: _index_by_id()[r["id"]])
    cap_raw = os.environ.get("ANIMLAB_PARADE_MAX", "570").strip()
    if cap_raw:
        try:
            cap = int(cap_raw)
            if cap > 0:
                rows = rows[:cap]
        except ValueError:
            pass
    return rows


def _parade_slot_count() -> int:
    """Number of grid guards — one per usable named animation."""
    return len(parade_usable_rows())


@lru_cache(maxsize=1)
def _parade_slots_ordered() -> list[dict[str, Any]]:
    """Parade slot order — grouped by category district, ROM order within category."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in parade_usable_rows():
        cat, _ = _auto_classify(row["id"])
        by_cat.setdefault(cat, []).append(row)
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cat in PARADE_DISTRICT_ORDER:
        if cat in by_cat:
            ordered.extend(by_cat[cat])
            seen.add(cat)
    for cat in sorted(by_cat.keys()):
        if cat not in seen:
            ordered.extend(by_cat[cat])
    return ordered


@lru_cache(maxsize=1)
def _parade_plan() -> dict[str, Any]:
    """District → sub-zone → slot mapping for spatial layout and tile rooms."""
    ordered = _parade_slots_ordered()
    districts: list[dict[str, Any]] = []
    zones_flat: list[dict[str, Any]] = []
    slot_meta: dict[int, dict[str, Any]] = {}
    global_zone = 0
    slot_num = 1

    for cat in PARADE_DISTRICT_ORDER:
        cat_rows = [r for r in ordered if _auto_classify(r["id"])[0] == cat]
        layout = PARADE_DISTRICT_LAYOUT.get(cat, {"gridCol": 0, "gridRow": 0, "spanCols": 1, "spanRows": 1})
        if not cat_rows:
            if cat != "cutscene":
                continue
            span_cols = max(1, int(layout.get("spanCols", 1)))
            span_rows = max(1, int(layout.get("spanRows", 1)))
            grid_col = int(layout.get("gridCol", 0))
            grid_row = int(layout.get("gridRow", 0))
            dcx = (
                PARADE_DISTRICT_ORIGIN_X
                + (grid_col + (span_cols - 1) / 2.0) * PARADE_DISTRICT_CELL_W
            )
            dcz = (
                PARADE_DISTRICT_ORIGIN_Z
                + (grid_row + (span_rows - 1) / 2.0) * PARADE_DISTRICT_CELL_D
            )
            meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
            districts.append(
                {
                    "id": cat,
                    "label": meta["title"],
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "gridCol": grid_col,
                    "gridRow": grid_row,
                    "spanCols": span_cols,
                    "spanRows": span_rows,
                    "centerX": dcx,
                    "centerZ": dcz,
                    "animCount": 0,
                    "zoneCount": 0,
                    "zones": [],
                    "reserved": True,
                    "reserveNote": (
                        f"{_cutscene_rom_count()} CUT_* ROM clips — mission body rigs required (Phase 4)"
                    ),
                    "romCutsceneCount": _cutscene_rom_count(),
                }
            )
            continue
        span_cols = max(1, int(layout.get("spanCols", 1)))
        span_rows = max(1, int(layout.get("spanRows", 1)))
        grid_col = int(layout.get("gridCol", 0))
        grid_row = int(layout.get("gridRow", 0))

        # District centre from grid cell + span.
        dcx = (
            PARADE_DISTRICT_ORIGIN_X
            + (grid_col + (span_cols - 1) / 2.0) * PARADE_DISTRICT_CELL_W
        )
        dcz = (
            PARADE_DISTRICT_ORIGIN_Z
            + (grid_row + (span_rows - 1) / 2.0) * PARADE_DISTRICT_CELL_D
        )

        num_subzones = max(1, math.ceil(len(cat_rows) / PARADE_MAX_CHR_PER_ZONE))
        sub_cols = min(PARADE_SUBZONE_COLS, max(1, math.ceil(math.sqrt(num_subzones))))
        if cat == "weapon":
            sub_cols = 2
        if cat == "cutscene":
            sub_cols = 4

        zone_entries: list[dict[str, Any]] = []
        for z in range(num_subzones):
            chunk = cat_rows[z * PARADE_MAX_CHR_PER_ZONE : (z + 1) * PARADE_MAX_CHR_PER_ZONE]
            if not chunk:
                continue
            sub_col = z % sub_cols
            sub_row = z // sub_cols
            sub_cols_used = min(sub_cols, num_subzones)
            sub_origin_x = dcx - (sub_cols_used - 1) * PARADE_SUBZONE_PITCH_X / 2.0
            sub_origin_z = dcz - (math.ceil(num_subzones / sub_cols) - 1) * PARADE_SUBZONE_PITCH_Z / 2.0
            sub_cx = sub_origin_x + sub_col * PARADE_SUBZONE_PITCH_X
            sub_cz = sub_origin_z + sub_row * PARADE_SUBZONE_PITCH_Z

            slots_in_zone: list[int] = []
            for _ in chunk:
                slots_in_zone.append(slot_num)
                slot_meta[slot_num] = {
                    "slot": slot_num,
                    "category": cat,
                    "district": cat,
                    "zoneIndex": global_zone,
                    "zone": global_zone + 1,
                    "subZone": z + 1,
                    "slotInZone": len(slots_in_zone),
                    "subCenterX": sub_cx,
                    "subCenterZ": sub_cz,
                }
                slot_num += 1

            zone_rec = {
                "zoneIndex": global_zone,
                "index": global_zone + 1,
                "district": cat,
                "subZone": z + 1,
                "subCenterX": sub_cx,
                "subCenterZ": sub_cz,
                "room": parade_room_for_zone(global_zone),
                "slots": slots_in_zone,
                "slotCount": len(slots_in_zone),
            }
            zone_entries.append(zone_rec)
            zones_flat.append(zone_rec)
            global_zone += 1

        meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
        districts.append(
            {
                "id": cat,
                "label": meta["title"],
                "icon": meta["icon"],
                "color": meta["color"],
                "gridCol": grid_col,
                "gridRow": grid_row,
                "spanCols": span_cols,
                "spanRows": span_rows,
                "centerX": dcx,
                "centerZ": dcz,
                "animCount": len(cat_rows),
                "zoneCount": len(zone_entries),
                "zones": zone_entries,
            }
        )

    return {
        "districts": districts,
        "zones": zones_flat,
        "slotMeta": slot_meta,
        "ordered": ordered,
    }


def parade_zone_count(count: int | None = None) -> int:
    """Number of tile-room sub-zones (each ≤ ``PARADE_MAX_CHR_PER_ZONE`` guards)."""
    if count is not None and count != _parade_slot_count():
        return max(1, math.ceil(max(0, count) / PARADE_MAX_CHR_PER_ZONE))
    return max(1, len(_parade_plan()["zones"]))


def parade_zone_index(slot: int) -> int:
    """0-based sub-zone index for parade slot 1..N."""
    meta = _parade_plan()["slotMeta"].get(slot)
    if meta:
        return int(meta["zoneIndex"])
    return max(0, slot - 1) // PARADE_MAX_CHR_PER_ZONE


def parade_slot_in_zone(slot: int) -> int:
    """1-based slot index within the sub-zone grid."""
    meta = _parade_plan()["slotMeta"].get(slot)
    if meta:
        return int(meta["slotInZone"])
    return (max(0, slot - 1) % PARADE_MAX_CHR_PER_ZONE) + 1


def parade_district_for_slot(slot: int) -> str:
    """Category district id for parade slot 1..N."""
    meta = _parade_plan()["slotMeta"].get(slot)
    if meta:
        return str(meta["district"])
    row = _parade_slots_ordered()[slot - 1] if 0 < slot <= _parade_slot_count() else None
    if row:
        return _auto_classify(row["id"])[0]
    return "other"


def parade_room_for_zone(zone_index: int) -> int:
    """Tile room for guards in *zone_index* (0-based). Room 1 is hub/tour/props."""
    return PARADE_ZONE_ROOM_BASE + max(0, zone_index)


def parade_room_for_slot(slot: int) -> int:
    """Tile room for parade slot (sub-zone rooms 2+; hub room 1 for tour/props)."""
    return parade_room_for_zone(parade_zone_index(slot))


def parade_spacing(count: int | None = None) -> tuple[float, float]:
    """Per-zone cell spacing (x, z)."""
    _ = _parade_slot_count() if count is None else count
    return PARADE_ZONE_SPACING_X, PARADE_ZONE_SPACING_Z


def parade_zone_half(count: int | None = None) -> float:
    """Floor marker half-size — scales with zone cell spacing."""
    sx, _ = parade_spacing(count)
    return min(PARADE_ZONE_HALF, max(50.0, sx * 0.42))


def parade_grid_dims(count: int | None = None) -> tuple[int, int]:
    """Return ``(cols, rows)`` for one zone's local grid (not the full catalog)."""
    _ = _parade_slot_count() if count is None else count
    return PARADE_ZONE_COLS, PARADE_ZONE_ROWS


def parade_zone_origin_z(zone_index: int) -> float:
    """South row centre Z for sub-zone *zone_index* (legacy helper)."""
    plan = _parade_plan()
    for z in plan["zones"]:
        if z["zoneIndex"] == zone_index:
            _, sz = parade_spacing()
            rows = PARADE_ZONE_ROWS
            return float(z["subCenterZ"]) - max(0, rows - 1) * sz / 2.0
    _, rows = parade_grid_dims()
    _, sz = parade_spacing()
    zone_depth = max(0, rows - 1) * sz
    pitch = zone_depth + PARADE_ZONE_GAP_Z
    return PARADE_DISTRICT_ORIGIN_Z + zone_index * pitch


def parade_arena_half(count: int | None = None) -> float:
    """Box arena half-extent for all districts + hub + props + tour pad."""
    n = _parade_slot_count() if count is None else max(0, count)
    if n == 0:
        return 8000.0
    plan = _parade_plan()
    max_x = abs(PARADE_SPECIAL_X)
    max_z = abs(PARADE_PLAYER_SPAWN_Z)
    min_x = abs(PARADE_PROPS_CENTER_X) + PARADE_PROPS_HALF
    min_z = max_z

    sx, sz = parade_spacing(n)
    half_cell = max(PARADE_ZONE_COLS * sx, PARADE_ZONE_ROWS * sz) / 2.0

    for d in plan["districts"]:
        span_cols = int(d.get("spanCols", 1))
        span_rows = int(d.get("spanRows", 1))
        dcx = float(d["centerX"])
        dcz = float(d["centerZ"])
        hw = span_cols * PARADE_DISTRICT_CELL_W / 2.0 + half_cell + 200.0
        hd = span_rows * PARADE_DISTRICT_CELL_D / 2.0 + half_cell + 200.0
        max_x = max(max_x, abs(dcx) + hw)
        min_x = max(min_x, abs(dcx) - hw)
        max_z = max(max_z, abs(dcz) + hd)
        min_z = max(min_z, abs(dcz) - hd)

    max_x = max(max_x, min_x, abs(PARADE_PROPS_CENTER_X) + PARADE_PROPS_HALF)
    cat_metrics = parade_museum_grid_metrics()
    cat_cx = float(cat_metrics.get("centerX", OBJECT_CATALOG_HUB_X))
    cat_cz = float(cat_metrics.get("centerZ", OBJECT_CATALOG_HUB_Z))
    cat_half = float(cat_metrics.get("half", parade_museum_half()))
    max_x = max(max_x, abs(cat_cx) + cat_half)
    max_z = max(max_z, abs(cat_cz) + cat_half)
    max_x = max(max_x, abs(PARADE_TRUE_SCALE_NORMAL_CENTER_X) + parade_true_scale_normal_half())
    max_x = max(max_x, abs(PARADE_TRUE_SCALE_MEGA_CENTER_X) + parade_true_scale_mega_half())
    max_x = max(max_x, abs(PARADE_CHARACTERS_CENTER_X) + PARADE_CHARACTERS_HALF)
    max_z = max(max_z, abs(PARADE_TRUE_SCALE_NORMAL_CENTER_Z) + parade_true_scale_normal_half())
    max_z = max(max_z, abs(PARADE_TRUE_SCALE_MEGA_CENTER_Z) + parade_true_scale_mega_half())
    max_z = max(max_z, abs(PARADE_CHARACTERS_CENTER_Z) + PARADE_CHARACTERS_HALF)
    max_z = max(max_z, abs(PARADE_CORRIDOR_END_Z), abs(PARADE_HUB_Z))
    from .anim_levels import megaworld_bounds

    mb = megaworld_bounds()
    max_x = max(max_x, abs(mb["centerX"]) + mb["half"], mb["maxX"])
    max_z = max(max_z, abs(mb["centerZ"]) + mb["half"], mb["maxZ"])
    half = max(max_x, max_z) + 2000.0
    half = max(8000.0, math.ceil(half / 500.0) * 500.0)
    # Seg box faces pack coordinates as s16 — clamp arena to stay buildable.
    from .museum_layout import PARADE_ARENA_HALF_S16_MAX

    return min(PARADE_ARENA_HALF_S16_MAX, half)


def walkable_regions() -> list[dict[str, Any]]:
    """Walkable area quads for UI overlay and Map Editor 3D preview."""
    from .anim_interactions import INTERACTION_CONTEXT

    regions: list[dict[str, Any]] = []

    # Spawn plaza — open floor (no prop ring; room 1 clearance).
    sr = PARADE_SPAWN_CLEARANCE
    regions.append(
        {
            "id": "spawn_plaza",
            "label": "Spawn plaza (clear)",
            "kind": "plaza",
            "x0": -sr,
            "z0": PARADE_PLAYER_SPAWN_Z - sr,
            "x1": sr,
            "z1": PARADE_PLAYER_SPAWN_Z + sr,
            "color": "#1e293b",
        }
    )

    # North walk spine — hub corridor from spawn toward districts.
    from .anim_wayfinding import spawn_corridor_routes

    for route in spawn_corridor_routes():
        regions.append(
            {
                "id": route["id"],
                "label": route["label"],
                "kind": "corridor",
                "compass": route.get("compass"),
                "x0": route["x0"],
                "z0": route["z0"],
                "x1": route["x1"],
                "z1": route["z1"],
                "color": route["color"],
            }
        )

    # West approach — horizontal strip at spawn (props gallery mouth).
    regions.append(
        {
            "id": "west_approach",
            "label": "West approach",
            "kind": "corridor",
            "x0": PARADE_PROPS_CENTER_X + PARADE_PROPS_HALF,
            "z0": PARADE_PLAYER_SPAWN_Z - 160.0,
            "x1": 120.0,
            "z1": PARADE_PLAYER_SPAWN_Z + 160.0,
            "color": "#38bdf8",
        }
    )

    # Props yard (west hub).
    regions.append(
        {
            "id": "props_yard",
            "label": "Props yard",
            "kind": "props",
            "x0": PARADE_PROPS_CENTER_X - PARADE_PROPS_HALF,
            "z0": PARADE_PROPS_CENTER_Z - PARADE_PROPS_HALF,
            "x1": PARADE_PROPS_CENTER_X + PARADE_PROPS_HALF,
            "z1": PARADE_PROPS_CENTER_Z + PARADE_PROPS_HALF,
            "color": "#38bdf8",
        }
    )

    # Object catalog megazone — per-tag walkable carpets.
    from .anim_props import _museum_tag_packed
    from .museum_layout import tag_district_metrics

    packed = _museum_tag_packed()
    for tag in OBJECT_TAG_ORDER:
        placements = packed.get(tag)
        if not placements:
            continue
        td = tag_district_metrics(tag, placements)
        meta = OBJECT_TAG_META.get(tag, OBJECT_TAG_META["misc"])
        half = float(td["half"])
        cx, cz = float(td["centerX"]), float(td["centerZ"])
        regions.append(
            {
                "id": f"object_tag_{tag}",
                "label": f"{meta['label']} ({len(placements)})",
                "kind": "object_tag",
                "tag": tag,
                "x0": cx - half,
                "z0": cz - half,
                "x1": cx + half,
                "z1": cz + half,
                "color": meta["color"],
            }
        )

    # Catalog megazone bounding envelope (approach corridors are in spawn_corridor_routes).
    cat_metrics = parade_museum_grid_metrics()
    cat_cx = float(cat_metrics.get("centerX", OBJECT_CATALOG_HUB_X))
    cat_cz = float(cat_metrics.get("centerZ", OBJECT_CATALOG_HUB_Z))
    cat_half = float(cat_metrics.get("half", parade_museum_half()))
    regions.append(
        {
            "id": "object_catalog",
            "label": "Object catalog megazone",
            "kind": "museum",
            "x0": cat_cx - cat_half,
            "z0": cat_cz - cat_half,
            "x1": cat_cx + cat_half,
            "z1": cat_cz + cat_half,
            "color": PARADE_MUSEUM_COLOUR,
        }
    )

    # Southwest approach duplicate removed — covered by route_props_approach / route_catalog_cross.

    # Hub signpost ring (spawn plaza edge).
    sr = PARADE_HUB_SIGNPOST_RADIUS
    regions.append(
        {
            "id": "hub_signpost_ring",
            "label": "Signpost ring",
            "kind": "signpost",
            "x0": -sr,
            "z0": PARADE_PLAYER_SPAWN_Z - sr,
            "x1": sr,
            "z1": PARADE_PLAYER_SPAWN_Z + sr,
            "color": PARADE_HUB_SIGNPOST_COLOUR,
        }
    )

    # True-scale gallery — normal objects wing (east-north, teal carpet).
    regions.append(
        {
            "id": "true_scale_normal",
            "label": "True scale — normal objects",
            "kind": "true_scale",
            "x0": PARADE_TRUE_SCALE_NORMAL_CENTER_X - parade_true_scale_normal_half(),
            "z0": PARADE_TRUE_SCALE_NORMAL_CENTER_Z - parade_true_scale_normal_half(),
            "x1": PARADE_TRUE_SCALE_NORMAL_CENTER_X + parade_true_scale_normal_half(),
            "z1": PARADE_TRUE_SCALE_NORMAL_CENTER_Z + parade_true_scale_normal_half(),
            "color": PARADE_TRUE_SCALE_COLOUR,
        }
    )

    # True-scale megastructure yard (far northwest — carpet clamped to s16 tile limits).
    regions.append(
        {
            "id": "true_scale_mega",
            "label": "True scale — megastructure yard",
            "kind": "true_scale",
            "x0": PARADE_TRUE_SCALE_MEGA_CENTER_X - parade_true_scale_mega_half(),
            "z0": PARADE_TRUE_SCALE_MEGA_CENTER_Z - parade_true_scale_mega_half(),
            "x1": PARADE_TRUE_SCALE_MEGA_CENTER_X + parade_true_scale_mega_half(),
            "z1": PARADE_TRUE_SCALE_MEGA_CENTER_Z + parade_true_scale_mega_half(),
            "color": PARADE_TRUE_SCALE_MEGA_COLOUR,
        }
    )

    # Character gallery (southeast wing).
    regions.append(
        {
            "id": "characters",
            "label": "Character gallery",
            "kind": "characters",
            "x0": PARADE_CHARACTERS_CENTER_X - PARADE_CHARACTERS_HALF,
            "z0": PARADE_CHARACTERS_CENTER_Z - PARADE_CHARACTERS_HALF,
            "x1": PARADE_CHARACTERS_CENTER_X + PARADE_CHARACTERS_HALF,
            "z1": PARADE_CHARACTERS_CENTER_Z + PARADE_CHARACTERS_HALF,
            "color": PARADE_CHARACTERS_COLOUR,
        }
    )

    sx, sz = PARADE_ZONE_SPACING_X, PARADE_ZONE_SPACING_Z
    half_cell_x = PARADE_ZONE_COLS * sx / 2.0 + PARADE_ZONE_HALF
    half_cell_z = PARADE_ZONE_ROWS * sz / 2.0 + PARADE_ZONE_HALF

    plan = _parade_plan()
    for district in plan["districts"]:
        cat = str(district["id"])
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        span_cols = int(district.get("spanCols", 1))
        span_rows = int(district.get("spanRows", 1))
        hw = span_cols * PARADE_DISTRICT_CELL_W / 2.0 + 80.0
        hd = span_rows * PARADE_DISTRICT_CELL_D / 2.0 + 80.0
        meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
        regions.append(
            {
                "id": f"district_{cat}",
                "label": meta["title"],
                "kind": "district",
                "district": cat,
                "x0": dcx - hw,
                "z0": dcz - hd,
                "x1": dcx + hw,
                "z1": dcz + hd,
                "color": meta["color"],
            }
        )

    for zone in plan["zones"]:
        sub_cx = float(zone["subCenterX"])
        sub_cz = float(zone["subCenterZ"])
        cat = str(zone["district"])
        meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
        regions.append(
            {
                "id": f"zone_{zone['zoneIndex']}",
                "label": f"{meta['title']} z{zone['subZone']}",
                "kind": "subzone",
                "district": cat,
                "zoneIndex": zone["zoneIndex"],
                "x0": sub_cx - half_cell_x,
                "z0": sub_cz - half_cell_z,
                "x1": sub_cx + half_cell_x,
                "z1": sub_cz + half_cell_z,
                "color": meta["color"],
            }
        )

    # Vignette entrance pads per district (south mouth toward corridor).
    for district in plan["districts"]:
        cat = str(district["id"])
        ctx = INTERACTION_CONTEXT.get(cat)
        if not ctx or not ctx.get("propModels"):
            continue
        dcx = float(district["centerX"])
        dcz = float(district["centerZ"])
        span_rows = int(district.get("spanRows", 1))
        mouth_z = dcz - span_rows * PARADE_DISTRICT_CELL_D / 2.0 - 120.0
        meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
        regions.append(
            {
                "id": f"vignette_{cat}",
                "label": f"{ctx['vignetteLabel']} entrance",
                "kind": "vignette",
                "district": cat,
                "x0": dcx - 280.0,
                "z0": mouth_z - 120.0,
                "x1": dcx + 280.0,
                "z1": mouth_z + 120.0,
                "color": meta["color"],
            }
        )

    from .anim_levels import megaworld_walkable_regions

    regions.extend(megaworld_walkable_regions())

    return regions


_PARADE_COUNT = _parade_slot_count()
PARADE_COLS, PARADE_ROWS = parade_grid_dims(_PARADE_COUNT)
PARADE_ZONE_COUNT = parade_zone_count(_PARADE_COUNT)


def _hex_to_floor_colour(hex_color: str) -> int:
    """12-bit RRRR GGGG BBBB floorcolour from ``#RRGGBB`` (matches pdmap tile format)."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) >> 4
    g = int(h[2:4], 16) >> 4
    b = int(h[4:6], 16) >> 4
    return (r << 8) | (g << 4) | b


def _hex_to_seg_rgba(hex_color: str, *, alpha: int = 0xFF) -> int:
    """RGBA8 for visible seg floor markers."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r << 24) | (g << 16) | (b << 8) | alpha


def parade_grid_xy(slot: int, *, count: int | None = None) -> tuple[float, float]:
    """Centre (x, z) for parade slot 1..N within its district sub-zone grid."""
    _ = _parade_slot_count() if count is None else count
    meta = _parade_plan()["slotMeta"].get(slot)
    if not meta:
        return 0.0, PARADE_DISTRICT_ORIGIN_Z
    local = int(meta["slotInZone"]) - 1
    cols, _ = parade_grid_dims()
    sx, sz = parade_spacing()
    col = local % cols
    row = local // cols
    sub_cx = float(meta["subCenterX"])
    sub_cz = float(meta["subCenterZ"])
    origin_x = sub_cx - (cols - 1) * sx / 2.0
    origin_z = sub_cz - (PARADE_ZONE_ROWS - 1) * sz / 2.0
    x = origin_x + col * sx
    z = origin_z + row * sz
    return x, z


def parade_special_marker(count: int | None = None) -> dict[str, Any]:
    """Metadata for the full-tour cycler pad (not on a zone grid)."""
    n = _parade_slot_count() if count is None else count
    pad = n + 1
    chr_num = 0x50 + n
    colour = PARADE_SPECIAL_COLOUR
    return {
        "slot": 0,
        "pad": pad,
        "room": 1,
        "x": PARADE_SPECIAL_X,
        "z": PARADE_SPECIAL_Z,
        "row": -1,
        "col": -1,
        "label": PARADE_SPECIAL_LABEL,
        "animId": "__FULL_TOUR__",
        "category": "tour",
        "categoryColor": colour,
        "floorColour": _hex_to_floor_colour(colour),
        "segRgba": _hex_to_seg_rgba(colour),
        "chrRef": f"0x{chr_num:02X}",
        "hint": PARADE_SPECIAL_HINT,
        "isSpecialTour": True,
        "tourAnimCount": n,
        "zone": 0,
        "zoneLabel": "Full tour",
    }


def parade_slot_markers() -> list[dict[str, Any]]:
    """Per-slot floor marker metadata for tiles/seg and the Animation Lab UI grid."""
    curated_by_id = {e["id"]: e for e in CURATED}
    n = _parade_slot_count()
    cols, _ = parade_grid_dims(n)
    rows: list[dict[str, Any]] = []
    for slot, row in enumerate(_parade_slots_ordered(), start=1):
        anim_id = row["id"]
        curated = curated_by_id.get(anim_id)
        rec = enrich_entry(anim_id, curated=curated, parade_slot=slot)
        colour = rec["categoryColor"]
        x, z = parade_grid_xy(slot, count=n)
        plan_meta = _parade_plan()["slotMeta"][slot]
        zone_idx = int(plan_meta["zoneIndex"])
        local = int(plan_meta["slotInZone"])
        district = str(plan_meta["district"])
        d_meta = CATEGORY_META.get(district, CATEGORY_META["other"])
        rows.append(
            {
                "slot": slot,
                "pad": slot,
                "x": x,
                "z": z,
                "row": (local - 1) // cols,
                "col": (local - 1) % cols,
                "zoneIndex": zone_idx,
                "zone": zone_idx + 1,
                "zoneLabel": f"{d_meta['title']} · z{plan_meta['subZone']}",
                "district": district,
                "districtLabel": d_meta["title"],
                "districtIcon": d_meta["icon"],
                "districtColor": d_meta["color"],
                "subZone": int(plan_meta["subZone"]),
                "slotInZone": local,
                "room": parade_room_for_slot(slot),
                "label": rec["label"],
                "animId": anim_id,
                "category": rec["category"],
                "categoryColor": colour,
                "floorColour": _hex_to_floor_colour(colour),
                "segRgba": _hex_to_seg_rgba(colour),
                "chrRef": rec["chrRef"],
                "index": rec["index"],
                "indexHex": rec["indexHex"],
            }
        )
    return rows


def parade_district_markers() -> list[dict[str, Any]]:
    """Category district metadata for UI tabs, tiles, and docs."""
    return list(_parade_plan()["districts"])


def parade_zone_markers() -> list[dict[str, Any]]:
    """Sub-zone metadata grouped by district (legacy name — use parade_district_markers)."""
    markers = parade_slot_markers()
    zones: list[dict[str, Any]] = []
    for zone_idx in range(parade_zone_count()):
        slots = [s for s in markers if s["zoneIndex"] == zone_idx]
        if not slots:
            continue
        cols, rows = parade_grid_dims()
        district = slots[0]["district"]
        d_meta = CATEGORY_META.get(district, CATEGORY_META["other"])
        zones.append(
            {
                "index": zone_idx + 1,
                "zoneIndex": zone_idx,
                "label": slots[0]["zoneLabel"],
                "district": district,
                "districtLabel": d_meta["title"],
                "room": parade_room_for_zone(zone_idx),
                "originZ": parade_zone_origin_z(zone_idx),
                "slotCount": len(slots),
                "maxSlots": PARADE_MAX_CHR_PER_ZONE,
                "cols": cols,
                "rows": rows,
                "slots": slots,
            }
        )
    return zones


def parade_layout_payload() -> dict[str, Any]:
    """Grid layout summary for docs and ``anim_lab.html``."""
    from .anim_interactions import enrich_slots_with_interactions, interaction_registry_payload
    from .anim_characters import character_gallery_layout_payload
    from .anim_levels import level_megaworld_layout_payload
    from .anim_props import (
        parade_all_prop_markers,
        parade_museum_layout_payload,
        parade_props_layout_payload,
        parade_true_scale_layout_payload,
        parade_vignette_layout_payload,
    )

    from .anim_wayfinding import in_game_guide_payload

    count = _parade_slot_count()
    cols, rows = parade_grid_dims(count)
    sx, sz = parade_spacing(count)
    districts = parade_district_markers()
    zones = parade_zone_markers()
    special = parade_special_marker(count)
    zone_count = len(zones)
    district_count = len(districts)
    all_props = parade_all_prop_markers()
    slots = enrich_slots_with_interactions(parade_slot_markers(), all_props)
    return {
        "slotCount": count,
        "gridSlotCount": count,
        "specialSlot": special,
        "totalGuards": count + 1,
        "maxChrPerZone": PARADE_MAX_CHR_PER_ZONE,
        "zoneCount": zone_count,
        "districtCount": district_count,
        "districts": districts,
        "zones": zones,
        "propsDistrict": parade_props_layout_payload(),
        "vignetteProps": parade_vignette_layout_payload(),
        "museumDistrict": parade_museum_layout_payload(),
        "trueScaleDistrict": parade_true_scale_layout_payload(),
        "levelMegaworldDistrict": level_megaworld_layout_payload(),
        "characterDistrict": character_gallery_layout_payload(),
        "hubSignposts": hub_signpost_layout_payload(),
        "inGameGuide": in_game_guide_payload(),
        "interactionRegistry": interaction_registry_payload(),
        "walkableRegions": walkable_regions(),
        "cols": cols,
        "rows": rows,
        "spacingX": sx,
        "spacingZ": sz,
        "zoneGapZ": PARADE_ZONE_GAP_Z,
        "originZ": PARADE_DISTRICT_ORIGIN_Z,
        "zoneHalf": parade_zone_half(count),
        "arenaHalf": parade_arena_half(count),
        "playerSpawn": {"x": 0.0, "z": PARADE_PLAYER_SPAWN_Z},
        "hubZ": PARADE_HUB_Z,
        "corridorEndZ": PARADE_CORRIDOR_END_Z,
        "engineLimitNote": (
            "cdCollectGeoForCyl uses propnums[256] with no bounds check — "
            f"≤{PARADE_MAX_CHR_PER_ZONE} guards per tile room."
        ),
        "includedPolicy": (
            "All named (non-ANIM_XXXX stub) animations with numframes > 0 from "
            "animations.json — {count} grid loops in {districts} category districts "
            f"({zone_count} sub-zones, ≤{PARADE_MAX_CHR_PER_ZONE}/zone) plus one "
            "full-tour cycler, props yard, district vignettes, object catalog (tag districts), true-scale "
            "gallery (normal + megastructure wings), level megaworld (all stagetable "
            "stages), character gallery, and spawn signpost ring."
        ).format(count=count, districts=district_count, zone_count=zone_count),
        "description": (
            f"{district_count} category districts ({cols}×{rows} cells/sub-zone, "
            f"≤{PARADE_MAX_CHR_PER_ZONE} loops/zone) — walk north from spawn through "
            "districts; props southwest; object catalog far southwest (tag-coloured clusters); "
            "true-scale gallery east-north + megastructure yard far northwest; level megaworld "
            "northeast; character gallery southeast; signpost ring at spawn; full-tour cycler east."
        ),
        "slots": slots,
    }


def parade_showcase() -> list[tuple[str, int]]:
    """Ordered (short_label, index) list for anim_parade.py — district-grouped slots."""
    curated_by_id = {e["id"]: e for e in CURATED}
    items: list[tuple[str, int]] = []
    for row in _parade_slots_ordered():
        anim_id = row["id"]
        idx = _index_by_id()[anim_id]
        curated = curated_by_id.get(anim_id)
        if curated:
            short = curated["label"].upper().replace(" ", "_")[:24]
        else:
            short = _humanize_id(anim_id).upper().replace(" ", "_")[:24]
        items.append((short, idx))
    return items


def computer_interaction_showcase() -> list[tuple[str, int]]:
    """(short_label, index) for stock computer/console chr anims — subset of parade_showcase()."""
    by_id = _index_by_id()
    curated_by_id = {e["id"]: e for e in CURATED}
    items: list[tuple[str, int]] = []
    for anim_id in COMPUTER_INTERACTION_IDS:
        idx = by_id.get(anim_id)
        if idx is None:
            continue
        row = _load_anims()[idx]
        if row.get("numframes", 0) <= 0:
            continue
        curated = curated_by_id.get(anim_id)
        if curated:
            short = curated["label"].upper().replace(" ", "_")[:24]
        else:
            short = _humanize_id(anim_id).upper().replace(" ", "_")[:24]
        items.append((short, idx))
    return items


def computer_interaction_parade_slots() -> list[dict[str, Any]]:
    """Parade grid slot metadata for computer/console anims (for docs and lab UI)."""
    markers = {m["animId"]: m for m in parade_slot_markers()}
    rows: list[dict[str, Any]] = []
    for anim_id in COMPUTER_INTERACTION_IDS:
        marker = markers.get(anim_id)
        if not marker:
            continue
        curated = next((e for e in CURATED if e["id"] == anim_id), None)
        rows.append({**enrich_entry(anim_id, curated=curated, parade_slot=marker["slot"]), **marker})
    return rows


def parade_tour_indices() -> list[int]:
    """ROM indices for the full-tour cycler — same set as the grid, ROM order."""
    return [idx for _, idx in parade_showcase()]


def catalog_sections() -> list[dict[str, Any]]:
    """Curated sections for the lab UI."""
    by_id = _index_by_id()
    seen: set[str] = set()
    sections: dict[str, list[dict[str, Any]]] = {}

    for entry in CURATED:
        anim_id = entry["id"]
        if anim_id not in by_id:
            continue
        seen.add(anim_id)
        cat = entry["category"]
        sections.setdefault(cat, []).append(enrich_entry(anim_id, curated=entry))

    result: list[dict[str, Any]] = []
    order = ["idle", "social", "movement", "combat", "preset", "computer", "use", "react", "death", "weapon"]
    for cat in order:
        if cat not in sections:
            continue
        meta = CATEGORY_META[cat]
        result.append(
            {
                "id": cat,
                "title": meta["title"],
                "icon": meta["icon"],
                "color": meta["color"],
                "blurb": meta["blurb"],
                "animations": sections[cat],
            }
        )
    return result


def study_steps_index() -> list[dict[str, Any]]:
    """Animations grouped by CHARACTER_ANIMATIONS.md study step."""
    by_id = _index_by_id()
    buckets: dict[int, list[dict[str, Any]]] = {}
    for entry in CURATED:
        step = entry.get("step")
        if not step or entry["id"] not in by_id:
            continue
        buckets.setdefault(step, []).append(enrich_entry(entry["id"], curated=entry))
    return [
        {
            "step": step,
            "title": STUDY_STEPS[step],
            "animations": buckets[step],
        }
        for step in sorted(buckets)
    ]


def full_catalog_payload(*, include_stubs: bool = False, limit_per_category: int = 200) -> dict[str, Any]:
    """Full named-animation catalog with auto labels, grouped by category."""
    anims = _load_anims()
    curated_by_id = {e["id"]: e for e in CURATED}
    groups: dict[str, list[dict[str, Any]]] = {}

    for row in anims:
        anim_id = row["id"]
        if not include_stubs and _HEX_STUB.match(anim_id):
            continue
        curated = curated_by_id.get(anim_id)
        rec = enrich_entry(anim_id, curated=curated)
        groups.setdefault(rec["category"], []).append(rec)

    sections: list[dict[str, Any]] = []
    cat_order = list(CATEGORY_META.keys())
    for cat in cat_order:
        rows = groups.get(cat, [])
        if not rows:
            continue
        rows.sort(key=lambda r: (r["index"] if r["index"] is not None else 99999))
        if limit_per_category:
            rows = rows[:limit_per_category]
        meta = CATEGORY_META[cat]
        sections.append(
            {
                "id": cat,
                "title": meta["title"],
                "icon": meta["icon"],
                "color": meta["color"],
                "blurb": meta["blurb"],
                "count": len(groups.get(cat, [])),
                "animations": rows,
            }
        )

    parade_rows = parade_slot_markers()
    parade = [
        enrich_entry(
            s["animId"],
            curated=curated_by_id.get(s["animId"]),
            parade_slot=s["slot"],
        )
        for s in parade_rows
    ]
    special = parade_layout_payload()["specialSlot"]
    parade.append(
        {
            **enrich_entry("ANIM_OPERATE_0204", curated=curated_by_id.get("ANIM_OPERATE_0204")),
            "id": "__FULL_TOUR__",
            "label": special["label"],
            "hint": special["hint"],
            "category": "tour",
            "categoryTitle": "Full tour",
            "categoryIcon": "🎞️",
            "categoryColor": special["categoryColor"],
            "inParade": True,
            "isSpecialTour": True,
            "paradeSlot": None,
            "chrRef": special["chrRef"],
            "padRef": special["pad"],
            "tourAnimCount": special["tourAnimCount"],
        }
    )

    return {
        "totalAnimations": len(anims),
        "namedCount": sum(1 for a in anims if not _HEX_STUB.match(a["id"])),
        "curatedCount": len(CURATED),
        "paradeCount": len(parade_showcase()),
        "studySteps": STUDY_STEPS,
        "categories": {k: CATEGORY_META[k] for k in CATEGORY_META},
        "parade": parade,
        "paradeLayout": parade_layout_payload(),
        "curatedSections": catalog_sections(),
        "studyGuide": study_steps_index(),
        "computerInteraction": {
            "count": len(computer_interaction_showcase()),
            "ids": list(COMPUTER_INTERACTION_IDS),
            "animations": computer_interaction_parade_slots(),
        },
        "allSections": sections,
    }


def search_enriched(*, search: str = "", category: str = "", limit: int = 80, named_only: bool = True) -> list[dict[str, Any]]:
    anims = _load_anims()
    curated_by_id = {e["id"]: e for e in CURATED}
    needle = search.lower().strip()
    rows: list[dict[str, Any]] = []

    for row in anims:
        anim_id = row["id"]
        if named_only and _HEX_STUB.match(anim_id):
            continue
        rec = enrich_entry(anim_id, curated=curated_by_id.get(anim_id))
        if category and rec["category"] != category:
            continue
        if needle:
            hay = " ".join(
                str(x)
                for x in (
                    anim_id,
                    rec["label"],
                    rec["hint"],
                    rec["usage"],
                    rec["index"],
                    rec.get("indexHex"),
                )
                if x
            ).lower()
            if needle not in hay:
                continue
        rows.append(rec)
        if limit and len(rows) >= limit:
            break
    return rows
