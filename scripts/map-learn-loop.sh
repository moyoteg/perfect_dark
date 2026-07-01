#!/bin/bash
# Fixed-interval heartbeat for the map learn engine loop.
# Emits AGENT_LOOP_WAKE_map_learn every MAP_LEARN_INTERVAL_SEC (default 120).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$REPO/journal/map_learn/.learn-loop.pid"
INTERVAL="${MAP_LEARN_INTERVAL_SEC:-120}"
PROMPT='Run pdmap learn iteration: probe codebase, merge facts, update gaps.md and MAP_DETERMINISTIC_SPEC.md, fix probes if doc coverage stalls, target near-perfect deterministic map creation docs.'

mkdir -p "$(dirname "$PIDFILE")"
echo "$$ heartbeat" > "$PIDFILE"

while true; do
  sleep "$INTERVAL"
  echo "AGENT_LOOP_WAKE_map_learn {\"prompt\":\"$PROMPT\"}"
done
