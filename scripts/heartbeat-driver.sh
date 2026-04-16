#!/usr/bin/env bash
# heartbeat-driver.sh — v2.1: Pipeline scheduler + result notifier
#
# Runs every 30 minutes via cron daemon. Checks pipeline schedules,
# launches due pipelines in tmux, and forwards completed results.
#
# Pipelines:
#   github-pr:        every 2.5h (configured in state.json)
#   blog-maintenance: every 1h   (configured in state.json)

set -euo pipefail

SHARED_DIR="/home/yarizakurahime/claw/.openclaw/hermes"
LOG_DIR="$SHARED_DIR/logs"
PIPELINE_DIR="$SHARED_DIR/pipelines"
MAIL_BIN="node $SHARED_DIR/scripts/mail.mjs"

mkdir -p "$LOG_DIR"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EPOCH=$(date +%s)

log() { echo "[$TS] heartbeat: $*"; }

# Check if a pipeline is due to run
check_pipeline() {
  local name="$1"
  local state_file="$PIPELINE_DIR/$name/state.json"
  local run_script="$PIPELINE_DIR/$name/test-run.sh"

  if [ ! -f "$state_file" ] || [ ! -f "$run_script" ]; then
    log "$name: missing state or run script, skipping"
    return
  fi

  local status last_run next_run interval
  status=$(python3 -c "import json; d=json.load(open('$state_file')); print(d.get('status','IDLE'))" 2>/dev/null || echo "IDLE")
  interval=$(python3 -c "import json; d=json.load(open('$state_file')); print(d.get('interval_hours',0))" 2>/dev/null || echo "0")

  # Check if tmux session exists
  if tmux has-session -t "$name" 2>/dev/null; then
    # Get the shell PID inside the tmux pane
    local pane_pid
    pane_pid=$(tmux list-panes -t "$name" -F '#{pane_pid}' 2>/dev/null | head -1)
    # Check if timeout or claude is still a child of that shell
    if [ -n "$pane_pid" ] && ps --ppid "$pane_pid" -o args --no-headers 2>/dev/null | grep -q "timeout.*claude"; then
      log "$name: still running, skipping"
      return
    else
      log "$name: tmux session stale (pipeline finished), cleaning up"
      tmux kill-session -t "$name" 2>/dev/null
    fi
  fi

  # Skip if interval is null/0 (disabled pipeline)
  if [ "$interval" = "0" ] || [ "$interval" = "null" ] || [ "$interval" = "None" ]; then
    log "$name: disabled (interval=0), skipping"
    return
  fi

  # Check if due
  last_run=$(python3 -c "import json; d=json.load(open('$state_file')); print(d.get('last_run',''))" 2>/dev/null || echo "")

  # Helper: write last_run=NOW to state.json and launch the pipeline
  launch_pipeline() {
    python3 -c "
import json, datetime
p = '$state_file'
with open(p) as f: d = json.load(f)
d['last_run'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
with open(p, 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null
    bash "$run_script"
  }

  if [ -z "$last_run" ] || [ "$last_run" = "null" ]; then
    log "$name: never run before, launching now"
    launch_pipeline
    return
  fi

  # Calculate if enough time has passed.
  # Support fractional hours (e.g. 2.5) from state.json.
  local last_epoch interval_seconds next_epoch
  last_epoch=$(date -d "$last_run" +%s 2>/dev/null || echo "0")
  interval_seconds=$(python3 -c "import math; v=float('$interval'); print(max(0, int(v*3600)))" 2>/dev/null || echo "0")
  next_epoch=$((last_epoch + interval_seconds))

  if [ "$interval_seconds" -le 0 ]; then
    log "$name: disabled (interval_seconds=$interval_seconds), skipping"
    return
  fi

  if [ "$EPOCH" -ge "$next_epoch" ]; then
    log "$name: due (last=$last_run, interval=${interval}h), launching"
    launch_pipeline
  else
    local remaining=$(( (next_epoch - EPOCH) / 60 ))
    log "$name: not due yet (${remaining}min remaining)"
  fi
}

# Check for completed pipeline results and notify via mailbox
check_results() {
  for result_file in "$LOG_DIR"/*.result; do
    [ -f "$result_file" ] || continue

    local pipeline status
    pipeline=$(python3 -c "import json; d=json.load(open('$result_file')); print(d.get('pipeline','unknown'))" 2>/dev/null || echo "unknown")
    status=$(python3 -c "import json; d=json.load(open('$result_file')); print(d.get('status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")

    log "Result found: $pipeline=$status"

    # Send to Aoi mailbox
    $MAIL_BIN send \
      --from "aoi" \
      --to "aoi" \
      --type "task_result" \
      --subject "$pipeline completed: $status" \
      --body "{\"pipeline\":\"$pipeline\",\"status\":\"$status\",\"file\":\"$result_file\"}" \
      2>/dev/null || log "WARNING: mailbox send failed"

    mv "$result_file" "${result_file}.processed"
  done
}

# Main
log "=== heartbeat tick ==="
check_results
check_pipeline "github-pr"
check_pipeline "blog-maintenance"
log "=== heartbeat done ==="
