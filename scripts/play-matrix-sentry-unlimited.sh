#!/usr/bin/env bash
# Deploy matrix_battle_sentry_inf (uff test slot) and launch with infinite sentry ammo.
# Usage: ./scripts/play-matrix-sentry-unlimited.sh [--no-play] [--num-sims N]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
MODDIR="$REPO/mods/mod_allinone"
DATA_DIR="$REPO/data"
ROM="$DATA_DIR/pd.ntsc-final.z64"
LOG_DIR="$REPO/journal/map_learn"
LAST_LOG="$LOG_DIR/.matrix_battle_sentry_inf_test.log"
NUM_SIMS=50
NO_PLAY=false

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-play) NO_PLAY=true; shift ;;
	--num-sims)
		NUM_SIMS="${2:?--num-sims requires a value}"
		shift 2
		;;
	*) echo "Unknown arg: $1" >&2; exit 1 ;;
	esac
done

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

build_play_flags() {
	play_parts=(
		--test-map
		--laptop-sentry-infinite-ammo
		--unlimited-sentries
		--scenario-0
		--basedir "$DATA_DIR"
		--moddir "$MODDIR"
		--savedir "$REPO"
		--num-sims "$NUM_SIMS"
		--teams-battle
		--sim-difficulty 5
	)
}

cd "$REPO"

echo "=== Matrix Battle Sentry (Infinite Ammo) ==="
echo "  Deploy: python3 tools/pdmap.py build matrix_battle_sentry_inf --seg --deploy"
echo "  Binary: ${PD#$REPO/}"
echo "  Flags:  --laptop-sentry-infinite-ammo --unlimited-sentries"
echo "  Sims:   $NUM_SIMS (Dark difficulty, teams Combat)"

if [[ ! -x "$PD" ]]; then
	echo "Building pd.arm64 (cmake --build build --target pd -j8)…"
	cmake --build build --target pd -j8
fi

python3 tools/pdmap.py build matrix_battle_sentry_inf --seg --deploy

if [[ "$NO_PLAY" == true ]]; then
	echo "  --no-play: deploy only"
	exit 0
fi

ensure_rom
build_play_flags

{
	echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) matrix_battle_sentry_inf infinite sentry ammo test ==="
	echo "cmd: $PD ${play_parts[*]}"
} >>"$LAST_LOG"

if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
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

	pgrep_play() {
		local p cmd
		for p in $(pgrep -x pd.arm64 2>/dev/null); do
			cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
			if [[ "$cmd" == *"$PD"* && "$cmd" == *"--test-map"* && "$cmd" == *"--laptop-sentry-infinite-ammo"* ]]; then
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
		osascript -e "display notification \"Infinite sentry ammo + unlimited deploys.\" with title \"Perfect Dark — Matrix Sentry Inf\"" >/dev/null 2>&1 || true
	fi
	echo "  game window: separate SDL window titled \"Perfect Dark\""
	if [[ -n "$play_pid" ]]; then
		echo "  pid: $play_pid"
	else
		echo "  pid: (not detected — check pgrep pd.arm64)"
	fi
else
	exec "$PD" "${play_parts[@]}" 2>&1 | tee -a "$LAST_LOG"
fi
