#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
SESSION="${SESSION_NAME:-beatless-v2}"
INTERVAL_SEC="${SUPERVISOR_INTERVAL_SEC:-20}"
MAX_FAILS="${SUPERVISOR_MAX_FAILS:-3}"
ACTIVE_PARALLEL="${DISPATCH_MAX_PARALLEL:-4}"
LOG="$BEATLESS/logs/rawcli-supervisor.log"
HEARTBEAT_JSON="$BEATLESS/metrics/supervisor-heartbeat.json"
DAYTIME_HEARTBEAT_ENABLED="${DAYTIME_HEARTBEAT_ENABLED:-true}"
DAYTIME_HEARTBEAT_START_HOUR="${DAYTIME_HEARTBEAT_START_HOUR:-8}"
DAYTIME_HEARTBEAT_END_HOUR="${DAYTIME_HEARTBEAT_END_HOUR:-23}"
DAYTIME_HEARTBEAT_INTERVAL_MIN="${DAYTIME_HEARTBEAT_INTERVAL_MIN:-30}"
DAYTIME_HEARTBEAT_SEND_ENABLED="${DAYTIME_HEARTBEAT_SEND_ENABLED:-true}"
DAYTIME_HEARTBEAT_CHAT_ID="${DAYTIME_HEARTBEAT_CHAT_ID:-${FEISHU_TARGET_CHAT_ID:-}}"
HOOK_LAG_THRESHOLD_MS="${HOOK_LAG_THRESHOLD_MS:-30000}"
DAYTIME_SLOT_FILE="$BEATLESS/metrics/daytime-heartbeat-slot.txt"
DAYTIME_MORNING_FILE="$BEATLESS/metrics/daytime-heartbeat-morning.txt"
DAYTIME_CLOSING_FILE="$BEATLESS/metrics/daytime-heartbeat-closing.txt"
RESTART_HISTORY_FILE="$BEATLESS/metrics/supervisor-restart-history.jsonl"
AUTOMATION_TICK_ENABLED="${AUTOMATION_TICK_ENABLED:-true}"
AUTOMATION_TICK_INTERVAL_SEC="${AUTOMATION_TICK_INTERVAL_SEC:-1800}"
AUTOMATION_TICK_STAMP_FILE="$BEATLESS/metrics/automation-tick-last-epoch.txt"

mkdir -p "$BEATLESS/logs" "$BEATLESS/metrics"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

ensure_hooks_window() {
  if ! tmux list-windows -t "$SESSION" -F '#W' 2>/dev/null | rg -q '^hooks$'; then
    log "hooks window missing -> creating"
    tmux new-window -t "$SESSION" -n hooks -c "$BEATLESS" || true
  fi
}

restart_hooks() {
  ensure_hooks_window
  log "restarting hooks loop in session=$SESSION parallel=$ACTIVE_PARALLEL"
  tmux send-keys -t "$SESSION:hooks" C-c || true
  sleep 1
  tmux send-keys -t "$SESSION:hooks" "SESSION_NAME=$SESSION DISPATCH_MAX_PARALLEL=$ACTIVE_PARALLEL bash $SCRIPTS/dispatch_hook_loop.sh" C-m || true
}

ensure_session() {
  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    log "session missing -> recreating via beatless_tmux_v2.sh"
    SESSION_NAME="$SESSION" bash "$SCRIPTS/beatless_tmux_v2.sh" || true
  fi
}

ensure_hooks_alive() {
  local queue_tail_pattern="$BEATLESS/dispatch-queue.jsonl"
  local pids=()
  mapfile -t pids < <(pgrep -f "tail -n 0 -F ${queue_tail_pattern}" || true)
  if [[ "${#pids[@]}" -eq 0 ]]; then
    log "hook process missing -> restart"
    restart_hooks
    return
  fi
  if [[ "${#pids[@]}" -gt 1 ]]; then
    log "hook process duplicated (${#pids[@]} queue-tail instances) -> restart hooks cleanly"
    restart_hooks
  fi
}

reconcile_stuck_results() {
  if ! bash "$SCRIPTS/rawcli_reconcile_stuck_results.sh" >/dev/null 2>&1; then
    log "stuck-result reconcile failed"
  fi
}

read_queue_lag_p95_ms() {
  python3 - "$BEATLESS/metrics/rawcli-metrics-latest.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
if not p.exists():
    print(0)
    raise SystemExit(0)
try:
    d = json.loads(p.read_text(encoding='utf-8'))
except Exception:
    print(0)
    raise SystemExit(0)
print(int(float(d.get('queue_lag_ms_p95', 0.0) or 0.0)))
PY
}

record_restart() {
  local reason="$1"
  printf '{"ts":"%s","session":"%s","reason":"%s","parallel":%s}\n' \
    "$(date -Iseconds)" "$SESSION" "$reason" "$ACTIVE_PARALLEL" >> "$RESTART_HISTORY_FILE"
}

read_queue_depth_metric() {
  python3 - "$BEATLESS/metrics/rawcli-metrics-latest.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
if not p.exists():
    print(0)
    raise SystemExit(0)
try:
    d = json.loads(p.read_text(encoding='utf-8'))
except Exception:
    print(0)
    raise SystemExit(0)
print(int(d.get('queue_depth', 0) or 0))
PY
}

emit_smalltalk_once_per_day() {
  local key="$1"
  local mark_file="$2"
  local today
  today="$(date +%Y%m%d)"
  if [[ -f "$mark_file" ]] && [[ "$(cat "$mark_file" 2>/dev/null)" == "$today" ]]; then
    return
  fi
  if [[ "$DAYTIME_HEARTBEAT_SEND_ENABLED" == "true" && -n "$DAYTIME_HEARTBEAT_CHAT_ID" ]]; then
    EVENT_SIGNAL_SEND_ENABLED=true FEISHU_TARGET_CHAT_ID="$DAYTIME_HEARTBEAT_CHAT_ID" \
      bash "$SCRIPTS/event_signal_emit.sh" "smalltalk.${key}" "" "ok" "0" "0" "$DAYTIME_HEARTBEAT_CHAT_ID" >/dev/null || true
    echo "$today" > "$mark_file"
  fi
}

emit_daytime_heartbeat_if_due() {
  if [[ "$DAYTIME_HEARTBEAT_ENABLED" != "true" ]]; then
    return
  fi
  if ! [[ "$DAYTIME_HEARTBEAT_START_HOUR" =~ ^[0-9]+$ && "$DAYTIME_HEARTBEAT_END_HOUR" =~ ^[0-9]+$ ]]; then
    return
  fi
  if ! [[ "$DAYTIME_HEARTBEAT_INTERVAL_MIN" =~ ^[0-9]+$ ]] || [[ "$DAYTIME_HEARTBEAT_INTERVAL_MIN" -le 0 ]]; then
    return
  fi

  local hour minute slot_key slot_num current_slot
  hour=$((10#$(date +%H)))
  minute=$((10#$(date +%M)))

  if [[ "$hour" -lt "$DAYTIME_HEARTBEAT_START_HOUR" || "$hour" -gt "$DAYTIME_HEARTBEAT_END_HOUR" ]]; then
    return
  fi

  slot_num=$(( (hour * 60 + minute) / DAYTIME_HEARTBEAT_INTERVAL_MIN ))
  slot_key="$(date +%Y%m%d)-$slot_num"
  current_slot="$(cat "$DAYTIME_SLOT_FILE" 2>/dev/null || true)"
  if [[ "$current_slot" == "$slot_key" ]]; then
    return
  fi

  echo "$slot_key" > "$DAYTIME_SLOT_FILE"

  local queue_depth
  queue_depth="$(read_queue_depth_metric)"

  if [[ "$DAYTIME_HEARTBEAT_SEND_ENABLED" == "true" && -n "$DAYTIME_HEARTBEAT_CHAT_ID" ]]; then
    EVENT_SIGNAL_SEND_ENABLED=true FEISHU_TARGET_CHAT_ID="$DAYTIME_HEARTBEAT_CHAT_ID" \
      bash "$SCRIPTS/event_signal_emit.sh" "heartbeat_status" "" "ok" "$queue_depth" "0" "$DAYTIME_HEARTBEAT_CHAT_ID" >/dev/null || true
  else
    bash "$SCRIPTS/event_signal_emit.sh" "heartbeat_status" "" "ok" "$queue_depth" "0" >/dev/null || true
  fi

  if [[ "$hour" -eq "$DAYTIME_HEARTBEAT_START_HOUR" ]]; then
    emit_smalltalk_once_per_day "morning" "$DAYTIME_MORNING_FILE"
  fi
  if [[ "$hour" -eq "$DAYTIME_HEARTBEAT_END_HOUR" ]]; then
    emit_smalltalk_once_per_day "closing" "$DAYTIME_CLOSING_FILE"
  fi
}

run_automation_tick_if_due() {
  if [[ "$AUTOMATION_TICK_ENABLED" != "true" ]]; then
    return
  fi
  if ! [[ "$AUTOMATION_TICK_INTERVAL_SEC" =~ ^[0-9]+$ ]] || [[ "$AUTOMATION_TICK_INTERVAL_SEC" -lt 60 ]]; then
    AUTOMATION_TICK_INTERVAL_SEC=1800
  fi
  if [[ ! -x "$SCRIPTS/rawcli_cron_tick.sh" ]]; then
    return
  fi

  local now last elapsed
  now="$(date +%s)"
  last="$(cat "$AUTOMATION_TICK_STAMP_FILE" 2>/dev/null || echo 0)"
  if ! [[ "$last" =~ ^[0-9]+$ ]]; then
    last=0
  fi
  elapsed=$((now - last))
  if [[ "$elapsed" -lt "$AUTOMATION_TICK_INTERVAL_SEC" ]]; then
    return
  fi

  echo "$now" > "$AUTOMATION_TICK_STAMP_FILE"
  nohup bash "$SCRIPTS/rawcli_cron_tick.sh" >/dev/null 2>&1 < /dev/null &
  log "automation_tick triggered (elapsed=${elapsed}s)"
}

fails=0
log "supervisor started session=$SESSION interval=${INTERVAL_SEC}s max_fails=$MAX_FAILS"

while true; do
  ensure_session
  ensure_hooks_window
  ensure_hooks_alive
  reconcile_stuck_results

  SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_metrics_rollup.sh" >/dev/null 2>&1 || log "metrics rollup failed"

  # P1: mode switch gate + dynamic parallel
  if [[ -x "$SCRIPTS/mode_switch_gate.sh" ]]; then
    mode_out=$(bash "$SCRIPTS/mode_switch_gate.sh" 2>&1 || true)
    [[ -n "$mode_out" ]] && log "mode_gate: $mode_out"

    current_mode=$(cat /tmp/beatless_exec_mode 2>/dev/null || echo "daily")
    case "$current_mode" in
      degraded) target_parallel=1 ;;
      stressed) target_parallel=2 ;;
      *) target_parallel=4 ;;
    esac

    if [[ "$target_parallel" != "$ACTIVE_PARALLEL" ]]; then
      log "parallel update: $ACTIVE_PARALLEL -> $target_parallel (mode=$current_mode)"
      ACTIVE_PARALLEL="$target_parallel"
      restart_hooks
    fi
  fi

  if SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_healthcheck.sh" >/dev/null 2>&1; then
    fails=0
    log "healthcheck ok"
  else
    fails=$((fails + 1))
    log "healthcheck failed count=$fails"
  fi

  if [ "$fails" -ge "$MAX_FAILS" ]; then
    log "healthcheck threshold exceeded -> restarting hooks"
    record_restart "healthcheck_threshold_exceeded"
    restart_hooks
    fails=0
  fi

  queue_lag_p95="$(read_queue_lag_p95_ms)"
  if [[ "$queue_lag_p95" -gt "$HOOK_LAG_THRESHOLD_MS" ]]; then
    log "queue_lag_p95=${queue_lag_p95}ms exceeds ${HOOK_LAG_THRESHOLD_MS}ms -> restarting hooks"
    record_restart "queue_lag_exceeded"
    restart_hooks
  fi

  if SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_alert_check.sh" >/dev/null 2>&1; then
    :
  else
    log "alert check returned non-zero (warning/critical), see Report/rawcli-alert-latest.md"
  fi

  if [[ -x "$SCRIPTS/rawcli_observability_panel.sh" ]]; then
    bash "$SCRIPTS/rawcli_observability_panel.sh" >/dev/null 2>&1 || log "observability panel refresh failed"
  fi

  run_automation_tick_if_due
  emit_daytime_heartbeat_if_due

  printf '{"ts":"%s","session":"%s","interval_sec":%s,"health_fail_streak":%s}\n' \
    "$(date -Iseconds)" "$SESSION" "$INTERVAL_SEC" "$fails" > "$HEARTBEAT_JSON"

  sleep "$INTERVAL_SEC"
done
