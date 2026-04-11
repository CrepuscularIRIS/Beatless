#!/usr/bin/env bash
# session-watcher.sh — Monitor pipeline tmux sessions and clean up zombie processes
#
# Usage: bash session-watcher.sh [--once]
#
# Problem: AgentTeam teammates may not close when the main team leader exits.
# This script:
# 1. Watches for .result files (written when pipeline finishes)
# 2. After pipeline completion, kills any orphaned claude/codex/gemini processes
# 3. Reports result via mailbox to Aoi
#
# Run alongside pipelines:
#   nohup bash session-watcher.sh >> ~/.hermes/shared/logs/session-watcher.log 2>&1 &

set -euo pipefail

LOG_DIR="$HOME/.hermes/shared/logs"
MAIL_BIN="node $HOME/.hermes/shared/scripts/mail.mjs"
POLL_INTERVAL=30  # seconds
ONCE="${1:-}"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

cleanup_zombies() {
  local pipeline="$1"
  local log_file="$2"

  log "Checking for orphaned processes after $pipeline completion..."

  # Find claude processes spawned by our pipeline that are still running
  # AgentTeam teammates show up as separate claude processes
  local orphans
  orphans=$(ps aux | grep -E 'claude.*--print|codex.*--approval|gemini.*-p' | grep -v grep | grep -v "session-watcher" || true)

  if [ -n "$orphans" ]; then
    log "Found potential orphaned processes:"
    echo "$orphans" | while read -r line; do
      local pid
      pid=$(echo "$line" | awk '{print $2}')
      local cmd
      cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
      log "  PID=$pid CMD=$cmd"
    done

    # Only kill processes that started AFTER the pipeline started
    # Be conservative — only kill claude --print processes, not interactive sessions
    ps aux | grep -E 'claude --print' | grep -v grep | grep -v "session-watcher" | awk '{print $2}' | while read -r pid; do
      # Check if this is a teammate process (child of our pipeline)
      local ppid
      ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
      # If parent is init (1) or gone, it's orphaned
      if [ "$ppid" = "1" ] || [ -z "$ppid" ]; then
        log "  Killing orphaned claude process PID=$pid (parent=$ppid)"
        kill "$pid" 2>/dev/null || true
      fi
    done

    # Also kill any orphaned codex/gemini CLI processes
    for cli in codex gemini; do
      pgrep -f "^$cli " 2>/dev/null | while read -r pid; do
        local ppid
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        if [ "$ppid" = "1" ] || [ -z "$ppid" ]; then
          log "  Killing orphaned $cli process PID=$pid"
          kill "$pid" 2>/dev/null || true
        fi
      done
    done
  else
    log "No orphaned processes found."
  fi
}

process_result() {
  local result_file="$1"

  log "Processing result: $result_file"

  local pipeline status exit_code
  pipeline=$(grep -oP '"pipeline"\s*:\s*"\K[^"]+' "$result_file" || echo "unknown")
  status=$(grep -oP '"status"\s*:\s*"\K[^"]+' "$result_file" || echo "UNKNOWN")
  exit_code=$(grep -oP '"exit_code"\s*:\s*\K[0-9]+' "$result_file" || echo "-1")

  log "$pipeline completed: status=$status exit=$exit_code"

  # Cleanup zombie processes
  cleanup_zombies "$pipeline" "$result_file"

  # Notify via mailbox
  $MAIL_BIN send \
    --from "watcher" \
    --to "aoi" \
    --type "task_result" \
    --subject "$pipeline: $status" \
    --body "{\"pipeline\":\"$pipeline\",\"status\":\"$status\",\"exit_code\":$exit_code,\"result_file\":\"$result_file\"}" \
    2>/dev/null || log "WARNING: Failed to send mailbox notification"

  # Mark result as processed
  mv "$result_file" "${result_file}.processed"
  log "Result processed and archived."
}

log "session-watcher started (poll_interval=${POLL_INTERVAL}s)"

while true; do
  # Check for unprocessed .result files
  for result_file in "$LOG_DIR"/*.result; do
    [ -f "$result_file" ] || continue
    process_result "$result_file"
  done

  [ "$ONCE" = "--once" ] && break
  sleep "$POLL_INTERVAL"
done
