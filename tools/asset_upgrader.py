#!/usr/bin/env python3
"""Wrapper for tools.asset_upgrader."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.asset_upgrader.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
