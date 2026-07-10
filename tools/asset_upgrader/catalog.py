"""Discover graphical assets that can be upgraded."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TEXTURE_RE = re.compile(r"^[0-9a-fA-F]{4}\.bin$")


@dataclass
class AssetEntry:
    asset_type: str
    texture_id: str
    source_path: str
    mod_name: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _mod_name(path: Path, repo_root: Path) -> str | None:
    parts = path.relative_to(repo_root).parts
    if len(parts) >= 2 and parts[0] == "mods":
        return parts[1]
    return None


def discover_textures(paths: Iterable[Path], repo_root: Path) -> list[AssetEntry]:
    entries: list[AssetEntry] = []
    seen: set[tuple[str, str]] = set()

    for base in paths:
        base = base.resolve()
        if base.is_file() and TEXTURE_RE.match(base.name):
            candidates = [base]
            root = repo_root
        elif base.is_dir():
            candidates = sorted(base.rglob("*.bin"))
            root = repo_root
        else:
            continue

        for path in candidates:
            parent = path.parent.name
            if parent != "textures" or not TEXTURE_RE.match(path.name):
                continue
            texture_id = path.stem.lower()
            mod_name = _mod_name(path, root)
            if mod_name == "mod_upgraded":
                continue
            key = (mod_name or "", texture_id)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                AssetEntry(
                    asset_type="texture",
                    texture_id=texture_id,
                    source_path=str(path.relative_to(root)),
                    mod_name=mod_name,
                )
            )

    entries.sort(key=lambda e: (e.mod_name or "", e.texture_id))
    return entries


def write_catalog(entries: list[AssetEntry], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "asset_count": len(entries),
        "assets": [e.to_dict() for e in entries],
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_catalog(path: Path) -> list[AssetEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [AssetEntry(**row) for row in payload["assets"]]
