#!/usr/bin/env python3
"""Backward-compatible entry — delegates to sibling llm-play project."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if "--game" not in sys.argv:
    sys.argv[1:1] = ["--game", "perfect_dark"]

llm_play = Path(os.environ.get("LLM_PLAY_ROOT", "")).resolve() if os.environ.get("LLM_PLAY_ROOT") else ROOT.parent / "llm-play"
if not (llm_play / "run_adapter.py").is_file():
    raise SystemExit("LLM Play project not found beside this repo (expected ../llm-play).")

env = os.environ.copy()
env.setdefault("LLM_PLAY_ROOT", str(llm_play))
env.setdefault("GAME_REPO_ROOT", str(ROOT))
env.setdefault("PD_REPO_ROOT", str(ROOT))
os.execve(
    sys.executable,
    [sys.executable, str(llm_play / "run_adapter.py"), *sys.argv[1:]],
    env,
)
