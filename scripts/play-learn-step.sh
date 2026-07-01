#!/bin/bash
# Deploy curriculum step N into the uff test slot and launch pd (--test-map).
# Usage: ./scripts/play-learn-step.sh [STEP] [--no-play]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
STEP="${1:-1}"
NO_PLAY=false
if [[ "${2:-}" == "--no-play" ]]; then
  NO_PLAY=true
fi

STEP_PADDED=$(printf '%02d' "$STEP")
JSON=""
for candidate in "$REPO/journal/map_learn/maps/learn_${STEP_PADDED}"_*.json; do
  if [[ -f "$candidate" ]]; then
    JSON="$candidate"
    break
  fi
done
if [[ -z "$JSON" ]]; then
  echo "ERROR: no curriculum map for step $STEP" >&2
  echo "Run: python3 tools/pdmap.py learn curriculum generate" >&2
  exit 1
fi

# Scenario flags per step (must match tools/pdmap/learn/curriculum.py).
SCENARIO=0
case "$STEP" in
  7) SCENARIO=4 ;;  # KOTH
  8) SCENARIO=5 ;;  # CTF
esac

# KOTH steps need visible hill floor in seg room 2 (tiles are collision-only).
SEG_MODE=empty
if [[ "$STEP" == "7" || "$STEP" == "10" ]]; then
  SEG_MODE=hill
elif [[ "$STEP" == "8" ]]; then
  SEG_MODE=ctf
fi

CMD_ARGS=(
  from-json "$JSON"
  --deploy-as uff
  --deploy
  --seg-mode "$SEG_MODE"
  --scenario "$SCENARIO"
  --binary "$PD"
)
if [[ "$NO_PLAY" == false ]]; then
  CMD_ARGS+=(--play)
fi

cd "$REPO"
# seg-mode flag wins inside pdmap; do not clobber with empty here.

echo "=== Learn step $STEP ==="
echo "  JSON: ${JSON#$REPO/}"
echo "  Deploy-as: uff (--test-map)"
echo "  Scenario: $SCENARIO"
echo "  Binary: ${PD#$REPO/}"
if [[ ! -x "$PD" ]]; then
  echo "ERROR: build $PD first (make -j8)" >&2
  exit 1
fi

python3 tools/pdmap.py "${CMD_ARGS[@]}"
