"""Load and validate OpenAI credentials for the asset upgrader."""

from __future__ import annotations

import os
from pathlib import Path


def env_file(workdir: Path) -> Path:
    return workdir / ".env"


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overwriting existing vars."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_openai_key(workdir: Path) -> str:
    """Return a usable OPENAI_API_KEY, loading workdir/.env first."""
    load_env_file(env_file(workdir))
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No OpenAI API key found. OpenAI does not allow creating billing API keys "
            "from nothing on the CLI — you need an existing account key once.\n"
            "Options:\n"
            "  1. export OPENAI_API_KEY=sk-...  (from https://platform.openai.com/api-keys)\n"
            f"  2. Save the same line to {env_file(workdir)} (auto-loaded on later runs)\n"
            "  3. If you have OPENAI_ADMIN_KEY, run: ./scripts/setup-asset-upgrader.sh --provision-key"
        )
    return key


def validate_openai_key(key: str) -> None:
    """Fail fast if the key is missing or rejected."""
    from openai import OpenAI

    client = OpenAI(api_key=key)
    # Lightweight call; confirms key works without generating images.
    client.models.list()
