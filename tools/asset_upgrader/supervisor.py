"""Snapshot workdir state for the Electron supervisor UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.asset_upgrader.catalog import load_catalog
from tools.asset_upgrader.state import item_key, load_state


def build_snapshot(workdir: Path, repo_root: Path) -> dict[str, Any]:
    workdir = workdir.resolve()
    catalog_path = workdir / "catalog.json"
    state_path = workdir / "state.json"
    state = load_state(state_path)
    items = state.get("items", {})

    assets: list[dict[str, Any]] = []
    if catalog_path.exists():
        for entry in load_catalog(catalog_path):
            key = item_key(entry.texture_id, entry.mod_name)
            item = items.get(key, {})
            mod = entry.mod_name or "base"
            stage = item.get("stage", "pending")
            assets.append(
                {
                    "key": key,
                    "texture_id": entry.texture_id,
                    "mod_name": entry.mod_name,
                    "source_path": entry.source_path,
                    "stage": stage,
                    "error": item.get("error"),
                    "extracted_png": str(workdir / "extracted" / mod / f"{entry.texture_id}.png"),
                    "upgraded_png": str(workdir / "upgraded" / mod / f"{entry.texture_id}.png"),
                    "encoded_bin": item.get("encoded"),
                }
            )
    else:
        for key, item in sorted(items.items()):
            assets.append({"key": key, "stage": item.get("stage", "unknown"), **item})

    by_stage: dict[str, int] = {}
    for row in assets:
        stage = row.get("stage", "pending")
        by_stage[stage] = by_stage.get(stage, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workdir": str(workdir),
        "repo_root": str(repo_root.resolve()),
        "total": len(assets),
        "by_stage": by_stage,
        "assets": assets,
        "running": state.get("running", False),
        "last_command": state.get("last_command"),
        "last_exit_code": state.get("last_exit_code"),
    }


def write_snapshot(workdir: Path, repo_root: Path, out_path: Path | None = None) -> Path:
    payload = build_snapshot(workdir, repo_root)
    target = out_path or (workdir / "snapshot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
