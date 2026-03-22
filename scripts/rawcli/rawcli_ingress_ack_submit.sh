#!/usr/bin/env bash
set -euo pipefail

# rawcli_ingress_ack_submit.sh
# First writes an immediate ACK artifact, then submits to dispatch queue when executor_tool is set.
#
# Usage:
#   rawcli_ingress_ack_submit.sh "REQUEST_TEXT" [OWNER_AGENT] [EXECUTOR_TOOL] [TASK_ID] [TIMEOUT_OVERRIDE] [EXPECT_REGEX] [EXPECT_EXACT_LINE] [MODEL_OVERRIDE] [TRACE_ID]

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
EVENT_PHRASES="$BEATLESS/templates/event-phrases.yaml"
EVENT_SIGNAL="$SCRIPTS/event_signal_emit.sh"
REPORT_ACK_DIR="/home/yarizakurahime/claw/Report/acks"
REPORT_DIR="/home/yarizakurahime/claw/Report"
INGRESS_EVENTS="$BEATLESS/metrics/ingress-events.jsonl"
DISPATCH_EVENTS="$BEATLESS/metrics/dispatch-events.jsonl"
RESULTS_DIR="$BEATLESS/dispatch-results"
ACK_LEDGER="$BEATLESS/metrics/ack-sent-task-ids.txt"
ACK_LEDGER_LOCK="$BEATLESS/metrics/ack-sent-task-ids.lock"
ROUTER="$SCRIPTS/route_task.sh"
DISPATCH_SUBMIT="$SCRIPTS/dispatch_submit.sh"
CAPTURE_SCRIPT="/home/yarizakurahime/.openclaw/workspace-lacia/skills/visual-proof/scripts/capture_url.sh"
CAPTURE_DEFAULT_URL="${CAPTURE_DEFAULT_URL:-https://example.com}"
CAPTURE_BLOG_URL="${CAPTURE_BLOG_URL:-http://127.0.0.1:3000}"
CAPTURE_BLOG_ALT_URL="${CAPTURE_BLOG_ALT_URL:-http://127.0.0.1:4321}"
CAPTURE_AUTO_START_BLOG_DEV="${CAPTURE_AUTO_START_BLOG_DEV:-true}"
BLOG_BOOT_PID=""
INGRESS_PHRASE_ENABLED="${INGRESS_PHRASE_ENABLED:-true}"
ACK_STDOUT_MODE="${ACK_STDOUT_MODE:-once}"
START_MS="$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"REQUEST_TEXT\" [OWNER_AGENT] [EXECUTOR_TOOL] [TASK_ID] [TIMEOUT_OVERRIDE] [EXPECT_REGEX] [EXPECT_EXACT_LINE] [MODEL_OVERRIDE] [TRACE_ID]" >&2
  exit 2
fi

REQUEST_TEXT="$1"
OWNER_AGENT="${2:-}"
EXECUTOR_TOOL="${3:-}"
TASK_ID="${4:-E2E-$(date +%Y%m%d-%H%M%S)}"
TIMEOUT_OVERRIDE="${5:-}"
EXPECT_REGEX="${6:-}"
EXPECT_EXACT_LINE="${7:-}"
MODEL_OVERRIDE="${8:-}"
TRACE_ID="${9:-}"

if [[ -z "$TRACE_ID" ]]; then
  TRACE_ID="trace-${TASK_ID}-$(date +%s)"
fi

mkdir -p "$REPORT_ACK_DIR" "$REPORT_DIR" "$RESULTS_DIR" "$BEATLESS/metrics" "$BEATLESS/logs"
touch "$ACK_LEDGER"
touch "$DISPATCH_EVENTS"

if [[ -z "$OWNER_AGENT" || -z "$EXECUTOR_TOOL" ]]; then
  ROUTE_OUT="$($ROUTER "$REQUEST_TEXT")"
  OWNER_AGENT="$(printf '%s\n' "$ROUTE_OUT" | awk -F= '/^owner_agent=/{print $2}')"
  EXECUTOR_TOOL="$(printf '%s\n' "$ROUTE_OUT" | awk -F= '/^executor_tool=/{print $2}')"
fi

ACK_TIME="$(date -Iseconds)"
ACK_FILE="$REPORT_ACK_DIR/${TASK_ID}-ack.md"

cat > "$ACK_FILE" <<ACK
# Ingress ACK

- time: $ACK_TIME
- task_id: $TASK_ID
- owner_agent: ${OWNER_AGENT:-unknown}
- executor_tool: ${EXECUTOR_TOOL:-none}
- status: RECEIVED
- note: request accepted; execution has been queued if executor_tool is set.
ACK

printf '{"ts":"%s","task_id":"%s","owner_agent":"%s","executor_tool":"%s","event":"ingress_ack"}\n' \
  "$ACK_TIME" "$TASK_ID" "${OWNER_AGENT:-}" "${EXECUTOR_TOOL:-}" >> "$INGRESS_EVENTS"

is_screenshot_request() {
  local normalized
  normalized="$(printf '%s' "$REQUEST_TEXT" | tr '[:upper:]' '[:lower:]')"
  [[ "$normalized" =~ (截图|截屏|screenshot|screen[[:space:]_-]*shot|screen[[:space:]_-]*capture) ]]
}

extract_first_url() {
  python3 - "$REQUEST_TEXT" <<'PY'
import re
import sys
text = sys.argv[1]
m = re.search(r'https?://[^\s)]+', text, flags=re.IGNORECASE)
print(m.group(0) if m else "")
PY
}

infer_capture_url() {
  local direct_url normalized
  direct_url="$(extract_first_url)"
  if [[ -n "$direct_url" ]]; then
    echo "$direct_url"
    return
  fi

  normalized="$(printf '%s' "$REQUEST_TEXT" | tr '[:upper:]' '[:lower:]')"
  if [[ "$normalized" =~ (blog|前端|frontend|ui|页面) ]]; then
    if curl -I -sSf --max-time 3 "$CAPTURE_BLOG_URL" >/dev/null 2>&1; then
      echo "$CAPTURE_BLOG_URL"
      return
    fi
    if curl -I -sSf --max-time 3 "$CAPTURE_BLOG_ALT_URL" >/dev/null 2>&1; then
      echo "$CAPTURE_BLOG_ALT_URL"
      return
    fi
    if [[ "$CAPTURE_AUTO_START_BLOG_DEV" == "true" && -f "/home/yarizakurahime/blog/package.json" ]] && command -v pnpm >/dev/null 2>&1; then
      local dev_log dev_pid
      dev_log="/tmp/${TASK_ID}-blog-dev.log"
      (
        cd /home/yarizakurahime/blog
        nohup pnpm dev --host 127.0.0.1 --port 3000 >"$dev_log" 2>&1 &
        echo $! >"/tmp/${TASK_ID}-blog-dev.pid"
      ) || true
      dev_pid="$(cat "/tmp/${TASK_ID}-blog-dev.pid" 2>/dev/null || true)"
      if [[ -n "$dev_pid" ]]; then
        for _ in $(seq 1 20); do
          if curl -I -sSf --max-time 2 "$CAPTURE_BLOG_URL" >/dev/null 2>&1; then
            BLOG_BOOT_PID="$dev_pid"
            echo "$CAPTURE_BLOG_URL"
            return
          fi
          sleep 1
        done
        kill "$dev_pid" >/dev/null 2>&1 || true
      fi
    fi
    if [[ -f "/home/yarizakurahime/blog/dist/client/index.html" ]]; then
      echo "file:///home/yarizakurahime/blog/dist/client/index.html"
      return
    fi
  fi
  echo "$CAPTURE_DEFAULT_URL"
}

run_screenshot_fastpath() {
  local capture_url out_file result_file capture_png err_file status failure_type start_epoch end_epoch duration_sec
  capture_url="$(infer_capture_url)"
  out_file="$REPORT_DIR/${TASK_ID}-cli-output.md"
  result_file="$RESULTS_DIR/${TASK_ID}.json"
  err_file="/tmp/${TASK_ID}-capture.err"
  start_epoch="$(date +%s)"
  status="failed"
  failure_type=""
  capture_png=""

  if [[ ! -x "$CAPTURE_SCRIPT" ]]; then
    failure_type="capture_script_missing"
  else
    if capture_png="$(bash "$CAPTURE_SCRIPT" "$capture_url" "$TASK_ID" "blog-front" 2>"$err_file")"; then
      status="success"
    else
      failure_type="capture_failed"
    fi
  fi

  end_epoch="$(date +%s)"
  duration_sec=$((end_epoch - start_epoch))
  if [[ -n "$BLOG_BOOT_PID" ]]; then
    kill "$BLOG_BOOT_PID" >/dev/null 2>&1 || true
  fi

  {
    echo "# CLI Output: $TASK_ID"
    echo "trace_id: $TRACE_ID"
    echo "tool: local_capture"
    echo "started: $(date -Iseconds -d "@$start_epoch")"
    echo "---"
    if [[ "$status" == "success" ]]; then
      echo "screenshot_path: $capture_png"
      echo "capture_url: $capture_url"
    else
      echo "capture_url: $capture_url"
      echo "capture_error: ${failure_type:-unknown}"
      [[ -s "$err_file" ]] && sed -n '1,30p' "$err_file"
    fi
    echo "---"
    echo "exit_code: $([[ \"$status\" == \"success\" ]] && echo 0 || echo 1)"
    echo "finished: $(date -Iseconds)"
  } > "$out_file"

  export RESULT_FILE="$result_file"
  export EVENTS_FILE="$DISPATCH_EVENTS"
  export TASK_ID
  export TRACE_ID
  export CAPTURE_STATUS="$status"
  export CAPTURE_FAILURE="$failure_type"
  export CAPTURE_OUT="$out_file"
  export CAPTURE_STARTED="$(date -Iseconds -d "@$start_epoch")"
  export CAPTURE_FINISHED="$(date -Iseconds)"
  export CAPTURE_DURATION="$duration_sec"
  export CAPTURE_URL="$capture_url"
  python3 <<'PY'
import json
import os
from pathlib import Path

task_id = os.environ["TASK_ID"]
trace_id = os.environ["TRACE_ID"]
status = os.environ["CAPTURE_STATUS"]
failure = os.environ.get("CAPTURE_FAILURE", "")
result = {
    "task_id": task_id,
    "trace_id": trace_id,
    "status": status,
    "executor_tool": "local_capture",
    "output_path": os.environ["CAPTURE_OUT"],
    "started_at": os.environ["CAPTURE_STARTED"],
    "finished_at": os.environ["CAPTURE_FINISHED"],
    "duration_sec": int(os.environ.get("CAPTURE_DURATION", "0") or 0),
}
if failure:
    result["failure_type"] = failure

event = {
    "ts": os.environ["CAPTURE_FINISHED"],
    "task_id": task_id,
    "trace_id": trace_id,
    "tool": "local_capture",
    "status": status,
    "exit_code": 0 if status == "success" else 1,
    "duration_sec": int(os.environ.get("CAPTURE_DURATION", "0") or 0),
}
if failure:
    event["failure_type"] = failure

Path(os.environ["RESULT_FILE"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
with Path(os.environ["EVENTS_FILE"]).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
PY

  [[ "$status" == "success" ]]
}

QUEUE_STATE="accepted_no_executor"
FASTPATH_DONE="false"

if is_screenshot_request && [[ "${INGRESS_DISABLE_CAPTURE_FASTPATH:-false}" != "true" ]]; then
  OWNER_AGENT="${OWNER_AGENT:-kouka}"
  if run_screenshot_fastpath; then
    EXECUTOR_TOOL="local_capture"
    QUEUE_STATE="captured_direct"
    FASTPATH_DONE="true"
  fi
fi

if [[ "$FASTPATH_DONE" != "true" ]]; then
  if [[ -n "$EXECUTOR_TOOL" ]]; then
    if [[ -n "$TIMEOUT_OVERRIDE" ]]; then
      "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" "$TIMEOUT_OVERRIDE" "$EXPECT_REGEX" "$EXPECT_EXACT_LINE" "$MODEL_OVERRIDE" "" "" "$TRACE_ID" >/dev/null
    else
      "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" "" "$EXPECT_REGEX" "$EXPECT_EXACT_LINE" "$MODEL_OVERRIDE" "" "" "$TRACE_ID" >/dev/null
    fi
    QUEUE_STATE="queued"
  fi
fi

maybe_emit_ingress_phrase() {
  if [[ "$INGRESS_PHRASE_ENABLED" != "true" ]]; then
    return
  fi
  if [[ ! -x "$EVENT_SIGNAL" ]]; then
    return
  fi
  if [[ -z "${FEISHU_TARGET_CHAT_ID:-}" ]]; then
    return
  fi

  local normalized phrase_key hour
  normalized="$(printf '%s' "$REQUEST_TEXT" | tr '[:upper:]' '[:lower:]')"
  phrase_key=""

  if [[ "$normalized" =~ (辛苦|累|疲惫|休息|晚安) ]]; then
    phrase_key="rest"
  elif [[ "$normalized" =~ (你好|在吗|收到|hello|hi) ]]; then
    phrase_key="welcome_back"
  elif [[ "$normalized" =~ (早上好|早安|morning) ]]; then
    phrase_key="morning"
  fi

  if [[ -z "$phrase_key" ]]; then
    hour=$((10#$(date +%H)))
    if [[ "$hour" -ge 22 || "$hour" -lt 6 ]]; then
      phrase_key="closing"
    fi
  fi

  if [[ -n "$phrase_key" ]]; then
    EVENT_SIGNAL_SEND_ENABLED=true FEISHU_TARGET_CHAT_ID="$FEISHU_TARGET_CHAT_ID" \
      "$EVENT_SIGNAL" "smalltalk.${phrase_key}" "" "ok" "0" "0" "$FEISHU_TARGET_CHAT_ID" >/dev/null || true
  fi
}

# Resolve ACK template from event phrases (optional).
ACK_TEXT="${ACK_TEXT:-ACK_RECEIVED}"
ACK_TASK_PREFIX="${ACK_TASK_PREFIX:-task_id: }"
if [[ -f "$EVENT_PHRASES" ]]; then
  readarray -t ACK_TEMPLATE < <(python3 - "$EVENT_PHRASES" <<'PY'
import pathlib
import sys
try:
    import yaml
except Exception:
    print("ACK_RECEIVED")
    print("task_id: ")
    raise SystemExit(0)

path = pathlib.Path(sys.argv[1])
try:
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
except Exception:
    print("ACK_RECEIVED")
    print("task_id: ")
    raise SystemExit(0)

ack_text = "ACK_RECEIVED"
task_prefix = "task_id: "
ack_block = (data.get("ack") or {})
immediate = ack_block.get("immediate") or []
if isinstance(immediate, list) and immediate and isinstance(immediate[0], str):
    value = immediate[0].strip()
    if value:
        ack_text = value

with_task = ack_block.get("with_task_id") or []
if isinstance(with_task, list) and with_task and isinstance(with_task[0], str):
    first_line = with_task[0].splitlines()[0:2]
    if len(first_line) >= 2 and "{task_id}" in first_line[1]:
        task_prefix = first_line[1].replace("{task_id}", "")

print(ack_text)
print(task_prefix)
PY
  )
  if [[ "${#ACK_TEMPLATE[@]}" -ge 2 ]]; then
    [[ -n "${ACK_TEMPLATE[0]}" ]] && ACK_TEXT="${ACK_TEMPLATE[0]}"
    [[ -n "${ACK_TEMPLATE[1]}" ]] && ACK_TASK_PREFIX="${ACK_TEMPLATE[1]}"
  fi
fi

# Strict ACK output contract (no debug prose).
should_emit_ack_stdout() {
  case "$ACK_STDOUT_MODE" in
    always) return 0 ;;
    never) return 1 ;;
    once|*)
      exec 9>"$ACK_LEDGER_LOCK"
      flock 9
      if rg -Fxq "$TASK_ID" "$ACK_LEDGER"; then
        flock -u 9
        return 1
      fi
      printf '%s\n' "$TASK_ID" >> "$ACK_LEDGER"
      flock -u 9
      return 0
      ;;
  esac
}

if should_emit_ack_stdout; then
  printf '%s\n' "$ACK_TEXT"
  printf '%s%s\n' "$ACK_TASK_PREFIX" "$TASK_ID"
fi
maybe_emit_ingress_phrase

END_MS="$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)"
ACK_LATENCY_MS=$((END_MS - START_MS))
printf '{"ts":"%s","task_id":"%s","trace_id":"%s","owner_agent":"%s","executor_tool":"%s","queue_state":"%s","ack_latency_ms":%s,"event":"ingress_complete"}\n' \
  "$(date -Iseconds)" "$TASK_ID" "$TRACE_ID" "${OWNER_AGENT:-}" "${EXECUTOR_TOOL:-}" "$QUEUE_STATE" "$ACK_LATENCY_MS" >> "$INGRESS_EVENTS"
