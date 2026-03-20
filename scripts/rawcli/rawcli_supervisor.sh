#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
SESSION="${SESSION_NAME:-beatless-v2}"
INTERVAL_SEC="${SUPERVISOR_INTERVAL_SEC:-20}"
MAX_FAILS="${SUPERVISOR_MAX_FAILS:-3}"
LOG="$BEATLESS/logs/rawcli-supervisor.log"
HEARTBEAT_JSON="$BEATLESS/metrics/supervisor-heartbeat.json"

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
  log "restarting hooks loop in session=$SESSION"
  tmux send-keys -t "$SESSION:hooks" C-c || true
  sleep 1
  tmux send-keys -t "$SESSION:hooks" "SESSION_NAME=$SESSION bash $SCRIPTS/dispatch_hook_loop.sh" C-m || true
}

ensure_session() {
  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    log "session missing -> recreating via beatless_tmux_v2.sh"
    SESSION_NAME="$SESSION" bash "$SCRIPTS/beatless_tmux_v2.sh" || true
  fi
}

ensure_hooks_alive() {
  if ! ps -eo cmd | rg -q "dispatch_hook_loop.sh"; then
    log "hook process missing -> restart"
    restart_hooks
  fi
}

fails=0
log "supervisor started session=$SESSION interval=${INTERVAL_SEC}s max_fails=$MAX_FAILS"

while true; do
  ensure_session
  ensure_hooks_window
  ensure_hooks_alive

  SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_metrics_rollup.sh" >/dev/null 2>&1 || log "metrics rollup failed"

  if SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_healthcheck.sh" >/dev/null 2>&1; then
    fails=0
    log "healthcheck ok"
  else
    fails=$((fails + 1))
    log "healthcheck failed count=$fails"
  fi

  if [ "$fails" -ge "$MAX_FAILS" ]; then
    log "healthcheck threshold exceeded -> restarting hooks"
    restart_hooks
    fails=0
  fi

  if SESSION_NAME="$SESSION" bash "$SCRIPTS/rawcli_alert_check.sh" >/dev/null 2>&1; then
    :
  else
    log "alert check returned non-zero (warning/critical), see Report/rawcli-alert-latest.md"
  fi

  printf '{"ts":"%s","session":"%s","interval_sec":%s,"health_fail_streak":%s}\n' \
    "$(date -Iseconds)" "$SESSION" "$INTERVAL_SEC" "$fails" > "$HEARTBEAT_JSON"

  sleep "$INTERVAL_SEC"
done
