"""Shared build pipeline: MapDef → binaries → validate → deploy."""

from __future__ import annotations

import json
import os
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
from .deploy import deploy_all
from .builders import ctf_zones_from_mapdef, hill_zone_center_from_mapdef
from .from_json import EditorMapSpec
from .pads_builder import write_pads_json
from .setup_packer import write_setup_binary
from .tiles import copy_tiles_from_template
from .validate import validate_all, validate_mapdef


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
) -> str:
    from .seg import validate_seg_g_vtx, write_box_seg, write_ctf_box_seg, write_hill_box_seg

    os.makedirs(BUILD_DIR, exist_ok=True)
    build_dst = os.path.join(BUILD_DIR, f"bg_{name}.seg")
    if ctf_zones:
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

    subprocess.run([__import__("sys").executable, abs_script], cwd=ROOT, check=True)

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


def build_from_spec(
    spec: EditorMapSpec,
    *,
    deploy: bool = False,
    want_seg: bool = True,
    seg_mode: str | None = "empty",
    mod_dirs: list[str] | None = None,
    skip_validate: bool = False,
    verbose: bool = False,
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

    if want_seg:
        hill_center = hill_zone_center_from_mapdef(mapdef)
        ctf_zones = ctf_zones_from_mapdef(mapdef)
        if seg_mode:
            effective_seg_mode = seg_mode
        elif ctf_zones:
            effective_seg_mode = "ctf"
        elif hill_center:
            effective_seg_mode = "hill"
        else:
            effective_seg_mode = "empty"
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
        )

    pads_json_path = write_pads_json(mapdef)
    if verbose:
        print(f"  Generated pads JSON: {pads_json_path}")
    compile_pads(name, pads_json_path)
    if verbose:
        print("  Compiled pads binary")
        print(f"  Pad layout log: {_write_pad_layout_log(name, mapdef)}")

    tiles_json_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
    tiles_data = spec.tiles_json()
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
        if deploy:
            if verbose:
                print("  Deploying...")
            deploy_all(name, mod_dirs)
            if verbose:
                print("  Deploy complete")
        return [], warnings

    errors, post_warnings = validate_all(name, mapdef)
    warnings.extend(post_warnings)
    if errors:
        return errors, warnings

    if deploy:
        if verbose:
            print("  Deploying...")
        deploy_all(name, mod_dirs)
        if verbose:
            print("  Deploy complete")

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
) -> tuple[list[str], list[str]]:
    """Build from ``src/levels/<name>.py`` (legacy / hand-authored levels)."""
    mod = load_level_module(name)
    mapdef = mod.build()
    deploy_as = getattr(mod, "DEPLOY_AS", None)
    seg_script = seg_script_path or _resolve_seg_script(mod, name)
    has_box_dims = hasattr(mod, "BOX_HALF") and hasattr(mod, "BOX_HEIGHT")
    do_seg = want_seg or bool(seg_script) or has_box_dims

    if do_seg:
        hill_center = hill_zone_center_from_mapdef(mapdef)
        ctf_zones = ctf_zones_from_mapdef(mapdef)
        seg_mode = getattr(mod, "SEG_MODE", None)
        if seg_mode:
            effective_seg_mode = str(seg_mode)
        elif ctf_zones:
            effective_seg_mode = "ctf"
        elif hill_center:
            effective_seg_mode = "hill"
        elif has_box_dims:
            effective_seg_mode = "empty"
        else:
            effective_seg_mode = "empty"
        os.environ["PDMAP_SEG_MODE"] = effective_seg_mode
        if seg_script:
            if verbose:
                print(f"  Building seg via {seg_script}")
            _build_seg_script_to_build_dir(name, seg_script)
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
            )
    elif deploy and verbose:
        print(
            "  WARNING: seg build skipped; deploy will copy existing BUILD_DIR seg "
            "(must pass G_VTX validation)"
        )

    pads_json_path = write_pads_json(mapdef)
    if verbose:
        print(f"  Generated pads JSON: {pads_json_path}")
    compile_pads(name, pads_json_path)
    if verbose:
        print("  Compiled pads binary")
        print(f"  Pad layout log: {_write_pad_layout_log(name, mapdef)}")

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

    if skip_validate:
        if deploy:
            if verbose:
                print("  Deploying...")
            deploy_all(name, mod_dirs, deploy_as=deploy_as)
        return [], []

    errors, warnings = validate_all(name, mapdef)
    if errors:
        return errors, warnings

    if deploy:
        if verbose:
            if deploy_as and deploy_as != name:
                print(f"  Deploy-as: {name} → {deploy_as} (test-map slot)")
            print("  Deploying...")
        deploy_all(name, mod_dirs, deploy_as=deploy_as)
        if verbose:
            print("  Deploy complete")

    return [], warnings
