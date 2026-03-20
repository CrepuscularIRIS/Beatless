#!/usr/bin/env bash
set -euo pipefail

# beatless_tmux_v2.sh - V2 RawCLI tmux session bootstrap

SESSION="${SESSION_NAME:-beatless-v2}"
ROOT="/home/yarizakurahime/claw"
BEATLESS="$HOME/.openclaw/beatless"
OPENCLAW_REPO="$ROOT/openclaw"
RUN_GATEWAY="${1:-}"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "session already exists: $SESSION"
  echo "attach: tmux attach -t $SESSION"
  exit 0
fi

mkdir -p "$ROOT/Report" "$ROOT/Report/acks" "$BEATLESS/dispatch-results" "$BEATLESS/logs" "$BEATLESS/metrics"
touch "$BEATLESS/dispatch-queue.jsonl"

# Window 1: control

tmux new-session -d -s "$SESSION" -n control -c "$ROOT"
tmux set-option -t "$SESSION" -g remain-on-exit on

tmux send-keys -t "$SESSION:control" "echo '[control] Beatless V2 operator shell. Root: $ROOT'" C-m

# Window 2: gateway

tmux new-window -t "$SESSION" -n gateway -c "$OPENCLAW_REPO"
if [[ "$RUN_GATEWAY" == "--run-gateway" ]]; then
  tmux send-keys -t "$SESSION:gateway" "node openclaw.mjs gateway run" C-m
else
  tmux send-keys -t "$SESSION:gateway" "echo '[gateway] use --run-gateway to start. Manual: node openclaw.mjs gateway run'" C-m
fi

# Window 3: dispatch

tmux new-window -t "$SESSION" -n dispatch -c "$ROOT"
tmux send-keys -t "$SESSION:dispatch" "echo '[dispatch] CLI execution area. panes are created by hook loop.'" C-m

# Window 4: hooks

tmux new-window -t "$SESSION" -n hooks -c "$BEATLESS"
tmux send-keys -t "$SESSION:hooks" "SESSION_NAME=$SESSION bash $BEATLESS/scripts/dispatch_hook_loop.sh" C-m

# Window 5: monitor (supervisor + watch)

tmux new-window -t "$SESSION" -n monitor -c "$ROOT"
tmux send-keys -t "$SESSION:monitor" "SESSION_NAME=$SESSION SUPERVISOR_INTERVAL_SEC=20 bash $BEATLESS/scripts/rawcli_supervisor.sh >> $BEATLESS/logs/rawcli-supervisor.log 2>&1 &" C-m
tmux send-keys -t "$SESSION:monitor" "watch -n 15 '$BEATLESS/scripts/rawcli_monitor_snapshot.sh'" C-m

# Prime an initial health+metrics snapshot
SESSION_NAME="$SESSION" bash "$BEATLESS/scripts/rawcli_metrics_rollup.sh" >/dev/null 2>&1 || true
SESSION_NAME="$SESSION" bash "$BEATLESS/scripts/rawcli_healthcheck.sh" >/dev/null 2>&1 || true
SESSION_NAME="$SESSION" bash "$BEATLESS/scripts/rawcli_alert_check.sh" >/dev/null 2>&1 || true

tmux select-window -t "$SESSION:control"

echo "Beatless V2 tmux session created: $SESSION"
echo "Windows: control | gateway | dispatch | hooks | monitor"
echo "Attach: tmux attach -t $SESSION"
