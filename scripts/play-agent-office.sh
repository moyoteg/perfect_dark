#!/usr/bin/env bash
# Virtual Agent Office — dataDyne G5 Building (STAGE_AGENT_OFFICE 0x83).
#
# Deploys Ump_setupagent_officeZ with friendly office agents at computer stations.
# Retail depo seg/tiles/pads load from ROM; only the MP setup is overridden.
#
# Usage:
#   ./scripts/play-agent-office.sh              # deploy + solo peaceful explore
#   ./scripts/play-agent-office.sh --no-play    # deploy only
#   ./scripts/play-agent-office.sh --with-bots  # 4 combat sims (MP loadout restored)
#   ./scripts/play-agent-office.sh --force      # kill existing game and relaunch
# App:
#   ./scripts/launch-agent-office-app.sh
#
# macOS: launch via Terminal only (no open -na fallback) to avoid double-launch loops.
# Expected GL log noise on macOS: GL3.0 compat fails, 4.1 core succeeds; missing
# gl*P*ui pointers in core profile are benign (compat-only entry points).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
MODDIR="$REPO/mods/mod_allinone"
DATA_DIR="$REPO/data"
ROM="$DATA_DIR/pd.ntsc-final.z64"
BOOT_STAGE="0x83"  # STAGE_AGENT_OFFICE
LOG_DIR="$REPO/journal/agent_office"
LAST_LOG="$LOG_DIR/.last_launch.log"
LAST_PID="$LOG_DIR/.last_play.pid"

mkdir -p "$LOG_DIR"

NO_PLAY=false
WITH_BOTS=false
FORCE_LAUNCH=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-play) NO_PLAY=true; shift ;;
	--with-bots) WITH_BOTS=true; shift ;;
	--force) FORCE_LAUNCH=true; shift ;;
	*) EXTRA_ARGS+=("$1"); shift ;;
	esac
done

log() {
	echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*" | tee -a "$LAST_LOG"
}

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

build_launch_args() {
	LAUNCH_ARGS=(
		--basedir "$DATA_DIR"
		--moddir "$MODDIR"
		--savedir "$REPO"
		--boot-stage "$BOOT_STAGE"
		--skip-intro
		--scenario-0
	)
	if [[ "$WITH_BOTS" == true ]]; then
		LAUNCH_ARGS+=(--num-sims 4)
	else
		LAUNCH_ARGS+=(--solo)
	fi
	if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
		LAUNCH_ARGS+=("${EXTRA_ARGS[@]}")
	fi
}

pgrep_play() {
	local p cmd
	for p in $(pgrep -x pd.arm64 2>/dev/null); do
		cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
		if [[ "$cmd" == *"$PD"* && "$cmd" == *"--boot-stage"* && "$cmd" == *"$BOOT_STAGE"* ]]; then
			echo "$p"
			return 0
		fi
	done
}

deploy_lang_bank() {
	# Copy the compiled LANGBANK_DEPO into the mod so agent Z-target and console
	# strings resolve. Requires a prior `cmake --build build --target pd_headers`
	# to regenerate the .o. No-op (uses the existing bank) when not yet built.
	local src="$REPO/build/ntsc-final/assets/files/LdepoE.o"
	local dst="$MODDIR/files/LdepoE"
	if [[ -f "$src" ]]; then
		if [[ ! -f "$dst" || "$src" -nt "$dst" ]]; then
			mkdir -p "$MODDIR/files"
			cp "$src" "$dst"
			log "Lang bank updated: LdepoE ($(wc -c <"$dst" | tr -d ' ') bytes)"
		else
			log "Lang bank up to date: LdepoE"
		fi
	else
		log "Lang source not built ($src) — run: cmake --build build --target pd_headers -j8 (using existing mod LdepoE)"
	fi
}

log "=== Virtual Agent Office ==="
log "Building + deploying agent_office → STAGE_AGENT_OFFICE (0x83)"
python3 "$REPO/tools/pdmap.py" build agent_office --deploy 2>&1 | tee -a "$LAST_LOG"
deploy_lang_bank

if [[ "$NO_PLAY" == true ]]; then
	log "Deploy complete (--no-play)"
	exit 0
fi

ensure_rom
build_launch_args

existing_pid="$(pgrep_play || true)"
if [[ -n "$existing_pid" && "$FORCE_LAUNCH" != true ]]; then
	echo "$existing_pid" >"$LAST_PID"
	log "Game already running (PID $existing_pid) — skipping launch (pass --force to relaunch)"
	exit 0
fi
if [[ -n "$existing_pid" && "$FORCE_LAUNCH" == true ]]; then
	log "Stopping existing PID $existing_pid (--force)"
	kill "$existing_pid" 2>/dev/null || true
	sleep 1
fi

log "Launching: $PD ${LAUNCH_ARGS[*]}"

if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
	play_cmd="cd $(printf '%q' "$REPO") && $(printf '%q' "$PD")"
	for arg in "${LAUNCH_ARGS[@]}"; do
		play_cmd+=" $(printf '%q' "$arg")"
	done
	play_cmd+=" 2>&1 | tee -a $(printf '%q' "$LAST_LOG")"
	osascript - "$play_cmd" <<'APPLESCRIPT' >/dev/null
on run argv
	tell application "Terminal"
		do script (item 1 of argv)
	end tell
end run
APPLESCRIPT

	play_pid=""
	for _ in $(seq 1 48); do
		play_pid="$(pgrep_play || true)"
		if [[ -n "$play_pid" ]]; then
			break
		fi
		sleep 0.25
	done

	if [[ -n "$play_pid" ]]; then
		echo "$play_pid" >"$LAST_PID"
		log "Game PID $play_pid (log: $LAST_LOG)"
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
		osascript -e 'display notification "Look for the separate Perfect Dark game window (not Terminal)." with title "Virtual Agent Office"' >/dev/null 2>&1 || true
	else
		log "WARNING: game PID not detected after Terminal launch — check pgrep pd.arm64 (no open -na fallback; avoids double-launch loop)"
	fi
else
	nohup "$PD" "${LAUNCH_ARGS[@]}" >>"$LAST_LOG" 2>&1 &
	GAME_PID=$!
	echo "$GAME_PID" >"$LAST_PID"
	log "Game PID $GAME_PID (log: $LAST_LOG)"
fi
