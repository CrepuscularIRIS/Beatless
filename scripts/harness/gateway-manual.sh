#!/usr/bin/env bash
set -euo pipefail

PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
LOG="${HOME}/.openclaw/logs/openclaw-gateway-manual.out"
PIDF="${HOME}/.openclaw/logs/openclaw-gateway-manual.pid"
OPENCLAW_BIN="${HOME}/claw/openclaw-local"

mkdir -p "${HOME}/.openclaw/logs"

status() {
  local pid=""
  if [[ -f "$PIDF" ]]; then
    pid="$(cat "$PIDF" 2>/dev/null || true)"
  fi
  if ss -lntp 2>/dev/null | rg -q "$PORT"; then
    echo "running (listener on port $PORT)"
  elif [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "running pid=$pid"
  else
    echo "stopped"
  fi
  ss -lntp | rg "$PORT" || true
}

start() {
  local pid=""
  if ss -lntp 2>/dev/null | rg -q "$PORT"; then
    echo "already running (listener on port $PORT)"
    return 0
  fi
  if [[ -f "$PIDF" ]]; then
    pid="$(cat "$PIDF" 2>/dev/null || true)"
  fi
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "already running pid=$pid"
    return 0
  fi
  pkill -f "openclaw-gateway|openclaw gateway --port $PORT" || true
  sleep 1
  setsid "$OPENCLAW_BIN" gateway run --port "$PORT" --bind loopback --force > "$LOG" 2>&1 < /dev/null &
  pid=$!
  echo "$pid" > "$PIDF"
  sleep 2
  echo "started pid=$pid"
  curl -sS -m 5 "http://127.0.0.1:${PORT}/health" || true
}

stop() {
  local pid=""
  if [[ -f "$PIDF" ]]; then
    pid="$(cat "$PIDF" 2>/dev/null || true)"
  fi
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    sleep 1
  fi
  pkill -f "openclaw-gateway|openclaw-local gateway run --port $PORT|openclaw gateway run --port $PORT" || true
  echo "stopped"
}

logs() {
  tail -n 120 "$LOG"
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac
