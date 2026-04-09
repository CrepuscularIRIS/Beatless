#!/usr/bin/env bash
# notify-user.sh — push a message to the user's StepFun app via OpenClaw broadcast.
#
# Usage: notify-user.sh "<message text>" [--dry-run]
#
# Called by Lacia (or any main agent) via the `exec` tool when they want to
# push a notification to the user's chat app. Verified to work against
# account=default, target=me on 2026-04-09.
#
# Exit codes: 0 ok, 1 usage, 2 push failed.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: notify-user.sh '<message>' [--dry-run]" >&2
  exit 1
fi

MSG="$1"
shift || true
DRY=""
if [ "${1:-}" = "--dry-run" ]; then DRY="--dry-run"; fi

cd /home/yarizakurahime/claw

OUTPUT=$(./openclaw-local message broadcast \
  --targets me \
  --message "$MSG" \
  --account default \
  $DRY 2>&1)

if echo "$OUTPUT" | grep -q "Broadcast complete (1/1 succeeded"; then
  echo "notify-user: ok"
  exit 0
else
  echo "notify-user: FAILED" >&2
  echo "$OUTPUT" | tail -10 >&2
  exit 2
fi
