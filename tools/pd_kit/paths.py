"""Canonical Perfect Dark Kit paths and version resolution."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_KIT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _KIT_DIR.parent.parent


def _read_trimmed(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=1)
def kit_manifest() -> dict[str, Any]:
    with (_KIT_DIR / "kit.json").open(encoding="utf-8") as fp:
        return json.load(fp)


def kit_name() -> str:
    return str(kit_manifest().get("name", "Perfect Dark Kit"))


def kit_version() -> str:
    env = os.environ.get("PD_KIT_VERSION", "").strip()
    if env:
        return env
    from_file = _read_trimmed(_REPO_ROOT / "KIT_VERSION")
    return from_file or "0.0.0"


def port_version() -> str:
    env = os.environ.get("PD_PORT_VERSION", "").strip()
    if env:
        return env
    from_file = _read_trimmed(_REPO_ROOT / "PORT_VERSION")
    return from_file or "0.0.0"


def _app_config(component: str) -> dict[str, Any]:
    apps = kit_manifest().get("apps", {})
    if component not in apps:
        raise KeyError(f"Unknown kit component: {component}")
    return apps[component]


def kit_support_root() -> Path:
    manifest = kit_manifest()
    name = str(manifest.get("supportDirName", "PerfectDarkKit"))
    return Path.home() / "Library" / "Application Support" / name


def kit_logs_root() -> Path:
    manifest = kit_manifest()
    name = str(manifest.get("logsDirName", "PerfectDarkKit"))
    return Path.home() / "Library" / "Logs" / name


def kit_support_dir(component: str) -> Path:
    cfg = _app_config(component)
    subdir = str(cfg.get("id", component))
    path = kit_support_root() / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def kit_log_file(component: str) -> Path:
    cfg = _app_config(component)
    log_name = str(cfg.get("logFile", f"{component}.log"))
    root = kit_logs_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / log_name


def _legacy_support_dir(component: str) -> Path | None:
    cfg = _app_config(component)
    legacy = cfg.get("legacySupportDir")
    if not legacy:
        return None
    return Path.home() / "Library" / "Application Support" / str(legacy)


def _repo_dir_writable(path: Path) -> bool:
    if not path.is_dir():
        return False
    probe = path / ".pd_kit_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_editor_state_dir(repo_root: str | Path | None = None) -> str:
    """Match map editor server/Electron state directory resolution."""
    env_state = os.environ.get("PD_EDITOR_STATE_DIR", "").strip()
    if env_state:
        os.makedirs(env_state, exist_ok=True)
        return env_state

    root = Path(repo_root).resolve() if repo_root else _REPO_ROOT
    repo_viewer = root / "journal" / "uff_viewer"
    if _repo_dir_writable(repo_viewer):
        return str(repo_viewer)

    kit_dir = kit_support_dir("mapEditor")
    legacy = _legacy_support_dir("mapEditor")
    if legacy and legacy.is_dir() and not any(kit_dir.iterdir()):
        # Prefer legacy data until the user saves into the kit directory.
        return str(legacy)
    return str(kit_dir)


def resolve_anim_lab_state_dir(repo_root: str | Path | None = None) -> str:
    """Match Animation Lab server/Electron state directory resolution."""
    env_state = os.environ.get("PD_ANIM_LAB_STATE_DIR", "").strip()
    if env_state:
        os.makedirs(env_state, exist_ok=True)
        return env_state

    root = Path(repo_root).resolve() if repo_root else _REPO_ROOT
    repo_lab = root / "journal" / "anim_lab"
    if _repo_dir_writable(repo_lab):
        return str(repo_lab)

    kit_dir = kit_support_dir("animLab")
    legacy = _legacy_support_dir("animLab")
    if legacy and legacy.is_dir() and not any(kit_dir.iterdir()):
        return str(legacy)
    return str(kit_dir)


def app_product_name(component: str) -> str:
    return str(_app_config(component).get("productName", kit_name()))


def app_bundle_filename(component: str) -> str:
    return str(_app_config(component).get("bundleFileName", f"{component}.app"))
