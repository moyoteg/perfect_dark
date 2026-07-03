"""Animation Lab interaction registry — category props, anim ids, walkable overlays.

Maps each parade **district** (animation category) to stock StdObject models and
representative chr animation ids used with those props in missions.
"""

from __future__ import annotations

import math
from typing import Any

# StdObject model IDs (must match anim_props / constants.h — kept here to avoid import cycles).
MODEL_DOORCONSOLE = 0x0018
MODEL_A51_CRATE1 = 0x0020
MODEL_A51_CRATE2 = 0x0021
MODEL_A51DESKENT = 0x0066
MODEL_LAB_CHAIR = 0x00BB
MODEL_LAB_TABLE = 0x00BC
MODEL_LAB_MAINFRAME = 0x00BE
MODEL_CI_DESK = 0x0161

# Chr animations used for computer / console / desk interaction in stock missions.
COMPUTER_INTERACTION_IDS: tuple[str, ...] = (
    "ANIM_STAND_UP_FROM_SITTING",
    "ANIM_SITTING_TYPING",
    "ANIM_OPERATE_0204",
    "ANIM_OPERATE_0205",
    "ANIM_OPERATE_0206",
    "ANIM_OPERATE_0221",
    "ANIM_OPERATE_0222",
    "ANIM_OPERATE_0223",
    "ANIM_SITTING_DORMANT",
    "ANIM_SITTING_0265",
)

# Representative combat / cover animations (subset — full set is the combat district).
COMBAT_INTERACTION_IDS: tuple[str, ...] = (
    "ANIM_DRAW_GUN",
    "ANIM_FIRE_GUN",
    "ANIM_RELOAD",
    "ANIM_KNEEL",
    "ANIM_THROW_GRENADE",
)

USE_INTERACTION_IDS: tuple[str, ...] = (
    "ANIM_SNIPER_SETUP",
    "ANIM_PRONE",
    "ANIM_OPERATE_0204",
)

SOCIAL_INTERACTION_IDS: tuple[str, ...] = (
    "ANIM_TALKING",
    "ANIM_YAWN",
    "ANIM_SNEEZE",
)

MOVEMENT_INTERACTION_IDS: tuple[str, ...] = (
    "ANIM_WALK",
    "ANIM_RUN",
    "ANIM_WALK_WITH_GUN",
)

# Per-category interaction context for UI and in-game vignette placement.
INTERACTION_CONTEXT: dict[str, dict[str, Any]] = {
    "computer": {
        "vignetteLabel": "Console / desk",
        "propModels": [
            MODEL_DOORCONSOLE,
            MODEL_A51DESKENT,
            MODEL_LAB_CHAIR,
            MODEL_LAB_TABLE,
            MODEL_LAB_MAINFRAME,
            MODEL_CI_DESK,
        ],
        "animIds": COMPUTER_INTERACTION_IDS,
    },
    "combat": {
        "vignetteLabel": "Cover / combat",
        "propModels": [MODEL_A51_CRATE1, MODEL_A51_CRATE2],
        "animIds": COMBAT_INTERACTION_IDS,
    },
    "use": {
        "vignetteLabel": "Operate / use object",
        "propModels": [MODEL_LAB_TABLE, MODEL_DOORCONSOLE],
        "animIds": USE_INTERACTION_IDS,
    },
    "social": {
        "vignetteLabel": "Briefing / social",
        "propModels": [MODEL_CI_DESK, MODEL_LAB_CHAIR],
        "animIds": SOCIAL_INTERACTION_IDS,
    },
    "movement": {
        "vignetteLabel": "Movement path",
        "propModels": [MODEL_A51_CRATE1],
        "animIds": MOVEMENT_INTERACTION_IDS,
    },
    "react": {
        "vignetteLabel": "Reaction context",
        "propModels": [MODEL_A51_CRATE1],
        "animIds": (),
    },
    "death": {
        "vignetteLabel": "Death / fall",
        "propModels": [MODEL_A51_CRATE2],
        "animIds": (),
    },
    "weapon": {
        "vignetteLabel": "Weapon handling",
        "propModels": [MODEL_A51_CRATE1, MODEL_A51_CRATE2],
        "animIds": COMBAT_INTERACTION_IDS,
    },
    "other": {
        "vignetteLabel": "Misc context",
        "propModels": [MODEL_A51_CRATE1],
        "animIds": (),
    },
    "cutscene": {
        "vignetteLabel": "Cutscene staging",
        "propModels": [MODEL_LAB_TABLE],
        "animIds": (),
    },
    "idle": {
        "vignetteLabel": "Idle pose",
        "propModels": [],
        "animIds": (),
    },
}


def _model_hex(model: int) -> str:
    return f"0x{model:04X}"


def interaction_registry_payload() -> dict[str, Any]:
    """Category → props + anim ids for Anim Lab UI and docs."""
    out: dict[str, Any] = {}
    for cat, ctx in INTERACTION_CONTEXT.items():
        out[cat] = {
            "vignetteLabel": ctx["vignetteLabel"],
            "propModels": [_model_hex(m) for m in ctx["propModels"]],
            "animIds": list(ctx["animIds"]),
        }
    return out


def _dist_xz(ax: float, az: float, bx: float, bz: float) -> float:
    return math.hypot(ax - bx, az - bz)


def enrich_slots_with_interactions(
    slots: list[dict[str, Any]],
    props: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach interactionContext and nearest vignette/hub prop pads per slot."""
    props_by_district: dict[str, list[dict[str, Any]]] = {}
    for prop in props:
        kind = prop.get("kind", "hub")
        if kind not in ("hub", "vignette"):
            continue
        district = str(prop.get("district", "props"))
        props_by_district.setdefault(district, []).append(prop)

    enriched: list[dict[str, Any]] = []
    for slot in slots:
        district = str(slot.get("district") or slot.get("category") or "other")
        ctx = INTERACTION_CONTEXT.get(district, INTERACTION_CONTEXT["other"])
        candidates = props_by_district.get(district, []) + props_by_district.get("props", [])
        sx, sz = float(slot["x"]), float(slot["z"])
        ranked = sorted(
            candidates,
            key=lambda p: _dist_xz(sx, sz, float(p["x"]), float(p["z"])),
        )
        linked = [int(p["pad"]) for p in ranked[:3] if "pad" in p]
        enriched.append(
            {
                **slot,
                "interactionContext": ctx["vignetteLabel"],
                "interactionAnimIds": list(ctx["animIds"]),
                "linkedPropPads": linked,
            }
        )
    return enriched
