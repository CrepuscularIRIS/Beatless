#!/usr/bin/env bash
# cron-driver.sh — v2.1: Heartbeat pipeline scheduler
#
# Called from cron daemon every 30 minutes.
# Runs heartbeat-driver.sh which checks pipeline schedules and launches due pipelines.
#
# Usage: */30 * * * * /home/yarizakurahime/claw/.openclaw/hermes/scripts/cron-driver.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/home/yarizakurahime/claw/.openclaw/hermes/logs"
mkdir -p "$LOG_DIR"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[$TS] cron-driver v2.1: running heartbeat"

bash "$SCRIPT_DIR/heartbeat-driver.sh" >> "$LOG_DIR/heartbeat.log" 2>&1

echo "[$TS] cron-driver v2.1: heartbeat complete"
