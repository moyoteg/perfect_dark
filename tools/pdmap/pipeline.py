"""Shared build pipeline: MapDef → binaries → validate → deploy."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from .core import (
    BUILD_DIR,
    MapDef,
    ROMID,
    ROOT,
    compile_pads,
    compile_tiles,
    load_level_module,
)
from .deploy import deploy_all, run_deploy
from .builders import ctf_zones_from_mapdef, hill_zone_center_from_mapdef
from .domain import (
    BuildOutcome,
    MapPipelineOutcome,
    PdmapFailureKind,
    PdmapLifecycleEvent,
    as_asset_name,
    bind_build_context,
    build_timeout_lifecycle_fields,
    classify_build_failure,
    classify_failure_recovery,
    current_build_run_id,
    current_build_scenario_id,
    current_pipeline_deploy_outcome,
    current_pipeline_validation_outcome,
    emit_lifecycle_event,
    make_build_outcome,
    make_map_pipeline_outcome,
    new_run_id,
    default_build_retry_policy,
    pdmap_build_retry_on_timeout_enabled,
    pdmap_build_timeout_seconds,
    PdmapRetryPolicy,
    record_pipeline_deploy_outcome,
    record_pipeline_validation_outcome,
    reset_build_context,
    reset_pipeline_stage_outcomes,
    restore_pipeline_stage_outcomes,
    retry_backoff_seconds,
    should_retry_build_timeout,
)
from .from_json import EditorMapSpec
from .pads_builder import write_pads_json
from .setup_packer import write_setup_binary
from .tiles import copy_tiles_from_template
from .validate import run_validation, validate_all, validate_mapdef


def _maybe_deploy(
    name: str,
    *,
    deploy: bool,
    run_id: str | None,
    mod_dirs: list[str] | None,
    deploy_kwargs: dict[str, object],
    verbose: bool,
) -> list[str]:
    """Deploy when requested; typed path when run_id is bound (Pass 3)."""
    if not deploy:
        return []

    if verbose:
        deploy_as = deploy_kwargs.get("deploy_as")
        if deploy_as and deploy_as != name:
            print(f"  Deploy-as: {name} → {deploy_as} (retail slot)")
        print("  Deploying...")

    if run_id:
        outcome = run_deploy(
            name,
            run_id=run_id,
            mod_dirs=mod_dirs,
            scenario_id=current_build_scenario_id(),
            verbose=verbose,
            **deploy_kwargs,  # type: ignore[arg-type]
        )
        record_pipeline_deploy_outcome(outcome)
        if not outcome.ok:
            return [outcome.error_message or "Deploy failed"]
        if verbose:
            print(f"  Deploy complete ({len(outcome.deployed_paths)} file(s))")
        return []

    deploy_all(name, mod_dirs, **deploy_kwargs)  # type: ignore[arg-type]
    if verbose:
        print("  Deploy complete")
    return []


def _write_pad_layout_log(name: str, mapdef: MapDef) -> str:
    """Dump pad positions + scenario intro anchors for post-deploy verification."""
    pad_log = os.path.join(BUILD_DIR, f"{name}_pads_layout.log")
    os.makedirs(BUILD_DIR, exist_ok=True)
    with open(pad_log, "w", encoding="utf-8") as fp:
        fp.write(f"# Pad layout for {name} ({len(mapdef.pads)} pads)\n")
        for p in mapdef.pads:
            fp.write(
                f"pad {p.index}: x={p.x:.0f} y={p.y:.0f} z={p.z:.0f} room={p.room}\n"
            )
        for cmd in mapdef.intro:
            if hasattr(cmd, "team") and hasattr(cmd, "pad"):
                fp.write(f"intro {type(cmd).__name__}: team={cmd.team} pad={cmd.pad}\n")
            elif hasattr(cmd, "pad"):
                fp.write(f"intro {type(cmd).__name__}: pad={cmd.pad}\n")
    return pad_log


def _resolve_seg_script(mod, name: str) -> str | None:
    if hasattr(mod, "SEG_SCRIPT"):
        return mod.SEG_SCRIPT
    if hasattr(mod, "seg_script"):
        return mod.seg_script()
    return None


def _build_box_seg_to_build_dir(
    name: str,
    *,
    half: float,
    height: float,
    hill_center: tuple[float, float] | None = None,
    ctf_zones: list[tuple[float, float, int, bool]] | None = None,
    parade_slots: list[dict] | None = None,
    parade_districts: list[dict] | None = None,
    parade_props_district: dict | None = None,
    parade_museum_district: dict | None = None,
    parade_true_scale_district: dict | None = None,
    parade_characters_district: dict | None = None,
    parade_special: dict | None = None,
    center_marker: bool = False,
    center_marker_half: float | None = None,
    cover_markers: list[tuple[float, float]] | None = None,
    pads: list | None = None,
    scale_factor: float = 1.0,
) -> str:
    from .seg import (
        validate_seg_g_vtx,
        write_box_seg,
        write_center_marker_box_seg,
        write_cover_markers_box_seg,
        write_ctf_box_seg,
        write_hill_box_seg,
        write_parade_box_seg,
        write_parade_districts_box_seg,
    )

    os.makedirs(BUILD_DIR, exist_ok=True)
    build_dst = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    if parade_districts is not None:
        write_parade_districts_box_seg(
            build_dst,
            half=half,
            height=height,
            districts=parade_districts,
            props_district=parade_props_district,
            museum_district=parade_museum_district,
            true_scale_district=parade_true_scale_district,
            characters_district=parade_characters_district,
            special=parade_special,
            pads=pads,
            scale_factor=scale_factor,
        )
    elif parade_slots:
        write_parade_box_seg(
            build_dst,
            half=half,
            height=height,
            slots=parade_slots,
        )
    elif ctf_zones:
        write_ctf_box_seg(
            build_dst,
            half=half,
            height=height,
            zones=ctf_zones,
        )
    elif hill_center is not None:
        write_hill_box_seg(
            build_dst,
            half=half,
            height=height,
            hill_center_x=hill_center[0],
            hill_center_z=hill_center[1],
        )
    elif center_marker:
        kwargs: dict = {"half": half, "height": height}
        if center_marker_half is not None:
            kwargs["marker_half"] = center_marker_half
        write_center_marker_box_seg(build_dst, **kwargs)
    elif cover_markers:
        kwargs = {"half": half, "height": height, "markers": cover_markers}
        if center_marker_half is not None:
            kwargs["marker_half"] = center_marker_half
        write_cover_markers_box_seg(build_dst, **kwargs)
    else:
        write_box_seg(build_dst, half=half, height=height)
    with open(build_dst, "rb") as seg_fp:
        errors = validate_seg_g_vtx(seg_fp.read())
    if errors:
        raise ValueError(
            "Box seg failed G_VTX validation:\n  " + "\n  ".join(errors)
        )
    return build_dst


def _build_seg_script_to_build_dir(name: str, script_path: str) -> str:
    import subprocess

    from .seg import validate_seg_g_vtx

    abs_script = script_path if os.path.isabs(script_path) else os.path.join(ROOT, script_path)
    if not os.path.exists(abs_script):
        raise FileNotFoundError(f"Seg script not found: {abs_script}")

    subprocess.run(
        [__import__("sys").executable, abs_script],
        cwd=ROOT,
        check=True,
        timeout=pdmap_build_timeout_seconds(),
    )

    script_dir = os.path.dirname(abs_script)
    generated = os.path.join(script_dir, f"bg_{name}.seg")
    if not os.path.exists(generated):
        raise FileNotFoundError(
            f"Seg script did not produce {generated}. "
            "Ensure the script writes bg_<name>.seg next to itself."
        )

    with open(generated, "rb") as seg_fp:
        errors = validate_seg_g_vtx(seg_fp.read())
    if errors:
        raise ValueError(
            "Seg script output failed G_VTX validation:\n  " + "\n  ".join(errors)
        )

    os.makedirs(BUILD_DIR, exist_ok=True)
    build_dst = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    import shutil

    shutil.copy2(generated, build_dst)
    return build_dst


def _post_build_validate(
    name: str,
    mapdef: MapDef,
    *,
    run_id: str | None = None,
    scenario_id: str | None = None,
    level_module: str | None = None,
) -> tuple[list[str], list[str]]:
    """Run post-build validation; typed path when run_id is bound (Pass 2)."""
    rid = run_id or current_build_run_id()
    if rid:
        outcome = run_validation(
            name,
            mapdef,
            run_id=rid,
            scenario_id=scenario_id or current_build_scenario_id(),
        )
        record_pipeline_validation_outcome(outcome)
        return list(outcome.errors), list(outcome.warnings)
    return validate_all(name, mapdef, level_module=level_module)


def run_build(
    name: str,
    *,
    run_id: str | None = None,
    scenario_id: str = "cli_build",
    deploy: bool = False,
    want_seg: bool = True,
    seg_script_path: str | None = None,
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
    recovery_attempted_on_timeout: bool = False,
) -> BuildOutcome:
    """Typed build entry point with structured lifecycle logging."""
    rid = run_id or new_run_id()
    asset = as_asset_name(name)
    t0 = time.perf_counter()

    def _latency_ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    base_fields = {
        "run_id": rid,
        "asset_name": str(asset),
        "operation": "build",
        "scenario_id": scenario_id,
    }
    emit_lifecycle_event(PdmapLifecycleEvent.BUILD_STARTED, **base_fields)

    run_token, scenario_token = bind_build_context(run_id=rid, scenario_id=scenario_id)
    try:
        try:
            if name.endswith(".json") or (os.path.exists(name) and name.lower().endswith(".json")):
                errors, warnings = build_from_json_file(
                    name,
                    deploy=deploy,
                    want_seg=want_seg,
                    mod_dirs=mod_dirs,
                    skip_validate=skip_validate,
                    verbose=verbose,
                    run_id=rid,
                )
            else:
                errors, warnings = build_from_module(
                    name,
                    deploy=deploy,
                    want_seg=want_seg,
                    seg_script_path=seg_script_path,
                    mod_dirs=mod_dirs,
                    skip_validate=skip_validate,
                    verbose=verbose,
                    run_id=rid,
                )
        except Exception as exc:
            kind = classify_build_failure(exc=exc)
            recovery = classify_failure_recovery(kind, exc=exc)
            fail_fields: dict[str, object] = {
                "outcome": "failed",
                "error_kind": kind.value,
                "recovery_class": recovery.value,
                "latency_ms": _latency_ms(),
                "error": str(exc),
                **base_fields,
            }
            fail_fields.update(
                build_timeout_lifecycle_fields(
                    exc=exc,
                    recovery_attempted=recovery_attempted_on_timeout,
                )
            )
            emit_lifecycle_event(PdmapLifecycleEvent.BUILD_FAILED, **fail_fields)
            return make_build_outcome(
                name,
                run_id=rid,
                ok=False,
                failure_kind=kind,
                errors=(str(exc),),
            )

        if errors:
            kind = classify_build_failure(errors=errors)
            recovery = classify_failure_recovery(
                kind,
                message=errors[0] if errors else "",
            )
            emit_lifecycle_event(
                PdmapLifecycleEvent.BUILD_FAILED,
                outcome="failed",
                error_kind=kind.value,
                recovery_class=recovery.value,
                latency_ms=_latency_ms(),
                error_count=len(errors),
                warning_count=len(warnings),
                **base_fields,
            )
            return make_build_outcome(
                name,
                run_id=rid,
                ok=False,
                failure_kind=kind,
                errors=errors,
                warnings=warnings,
            )

        emit_lifecycle_event(
            PdmapLifecycleEvent.BUILD_COMPLETED,
            outcome="ok",
            error_kind=PdmapFailureKind.NONE.value,
            latency_ms=_latency_ms(),
            warning_count=len(warnings),
            **base_fields,
        )
        return make_build_outcome(
            name,
            run_id=rid,
            ok=True,
            failure_kind=PdmapFailureKind.NONE,
            warnings=warnings,
        )
    finally:
        reset_build_context(run_token, scenario_token)


def _timeout_error_message(outcome: BuildOutcome) -> str:
    """First error line from a failed build outcome (for timeout detection)."""
    if outcome.errors:
        return outcome.errors[0]
    return ""


def run_build_with_retry(
    name: str,
    *,
    run_id: str | None = None,
    scenario_id: str = "cli_build",
    retry_policy: PdmapRetryPolicy | None = None,
    **kwargs: object,
) -> BuildOutcome:
    """Run build with optional single retry on transient timeout (Pass 15).

    When ``PDMAP_BUILD_RETRY_ON_TIMEOUT=1``, a timeout ``build_failed`` schedules
    one retry (two attempts total by default), emitting recovery lifecycle events.
    When the env flag is off, behavior matches ``run_build`` (single attempt).
    """
    rid = run_id or new_run_id()
    policy = retry_policy or default_build_retry_policy()
    retry_enabled = pdmap_build_retry_on_timeout_enabled()
    base_fields = {
        "run_id": rid,
        "asset_name": str(as_asset_name(name)),
        "operation": "build",
        "scenario_id": scenario_id,
    }

    attempt = 1
    while True:
        outcome = run_build(
            name,
            run_id=rid,
            scenario_id=scenario_id,
            recovery_attempted_on_timeout=attempt > 1,
            **kwargs,  # type: ignore[arg-type]
        )

        if outcome.ok:
            if retry_enabled and attempt > 1:
                emit_lifecycle_event(
                    PdmapLifecycleEvent.RECOVERY_SUCCEEDED,
                    outcome="ok",
                    attempt=attempt,
                    max_attempts=policy.max_attempts,
                    reason="timeout",
                    **base_fields,
                )
            return outcome

        if not retry_enabled:
            return outcome

        error_message = _timeout_error_message(outcome)
        if not should_retry_build_timeout(
            attempt=attempt,
            policy=policy,
            failure_kind=outcome.failure_kind,
            error_message=error_message,
        ):
            if attempt > 1:
                emit_lifecycle_event(
                    PdmapLifecycleEvent.RECOVERY_FAILED,
                    outcome="failed",
                    attempt=attempt,
                    max_attempts=policy.max_attempts,
                    reason="timeout",
                    error_kind=outcome.failure_kind.value,
                    **base_fields,
                )
            return outcome

        next_attempt = attempt + 1
        emit_lifecycle_event(
            PdmapLifecycleEvent.RETRY_SCHEDULED,
            attempt=attempt,
            next_attempt=next_attempt,
            max_attempts=policy.max_attempts,
            backoff_ms=policy.backoff_ms,
            reason="timeout",
            recovery_action="retry",
            **base_fields,
        )
        backoff = retry_backoff_seconds(attempt, policy)
        if backoff > 0:
            time.sleep(backoff)
        emit_lifecycle_event(
            PdmapLifecycleEvent.RECOVERY_ATTEMPTED,
            attempt=next_attempt,
            max_attempts=policy.max_attempts,
            reason="timeout",
            **base_fields,
        )
        attempt = next_attempt


def build_from_spec(
    spec: EditorMapSpec,
    *,
    deploy: bool = False,
    want_seg: bool = True,
    seg_mode: str | None = "empty",
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
    run_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """Build all assets from an ``EditorMapSpec``; validate before deploy."""
    name = spec.name
    mapdef = spec.mapdef
    warnings: list[str] = []

    if spec.y_corrected_pads:
        warnings.append(
            f"Auto-corrected pad Y to {spec.spawn_y} for pad(s) "
            f"{list(spec.y_corrected_pads)} (must be above floor Y=0)"
        )

    pre_errors = validate_mapdef(mapdef, tiles_room_count=spec.tiles_room_count())
    if pre_errors:
        return pre_errors, warnings

    hill_center = hill_zone_center_from_mapdef(mapdef)
    ctf_zones = ctf_zones_from_mapdef(mapdef)

    # Try to load level module to get seg_mode
    level_seg_mode = None
    if spec.level_module:
        try:
            from .core import load_level_module
            mod = load_level_module(spec.level_module)
            if mod:
                level_seg_mode = getattr(mod, "SEG_MODE", None)
        except Exception:
            pass

    if level_seg_mode:
        effective_seg_mode = str(level_seg_mode)
    elif getattr(mapdef, "anim_parade", False) or name == "parade" or name.startswith("parade_"):
        effective_seg_mode = "parade"
    elif name == "parade_districts":
        effective_seg_mode = "parade_districts"
    elif seg_mode and seg_mode != "empty":
        effective_seg_mode = seg_mode
    elif ctf_zones:
        effective_seg_mode = "ctf"
    elif hill_center:
        effective_seg_mode = "hill"
    elif spec.center_marker:
        effective_seg_mode = "marker"
    elif spec.cover_markers and mapdef.covers:
        effective_seg_mode = "marker"
    else:
        effective_seg_mode = "empty"

    if effective_seg_mode in ("parade", "parade_districts") or name in ("parade", "parade_districts") or name.startswith("parade_"):
        mapdef.anim_parade = True
    if name == "agent_office":
        mapdef.agent_office = True
    elif name == "agent_office_ci":
        mapdef.agent_office_ci = True
    elif name == "agent_office_lab":
        mapdef.agent_office_lab = True

    parade_slots = None
    parade_districts = None
    parade_props_district = None
    parade_museum_district = None
    parade_true_scale_district = None
    parade_characters_district = None
    parade_special = None

    if effective_seg_mode == "parade":
        from .anim_catalog import parade_slot_markers, parade_special_marker
        parade_slots = parade_slot_markers() + [parade_special_marker()]
    elif effective_seg_mode == "parade_districts":
        from .anim_catalog import parade_district_markers, parade_special_marker
        from .anim_props import (
            parade_museum_layout_payload,
            parade_props_layout_payload,
            parade_true_scale_layout_payload,
        )
        from .anim_characters import character_gallery_layout_payload

        parade_districts = parade_district_markers()
        parade_props_district = parade_props_layout_payload()
        parade_museum_district = parade_museum_layout_payload()
        parade_true_scale_district = parade_true_scale_layout_payload()
        parade_characters_district = character_gallery_layout_payload()
        parade_special = parade_special_marker()

    if want_seg:
        os.environ["PDMAP_SEG_MODE"] = effective_seg_mode
        if verbose:
            print(
                f"  Building box seg (half={spec.box_half:.0f} "
                f"height={spec.box_height:.0f}, mode={effective_seg_mode})"
            )
        _build_box_seg_to_build_dir(
            name,
            half=spec.box_half,
            height=spec.box_height,
            hill_center=hill_center,
            ctf_zones=ctf_zones or None,
            parade_slots=parade_slots,
            parade_districts=parade_districts,
            parade_props_district=parade_props_district,
            parade_museum_district=parade_museum_district,
            parade_true_scale_district=parade_true_scale_district,
            parade_characters_district=parade_characters_district,
            parade_special=parade_special,
            center_marker=spec.center_marker,
            center_marker_half=spec.center_marker_half,
            cover_markers=(
                [(c.x, c.z) for c in mapdef.covers]
                if spec.cover_markers and mapdef.covers
                else None
            ),
            pads=mapdef.pads,
            scale_factor=spec.scale_factor,
        )

    pads_json_path = write_pads_json(mapdef)
    if verbose:
        print(f"  Generated pads JSON: {pads_json_path}")
    compile_pads(name, pads_json_path)
    if verbose:
        print("  Compiled pads binary")
        print(f"  Pad layout log: {_write_pad_layout_log(name, mapdef)}")

    tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
    tiles_data = spec.tiles_json(seg_mode=effective_seg_mode if want_seg else None)
    os.makedirs(os.path.dirname(tiles_json_path), exist_ok=True)
    with open(tiles_json_path, "w", encoding="utf-8") as fp:
        json.dump(tiles_data, fp, indent=4)
    if verbose:
        print("  Generated tiles JSON from EditorMapSpec")

    compile_tiles(name, tiles_json_path)
    if verbose:
        print("  Compiled tiles binary")

    setup_path = write_setup_binary(mapdef, name)
    if verbose:
        print(f"  Wrote setup binary: {setup_path}")

    if skip_validate:
        deploy_errors = _maybe_deploy(
            name,
            deploy=deploy,
            run_id=run_id,
            mod_dirs=mod_dirs,
            deploy_kwargs={},
            verbose=verbose,
        )
        if deploy_errors:
            return deploy_errors, warnings
        return [], warnings

    errors, post_warnings = _post_build_validate(
        name, mapdef, run_id=run_id, level_module=spec.level_module
    )
    warnings.extend(post_warnings)
    if errors:
        return errors, warnings

    deploy_errors = _maybe_deploy(
        name,
        deploy=deploy,
        run_id=run_id,
        mod_dirs=mod_dirs,
        deploy_kwargs={},
        verbose=verbose,
    )
    if deploy_errors:
        return deploy_errors, warnings

    return [], warnings


def build_from_json_file(
    json_path: str,
    *,
    deploy: bool = False,
    want_seg: bool = True,
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
    run_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """Build all assets directly from a universal MapDef JSON file."""
    with open(json_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    mapdef = MapDef.from_json(data)
    name = mapdef.name
    warnings: list[str] = []

    if not skip_validate:
        pre_errors = validate_mapdef(mapdef)
        if pre_errors:
            return pre_errors, warnings

    # Geometry (Segment) Compiler
    box_half = data.get("box_half")
    box_height = data.get("box_height")
    skip_seg = data.get("skip_seg", False)

    if want_seg and not skip_seg:
        if box_half is not None and box_height is not None:
            effective_seg_mode = data.get("seg_mode", "empty")
            os.environ["PDMAP_SEG_MODE"] = effective_seg_mode
            if verbose:
                print(f"  Building box seg (half={float(box_half):.0f} height={float(box_height):.0f}, mode={effective_seg_mode})")
            _build_box_seg_to_build_dir(
                name,
                half=float(box_half),
                height=float(box_height),
                hill_center=hill_zone_center_from_mapdef(mapdef),
                ctf_zones=ctf_zones_from_mapdef(mapdef) or None,
                center_marker=bool(data.get("center_marker", False)),
                center_marker_half=float(data.get("center_marker_half", 200.0)),
            )
        else:
            seg_script_path = data.get("seg_script")
            if seg_script_path:
                if verbose:
                    print(f"  Building seg via {seg_script_path}")
                _build_seg_script_to_build_dir(name, seg_script_path)

    # Pads Compiler
    pads_json_path = write_pads_json(mapdef)
    if verbose:
        print(f"  Generated pads JSON: {pads_json_path}")
    compile_pads(name, pads_json_path)
    if verbose:
        print("  Compiled pads binary")
        print(f"  Pad layout log: {_write_pad_layout_log(name, mapdef)}")

    # Tiles Compiler
    skip_tiles = data.get("skip_tiles", False)
    if not skip_tiles:
        tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
        custom_tiles = data.get("tiles")
        if custom_tiles:
            if isinstance(custom_tiles, dict) and "obj_file" in custom_tiles:
                obj_file_path = os.path.join(ROOT, custom_tiles["obj_file"])
                default_ft = custom_tiles.get("default_floortype", "default")
                from .tiles import import_obj_to_tiles
                tiles_content = import_obj_to_tiles(obj_file_path, name, default_floortype=default_ft)
            else:
                tiles_content = custom_tiles

            os.makedirs(os.path.dirname(tiles_json_path), exist_ok=True)
            with open(tiles_json_path, "w", encoding="utf-8") as fp:
                json.dump(tiles_content, fp, indent=4)
            if verbose:
                print("  Generated tiles JSON from custom JSON / OBJ file")
        else:
            template = data.get("tiles_template", "mp14")
            tiles_json_path = copy_tiles_from_template(name, template)
            if verbose:
                print(f"  Copied tiles JSON from template ({template})")

        compile_tiles(name, tiles_json_path)
        if verbose:
            print("  Compiled tiles binary")

    # Setup Compiler
    setup_path = write_setup_binary(mapdef, name)
    if verbose:
        print(f"  Wrote setup binary: {setup_path}")

    # Validation & Deploy
    if not skip_validate:
        errors, post_warnings = _post_build_validate(name, mapdef, run_id=run_id)
        warnings.extend(post_warnings)
        if errors:
            return errors, warnings

    deploy_errors = _maybe_deploy(
        name,
        deploy=deploy,
        run_id=run_id,
        mod_dirs=mod_dirs,
        deploy_kwargs={},
        verbose=verbose,
    )
    if deploy_errors:
        return deploy_errors, warnings

    return [], warnings


def build_from_module(
    name: str,
    *,
    deploy: bool = False,
    want_seg: bool = True,
    seg_script_path: str | None = None,
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
    run_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """Build from ``src/levels/<name>.py`` (legacy / hand-authored levels)."""
    mod = load_level_module(name)
    mapdef = mod.build()
    deploy_as = getattr(mod, "DEPLOY_AS", None)
    skip_tiles = bool(getattr(mod, "SKIP_TILES", False))
    skip_seg = bool(getattr(mod, "SKIP_SEG", False))
    skip_pads = bool(getattr(mod, "SKIP_PADS", False))
    seg_script = seg_script_path or _resolve_seg_script(mod, name)
    has_box_dims = hasattr(mod, "BOX_HALF") and hasattr(mod, "BOX_HEIGHT")
    do_seg = (want_seg or bool(seg_script) or has_box_dims) and not skip_seg

    if do_seg:
        hill_center = hill_zone_center_from_mapdef(mapdef)
        ctf_zones = ctf_zones_from_mapdef(mapdef)
        seg_mode = getattr(mod, "SEG_MODE", None)
        if seg_mode:
            effective_seg_mode = str(seg_mode)
        elif getattr(mapdef, "anim_parade", False):
            effective_seg_mode = "parade"
        elif ctf_zones:
            effective_seg_mode = "ctf"
        elif hill_center:
            effective_seg_mode = "hill"
        elif getattr(mod, "CENTER_MARKER", False) or seg_mode == "marker":
            effective_seg_mode = "marker"
        elif has_box_dims:
            effective_seg_mode = "empty"
        else:
            effective_seg_mode = "empty"
        os.environ["PDMAP_SEG_MODE"] = effective_seg_mode
        parade_slots = None
        parade_districts = None
        parade_props_district = None
        parade_museum_district = None
        parade_true_scale_district = None
        parade_characters_district = None
        parade_special = None
        if effective_seg_mode == "parade":
            from .anim_catalog import parade_slot_markers, parade_special_marker

            parade_slots = parade_slot_markers() + [parade_special_marker()]
        elif effective_seg_mode == "parade_districts":
            from .anim_catalog import parade_district_markers, parade_special_marker
            from .anim_props import (
                parade_museum_layout_payload,
                parade_props_layout_payload,
                parade_true_scale_layout_payload,
                parade_vignette_layout_payload,
            )
            from .anim_characters import character_gallery_layout_payload

            parade_districts = parade_district_markers()
            parade_props_district = parade_props_layout_payload()
            parade_museum_district = parade_museum_layout_payload()
            parade_true_scale_district = parade_true_scale_layout_payload()
            parade_characters_district = character_gallery_layout_payload()
            parade_special = parade_special_marker()
        if seg_script:
            if verbose:
                print(f"  Building seg via {seg_script}")
            _build_seg_script_to_build_dir(name, seg_script)
        else:
            if hasattr(mod, "load_spec"):
                try:
                    spec = mod.load_spec()
                    half = spec.box_half
                except Exception:
                    half = float(getattr(mod, "BOX_HALF", 5000.0))
            else:
                half = float(getattr(mod, "BOX_HALF", 5000.0))
            height = float(getattr(mod, "BOX_HEIGHT", 3000.0))
            if verbose:
                print(
                    f"  Building box seg (half={half:.0f} height={height:.0f}, "
                    f"mode={effective_seg_mode})"
                )
            _build_box_seg_to_build_dir(
                name,
                half=half,
                height=height,
                hill_center=hill_center,
                ctf_zones=ctf_zones or None,
                parade_slots=parade_slots,
                parade_districts=parade_districts,
                parade_props_district=parade_props_district,
                parade_museum_district=parade_museum_district,
                parade_true_scale_district=parade_true_scale_district,
                parade_characters_district=parade_characters_district,
                parade_special=parade_special,
                pads=mapdef.pads,
                center_marker=(
                    getattr(mod, "CENTER_MARKER", False)
                    or (
                        effective_seg_mode == "marker"
                        and not mapdef.covers
                    )
                ),
                center_marker_half=getattr(mod, "CENTER_MARKER_HALF", None),
                cover_markers=(
                    [(c.x, c.z) for c in mapdef.covers]
                    if mapdef.covers
                    and (
                        getattr(mod, "COVER_MARKERS", False)
                        or effective_seg_mode == "marker"
                    )
                    else None
                ),
                scale_factor=getattr(mapdef, "scale_factor", 1.0),
            )
    elif deploy and verbose and skip_seg:
        print("  SKIP_SEG: retail seg/tiles left in ROM (deploy pads + setup only)")
    elif deploy and verbose:
        print(
            "  WARNING: seg build skipped; deploy will copy existing BUILD_DIR seg "
            "(must pass G_VTX validation)"
        )

    if skip_pads:
        if verbose:
            print("  SKIP_PADS: keeping mod_kakariko Conker-corrected bg_mp13_padsZ")
    else:
        pads_json_path = write_pads_json(mapdef)
        if verbose:
            print(f"  Generated pads JSON: {pads_json_path}")
        compile_pads(name, pads_json_path)
        if verbose:
            print("  Compiled pads binary")
            print(f"  Pad layout log: {_write_pad_layout_log(name, mapdef)}")

    if skip_tiles:
        if verbose:
            retail = getattr(mod, "RETAIL_TILES", "mp13")
            print(f"  SKIP_TILES: using retail {retail} collision from ROM/mod")
    else:
        tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
        if hasattr(mod, "build_tiles_json"):
            tiles_data = mod.build_tiles_json()
            os.makedirs(os.path.dirname(tiles_json_path), exist_ok=True)
            with open(tiles_json_path, "w", encoding="utf-8") as fp:
                json.dump(tiles_data, fp, indent=4)
            if verbose:
                print("  Generated tiles JSON from build_tiles_json()")
        elif os.path.exists(tiles_json_path):
            if verbose:
                print(f"  Using existing tiles JSON: {tiles_json_path}")
        else:
            template = getattr(mapdef, "tiles_template", "mp14")
            tiles_json_path = copy_tiles_from_template(name, template)
            if verbose:
                print(f"  Copied tiles JSON from template ({template})")

        compile_tiles(name, tiles_json_path)
        if verbose:
            print("  Compiled tiles binary")

    setup_path = write_setup_binary(mapdef, name)
    if verbose:
        print(f"  Wrote setup binary: {setup_path}")

    deploy_kwargs = dict(
        deploy_as=deploy_as,
        include_tiles=not skip_tiles,
        include_seg=not skip_seg,
        include_pads=not skip_pads,
    )

    if skip_validate:
        deploy_errors = _maybe_deploy(
            name,
            deploy=deploy,
            run_id=run_id,
            mod_dirs=mod_dirs,
            deploy_kwargs=deploy_kwargs,
            verbose=verbose,
        )
        if deploy_errors:
            return deploy_errors, []
        return [], []

    errors, warnings = _post_build_validate(name, mapdef, run_id=run_id)
    if errors:
        return errors, warnings

    deploy_errors = _maybe_deploy(
        name,
        deploy=deploy,
        run_id=run_id,
        mod_dirs=mod_dirs,
        deploy_kwargs=deploy_kwargs,
        verbose=verbose,
    )
    if deploy_errors:
        return deploy_errors, warnings

    return [], warnings


def run_map_pipeline(
    name: str,
    *,
    deploy: bool = False,
    seg: bool = True,
    run_id: str | None = None,
    scenario_id: str = "pipeline_map",
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
) -> MapPipelineOutcome:
    """Unified typed entry: build → validate → optional deploy with lifecycle logs.

    Curriculum and tooling call this instead of bare ``build_from_module`` when
    ``run_id`` should propagate through build, validation, and deploy events.
    Returns a composite ``MapPipelineOutcome`` with optional stage outcomes.
    """
    rid = run_id or new_run_id()
    val_token, dep_token = reset_pipeline_stage_outcomes()
    try:
        build_outcome = run_build(
            name,
            run_id=rid,
            scenario_id=scenario_id,
            deploy=deploy,
            want_seg=seg,
            mod_dirs=mod_dirs,
            skip_validate=skip_validate,
            verbose=verbose,
        )
        return make_map_pipeline_outcome(
            name,
            run_id=rid,
            build=build_outcome,
            validation=current_pipeline_validation_outcome(),
            deploy=current_pipeline_deploy_outcome(),
        )
    finally:
        restore_pipeline_stage_outcomes(val_token, dep_token)
