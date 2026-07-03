#!/usr/bin/env bash
# Probe Conker collision floor Y at War Colors spawn/weapon pad XY, build + deploy corrected bg_mp13_padsZ.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "Building pd.arm64…"
cmake --build build --target pd -j8
echo "Probing War Colors pads (engine cdFindGround at pad XY)…"
python3 tools/war_colors_correct_pads.py --pd "$REPO/build/pd.arm64" "$@"
