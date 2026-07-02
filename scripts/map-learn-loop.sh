#!/bin/bash
# Event-primary loop for map learn engine.
# Primary wake: new journal/map_learn/runs/*.json or external validation log.
# Fallback heartbeat: MAP_LEARN_HEARTBEAT_SEC (default 1800 = 30m).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LEARN_DIR="$REPO/journal/map_learn"
PIDFILE="$LEARN_DIR/.learn-loop.pid"
LOGFILE="$LEARN_DIR/loop.log"          # external/manual triggers only
INTERNAL_LOG="$LEARN_DIR/.loop-internal.log"
RUNS_DIR="$LEARN_DIR/runs"
VALIDATION_LOG="$LEARN_DIR/.last_validation_launch.log"
VALIDATION_STEP="$LEARN_DIR/.validation_step"
HEARTBEAT_SEC="${MAP_LEARN_HEARTBEAT_SEC:-1800}"
POLL_SEC="${MAP_LEARN_POLL_SEC:-5}"
MIN_WAKE_SEC="${MAP_LEARN_MIN_WAKE_SEC:-60}"
PROMPT='Continue map learn loop: read LEARN_PLAN.md, implement next pending learn map(s), run pdmap learn curriculum generate+validate, pdmap learn run, update LEARN_PLAN status. Event-driven — do not redo learn_01-11 manual validation.'

mkdir -p "$RUNS_DIR" "$LEARN_DIR"
echo "$$ event" >"$PIDFILE"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) map-learn-loop started pid=$$ mode=event heartbeat=${HEARTBEAT_SEC}s" >>"$INTERNAL_LOG"

emit_wake() {
  local reason="$1"
  local now last_wake
  now=$(date +%s)
  last_wake="${LAST_WAKE_TS:-0}"
  if (( now - last_wake < MIN_WAKE_SEC )); then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) wake suppressed reason=$reason (debounce ${MIN_WAKE_SEC}s)" >>"$INTERNAL_LOG"
    return 0
  fi
  LAST_WAKE_TS=$now
  local payload
  payload=$(printf '{"prompt":"%s","reason":"%s","ts":"%s"}' \
    "$PROMPT" "$reason" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")
  echo "AGENT_LOOP_WAKE_map_learn $payload"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) wake reason=$reason" >>"$INTERNAL_LOG"
}

# Seed watchers — only *external* events (not self-written loop-internal log).
last_run=""
if ls "$RUNS_DIR"/*.json >/dev/null 2>&1; then
  last_run=$(ls -t "$RUNS_DIR"/*.json | head -1)
fi
last_log_size=$(wc -c <"$LOGFILE" 2>/dev/null || echo 0)
last_validation_size=$(wc -c <"$VALIDATION_LOG" 2>/dev/null || echo 0)
last_validation_step=""
if [[ -f "$VALIDATION_STEP" ]]; then
  last_validation_step=$(cat "$VALIDATION_STEP")
fi
next_heartbeat=$(( $(date +%s) + HEARTBEAT_SEC ))

while true; do
  sleep "$POLL_SEC"

  # Event 1: new learn run completion JSON
  if ls "$RUNS_DIR"/*.json >/dev/null 2>&1; then
    newest=$(ls -t "$RUNS_DIR"/*.json | head -1)
    if [[ -n "$newest" && "$newest" != "$last_run" ]]; then
      last_run="$newest"
      emit_wake "run_complete:$(basename "$newest")"
      next_heartbeat=$(( $(date +%s) + HEARTBEAT_SEC ))
      continue
    fi
  fi

  # Event 2: external loop.log append (manual agent/user trigger)
  cur_log_size=$(wc -c <"$LOGFILE" 2>/dev/null || echo 0)
  if [[ "$cur_log_size" -gt "$last_log_size" ]]; then
    last_log_size=$cur_log_size
    emit_wake "loop_log_append"
    next_heartbeat=$(( $(date +%s) + HEARTBEAT_SEC ))
    continue
  fi

  # Event 3: manual validation launch log grew
  cur_validation_size=$(wc -c <"$VALIDATION_LOG" 2>/dev/null || echo 0)
  if [[ "$cur_validation_size" -gt "$last_validation_size" ]]; then
    last_validation_size=$cur_validation_size
    emit_wake "validation_launch"
    next_heartbeat=$(( $(date +%s) + HEARTBEAT_SEC ))
    continue
  fi

  # Event 4: validation step counter advanced
  if [[ -f "$VALIDATION_STEP" ]]; then
    cur_step=$(cat "$VALIDATION_STEP")
    if [[ -n "$cur_step" && "$cur_step" != "$last_validation_step" ]]; then
      last_validation_step="$cur_step"
      emit_wake "validation_step:$cur_step"
      next_heartbeat=$(( $(date +%s) + HEARTBEAT_SEC ))
      continue
    fi
  fi

  # Fallback heartbeat (long idle safety)
  now=$(date +%s)
  if (( now >= next_heartbeat )); then
    emit_wake "heartbeat_fallback"
    next_heartbeat=$(( now + HEARTBEAT_SEC ))
  fi
done
