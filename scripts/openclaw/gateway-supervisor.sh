#!/usr/bin/env bash
set -u
LOG=/home/yarizakurahime/.openclaw/logs/gateway-supervisor.log
GWLOG=/home/yarizakurahime/.openclaw/logs/gateway-live.log
CMD=(/home/yarizakurahime/claw/openclaw-local gateway run --port 18789 --bind loopback --force)

echo "[$(date '+%F %T')] supervisor started" >> "$LOG"
while true; do
  # Use port listener check instead of pgrep — the actual process renames itself to "openclaw-gateway"
  # after bootstrap, so matching on the launch command is unreliable.
  if ss -tlnp 2>/dev/null | grep -q ":18789 "; then
    sleep 30
    continue
  fi
  echo "[$(date '+%F %T')] gateway down (no listener on 18789), starting..." >> "$LOG"
  # Kill any orphan gateway procs before relaunch to avoid duplicate bind attempts
  pkill -f "openclaw-gateway" 2>/dev/null || true
  sleep 1
  nohup "${CMD[@]}" >> "$GWLOG" 2>&1 &
  # Give it time to bind the port before we check again
  sleep 15
done
