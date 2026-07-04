#!/usr/bin/env bash
# Start, stop, or inspect the Virtual Agent Office live LLM director sidecar.
#
# The director is intentionally separate from the map launcher: the office can still
# run as a static explore mode, and the live LLM layer can be started after the
# in-game HTTP bridge is available.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIRECTOR="$REPO/tools/agent_office_llm/office_director.py"
LOG_DIR="$REPO/journal/agent_office"
LOG_FILE="$LOG_DIR/office_director.log"
PID_FILE="$LOG_DIR/.office_director.pid"
URL="${AGENT_OFFICE_BRIDGE_URL:-http://127.0.0.1:8780}"
BACKEND="${AGENT_OFFICE_LLM_BACKEND:-auto}"
USE_LLM=1
FOREGROUND=0
ACTION="start"

mkdir -p "$LOG_DIR"

usage() {
	cat <<EOF
Usage: $0 [--backend auto|ollama|mlx] [--url URL] [--no-llm] [--foreground]
       $0 --status
       $0 --stop

Starts office_director.py against the Perfect Dark bridge. By default it uses the
llm-play backend factory (--llm --backend auto) and writes logs to:
  $LOG_FILE
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--backend)
		BACKEND="${2:-}"
		shift 2
		;;
	--url)
		URL="${2:-}"
		shift 2
		;;
	--no-llm)
		USE_LLM=0
		shift
		;;
	--foreground)
		FOREGROUND=1
		shift
		;;
	--status)
		ACTION="status"
		shift
		;;
	--stop)
		ACTION="stop"
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "Unknown option: $1" >&2
		usage >&2
		exit 2
		;;
	esac
done

is_alive() {
	local pid="$1"
	[[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

pid_from_file() {
	if [[ -f "$PID_FILE" ]]; then
		tr -cd '0-9' <"$PID_FILE"
	fi
}

find_director_pids() {
	local p cmd
	for p in $(pgrep -f "office_director.py" 2>/dev/null || true); do
		cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
		if [[ "$cmd" == *"$DIRECTOR"* ]]; then
			echo "$p"
		fi
	done
}

status() {
	local pid
	pid="$(pid_from_file || true)"
	if is_alive "$pid"; then
		echo "running pid=$pid log=$LOG_FILE"
		return 0
	fi
	local pids
	pids="$(find_director_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
	if [[ -n "$pids" ]]; then
		echo "running pid=$pids log=$LOG_FILE"
		return 0
	fi
	echo "stopped log=$LOG_FILE"
}

stop_director() {
	local killed=0 pid
	pid="$(pid_from_file || true)"
	if is_alive "$pid"; then
		kill "$pid" 2>/dev/null || true
		killed=1
	fi
	while IFS= read -r pid; do
		[[ -z "$pid" ]] && continue
		kill "$pid" 2>/dev/null || true
		killed=1
	done < <(find_director_pids)
	rm -f "$PID_FILE"
	echo "stopped killed=$killed log=$LOG_FILE"
}

start_director() {
	if [[ ! -f "$DIRECTOR" ]]; then
		echo "ERROR: director not found: $DIRECTOR" >&2
		exit 1
	fi
	if ! command -v python3 >/dev/null 2>&1; then
		echo "ERROR: python3 not found" >&2
		exit 1
	fi

	local pid
	pid="$(pid_from_file || true)"
	if is_alive "$pid"; then
		echo "already running pid=$pid log=$LOG_FILE"
		return 0
	fi

	local args=("$DIRECTOR" "--url" "$URL")
	if [[ "$USE_LLM" -eq 1 ]]; then
		args+=("--llm" "--backend" "$BACKEND")
	fi

	{
		echo ""
		echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] starting director url=$URL backend=$([[ "$USE_LLM" -eq 1 ]] && echo "$BACKEND" || echo "scripted")"
	} >>"$LOG_FILE"

	if [[ "$FOREGROUND" -eq 1 ]]; then
		exec env PYTHONDONTWRITEBYTECODE=1 PD_REPO_ROOT="$REPO" python3 "${args[@]}"
	fi

	nohup env PYTHONDONTWRITEBYTECODE=1 PD_REPO_ROOT="$REPO" python3 "${args[@]}" >>"$LOG_FILE" 2>&1 &
	pid=$!
	echo "$pid" >"$PID_FILE"
	echo "started pid=$pid log=$LOG_FILE"
}

case "$ACTION" in
status) status ;;
stop) stop_director ;;
start) start_director ;;
esac
