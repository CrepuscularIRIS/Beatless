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
SCRIPTS="$BEATLESS/scripts"
SESSION="${SESSION_NAME:-beatless-v2}"
DISPATCH_WIN="dispatch"
DISPATCH_MAX_PARALLEL="${DISPATCH_MAX_PARALLEL:-4}"
RETRY_TIMEOUT_MAX="${RETRY_TIMEOUT_MAX:-1}"
RETRY_NETWORK_MAX="${RETRY_NETWORK_MAX:-2}"
RETRY_RUNTIME_MAX="${RETRY_RUNTIME_MAX:-1}"
RETRY_BACKOFF_BASE_SEC="${RETRY_BACKOFF_BASE_SEC:-2}"
RETRY_BACKOFF_CAP_SEC="${RETRY_BACKOFF_CAP_SEC:-20}"
LOG="$BEATLESS/logs/hook-loop.log"
LOCK_DIR="$BEATLESS/locks"
LOCK_FILE="$LOCK_DIR/dispatch-hook-loop.lock"
IDEMPOTENT_DIR="$RESULTS/.idempotent"

mkdir -p "$RESULTS" "$REPORT" "$BEATLESS/logs" "$METRICS_DIR" "$REPORT/acks" "$LOCK_DIR" "$IDEMPOTENT_DIR"
touch "$QUEUE"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] dispatch_hook_loop already running, exiting." >> "$LOG"
  exit 0
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

validate_parallel_limit() {
  if ! [[ "$DISPATCH_MAX_PARALLEL" =~ ^[0-9]+$ ]] || [[ "$DISPATCH_MAX_PARALLEL" -lt 1 ]]; then
    DISPATCH_MAX_PARALLEL=4
  fi
}

validate_retry_limits() {
  local key value
  for key in RETRY_TIMEOUT_MAX RETRY_NETWORK_MAX RETRY_RUNTIME_MAX RETRY_BACKOFF_BASE_SEC RETRY_BACKOFF_CAP_SEC; do
    value="${!key:-}"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
      export "$key"=0
    fi
  done
  if [[ "$RETRY_BACKOFF_BASE_SEC" -lt 1 ]]; then
    RETRY_BACKOFF_BASE_SEC=1
  fi
  if [[ "$RETRY_BACKOFF_CAP_SEC" -lt "$RETRY_BACKOFF_BASE_SEC" ]]; then
    RETRY_BACKOFF_CAP_SEC="$RETRY_BACKOFF_BASE_SEC"
  fi
}

idempotent_key_hash() {
  local task_id="$1"
  local run_id="$2"
  local phase="$3"
  local key="${run_id:-_}:${task_id}:${phase:-_}"
  printf '%s' "$key" | sha256sum | awk '{print $1}'
}

idempotent_state_file() {
  local task_id="$1"
  local run_id="$2"
  local phase="$3"
  local key_hash
  key_hash="$(idempotent_key_hash "$task_id" "$run_id" "$phase")"
  echo "$IDEMPOTENT_DIR/${key_hash}.state"
}

check_idempotent_success() {
  local task_id="$1"
  local run_id="$2"
  local phase="$3"
  local state_file
  state_file="$(idempotent_state_file "$task_id" "$run_id" "$phase")"
  if [[ -f "$state_file" ]] && [[ "$(cat "$state_file" 2>/dev/null || true)" == "success" ]]; then
    return 0
  fi
  return 1
}

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

count_running_tasks() {
  python3 - "$RESULTS" <<'PY'
import json
import pathlib
import sys

results = pathlib.Path(sys.argv[1])
count = 0
for path in results.glob("*.json"):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if row.get("status") == "running":
        count += 1
print(count)
PY
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

get_tool_requires_tty() {
  local tool_id="$1"
  python3 - "$TOOL_POOL" "$tool_id" <<'PY'
import sys, yaml
from pathlib import Path
pool = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
tool = (pool.get("tools") or {}).get(sys.argv[2]) or {}
print("true" if tool.get("requires_tty", True) else "false")
PY
}

process_line() {
  local line="$1"
  local task_id tool_id prompt timeout_override expect_regex expect_exact_line model_override run_id phase trace_id submitted_at
  local requested_tool_id budget_gate budget_result

  if ! echo "$line" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'task_id' in d and 'executor_tool' in d and 'prompt' in d" >/dev/null 2>&1; then
    log "WARN: skip malformed queue line"
    return
  fi
  task_id=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['task_id'])")
  tool_id=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['executor_tool'])")
  requested_tool_id="$tool_id"
  prompt=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['prompt'])")
  timeout_override=$(echo "$line" | python3 -c "import json,sys; v=json.load(sys.stdin).get('timeout_override'); print(v if v else '')")
  expect_regex=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('expect_regex') or ''))")
  expect_exact_line=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('expect_exact_line') or ''))")
  model_override=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('model_override') or ''))")
  run_id=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('run_id') or ''))")
  phase=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('phase') or ''))")
  trace_id=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('trace_id') or ''))")
  submitted_at=$(echo "$line" | python3 -c "import json,sys; print((json.load(sys.stdin).get('submitted_at') or ''))")
  if [[ -z "$trace_id" ]]; then
    trace_id="trace-${task_id}"
  fi

  if [[ -n "$run_id" ]] && [[ "$task_id" != "$run_id" && "$task_id" != "$run_id"-* ]]; then
    log "ERROR: run_id mismatch for $task_id (run_id=$run_id)"
    echo "{\"task_id\":\"$task_id\",\"trace_id\":\"$trace_id\",\"run_id\":\"$run_id\",\"phase\":\"$phase\",\"status\":\"failed\",\"error\":\"run_id_mismatch\",\"failure_type\":\"run_id_mismatch\",\"finished_at\":\"$(date -Iseconds)\"}" > "$RESULTS/$task_id.json"
    printf '{"ts":"%s","task_id":"%s","trace_id":"%s","run_id":"%s","phase":"%s","tool":"%s","status":"failed","exit_code":2,"failure_type":"run_id_mismatch"}\n' "$(date -Iseconds)" "$task_id" "$trace_id" "$run_id" "$phase" "$tool_id" >> "$EVENTS_FILE"
    return
  fi

  if check_idempotent_success "$task_id" "$run_id" "$phase"; then
    log "SKIP (idempotent success): $task_id phase=${phase:-_}"
    printf '{"ts":"%s","task_id":"%s","trace_id":"%s","run_id":"%s","phase":"%s","tool":"%s","status":"skipped","reason":"idempotent_success"}\n' \
      "$(date -Iseconds)" "$task_id" "$trace_id" "$run_id" "$phase" "$tool_id" >> "$EVENTS_FILE"
    return
  fi

  # P1 budget gate: enforce Anthropic daily limits with deterministic downgrade path.
  budget_gate="$SCRIPTS/budget_gate.sh"
  if [[ ! -x "$budget_gate" && -x "$SCRIPTS/rawcli/budget_gate.sh" ]]; then
    budget_gate="$SCRIPTS/rawcli/budget_gate.sh"
  fi
  if [[ -x "$budget_gate" ]]; then
    budget_result=""
    if budget_result=$(bash "$budget_gate" "$tool_id" 2>/dev/null); then
      [[ -n "$budget_result" ]] && tool_id="$budget_result"
    else
      if [[ -n "$budget_result" ]]; then
        tool_id="$budget_result"
      fi
      log "BUDGET_DOWNGRADE: task_id=$task_id requested=$requested_tool_id selected=$tool_id"
    fi
  fi

  local cmd
  cmd=$(get_tool_cmd "$tool_id" 2>/dev/null) || {
    log "ERROR: unknown tool $tool_id for $task_id"
    echo "{\"task_id\":\"$task_id\",\"trace_id\":\"$trace_id\",\"run_id\":\"$run_id\",\"phase\":\"$phase\",\"status\":\"failed\",\"error\":\"unknown_tool: $tool_id\",\"finished_at\":\"$(date -Iseconds)\"}" > "$RESULTS/$task_id.json"
    printf '{"ts":"%s","task_id":"%s","trace_id":"%s","run_id":"%s","phase":"%s","tool":"%s","status":"failed","exit_code":127,"failure_type":"unknown_tool"}\n' "$(date -Iseconds)" "$task_id" "$trace_id" "$run_id" "$phase" "$tool_id" >> "$EVENTS_FILE"
    return
  }
  if [[ -n "$model_override" && "$tool_id" == claude_*_cli ]]; then
    cmd="$cmd --model $model_override"
  fi

  local timeout_s prompt_mode requires_tty
  if [[ -n "$timeout_override" ]]; then
    timeout_s="$timeout_override"
  else
    timeout_s=$(get_tool_timeout "$tool_id")
  fi
  prompt_mode=$(get_tool_prompt_mode "$tool_id")
  requires_tty=$(get_tool_requires_tty "$tool_id")

  local out_file="$REPORT/${task_id}-cli-output.md"
  local result_file="$RESULTS/$task_id.json"
  local events_file="$EVENTS_FILE"
  local expect_regex_b64 expect_exact_line_b64 prompt_b64
  expect_regex_b64="$(printf '%s' "$expect_regex" | base64 -w0)"
  expect_exact_line_b64="$(printf '%s' "$expect_exact_line" | base64 -w0)"
  prompt_b64="$(printf '%s' "$prompt" | base64 -w0)"

  log "DISPATCH: $task_id -> $tool_id (trace_id=$trace_id phase=${phase:-_} timeout ${timeout_s}s)"

  # Write initial status
  echo "{\"task_id\":\"$task_id\",\"trace_id\":\"$trace_id\",\"run_id\":\"$run_id\",\"phase\":\"$phase\",\"status\":\"running\",\"tool\":\"$tool_id\",\"submitted_at\":\"$submitted_at\",\"started_at\":\"$(date -Iseconds)\"}" > "$result_file"

  # Create tmux pane and execute
  # Use a wrapper script to capture exit code properly
  local wrapper="/tmp/beatless-dispatch-${task_id}.sh"
  cat > "$wrapper" <<WRAPPER
#!/usr/bin/env bash
set -euo pipefail
cd /home/yarizakurahime/claw
echo "# CLI Output: $task_id" > "$out_file"
echo "trace_id: $trace_id" >> "$out_file"
echo "tool: $tool_id" >> "$out_file"
echo "phase: ${phase:-_}" >> "$out_file"
echo "started: \$(date -Iseconds)" >> "$out_file"
echo "---" >> "$out_file"
start_epoch=\$(date +%s)
PROMPT_B64="$prompt_b64"
PROMPT="\$(printf '%s' "\$PROMPT_B64" | base64 -d)"
EXPECT_REGEX="\$(printf '%s' "$expect_regex_b64" | base64 -d)"
EXPECT_EXACT_LINE="\$(printf '%s' "$expect_exact_line_b64" | base64 -d)"

classify_failure() {
  local exit_code="\$1"
  local target_file="\$2"
  if [[ "\$exit_code" -eq 124 || "\$exit_code" -eq 137 || "\$exit_code" -eq 143 ]]; then
    echo "timeout"
    return
  fi
  if grep -Eiq "api key|unauthorized|forbidden|authentication|login required|invalid token|access denied" "\$target_file"; then
    echo "auth_error"
  elif grep -Eiq "No such file|command not found|not found" "\$target_file"; then
    echo "missing_binary"
  elif grep -Eiq "unknown option|invalid option|Usage:|config profile .* not found|unknown argument" "\$target_file"; then
    echo "cli_argument_error"
  elif grep -Eiq "rate limit|too many requests|http[^0-9]*429|http[^0-9]*5[0-9][0-9]|temporarily unavailable|econnreset|econnrefused|enotfound|eai_again|network|socket hang up|connection reset|connection refused" "\$target_file"; then
    echo "network_error"
  else
    echo "runtime_error"
  fi
}

extract_provider_error_code() {
  local target_file="\$1"
  local hint
  hint="\$(grep -Eio 'HTTP[^0-9]*[45][0-9]{2}|rate limit|too many requests|unauthorized|forbidden|econnreset|econnrefused|enotfound|eai_again' "\$target_file" | head -n1 || true)"
  hint="\${hint// /_}"
  hint="\${hint//[^A-Za-z0-9_]/_}"
  echo "\${hint^^}"
}

resolve_retry_budget() {
  local failure_type="\$1"
  case "\$failure_type" in
    timeout)
      echo "$RETRY_TIMEOUT_MAX"
      ;;
    network_error)
      echo "$RETRY_NETWORK_MAX"
      ;;
    runtime_error)
      echo "$RETRY_RUNTIME_MAX"
      ;;
    *)
      echo 0
      ;;
  esac
}

attempt=1
max_attempts=1
final_status="failed"
final_failure_type=""
final_validation_error=""
final_provider_error_code=""
final_ec=1

while true; do
  echo "attempt: \$attempt" >> "$out_file"
  echo "attempt_started: \$(date -Iseconds)" >> "$out_file"
  set +e
  if [[ "$prompt_mode" == "positional" ]]; then
    timeout --kill-after=10s ${timeout_s}s $cmd "\$PROMPT" >> "$out_file" 2>&1
    ec=\$?
  else
    timeout --kill-after=10s ${timeout_s}s $cmd -p "\$PROMPT" >> "$out_file" 2>&1
    ec=\$?
  fi
  set -e
  final_ec="\$ec"

  if [[ "\$ec" -eq 0 ]]; then
    validation_error=""
    if [[ -n "\$EXPECT_REGEX" ]] && ! grep -Eq "\$EXPECT_REGEX" "$out_file"; then
      validation_error="expect_regex_not_matched"
    fi
    if [[ -z "\$validation_error" ]] && [[ -n "\$EXPECT_EXACT_LINE" ]] && ! grep -Fxq "\$EXPECT_EXACT_LINE" "$out_file"; then
      validation_error="expect_exact_line_not_matched"
    fi
    if [[ -n "\$validation_error" ]]; then
      final_status="failed"
      final_failure_type="output_validation_failed"
      final_validation_error="\$validation_error"
      break
    fi
    final_status="success"
    final_failure_type=""
    break
  fi

  failure_type="\$(classify_failure "\$ec" "$out_file")"
  retry_budget="\$(resolve_retry_budget "\$failure_type")"
  max_attempts=\$((retry_budget + 1))
  final_failure_type="\$failure_type"
  final_provider_error_code="\$(extract_provider_error_code "$out_file")"
  if [[ "\$attempt" -le "\$retry_budget" ]]; then
    sleep_sec=\$(( $RETRY_BACKOFF_BASE_SEC * (2 ** (attempt - 1)) ))
    if [[ "\$sleep_sec" -gt "$RETRY_BACKOFF_CAP_SEC" ]]; then
      sleep_sec="$RETRY_BACKOFF_CAP_SEC"
    fi
    echo "retrying_after_sec: \$sleep_sec (failure_type=\$failure_type attempt=\$attempt/\$max_attempts)" >> "$out_file"
    sleep "\$sleep_sec"
    attempt=\$((attempt + 1))
    continue
  fi

  if [[ "\$failure_type" == "timeout" ]]; then
    final_status="timeout"
  else
    final_status="failed"
  fi
  break
done

end_epoch=\$(date +%s)
duration_sec=\$((end_epoch - start_epoch))
retry_count=\$((attempt - 1))
echo "---" >> "$out_file"
echo "attempts: \$attempt" >> "$out_file"
echo "retry_count: \$retry_count" >> "$out_file"
echo "exit_code: \$final_ec" >> "$out_file"
echo "finished: \$(date -Iseconds)" >> "$out_file"

if [[ "\$final_status" != "success" && -z "\$final_failure_type" ]]; then
  final_failure_type="runtime_error"
fi
finished_at="\$(date -Iseconds)"
FINAL_STATUS="\$final_status" \
FINAL_EXIT_CODE="\$final_ec" \
FINAL_ATTEMPTS="\$attempt" \
FINAL_RETRY_COUNT="\$retry_count" \
FINAL_DURATION_SEC="\$duration_sec" \
FINAL_FAILURE_TYPE="\$final_failure_type" \
FINAL_VALIDATION_ERROR="\$final_validation_error" \
FINAL_PROVIDER_ERROR_CODE="\$final_provider_error_code" \
FINAL_FINISHED_AT="\$finished_at" \
FINAL_TIMEOUT_S="${timeout_s}" \
python3 - <<'PY'
import json
import os
from pathlib import Path

task_id = "$task_id"
trace_id = "$trace_id"
run_id = "$run_id"
phase = "$phase"
tool_id = "$tool_id"
status = os.environ.get("FINAL_STATUS", "")
exit_code = int(os.environ.get("FINAL_EXIT_CODE", "1"))
attempts = int(os.environ.get("FINAL_ATTEMPTS", "1"))
retry_count = int(os.environ.get("FINAL_RETRY_COUNT", "0"))
duration_sec = int(os.environ.get("FINAL_DURATION_SEC", "0"))
failure_type = os.environ.get("FINAL_FAILURE_TYPE", "").strip()
validation_error = os.environ.get("FINAL_VALIDATION_ERROR", "").strip()
provider_error_code = os.environ.get("FINAL_PROVIDER_ERROR_CODE", "").strip()
finished_at = os.environ.get("FINAL_FINISHED_AT", "")
timeout_s = os.environ.get("FINAL_TIMEOUT_S", "")
submitted_at = "$submitted_at"
started_at = ""
try:
    started_at = json.loads(Path("$result_file").read_text(encoding="utf-8")).get("started_at", "")
except Exception:
    started_at = ""

def parse_iso(v: str) -> float | None:
    if not v:
        return None
    try:
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return __import__("datetime").datetime.fromisoformat(v).timestamp()
    except Exception:
        return None

queue_lag_ms = 0
st = parse_iso(started_at)
sb = parse_iso(submitted_at)
if st is not None and sb is not None and st >= sb:
    queue_lag_ms = int((st - sb) * 1000)

result = {
    "task_id": task_id,
    "trace_id": trace_id,
    "run_id": run_id,
    "phase": phase,
    "executor_tool": tool_id,
    "requested_executor_tool": "$requested_tool_id",
    "status": status,
    "exit_code": exit_code,
    "attempts": attempts,
    "retry_count": retry_count,
    "duration_sec": duration_sec,
    "output_path": "$out_file",
    "output_file": "$out_file",
    "submitted_at": submitted_at,
    "started_at": started_at,
    "queue_lag_ms": queue_lag_ms,
    "finished_at": finished_at,
}
if failure_type:
    result["failure_type"] = failure_type
if validation_error:
    result["validation_error"] = validation_error
if provider_error_code:
    result["provider_error_code"] = provider_error_code
if status == "timeout" and timeout_s:
    result["error"] = f"exceeded {timeout_s}s"

event = {
    "ts": finished_at,
    "task_id": task_id,
    "trace_id": trace_id,
    "run_id": run_id,
    "phase": phase,
    "tool": tool_id,
    "status": status,
    "exit_code": exit_code,
    "duration_sec": duration_sec,
    "queue_lag_ms": queue_lag_ms,
    "attempts": attempts,
    "retry_count": retry_count,
}
if failure_type:
    event["failure_type"] = failure_type
if validation_error:
    event["validation_error"] = validation_error
if provider_error_code:
    event["provider_error_code"] = provider_error_code

Path("$result_file").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
with Path("$events_file").open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(event, ensure_ascii=False) + "\\n")

# Update idempotent state keyed by (run_id, task_id, phase)
import hashlib
idem_key = f"{run_id or '_'}:{task_id}:{phase or '_'}"
idem_hash = hashlib.sha256(idem_key.encode("utf-8")).hexdigest()
idem_dir = Path("$IDEMPOTENT_DIR")
idem_dir.mkdir(parents=True, exist_ok=True)
(idem_dir / f"{idem_hash}.state").write_text(status, encoding="utf-8")
PY
WRAPPER
  chmod +x "$wrapper"

  # Split a new pane in dispatch window
  if [[ "$requires_tty" != "true" ]]; then
    log "DISPATCH: $task_id running non-tty background mode"
    nohup bash "$wrapper" >/dev/null 2>&1 < /dev/null &
  elif tmux has-session -t "$SESSION" 2>/dev/null; then
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

validate_parallel_limit
validate_retry_limits
log "hook-loop started, watching $QUEUE (max_parallel=${DISPATCH_MAX_PARALLEL})"

# Watch for new lines
tail -n 0 -F "$QUEUE" 2>/dev/null | while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  [[ "$line" == "#"* ]] && continue
  while true; do
    running_now="$(count_running_tasks)"
    if [[ "$running_now" -lt "$DISPATCH_MAX_PARALLEL" ]]; then
      break
    fi
    sleep 1
  done
  process_line "$line" &
done
