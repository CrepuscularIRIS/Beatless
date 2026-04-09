#!/usr/bin/env bash
set -u
LOG=/home/yarizakurahime/.openclaw/logs/gateway-supervisor.log
GWLOG=/home/yarizakurahime/.openclaw/logs/gateway-live.log
CMD=(/home/yarizakurahime/claw/openclaw-local gateway run --port 18789 --bind loopback --force)

echo "[$(date '+%F %T')] supervisor started" >> "$LOG"
while true; do
  pgrep -f "openclaw-local gateway run --port 18789" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "[$(date '+%F %T')] gateway down, starting..." >> "$LOG"
    nohup "${CMD[@]}" >> "$GWLOG" 2>&1 &
    sleep 5
  fi
  sleep 10
done
