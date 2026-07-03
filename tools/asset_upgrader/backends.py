"""Upgrade backend selection."""

from __future__ import annotations

from tools.asset_upgrader.local_backend import LocalTextureUpgrader
from tools.asset_upgrader.openai_backend import DEFAULT_PROMPT, OpenAIImageUpgrader


def create_upgrader(args) -> LocalTextureUpgrader | OpenAIImageUpgrader:
    backend = getattr(args, "backend", "local")
    dry_run = bool(getattr(args, "dry_run", False))

    if backend == "openai":
        return OpenAIImageUpgrader(
            model=getattr(args, "model", "gpt-image-1"),
            prompt=getattr(args, "prompt", DEFAULT_PROMPT) or DEFAULT_PROMPT,
            upscale_to=getattr(args, "upscale_to", 1024),
            api_key=getattr(args, "api_key", None),
            dry_run=dry_run,
        )

    if backend == "local":
        return LocalTextureUpgrader(
            scale=getattr(args, "local_scale", 4),
            dry_run=dry_run,
        )

    raise ValueError(f"unknown backend {backend!r}; use 'local' or 'openai'")
