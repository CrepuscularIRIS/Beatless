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
INGRESS_EVENTS="$BEATLESS/metrics/ingress-events.jsonl"
ACK_LEDGER="$BEATLESS/metrics/ack-sent-task-ids.txt"
ACK_LEDGER_LOCK="$BEATLESS/metrics/ack-sent-task-ids.lock"
ROUTER="$SCRIPTS/route_task.sh"
DISPATCH_SUBMIT="$SCRIPTS/dispatch_submit.sh"
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

mkdir -p "$REPORT_ACK_DIR" "$BEATLESS/metrics" "$BEATLESS/logs"
touch "$ACK_LEDGER"

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

if [[ -n "$EXECUTOR_TOOL" ]]; then
  if [[ -n "$TIMEOUT_OVERRIDE" ]]; then
    "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" "$TIMEOUT_OVERRIDE" "$EXPECT_REGEX" "$EXPECT_EXACT_LINE" "$MODEL_OVERRIDE" "" "" "$TRACE_ID" >/dev/null
  else
    "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" "" "$EXPECT_REGEX" "$EXPECT_EXACT_LINE" "$MODEL_OVERRIDE" "" "" "$TRACE_ID" >/dev/null
  fi
  QUEUE_STATE="queued"
else
  QUEUE_STATE="accepted_no_executor"
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
