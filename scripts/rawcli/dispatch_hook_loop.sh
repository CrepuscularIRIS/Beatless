#!/usr/bin/env bash
set -euo pipefail

# dispatch_hook_loop.sh — tmux hook 循环：监听 dispatch queue，创建 pane 执行 CLI
# 位置: ~/.openclaw/beatless/scripts/dispatch_hook_loop.sh

BEATLESS="${HOME}/.openclaw/beatless"
QUEUE="$BEATLESS/dispatch-queue.jsonl"
RESULTS="$BEATLESS/dispatch-results"
REPORT="/home/yarizakurahime/claw/Report"
TOOL_POOL="$BEATLESS/TOOL_POOL.yaml"
METRICS_DIR="$BEATLESS/metrics"
EVENTS_FILE="$METRICS_DIR/dispatch-events.jsonl"
SESSION="${SESSION_NAME:-beatless-v2}"
DISPATCH_WIN="dispatch"
LOG="$BEATLESS/logs/hook-loop.log"

mkdir -p "$RESULTS" "$REPORT" "$BEATLESS/logs" "$METRICS_DIR" "$REPORT/acks"
touch "$QUEUE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

ensure_dispatch_window() {
  if ! tmux list-windows -t "$SESSION" -F '#W' 2>/dev/null | rg -q "^${DISPATCH_WIN}\$"; then
    tmux new-window -t "$SESSION" -n "$DISPATCH_WIN" -c "/home/yarizakurahime/claw" >/dev/null 2>&1 || true
  fi
}

cleanup_dead_panes() {
  tmux list-panes -t "$SESSION:$DISPATCH_WIN" -F '#{pane_dead} #{pane_id}' 2>/dev/null \
    | awk '$1 == 1 {print $2}' \
    | while read -r pane_id; do
        tmux kill-pane -t "$pane_id" >/dev/null 2>&1 || true
      done
}

# Load tool commands from TOOL_POOL.yaml
get_tool_cmd() {
  local tool_id="$1"
  python3 - "$TOOL_POOL" "$tool_id" <<'PY'
import sys, yaml
from pathlib import Path
pool = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
tool = (pool.get("tools") or {}).get(sys.argv[2])
if not tool:
    sys.exit(1)
cmd = tool["command"]
args = tool.get("args", [])
print(f"{cmd} {' '.join(args)}")
PY
}

get_tool_timeout() {
  local tool_id="$1"
  python3 - "$TOOL_POOL" "$tool_id" <<'PY'
import sys, yaml
from pathlib import Path
pool = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
tool = (pool.get("tools") or {}).get(sys.argv[2])
print(tool.get("timeout_seconds", 1800) if tool else 1800)
PY
}

get_tool_prompt_mode() {
  local tool_id="$1"
  python3 - "$TOOL_POOL" "$tool_id" <<'PY'
import sys, yaml
from pathlib import Path
pool = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
tool = (pool.get("tools") or {}).get(sys.argv[2]) or {}
print(tool.get("prompt_mode", "dash_p"))
PY
}

process_line() {
  local line="$1"
  local task_id tool_id prompt timeout_override

  task_id=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['task_id'])")
  tool_id=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['executor_tool'])")
  prompt=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['prompt'])")
  timeout_override=$(echo "$line" | python3 -c "import json,sys; v=json.load(sys.stdin).get('timeout_override'); print(v if v else '')")

  local cmd
  cmd=$(get_tool_cmd "$tool_id" 2>/dev/null) || {
    log "ERROR: unknown tool $tool_id for $task_id"
    echo "{\"task_id\":\"$task_id\",\"status\":\"failed\",\"error\":\"unknown_tool: $tool_id\",\"finished_at\":\"$(date -Iseconds)\"}" > "$RESULTS/$task_id.json"
    printf '{"ts":"%s","task_id":"%s","tool":"%s","status":"failed","exit_code":127,"failure_type":"unknown_tool"}\n' "$(date -Iseconds)" "$task_id" "$tool_id" >> "$EVENTS_FILE"
    return
  }

  local timeout_s prompt_mode
  if [[ -n "$timeout_override" ]]; then
    timeout_s="$timeout_override"
  else
    timeout_s=$(get_tool_timeout "$tool_id")
  fi
  prompt_mode=$(get_tool_prompt_mode "$tool_id")

  local out_file="$REPORT/${task_id}-cli-output.md"
  local result_file="$RESULTS/$task_id.json"
  local events_file="$EVENTS_FILE"

  log "DISPATCH: $task_id -> $tool_id (timeout ${timeout_s}s)"

  # Write initial status
  echo "{\"task_id\":\"$task_id\",\"status\":\"running\",\"tool\":\"$tool_id\",\"started_at\":\"$(date -Iseconds)\"}" > "$result_file"

  # Create tmux pane and execute
  # Use a wrapper script to capture exit code properly
  local wrapper="/tmp/beatless-dispatch-${task_id}.sh"
  cat > "$wrapper" <<WRAPPER
#!/usr/bin/env bash
cd /home/yarizakurahime/claw
echo "# CLI Output: $task_id" > "$out_file"
echo "tool: $tool_id" >> "$out_file"
echo "started: \$(date -Iseconds)" >> "$out_file"
echo "---" >> "$out_file"
start_epoch=\$(date +%s)
if [[ "$prompt_mode" == "positional" ]]; then
  timeout ${timeout_s}s $cmd "$prompt" 2>&1 | tee -a "$out_file"
else
  timeout ${timeout_s}s $cmd -p "$prompt" 2>&1 | tee -a "$out_file"
fi
ec=\$?
end_epoch=\$(date +%s)
duration_sec=\$((end_epoch - start_epoch))
echo "---" >> "$out_file"
echo "exit_code: \$ec" >> "$out_file"
echo "finished: \$(date -Iseconds)" >> "$out_file"
if [ \$ec -eq 0 ]; then
  echo '{"task_id":"$task_id","status":"success","exit_code":0,"output_path":"$out_file","finished_at":"'"\$(date -Iseconds)"'"}' > "$result_file"
  printf '{"ts":"%s","task_id":"%s","tool":"%s","status":"success","exit_code":0,"duration_sec":%s}\n' "\$(date -Iseconds)" "$task_id" "$tool_id" "\$duration_sec" >> "$events_file"
elif [ \$ec -eq 124 ]; then
  echo '{"task_id":"$task_id","status":"timeout","error":"exceeded ${timeout_s}s","finished_at":"'"\$(date -Iseconds)"'"}' > "$result_file"
  printf '{"ts":"%s","task_id":"%s","tool":"%s","status":"timeout","exit_code":124,"duration_sec":%s,"failure_type":"timeout"}\n' "\$(date -Iseconds)" "$task_id" "$tool_id" "\$duration_sec" >> "$events_file"
else
  failure_type="runtime_error"
  if grep -Eiq "api key|unauthorized|forbidden|auth|login required|authentication" "$out_file"; then
    failure_type="auth_error"
  elif grep -Eiq "No such file|not found|command not found" "$out_file"; then
    failure_type="missing_binary"
  elif grep -Eiq "unknown option|invalid option|config profile .* not found|Usage:" "$out_file"; then
    failure_type="cli_argument_error"
  fi
  echo '{"task_id":"$task_id","status":"failed","exit_code":'\$ec',"failure_type":"'\$failure_type'","output_path":"$out_file","finished_at":"'"\$(date -Iseconds)"'"}' > "$result_file"
  printf '{"ts":"%s","task_id":"%s","tool":"%s","status":"failed","exit_code":%s,"duration_sec":%s,"failure_type":"%s"}\n' "\$(date -Iseconds)" "$task_id" "$tool_id" "\$ec" "\$duration_sec" "\$failure_type" >> "$events_file"
fi
WRAPPER
  chmod +x "$wrapper"

  # Split a new pane in dispatch window
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    ensure_dispatch_window
    cleanup_dead_panes
    if ! tmux split-window -d -t "$SESSION:$DISPATCH_WIN" -h "bash $wrapper; sleep 2" 2>/dev/null; then
      local live_pane
      live_pane=$(tmux list-panes -t "$SESSION:$DISPATCH_WIN" -F '#{pane_dead} #{pane_id}' 2>/dev/null | awk '$1 == 0 {print $2; exit}')
      if [[ -n "$live_pane" ]]; then
        tmux send-keys -t "$live_pane" "bash $wrapper" C-m || true
      else
        log "WARN: no live pane in dispatch window, running $task_id in background"
        bash "$wrapper" &
      fi
    fi
  else
    log "WARN: tmux session $SESSION not found, running in background"
    bash "$wrapper" &
  fi
}

log "hook-loop started, watching $QUEUE"

# Watch for new lines
tail -n 0 -F "$QUEUE" 2>/dev/null | while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  [[ "$line" == "#"* ]] && continue
  process_line "$line" &
done
