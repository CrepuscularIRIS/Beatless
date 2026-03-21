#!/usr/bin/env bash
set -euo pipefail

# receipt_schema_gate.sh
# Validate final user-facing receipt format before delivery.
#
# Usage:
#   receipt_schema_gate.sh TASK_ID RECEIPT_FILE [RUN_ID] [TRACE_ID]

BEATLESS="${HOME}/.openclaw/beatless"
EVENTS_FILE="$BEATLESS/metrics/receipt-gate-events.jsonl"

if [[ $# -lt 2 || $# -gt 4 ]]; then
  echo "Usage: $0 TASK_ID RECEIPT_FILE [RUN_ID] [TRACE_ID]" >&2
  exit 2
fi

TASK_ID="$1"
RECEIPT_FILE="$2"
RUN_ID="${3:-}"
TRACE_ID="${4:-${TRACE_ID:-}}"

mkdir -p "$BEATLESS/metrics"

fail() {
  local reason="$1"
  printf '{"ts":"%s","task_id":"%s","trace_id":"%s","status":"fail","reason":"%s","receipt_file":"%s"}\n' \
    "$(date -Iseconds)" "$TASK_ID" "$TRACE_ID" "$reason" "$RECEIPT_FILE" >> "$EVENTS_FILE"
  echo "RECEIPT_SCHEMA_FAIL task_id=$TASK_ID reason=$reason"
  exit 1
}

pass() {
  printf '{"ts":"%s","task_id":"%s","trace_id":"%s","status":"pass","receipt_file":"%s"}\n' \
    "$(date -Iseconds)" "$TASK_ID" "$TRACE_ID" "$RECEIPT_FILE" >> "$EVENTS_FILE"
  echo "RECEIPT_SCHEMA_PASS task_id=$TASK_ID"
}

[[ -f "$RECEIPT_FILE" ]] || fail "receipt_file_missing"
[[ -s "$RECEIPT_FILE" ]] || fail "receipt_file_empty"

line_count="$(wc -l < "$RECEIPT_FILE" | tr -d ' ')"
if [[ "$line_count" -gt 20 ]]; then
  fail "too_many_lines"
fi

actual_task_id="$(awk -F':' '/^task_id:[[:space:]]*/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' "$RECEIPT_FILE")"
[[ -n "$actual_task_id" ]] || fail "task_id_missing"
[[ "$actual_task_id" == "$TASK_ID" ]] || fail "task_id_mismatch"
if [[ -n "$RUN_ID" ]] && [[ "$TASK_ID" != "$RUN_ID" && "$TASK_ID" != "$RUN_ID"-* ]]; then
  fail "task_id_not_in_run_id"
fi

grep -Eq '^VERDICT:[[:space:]]*(PASS|FAIL|PARTIAL)$' "$RECEIPT_FILE" || fail "verdict_missing_or_invalid"
grep -Eq '^DONE:[[:space:]]*$' "$RECEIPT_FILE" || fail "done_section_missing"
grep -Eq '^(证据|evidence_path|dispatch_result_path|cli_output_path|evidence_root):' "$RECEIPT_FILE" || fail "evidence_field_missing"

if [[ -z "$TRACE_ID" ]]; then
  TRACE_ID="$(awk -F':' '/^trace_id:[[:space:]]*/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' "$RECEIPT_FILE" || true)"
fi

if grep -Eiq '(Conversation info|message_id|sender_id|我需要|让我|用户要求|翻译反馈|正在执行)' "$RECEIPT_FILE"; then
  fail "debug_or_internal_text_detected"
fi

# Block stack traces / shell error residue.
if grep -Eiq '(Traceback \(most recent call last\)|TimeoutError|SyntaxError:|ModuleNotFoundError:|command not found|Permission denied|ECONNREFUSED|ECONNRESET)' "$RECEIPT_FILE"; then
  fail "raw_stacktrace_or_shell_error_detected"
fi

# Block internal path leakage.
if grep -Eq '(/home/yarizakurahime/|\.openclaw/|dispatch-results/|dispatch-queue\.jsonl)' "$RECEIPT_FILE"; then
  fail "internal_path_leaked"
fi

# If run_id is provided, all referenced task_id fields must stay inside run scope.
if [[ -n "$RUN_ID" ]]; then
  while IFS= read -r ref_task_id; do
    if [[ "$ref_task_id" != "$RUN_ID" && "$ref_task_id" != "$RUN_ID"-* ]]; then
      fail "cross_run_task_reference:$ref_task_id"
    fi
  done < <(grep -oE 'task_id:[[:space:]]*[A-Za-z0-9._:-]+' "$RECEIPT_FILE" | awk -F': *' '{print $2}' | sort -u)
fi

if grep -q '```' "$RECEIPT_FILE"; then
  fail "markdown_code_fence_not_allowed"
fi

pass
