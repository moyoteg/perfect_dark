#!/bin/bash
# Deploy curriculum step N into the uff test slot and launch pd (--test-map).
# Usage: ./scripts/play-learn-step.sh [STEP] [--no-play]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
MODDIR="$REPO/mods/mod_allinone"
LOG_DIR="$REPO/journal/map_learn"
LAST_LOG="$LOG_DIR/.last_validation_launch.log"
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
  8|10) SCENARIO=5 ;;  # CTF (step 10 composite: briefcase prop needs scenario 5)
esac

# KOTH / CTF steps need visible floor markers in seg (tiles are collision-only).
SEG_MODE=empty
if [[ "$STEP" == "7" ]]; then
  SEG_MODE=hill
elif [[ "$STEP" == "8" || "$STEP" == "10" ]]; then
  SEG_MODE=ctf
fi

DEPLOY_ARGS=(
  from-json "$JSON"
  --deploy-as uff
  --deploy
  --seg-mode "$SEG_MODE"
  --scenario "$SCENARIO"
  --binary "$PD"
)

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

if [[ "$NO_PLAY" == false ]]; then
  map_name="$(basename "$JSON" .json)"
  {
    echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ${map_name} test-map scenario-${SCENARIO} (play-learn-step) ==="
    echo "cmd: $PD --test-map --scenario-${SCENARIO} --num-sims 0 --moddir mods/mod_allinone"
  } >>"$LAST_LOG"
  if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
    # Build + deploy here; launch in Terminal.app for a real GL context (matches validate-maps).
    python3 tools/pdmap.py "${DEPLOY_ARGS[@]}"
    play_cmd="cd $(printf '%q' "$REPO") && $(printf '%q' "$PD") --test-map --scenario-${SCENARIO} --num-sims 0 --moddir $(printf '%q' "$MODDIR") 2>&1 | tee -a $(printf '%q' "$LAST_LOG")"
    osascript - "$play_cmd" <<'APPLESCRIPT' >/dev/null
on run argv
	tell application "Terminal"
		activate
		do script (item 1 of argv)
	end tell
end run
APPLESCRIPT
    echo "  opened: Terminal.app (--scenario-${SCENARIO})"
    echo "  log: ${LAST_LOG#$REPO/}"
    exit 0
  fi
fi

if [[ "$NO_PLAY" == true ]]; then
  python3 tools/pdmap.py "${DEPLOY_ARGS[@]}"
else
  python3 tools/pdmap.py "${DEPLOY_ARGS[@]}" --play
fi
