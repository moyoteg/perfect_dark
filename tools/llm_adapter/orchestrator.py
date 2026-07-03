"""Backward-compatible re-exports — canonical code in sibling llm-play project."""

from __future__ import annotations

import sys
from pathlib import Path

_LLM_PLAY = Path(__file__).resolve().parents[2].parent / "llm-play"
if _LLM_PLAY.is_dir() and str(_LLM_PLAY) not in sys.path:
    sys.path.insert(0, str(_LLM_PLAY))

from game_llm.engine.orchestrator import AdapterOrchestrator, choose_backend
from game_llm.engine.bridge_client import BridgeClient as GameBridgeClient

__all__ = ["AdapterOrchestrator", "GameBridgeClient", "choose_backend"]
