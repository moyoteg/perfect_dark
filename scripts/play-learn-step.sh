#!/bin/bash
# Deploy curriculum step N into the uff test slot and launch pd (--test-map).
# Usage: ./scripts/play-learn-step.sh [STEP] [--no-play]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
MODDIR="$REPO/mods/mod_allinone"
DATA_DIR="$REPO/data"
ROM="$DATA_DIR/pd.ntsc-final.z64"
LOG_DIR="$REPO/journal/map_learn"
LAST_LOG="$LOG_DIR/.last_validation_launch.log"
STEP="${1:-1}"
NO_PLAY=false
if [[ "${2:-}" == "--no-play" ]]; then
  NO_PLAY=true
fi

ensure_rom() {
  if [[ -f "$ROM" ]]; then
    return 0
  fi
  local fb=(
    "/Users/moigutierrez/Library/CloudStorage/GoogleDrive-moyoteg@gmail.com/My Drive/Games/N64 Decomp/PerfectDarkShared/pd.ntsc-final.z64"
    "/Users/moigutierrez/Library/Mobile Documents/com~apple~CloudDocs/Work/Personal/Games/perfect_dark/pd.ntsc-final.z64"
  )
  for p in "${fb[@]}"; do
    if [[ -f "$p" ]]; then
      mkdir -p "$DATA_DIR"
      cp "$p" "$ROM" && return 0
    fi
  done
  echo "ERROR: missing ROM at $ROM (see README_MOD_INFO.md)" >&2
  exit 1
}

# Absolute fs paths so pd.arm64 finds ROM/mod assets even when cwd is wrong
# (e.g. open -na from an agent shell). ROM lives in data/, not mods/.
build_play_flags() {
  play_parts=(
    --test-map
    "--scenario-${SCENARIO}"
    --basedir "$DATA_DIR"
    --moddir "$MODDIR"
    --savedir "$REPO"
  )
  if ((${#EXTRA_PLAY_FLAGS[@]})); then
    play_parts+=("${EXTRA_PLAY_FLAGS[@]}")
  else
    play_parts+=(--num-sims 0)
  fi
}

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
  7|13|28) SCENARIO=4 ;;  # KOTH
  8|10|12|16|25|26) SCENARIO=5 ;;  # CTF
  19) SCENARIO=1 ;;  # Hold the Briefcase
  21) SCENARIO=2 ;;  # Hacker Central
  22) SCENARIO=3 ;;  # Pop a Cap
esac

# KOTH / CTF / full-seg steps need explicit seg mode (tiles are collision-only).
SEG_MODE=empty
case "$STEP" in
  7|13|28) SEG_MODE=hill ;;
  8|10|12|16|25|26) SEG_MODE=ctf ;;
  14|29) SEG_MODE=full ;;
  15|17) SEG_MODE=empty ;;
  20) SEG_MODE=marker ;;
  31) SEG_MODE=marker ;;
esac

# Optional sim count / loadout overrides for specific steps.
EXTRA_PLAY_FLAGS=()
case "$STEP" in
  23) EXTRA_PLAY_FLAGS=(--num-sims 8) ;;
  24) EXTRA_PLAY_FLAGS=(--loadout 1,9,16,4,0,37) ;;
  26) EXTRA_PLAY_FLAGS=(--num-sims 0) ;;
  31) EXTRA_PLAY_FLAGS=(--num-sims 2) ;;
esac

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
  ensure_rom
  map_name="$(basename "$JSON" .json)"
  build_play_flags
  {
    echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ${map_name} test-map scenario-${SCENARIO} (play-learn-step) ==="
    echo "cmd: $PD ${play_parts[*]}"
  } >>"$LAST_LOG"
  if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
    # Build + deploy here; launch pd in Terminal.app for a real GL context (matches validate-maps).
    # The game itself opens a separate SDL window titled "Perfect Dark" — not inside Terminal.
    python3 tools/pdmap.py "${DEPLOY_ARGS[@]}"
    play_cmd="cd $(printf '%q' "$REPO") && $(printf '%q' "$PD")"
    for pf in "${play_parts[@]}"; do
      play_cmd+=" $(printf '%q' "$pf")"
    done
    play_cmd+=" 2>&1 | tee -a $(printf '%q' "$LAST_LOG")"
    osascript - "$play_cmd" <<'APPLESCRIPT' >/dev/null
on run argv
	tell application "Terminal"
		do script (item 1 of argv)
	end tell
end run
APPLESCRIPT
    # Front the SDL game window once pd.arm64 starts (Terminal stays in background).
    # Match the real pd.arm64 process, not Terminal's bash wrapper command line.
    pgrep_play() {
      local p cmd
      for p in $(pgrep -x pd.arm64 2>/dev/null); do
        cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
        if [[ "$cmd" == *"$PD"* && "$cmd" == *"--test-map"* && "$cmd" == *"--scenario-${SCENARIO}"* ]]; then
          echo "$p"
          return 0
        fi
      done
    }
    play_pid=""
    for _ in $(seq 1 24); do
      play_pid="$(pgrep_play)"
      if [[ -n "$play_pid" ]]; then
        break
      fi
      sleep 0.25
    done
    if [[ -z "$play_pid" ]] && command -v open >/dev/null 2>&1; then
      # Terminal can be slow to spawn; fallback launch is cwd-independent via --basedir.
      open_args=(-na "$PD" --args)
      for pf in "${play_parts[@]}"; do
        open_args+=("$pf")
      done
      open "${open_args[@]}"
      for _ in $(seq 1 16); do
        play_pid="$(pgrep_play)"
        if [[ -n "$play_pid" ]]; then
          break
        fi
        sleep 0.25
      done
    fi
    if [[ -n "$play_pid" ]]; then
      echo "$play_pid" >"$LOG_DIR/.last_play.pid"
      osascript >/dev/null 2>&1 <<'APPLESCRIPT' || true
tell application "System Events"
  repeat with i from 1 to 30
    if exists (process "pd.arm64") then
      tell process "pd.arm64" to set frontmost to true
      exit repeat
    end if
    delay 0.2
  end repeat
end tell
APPLESCRIPT
      osascript -e "display notification \"Look for the separate Perfect Dark game window (not Terminal).\" with title \"Learn step ${STEP}\"" >/dev/null 2>&1 || true
    fi
    echo "  game window: separate SDL window titled \"Perfect Dark\" (not Terminal)"
    echo "  scenario: --scenario-${SCENARIO}"
    if [[ -n "$play_pid" ]]; then
      echo "  pid: $play_pid"
    else
      echo "  pid: (not detected — check pgrep pd.arm64)"
    fi
    echo "  log: ${LAST_LOG#$REPO/}"
    exit 0
  fi
fi

if [[ "$NO_PLAY" == true ]]; then
  python3 tools/pdmap.py "${DEPLOY_ARGS[@]}"
else
  python3 tools/pdmap.py "${DEPLOY_ARGS[@]}" --play
fi
