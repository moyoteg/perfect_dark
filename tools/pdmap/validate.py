from __future__ import annotations

import os
import json
from typing import Optional

from .core import MapDef, load_level_module, ROOT, ROMID, BUILD_DIR
from .domain import (
    DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX,
    PdmapFailureKind,
    PdmapLifecycleEvent,
    ValidationOutcome,
    as_asset_name,
    emit_limit_reached_events,
    emit_legacy_silent_path_selected,
    emit_lifecycle_event,
    failure_lifecycle_fields,
    make_validation_outcome,
    new_run_id,
)
from .seg import validate_seg_g_vtx
from .intro import Spawn, Case, CaseRespawn, Hill


def validate_mapdef(
    mapdef: MapDef,
    *,
    tiles_room_count: int | None = None,
    allow_negative_y: bool = False,
    skip_pad_spawn_limit: bool = False,
) -> list[str]:
    """Logical checks on a MapDef before compiling assets (no binary I/O)."""
    errors: list[str] = []
    pad_indices = {p.index for p in mapdef.pads}
    anim_parade = bool(getattr(mapdef, "anim_parade", False))

    # Retail overlay maps (SKIP_PADS) keep ROM pad binaries — MapDef pads are reference
    # only and may exceed MAX_SPAWN_POINTS; setup props reference retail pad indices.
    if not anim_parade and not skip_pad_spawn_limit:
        if len(mapdef.pads) > DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX:
            errors.append(
                f"Map has {len(mapdef.pads)} pads (max {DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX} "
                f"per MAX_SPAWN_POINTS in src/include/constants.h)"
            )
        for p in mapdef.pads:
            if p.index >= DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX:
                errors.append(
                    f"Pad {p.index} exceeds MAX_SPAWN_POINTS ceiling "
                    f"({DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX} — valid indices 0.."
                    f"{DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX - 1})"
                )
    elif len(mapdef.pads) > DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX:
        pass  # Warning emitted by _collect_validation_messages for anim_parade / SKIP_PADS.

    for position, p in enumerate(mapdef.pads):
        if p.index != position:
            errors.append(
                f"Pad at position {position} has index {p.index}; pad indices "
                f"must be contiguous from 0 (the asset compiler numbers pads by "
                f"array position and props/intro reference them by position)"
            )

    for p in mapdef.pads:
        # room=-1 matches retail pads (setupPreparePads auto-binds floor room).
        if p.room < -1:
            errors.append(f"Pad {p.index}: invalid room {p.room}")
        if not allow_negative_y and not anim_parade and p.y <= 0.0:
            errors.append(
                f"Pad {p.index}: Y={p.y} is at/below the floor; the ground "
                f"search will reject the floor and the player will fall through "
                f"(use a small positive Y such as 10)"
            )
        if tiles_room_count is not None and p.room >= tiles_room_count:
            errors.append(
                f"Pad {p.index} spawns in room {p.room} but tiles have "
                f"{tiles_room_count} rooms"
            )

    has_spawn = any(isinstance(cmd, Spawn) for cmd in mapdef.intro)
    if not has_spawn:
        errors.append("Intro has no Spawn commands — Combat Simulator cannot place players")

    for i, cmd in enumerate(mapdef.intro):
        from .intro import INTRO_CODE_MAP
        code = getattr(cmd, "code", None)
        if code is not None and code not in INTRO_CODE_MAP and code != 0xFF:
            errors.append(f"Intro[{i}]: unknown command code {code:#x}")
        if isinstance(cmd, Spawn) and cmd.pad not in pad_indices:
            errors.append(f"Intro Spawn references missing pad {cmd.pad}")
        if isinstance(cmd, (Case, CaseRespawn, Hill)) and cmd.pad not in pad_indices:
            errors.append(
                f"Intro {type(cmd).__name__} references missing pad {cmd.pad}"
            )

    # CTF: each team with a Case pad needs at least one CaseRespawn for that team.
    case_teams = {cmd.team for cmd in mapdef.intro if isinstance(cmd, Case)}
    respawn_teams = {cmd.team for cmd in mapdef.intro if isinstance(cmd, CaseRespawn)}
    for team in sorted(case_teams):
        if team not in respawn_teams:
            errors.append(
                f"CTF team {team} has Case pad(s) but no case_respawn pad "
                f"(add scenario pads with scenario='case_respawn' and matching team)"
            )

    for i, prop in enumerate(mapdef.props):
        try:
            data = prop.pack()
            if len(data) == 0:
                errors.append(f"Prop[{i}] packed to zero bytes")
        except Exception as e:
            errors.append(f"Prop[{i}] pack failed: {e}")

    from .retail_door_siblings import validate_packed_door_siblings
    errors.extend(validate_packed_door_siblings(mapdef.props, label=mapdef.name))

    # General sibling door check: verify that reciprocating sibling doors use different pads
    door_cmds = [idx for idx, p in enumerate(mapdef.props) if type(p).__name__ == "Door"]
    for cmd_idx in door_cmds:
        door = mapdef.props[cmd_idx]
        offset = door.sibling
        if offset != 0:
            target = cmd_idx + offset
            if 0 <= target < len(mapdef.props) and type(mapdef.props[target]).__name__ == "Door":
                sibling_door = mapdef.props[target]
                if door.pad == sibling_door.pad:
                    errors.append(
                        f"{mapdef.name}: door cmd {cmd_idx} (pad index {door.pad}) and "
                        f"sibling door cmd {target} (pad index {sibling_door.pad}) use the same pad!"
                    )

    errors.extend(validate_mapdef_props(mapdef))
    errors.extend(validate_mapdef_waypoints(mapdef))
    return errors


def _collect_validation_messages(
    name: str,
    mapdef: Optional[MapDef] = None,
    level_module: Optional[str] = None,
) -> tuple[list[str], list[str], Optional[MapDef]]:
    """Run all validation checks; returns (errors, warnings, mapdef used)."""
    errors: list[str] = []
    warnings: list[str] = []
    mod = None

    target_name = level_module or name

    if mapdef is None:
        try:
            mod = load_level_module(target_name)
            mapdef = mod.build()
        except Exception as e:
            errors.append(f"Cannot load level module: {e}")
            return errors, warnings, None
    else:
        try:
            mod = load_level_module(target_name)
        except Exception:
            mod = None

    allow_negative_y = bool(getattr(mod, "RETAIL_GEOMETRY", False)) if mod else False
    skip_tiles = bool(getattr(mod, "SKIP_TILES", False)) if mod else False
    skip_pads = bool(getattr(mod, "SKIP_PADS", False)) if mod else False
    retail_tiles = getattr(mod, "RETAIL_TILES", None) if mod else None

    errors.extend(
        validate_mapdef(
            mapdef,
            allow_negative_y=allow_negative_y,
            skip_pad_spawn_limit=skip_pads,
        )
    )

    if getattr(mapdef, "anim_parade", False) and len(mapdef.pads) > DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX:
        warnings.append(
            f"Anim parade map has {len(mapdef.pads)} pads (retail MAX_SPAWN_POINTS="
            f"{DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX}); STAGE_ANIMLAB uses extended pad table"
        )
    elif skip_pads and len(mapdef.pads) > DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX:
        warnings.append(
            f"Retail overlay map has {len(mapdef.pads)} reference pads (SKIP_PADS — "
            f"ROM pad binary unchanged; MAX_SPAWN_POINTS={DOMAIN_LIMIT_SPAWN_PAD_COUNT_MAX} "
            f"applies only to compiled pad assets)"
        )

    for p in mapdef.pads:
        if p.y > 200.0:
            warnings.append(
                f"Pad {p.index}: Y={p.y} is far above the floor; spawns may take fall damage"
            )

    has_spawn = any(isinstance(cmd, Spawn) for cmd in mapdef.intro)
    if has_spawn and not any(isinstance(cmd, Case) for cmd in mapdef.intro):
        warnings.append("Intro has no Case commands — Capture the Case scenario will not work")
    if has_spawn and not any(isinstance(cmd, Hill) for cmd in mapdef.intro):
        warnings.append("Intro has no Hill commands — King of the Hill scenario will not work")

    if mapdef.intro:
        first = mapdef.intro[0]
        if not isinstance(first, Spawn):
            warnings.append(
                f"First intro command should be Spawn, got {type(first).__name__}"
            )

    tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
    if skip_tiles and retail_tiles:
        tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{retail_tiles}.json")
    if not skip_tiles and os.path.exists(tiles_json_path):
        with open(tiles_json_path) as f:
            tiles_data = json.load(f)
        room_names = list(tiles_data.get("rooms", {}).keys())
        for p in mapdef.pads:
            if p.room >= len(room_names):
                errors.append(
                    f"Pad {p.index} spawns in room {p.room} but tiles have "
                    f"{len(room_names)} rooms"
                )
    elif skip_tiles:
        warnings.append(
            "SKIP_TILES: tile room validation skipped (retail collision from ROM/mod)"
        )

    skip_seg = bool(getattr(mod, "SKIP_SEG", False)) if mod else False
    seg_path = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    if skip_seg:
        warnings.append("SKIP_SEG: seg validation skipped (retail geometry from ROM/mod)")
    elif not os.path.exists(seg_path):
        warnings.append(f"Seg not built at {seg_path} — run build with --seg if needed")
    else:
        with open(seg_path, "rb") as seg_fp:
            for msg in validate_seg_g_vtx(seg_fp.read()):
                errors.append(f"Seg G_VTX: {msg}")

    setup_path = os.path.join(ROOT, "build", ROMID, f"Ump_setup{name}Z")
    if not os.path.exists(setup_path):
        warnings.append(f"Setup binary missing at {setup_path}")

    if name == "parade":
        try:
            from .animlab_validation import run_animlab_validation

            report = run_animlab_validation(scenario_id="pdmap_validate_animlab", name="parade")
            errors.extend(report.collision_errors)
            warnings.extend(report.walk_warnings)
            if report.y4_tile_count_room1 != 99:
                errors.append(
                    f"parade: room-1 has {report.y4_tile_count_room1} Y=4 overlay tiles "
                    f"(expected 99 — raised carpets with white frames)"
                )
            if not report.passed:
                errors.append(
                    f"parade: {report.scenario_id} baseline failed — "
                    + ", ".join(report.evidence_lines)
                )
            else:
                warnings.append(
                    f"parade: {report.scenario_id} PASS "
                    f"(collision=0 walk=0 chars={report.character_count} "
                    f"islands={report.level_island_count})"
                )
        except Exception as exc:
            errors.append(f"animlab validation failed: {exc}")

    if name in ("agent_office", "agent_office_ci"):
        try:
            from .retail_door_siblings import validate_packed_door_siblings

            if name == "agent_office":
                from .agent_office import (
                    agent_chr_props,
                    agent_office_meeting_terminal_props,
                    agent_office_std_props,
                )
                from .depo_retail_doors import agent_office_depo_doors
                from .depo_retail_office_props import agent_office_depo_office_props

                props = (
                    list(mapdef.props)
                    + agent_office_depo_doors()
                    + agent_office_depo_office_props()
                    + agent_office_meeting_terminal_props()
                    + agent_office_std_props()
                    + agent_chr_props()
                )
            else:
                from .agent_office_ci import (
                    agent_ci_chr_props,
                    agent_office_ci_std_props,
                )
                from .ci_retail_doors import agent_office_ci_doors
                from .ci_retail_lifts import agent_office_ci_lifts
                from .ci_retail_office_props import agent_office_ci_office_props

                props = (
                    list(mapdef.props)
                    + agent_office_ci_doors()
                    + agent_office_ci_lifts()
                    + agent_office_ci_office_props()
                    + agent_office_ci_std_props()
                    + agent_ci_chr_props()
                )
            errors.extend(validate_packed_door_siblings(props, label=name))
        except Exception as exc:
            errors.append(f"{name} door sibling validation failed: {exc}")

    return errors, warnings, mapdef


def run_validation(
    name: str,
    mapdef: Optional[MapDef] = None,
    *,
    run_id: str | None = None,
    scenario_id: str = "cli_validate",
) -> ValidationOutcome:
    """Typed validation entry point with structured lifecycle logging."""
    asset = as_asset_name(name)
    rid = run_id or new_run_id()
    emit_lifecycle_event(
        PdmapLifecycleEvent.VALIDATION_STARTED,
        run_id=rid,
        asset_name=str(asset),
        operation="validate",
        scenario_id=scenario_id,
    )

    errors, warnings, _ = _collect_validation_messages(name, mapdef)
    outcome = make_validation_outcome(name, errors, warnings, run_id=rid)

    base_fields = {
        "run_id": rid,
        "asset_name": str(asset),
        "operation": "validate",
        "scenario_id": scenario_id,
        "error_count": len(outcome.errors),
        "warning_count": len(outcome.warnings),
        "rule_codes": [code.value for code in outcome.rule_codes],
    }
    if outcome.ok:
        emit_lifecycle_event(
            PdmapLifecycleEvent.VALIDATION_COMPLETED,
            outcome="ok",
            error_kind=PdmapFailureKind.NONE.value,
            recovery_class=PdmapFailureKind.NONE.value,
            **base_fields,
        )
    else:
        recovery_fields = failure_lifecycle_fields(
            outcome.failure_kind,
            message=outcome.errors[0] if outcome.errors else "",
        )
        emit_lifecycle_event(
            PdmapLifecycleEvent.VALIDATION_FAILED,
            outcome="failed",
            **base_fields,
            **recovery_fields,
        )
        emit_limit_reached_events(
            outcome.limits_reached,
            run_id=rid,
            asset_name=str(asset),
            operation="validate",
            scenario_id=scenario_id,
            failure_kind=outcome.failure_kind,
            message=outcome.errors[0] if outcome.errors else "",
            errors=outcome.errors,
        )

    return outcome


def validate_all(
    name: str,
    mapdef: Optional[MapDef] = None,
    level_module: Optional[str] = None,
) -> tuple[list[str], list[str]]:
    """Legacy tuple return; emits lifecycle_path_selected marker (no full validation lifecycle)."""
    emit_legacy_silent_path_selected("validate", asset_name=name)
    errors, warnings, _ = _collect_validation_messages(
        name, mapdef, level_module=level_module
    )
    return errors, warnings


def validate_mapdef_props(mapdef: MapDef) -> list[str]:
    errors = []
    pad_indices = {p.index for p in mapdef.pads}
    props_len = len(mapdef.props)

    for i, prop in enumerate(mapdef.props):
        cls_name = type(prop).__name__

        # Validate GenericObject parameters
        if hasattr(prop, "scale") and prop.scale <= 0:
            errors.append(f"Prop[{i}] ({cls_name}): invalid scale {prop.scale} (must be > 0)")
        if hasattr(prop, "model") and prop.model < 0:
            errors.append(f"Prop[{i}] ({cls_name}): invalid model ID {prop.model}")
        if hasattr(prop, "pad") and prop.pad != 0:
            if prop.pad not in pad_indices:
                errors.append(f"Prop[{i}] ({cls_name}) references non-existent pad {prop.pad}")

        # Class-specific checks
        if cls_name == "Door":
            if prop.accel < 0 or prop.decel < 0:
                errors.append(f"Prop[{i}] (Door): accel/decel must be non-negative (got accel={prop.accel}, decel={prop.decel})")
            if prop.maxspeed < 0:
                errors.append(f"Prop[{i}] (Door): maxspeed must be non-negative (got {prop.maxspeed})")
            if prop.autoclosetime < 0:
                errors.append(f"Prop[{i}] (Door): autoclosetime must be non-negative (got {prop.autoclosetime})")

        elif cls_name == "Lift":
            stop_pads = [prop.pad1, prop.pad2, prop.pad3, prop.pad4]
            for idx, p_idx in enumerate(stop_pads):
                if p_idx not in pad_indices and p_idx not in (0xffff, -1):
                    errors.append(f"Prop[{i}] (Lift): stop pad {idx+1} references non-existent pad {p_idx}")
            lift_doors = [prop.door1, prop.door2, prop.door3, prop.door4]
            for idx, d_offset in enumerate(lift_doors):
                if d_offset not in (-1, 0xffffffff):
                    # signed conversion for check
                    signed_offset = d_offset if d_offset < 0x80000000 else d_offset - 0x100000000
                    target_idx = i + signed_offset
                    if target_idx < 0 or target_idx >= props_len or type(mapdef.props[target_idx]).__name__ != "Door":
                        errors.append(f"Prop[{i}] (Lift): door linkage {idx+1} offset {signed_offset:+d} does not point to a Door prop")

        elif cls_name == "Weapon":
            if prop.weapon < 0:
                errors.append(f"Prop[{i}] (Weapon): invalid weapon ID {prop.weapon}")

        elif cls_name == "AmmoCrate":
            if prop.ammotype < 0:
                errors.append(f"Prop[{i}] (AmmoCrate): invalid ammo type ID {prop.ammotype}")

        elif cls_name == "Tag":
            if prop.id < 0:
                errors.append(f"Prop[{i}] (Tag): invalid tag ID {prop.id}")

    return errors


def validate_mapdef_waypoints(mapdef: MapDef) -> list[str]:
    errors = []
    pad_indices = {p.index for p in mapdef.pads}
    pads_dict = {p.index: p for p in mapdef.pads}

    adjacency = {p.index: set() for p in mapdef.pads}
    if getattr(mapdef, "custom_waypoints", None):
        for item in mapdef.custom_waypoints:
            pad_idx = item["pad"]
            if pad_idx not in pad_indices:
                errors.append(f"Waypoint references non-existent pad index {pad_idx}")
                continue
            for n_idx in item.get("neighbours", []):
                if n_idx not in pad_indices:
                    errors.append(f"Waypoint {pad_idx} neighbour references non-existent pad index {n_idx}")
                    continue
                adjacency[pad_idx].add(n_idx)
    else:
        K_NEAREST = 6
        for p1 in mapdef.pads:
            distances = []
            for p2 in mapdef.pads:
                if p1 != p2:
                    dist = ((p2.x - p1.x) ** 2 + (p2.z - p1.z) ** 2) ** 0.5
                    distances.append((dist, p2.index))
            distances.sort()
            for _dist, j in distances[:K_NEAREST]:
                # Add edge in both directions to keep the graph symmetric
                adjacency[p1.index].add(j)
                adjacency[j].add(p1.index)

    # 1. Audit Symmetry
    for p_idx, neighbors in adjacency.items():
        for n_idx in neighbors:
            if p_idx not in adjacency[n_idx]:
                errors.append(
                    f"Waypoint connectivity asymmetry: pad {p_idx} has neighbor {n_idx}, "
                    f"but pad {n_idx} does not have neighbor {p_idx}. This will cause game crashes."
                )

    return errors
