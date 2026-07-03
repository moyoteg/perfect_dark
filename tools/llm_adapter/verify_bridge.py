#!/usr/bin/env python3
"""Backward-compatible verify — delegates to llm-play/verify_bridge.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
llm_play = Path(os.environ.get("LLM_PLAY_ROOT", "")).resolve() if os.environ.get("LLM_PLAY_ROOT") else ROOT.parent / "llm-play"
if str(llm_play) not in sys.path:
    sys.path.insert(0, str(llm_play))

os.environ.setdefault("GAME_REPO_ROOT", str(ROOT))

from verify_bridge import main

if __name__ == "__main__":
    raise SystemExit(main())
