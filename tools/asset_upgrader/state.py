"""Persistent job state for resumable batch upgrades."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "items": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def item_key(texture_id: str, mod_name: str | None) -> str:
    return f"{mod_name or 'base'}:{texture_id}"


def get_item(state: dict[str, Any], key: str) -> dict[str, Any]:
    return state.setdefault("items", {}).setdefault(key, {})


def mark(state: dict[str, Any], key: str, stage: str, **fields: Any) -> None:
    entry = get_item(state, key)
    entry["stage"] = stage
    entry.update(fields)
