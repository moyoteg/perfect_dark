#!/usr/bin/env python3
"""CLI for mass-upgrading Perfect Dark graphical assets via OpenAI image models."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from tools.asset_upgrader.catalog import discover_textures, load_catalog, write_catalog
from tools.asset_upgrader.backends import create_upgrader
from tools.asset_upgrader.openai_backend import DEFAULT_PROMPT
from tools.asset_upgrader.state import item_key, load_state, mark, save_state
from tools.asset_upgrader.supervisor import write_snapshot
from tools.asset_upgrader.texture_codec import (
    asset_to_png,
    decode_texture,
    encode_texture,
    png_to_asset,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_workdir() -> Path:
    return repo_root() / "work" / "asset_upgrader"


def _refresh_snapshot(workdir: Path) -> None:
    try:
        write_snapshot(workdir, repo_root())
    except OSError:
        pass


def cmd_snapshot(args: argparse.Namespace) -> int:
    path = write_snapshot(Path(args.workdir), repo_root())
    print(path)
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    root = repo_root()
    search_paths = [root / p for p in args.path]
    entries = discover_textures(search_paths, root)
    if args.limit:
        entries = entries[: args.limit]
    out = Path(args.output)
    write_catalog(entries, out)
    print(f"catalog: wrote {len(entries)} assets -> {out}")
    return 0


def _resolve_source(root: Path, rel_path: str) -> Path:
    path = root / rel_path
    if not path.exists():
        raise FileNotFoundError(rel_path)
    return path


def cmd_extract(args: argparse.Namespace) -> int:
    root = repo_root()
    workdir = Path(args.workdir)
    catalog = load_catalog(Path(args.catalog))
    state = load_state(workdir / "state.json")
    extracted = workdir / "extracted"
    meta_dir = workdir / "meta"

    ok = skipped = failed = 0
    for entry in catalog:
        key = item_key(entry.texture_id, entry.mod_name)
        if args.resume and get_stage(state, key) in {"extracted", "upgraded", "encoded", "deployed"}:
            skipped += 1
            continue
        try:
            src = _resolve_source(root, entry.source_path)
            data = src.read_bytes()
            asset = decode_texture(entry.texture_id, entry.source_path, data)
            png_path = extracted / (entry.mod_name or "base") / f"{entry.texture_id}.png"
            png_path.parent.mkdir(parents=True, exist_ok=True)
            asset_to_png(asset, str(png_path))
            meta_path = meta_dir / (entry.mod_name or "base") / f"{entry.texture_id}.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps(
                    {
                        "texture_id": entry.texture_id,
                        "mod_name": entry.mod_name,
                        "source_path": entry.source_path,
                        "format": asset.format_name,
                        "width": asset.width,
                        "height": asset.height,
                        "header_byte": asset.header_byte,
                        "num_lods": asset.num_lods,
                        "has_lod_data": asset.has_lod_data,
                        "palette_size": len(asset.palette),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            mark(
                state,
                key,
                "extracted",
                source=entry.source_path,
                png=str(png_path.relative_to(workdir)),
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 - batch tool reports and continues
            mark(state, key, "failed", failed_stage="extract", error=str(exc))
            failed += 1
            print(f"extract FAIL {entry.texture_id} ({entry.mod_name}): {exc}", file=sys.stderr)

    save_state(workdir / "state.json", state)
    _refresh_snapshot(workdir)
    print(f"extract: ok={ok} skipped={skipped} failed={failed}")
    return 1 if ok == 0 and failed else 0


def get_stage(state: dict, key: str) -> str | None:
    return state.get("items", {}).get(key, {}).get("stage")


def cmd_upgrade(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    state = load_state(workdir / "state.json")
    upgrader = create_upgrader(args)
    extracted = workdir / "extracted"
    upgraded = workdir / "upgraded"
    meta_dir = workdir / "meta"

    ok = skipped = failed = 0
    for meta_path in sorted(meta_dir.rglob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        key = item_key(meta["texture_id"], meta.get("mod_name"))
        if args.resume and get_stage(state, key) in {"upgraded", "encoded", "deployed"}:
            skipped += 1
            continue
        if get_stage(state, key) != "extracted" and not args.force:
            skipped += 1
            continue

        mod = meta.get("mod_name") or "base"
        src_png = extracted / mod / f"{meta['texture_id']}.png"
        dst_png = upgraded / mod / f"{meta['texture_id']}.png"
        try:
            result = upgrader.upgrade_png(
                src_png,
                dst_png,
                width=meta["width"],
                height=meta["height"],
            )
            mark(state, key, "upgraded", upgrade=result)
            ok += 1
            print(f"upgrade OK {meta['texture_id']} ({mod}) via {result.get('backend', result.get('mode', 'ok'))}")
            if args.sleep and getattr(args, "backend", "local") == "openai":
                time.sleep(args.sleep)
        except Exception as exc:  # noqa: BLE001
            mark(state, key, "failed", failed_stage="upgrade", error=str(exc))
            failed += 1
            print(f"upgrade FAIL {meta['texture_id']} ({mod}): {exc}", file=sys.stderr)

    save_state(workdir / "state.json", state)
    _refresh_snapshot(workdir)
    print(f"upgrade: ok={ok} skipped={skipped} failed={failed}")
    return 1 if ok == 0 and failed else 0


def cmd_encode(args: argparse.Namespace) -> int:
    root = repo_root()
    workdir = Path(args.workdir)
    state = load_state(workdir / "state.json")
    upgraded = workdir / "upgraded"
    encoded = workdir / "encoded"
    meta_dir = workdir / "meta"

    ok = skipped = failed = 0
    for meta_path in sorted(meta_dir.rglob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        key = item_key(meta["texture_id"], meta.get("mod_name"))
        if args.resume and get_stage(state, key) == "deployed":
            skipped += 1
            continue
        if get_stage(state, key) not in {"upgraded", "encoded"} and not args.force:
            skipped += 1
            continue

        mod = meta.get("mod_name") or "base"
        src_bin = _resolve_source(root, meta["source_path"])
        png_path = upgraded / mod / f"{meta['texture_id']}.png"
        if not png_path.exists():
            png_path = workdir / "extracted" / mod / f"{meta['texture_id']}.png"
        try:
            asset = decode_texture(meta["texture_id"], meta["source_path"], src_bin.read_bytes())
            out_bytes = png_to_asset(asset, str(png_path))
            out_path = encoded / mod / "textures" / f"{meta['texture_id']}.bin"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(out_bytes)
            mark(
                state,
                key,
                "encoded",
                encoded=str(out_path.relative_to(workdir)),
                encoded_size=len(out_bytes),
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001
            mark(state, key, "failed", failed_stage="encode", error=str(exc))
            failed += 1
            print(f"encode FAIL {meta['texture_id']} ({mod}): {exc}", file=sys.stderr)

    save_state(workdir / "state.json", state)
    _refresh_snapshot(workdir)
    print(f"encode: ok={ok} skipped={skipped} failed={failed}")
    return 1 if ok == 0 and failed else 0


def cmd_deploy(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    state = load_state(workdir / "state.json")
    encoded = workdir / "encoded"
    deploy_root = Path(args.output)

    copied = 0
    for bin_path in sorted(encoded.rglob("textures/*.bin")):
        rel = bin_path.relative_to(encoded)
        mod_name = rel.parts[0]
        texture_id = bin_path.stem.lower()
        key = item_key(texture_id, mod_name if mod_name != "base" else None)
        if get_stage(state, key) != "encoded":
            continue
        target = deploy_root / mod_name / "textures" / f"{texture_id}.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bin_path, target)
        mark(state, key, "deployed", deployed=str(target))
        copied += 1

    save_state(workdir / "state.json", state)
    _refresh_snapshot(workdir)
    print(f"deploy: copied {copied} textures -> {deploy_root}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = repo_root()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    catalog_path = workdir / "catalog.json"

    catalog_args = argparse.Namespace(
        path=args.path,
        output=str(catalog_path),
        limit=args.limit,
    )
    rc = cmd_catalog(catalog_args)
    if rc:
        return rc

    stages = [
        ("extract", {"catalog": str(catalog_path)}),
        ("upgrade", {}),
        ("encode", {}),
        ("deploy", {"output": args.deploy_dir}),
    ]
    for name, extra in stages:
        ns = argparse.Namespace(
            workdir=str(workdir),
            resume=not args.no_resume,
            force=False,
            dry_run=args.dry_run,
            backend=args.backend,
            model=args.model,
            prompt=args.prompt,
            upscale_to=args.upscale_to,
            local_scale=args.local_scale,
            api_key=args.api_key,
            sleep=args.sleep,
            **extra,
        )
        rc = globals()[f"cmd_{name}"](ns)
        if rc:
            print(f"run: stopped after '{name}' with errors", file=sys.stderr)
            return rc
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(Path(args.workdir) / "state.json")
    items = state.get("items", {})
    counts: dict[str, int] = {}
    for item in items.values():
        stage = item.get("stage", "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    print(json.dumps({"total": len(items), "by_stage": counts}, indent=2))
    if args.failed:
        for key, item in sorted(items.items()):
            if item.get("stage") == "failed":
                print(f"{key}: {item.get('error')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset_upgrader",
        description=(
            "Mass-upgrade Perfect Dark mod textures using OpenAI image generation. "
            "Workflow: catalog -> extract -> upgrade -> encode -> deploy."
        ),
    )
    parser.add_argument(
        "--workdir",
        default=str(default_workdir()),
        help="Working directory for catalog/state/PNGs (default: work/asset_upgrader)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_catalog = sub.add_parser("catalog", help="Scan mod folders and write catalog.json")
    p_catalog.add_argument(
        "--path",
        action="append",
        default=["mods", "src/assets/ntsc-final/textures"],
        help="Paths to scan (default: mods + base ROM textures)",
    )
    p_catalog.add_argument("--output", default=str(default_workdir() / "catalog.json"))
    p_catalog.add_argument("--limit", type=int, default=0, help="Limit number of catalog entries")
    p_catalog.set_defaults(func=cmd_catalog)

    for name in ("extract", "upgrade", "encode"):
        p = sub.add_parser(name, help=f"{name} stage")
        if name == "extract":
            p.add_argument("--catalog", default=str(default_workdir() / "catalog.json"))
        p.add_argument("--resume", action="store_true", default=True)
        p.add_argument("--no-resume", action="store_false", dest="resume")
        p.add_argument("--force", action="store_true", help="Ignore stage guards")
        p.add_argument(
            "--backend",
            choices=("local", "openai", "mlx"),
            default="local",
            help="local=free on-device enhance (default); openai=paid API; mlx=Apple Silicon local MLX Core",
        )
        if name == "upgrade":
            p.add_argument("--model", default="gpt-image-1", help="OpenAI image model")
            p.add_argument("--prompt", default=DEFAULT_PROMPT)
            p.add_argument("--upscale-to", type=int, default=1024)
            p.add_argument("--local-scale", type=int, default=4, help="Local upscale factor")
            p.add_argument("--api-key", default=None)
            p.add_argument("--dry-run", action="store_true", help="Skip enhancement logic")
            p.add_argument("--sleep", type=float, default=0.0, help="Seconds between OpenAI calls")
        p.set_defaults(func=globals()[f"cmd_{name}"])

    p_deploy = sub.add_parser("deploy", help="Copy encoded bins into a mod directory tree")
    p_deploy.add_argument(
        "--output",
        default=str(repo_root() / "mods" / "mod_upgraded"),
        help="Destination mod root",
    )
    p_deploy.set_defaults(func=cmd_deploy)

    p_run = sub.add_parser("run", help="Execute the full pipeline")
    p_run.add_argument("--path", action="append", default=["mods/mod_allinone"])
    p_run.add_argument("--limit", type=int, default=0)
    p_run.add_argument("--deploy-dir", default=str(repo_root() / "mods" / "mod_upgraded"))
    p_run.add_argument("--backend", choices=("local", "openai", "mlx"), default="local")
    p_run.add_argument("--model", default="gpt-image-1")
    p_run.add_argument("--prompt", default=DEFAULT_PROMPT)
    p_run.add_argument("--upscale-to", type=int, default=1024)
    p_run.add_argument("--local-scale", type=int, default=4)
    p_run.add_argument("--api-key", default=None)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--sleep", type=float, default=1.0)
    p_run.add_argument("--no-resume", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Summarize workdir state.json")
    p_status.add_argument("--failed", action="store_true", help="Print failed items")
    p_status.set_defaults(func=cmd_status)

    p_snapshot = sub.add_parser("snapshot", help="Write snapshot.json for the Electron supervisor")
    p_snapshot.set_defaults(func=cmd_snapshot)

    return parser


def main(argv: list[str] | None = None) -> int:
    from tools.asset_upgrader.auth import ensure_openai_key, load_env_file, validate_openai_key

    parser = build_parser()
    args = parser.parse_args(argv)
    workdir = Path(getattr(args, "workdir", default_workdir()))
    load_env_file(workdir / ".env")

    # OpenAI API key only required for paid backend.
    cmd = args.command
    backend = getattr(args, "backend", "local")
    dry = bool(getattr(args, "dry_run", False))
    if cmd in {"upgrade", "run"} and backend == "openai" and not dry:
        try:
            validate_openai_key(ensure_openai_key(workdir))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001
            print(f"OpenAI key validation failed: {exc}", file=sys.stderr)
            return 2

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
