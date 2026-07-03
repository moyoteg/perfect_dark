#!/usr/bin/env bash
# Overnight LLM Play guardian — auto-repairs the stack and wakes the agent if repair fails.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${HOME}/Library/Logs/PerfectDarkLlmPlay.log"
BRIDGE="http://127.0.0.1:8780/api/llm/health"
LOCK_FILE="${HOME}/Library/Logs/PerfectDarkLlmPlay.lock"
PROMPT='LLM Play overnight: auto-repair failed twice — inspect logs, run scripts/verify-llm-play.sh --keep, rebuild pd.arm64 or LLM Play.app if needed, confirm adapter_connected=1.'

health_ok() {
	local raw
	raw="$(curl -sf --max-time 4 "$BRIDGE" 2>/dev/null || true)"
	[[ -n "$raw" ]] && echo "$raw" | grep -q '"ok":true' && echo "$raw" | grep -q '"enabled":1' && echo "$raw" | grep -q '"adapter_connected":1'
}

repair() {
	printf '[overnight-guard] %s repairing stack\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$LOG"
	cd "$REPO_ROOT"
	if "$REPO_ROOT/scripts/verify-llm-play.sh" --keep >>"$LOG" 2>&1; then
		return 0
	fi
	if [[ -d "$REPO_ROOT/LLM Play.app" ]]; then
		printf '[overnight-guard] %s opening LLM Play.app\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$LOG"
		open "$REPO_ROOT/LLM Play.app" >>"$LOG" 2>&1 || true
		sleep 90
		health_ok
		return $?
	fi
	return 1
}

case "${1:-watch}" in
fix)
	cd "$REPO_ROOT"
	exec "$REPO_ROOT/scripts/verify-llm-play.sh" --keep
	;;
watch)
	failures=0
	while true; do
		sleep 60
		if health_ok; then
			failures=0
			continue
		fi
		printf '[overnight-guard] %s unhealthy — attempting repair\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$LOG"
		if repair; then
			failures=0
			continue
		fi
		failures=$((failures + 1))
		if ((failures >= 2)); then
			printf '%s\n' "AGENT_LOOP_WAKE_llm_play {\"prompt\":\"$PROMPT\",\"reason\":\"repair_failed_twice\",\"log\":\"$LOG\"}"
			failures=0
			sleep 600
		else
			sleep 120
		fi
	done
	;;
*)
	echo "usage: $0 [watch|fix]" >&2
	exit 2
	;;
esac
