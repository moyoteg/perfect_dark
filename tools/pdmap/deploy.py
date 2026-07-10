from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from .core import BUILD_DIR, MOD_DIRS, ROOT, SETUP_DIR
from .domain import (
    DeployOutcome,
    PdmapFailureKind,
    PdmapLifecycleEvent,
    as_asset_name,
    classify_deploy_failure,
    classify_failure_recovery,
    current_build_run_id,
    current_build_scenario_id,
    emit_legacy_silent_path_selected,
    emit_lifecycle_event,
    make_deploy_outcome,
    new_run_id,
    pdmap_build_timeout_seconds,
)
from .seg import validate_seg_g_vtx


def _validate_seg_before_deploy(seg_path: str) -> None:
    """Reject stale/corrupt segs that would reintroduce phantom collision walls."""
    with open(seg_path, "rb") as seg_fp:
        errors = validate_seg_g_vtx(seg_fp.read())
    if errors:
        raise ValueError(
            f"Refusing to deploy corrupt seg {seg_path}:\n  "
            + "\n  ".join(errors)
            + "\n  Rebuild with: python3 tools/pdmap.py build <name> --seg --deploy"
        )


def _bgdata_asset_names(
    asset_name: str,
    *,
    include_tiles: bool,
    include_pads: bool,
    include_seg: bool,
) -> list[str]:
    assets: list[str] = []
    if include_tiles:
        assets.append(f"bg_{asset_name}_tilesZ")
    if include_pads:
        assets.append(f"bg_{asset_name}_padsZ")
    if include_seg:
        assets.append(f"bg_{asset_name}.seg")
    return assets


def _deploy_bgdata_assets(
    name: str,
    mod_dirs: list[str],
    *,
    deploy_as: str | None = None,
    include_tiles: bool = True,
    include_seg: bool = True,
    include_pads: bool = True,
    verbose: bool = False,
    fail_on_missing: bool = False,
) -> list[str]:
    """Copy bgdata assets to mod dirs; return destination paths deployed."""
    asset_name = deploy_as or name
    deployed: list[str] = []
    missing: list[str] = []

    for mod_dir in mod_dirs:
        os.makedirs(mod_dir, exist_ok=True)
        for asset in _bgdata_asset_names(
            asset_name,
            include_tiles=include_tiles,
            include_pads=include_pads,
            include_seg=include_seg,
        ):
            built = asset.replace(asset_name, name, 1) if asset_name != name else asset
            src = os.path.join(BUILD_DIR, built)
            dst = os.path.join(mod_dir, asset)
            if os.path.exists(src):
                if asset.endswith(".seg"):
                    _validate_seg_before_deploy(src)
                shutil.copy2(src, dst)
                deployed.append(dst)
                if verbose:
                    print(f"  Deployed {asset} -> {dst}")
            elif fail_on_missing:
                missing.append(src)
            elif verbose:
                print(f"  WARNING: {src} not found, skipping")

    if missing:
        raise FileNotFoundError(
            "Missing build artifact(s) in BUILD_DIR: " + ", ".join(missing)
        )

    return deployed


def _deploy_setup_assets(
    name: str,
    mod_dirs: list[str],
    *,
    deploy_as: str | None = None,
    verbose: bool = False,
) -> list[str]:
    """Copy setup binary to mod files directories; return destination paths."""
    asset_name = deploy_as or name
    setup_path = os.path.join(SETUP_DIR, f"Ump_setup{name}Z")
    deployed: list[str] = []

    if not os.path.exists(setup_path):
        if verbose:
            print(f"  WARNING: Setup not found at {setup_path}")
        return deployed

    for mod_dir in mod_dirs:
        files_dir = os.path.dirname(mod_dir)
        os.makedirs(files_dir, exist_ok=True)
        dst = os.path.join(files_dir, f"Ump_setup{asset_name}Z")
        shutil.copy2(setup_path, dst)
        deployed.append(dst)
        if verbose:
            print(f"  Deployed setup -> {dst}")
        if True:
            usetup_dst = os.path.join(files_dir, f"Usetup{asset_name}Z")
            shutil.copy2(setup_path, usetup_dst)
            deployed.append(usetup_dst)
            if verbose:
                print(f"  Deployed setup -> {usetup_dst}")

    return deployed


def deploy(name: str, mod_dirs: list[str] | None = None, *, deploy_as: str | None = None):
    """Deploy built assets (tiles, pads, seg) to mod bgdata directories."""
    emit_legacy_silent_path_selected("deploy", asset_name=name)
    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    _deploy_bgdata_assets(
        name,
        mod_dirs,
        deploy_as=deploy_as,
        include_tiles=True,
        include_pads=True,
        include_seg=True,
        verbose=True,
    )


def deploy_setup(name: str, mod_dirs: list[str] | None = None, *, deploy_as: str | None = None):
    """Deploy setup binary to mod files directories (parent of bgdata)."""
    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    _deploy_setup_assets(name, mod_dirs, deploy_as=deploy_as, verbose=True)


def deploy_all(
    name: str,
    mod_dirs: list[str] | None = None,
    *,
    deploy_as: str | None = None,
    include_tiles: bool = True,
    include_seg: bool = True,
    include_pads: bool = True,
    include_setup: bool = True,
):
    """Deploy built assets; omit tiles/seg when overlaying retail geometry."""
    emit_legacy_silent_path_selected("deploy", asset_name=name)
    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    if include_pads or include_tiles or include_seg:
        _deploy_bgdata_assets(
            name,
            mod_dirs,
            deploy_as=deploy_as,
            include_tiles=include_tiles,
            include_pads=include_pads,
            include_seg=include_seg,
            verbose=True,
        )

    if include_setup:
        deploy_setup(name, mod_dirs, deploy_as=deploy_as)


def run_deploy(
    name: str,
    *,
    run_id: str | None = None,
    mod_dirs: list[str] | None = None,
    deploy_as: str | None = None,
    include_tiles: bool = True,
    include_seg: bool = True,
    include_pads: bool = True,
    include_setup: bool = True,
    scenario_id: str | None = None,
    verbose: bool = False,
) -> DeployOutcome:
    """Typed deploy entry point with structured lifecycle logging."""
    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    rid = run_id or current_build_run_id() or new_run_id()
    sid = scenario_id or current_build_scenario_id()
    asset = as_asset_name(name)
    t0 = time.perf_counter()

    def _latency_ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    base_fields = {
        "run_id": rid,
        "asset_name": str(asset),
        "operation": "deploy",
        "scenario_id": sid,
    }
    if deploy_as:
        base_fields["deploy_as"] = str(as_asset_name(deploy_as))
    emit_lifecycle_event(PdmapLifecycleEvent.DEPLOY_STARTED, **base_fields)

    deployed: list[str] = []
    try:
        if include_pads or include_tiles or include_seg:
            deployed.extend(
                _deploy_bgdata_assets(
                    name,
                    mod_dirs,
                    deploy_as=deploy_as,
                    include_tiles=include_tiles,
                    include_pads=include_pads,
                    include_seg=include_seg,
                    verbose=verbose,
                    fail_on_missing=True,
                )
            )
        if include_setup:
            deployed.extend(
                _deploy_setup_assets(
                    name,
                    mod_dirs,
                    deploy_as=deploy_as,
                    verbose=verbose,
                )
            )
    except Exception as exc:
        kind = classify_deploy_failure(exc=exc)
        recovery = classify_failure_recovery(kind, exc=exc)
        emit_lifecycle_event(
            PdmapLifecycleEvent.DEPLOY_FAILED,
            outcome="failed",
            error_kind=kind.value,
            recovery_class=recovery.value,
            latency_ms=_latency_ms(),
            error=str(exc),
            deployed_count=len(deployed),
            **base_fields,
        )
        return make_deploy_outcome(
            name,
            run_id=rid,
            ok=False,
            failure_kind=kind,
            deployed_paths=deployed,
            error_message=str(exc),
        )

    emit_lifecycle_event(
        PdmapLifecycleEvent.DEPLOY_COMPLETED,
        outcome="ok",
        error_kind=PdmapFailureKind.NONE.value,
        latency_ms=_latency_ms(),
        deployed_count=len(deployed),
        **base_fields,
    )
    return make_deploy_outcome(
        name,
        run_id=rid,
        ok=True,
        failure_kind=PdmapFailureKind.NONE,
        deployed_paths=deployed,
    )


def build_box_seg_asset(name: str, *, half: float = 5000.0, height: float = 3000.0,
                        mod_dirs: list[str] | None = None) -> str:
    """Generate a generic single-room box seg directly (no external script).

    This is the turnkey path for scaffolded maps that do not ship a bespoke
    ``SEG_SCRIPT``. It uses the procedural box generator in
    ``tools.pdmap.seg`` (the same engine ``build_custom_seg.py`` wraps for uff)
    to write ``bg_<name>.seg`` into the build tree and every mod directory.

    ``half``/``height`` should match the floor tiles so the visible walls line
    up with the collision floor; the seg's Section-3 bbox spans the full s16
    range regardless, so spawns always resolve to a room.
    """
    from .seg import write_box_seg

    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    os.makedirs(BUILD_DIR, exist_ok=True)
    build_dst = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    write_box_seg(build_dst, half=half, height=height)
    _validate_seg_before_deploy(build_dst)
    print(f"  Built box seg -> {build_dst} (half={half:.0f} height={height:.0f})")

    for mod_dir in mod_dirs:
        os.makedirs(mod_dir, exist_ok=True)
        mod_dst = os.path.join(mod_dir, f"bg_{name}.seg")
        shutil.copy2(build_dst, mod_dst)
        _validate_seg_before_deploy(mod_dst)
        print(f"  Deployed seg -> {mod_dst}")

    return build_dst


def build_seg(name: str, script_path: str, mod_dirs: list[str] | None = None) -> str:
    """Run a seg generator script and install bg_<name>.seg to build + mods."""
    if mod_dirs is None:
        mod_dirs = MOD_DIRS

    abs_script = script_path if os.path.isabs(script_path) else os.path.join(ROOT, script_path)
    if not os.path.exists(abs_script):
        raise FileNotFoundError(f"Seg script not found: {abs_script}")

    subprocess.run(
        [sys.executable, abs_script],
        cwd=ROOT,
        check=True,
        timeout=pdmap_build_timeout_seconds(),
    )

    script_dir = os.path.dirname(abs_script)
    generated = os.path.join(script_dir, f"bg_{name}.seg")
    if not os.path.exists(generated):
        raise FileNotFoundError(
            f"Seg script did not produce {generated}. "
            f"Ensure the script writes bg_{name}.seg next to itself."
        )

    _validate_seg_before_deploy(generated)

    os.makedirs(BUILD_DIR, exist_ok=True)
    build_dst = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    shutil.copy2(generated, build_dst)
    _validate_seg_before_deploy(build_dst)
    print(f"  Installed seg -> {build_dst}")

    for mod_dir in mod_dirs:
        os.makedirs(mod_dir, exist_ok=True)
        mod_dst = os.path.join(mod_dir, f"bg_{name}.seg")
        shutil.copy2(generated, mod_dst)
        _validate_seg_before_deploy(mod_dst)
        print(f"  Deployed seg -> {mod_dst}")

    return build_dst
