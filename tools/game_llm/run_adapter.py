#!/usr/bin/env python3
"""Shim — canonical LLM Play lives in sibling ``../llm-play``."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _llm_play_root() -> Path:
    env = os.environ.get("LLM_PLAY_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    sibling = here.parents[2].parent / "llm-play"
    if sibling.is_dir() and (sibling / "run_adapter.py").is_file():
        return sibling.resolve()
    raise SystemExit(
        "LLM Play project not found. Clone llm-play beside this repo or set LLM_PLAY_ROOT."
    )


def _game_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    llm_play = _llm_play_root()
    game_repo = _game_repo_root()
    env = os.environ.copy()
    env.setdefault("LLM_PLAY_ROOT", str(llm_play))
    env.setdefault("GAME_REPO_ROOT", str(game_repo))
    env.setdefault("PD_REPO_ROOT", str(game_repo))
    os.execve(
        sys.executable,
        [sys.executable, str(llm_play / "run_adapter.py"), *sys.argv[1:]],
        env,
    )
