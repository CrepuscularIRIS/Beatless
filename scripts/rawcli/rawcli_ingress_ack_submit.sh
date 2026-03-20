#!/usr/bin/env bash
set -euo pipefail

# rawcli_ingress_ack_submit.sh
# First writes an immediate ACK artifact, then submits to dispatch queue when executor_tool is set.
#
# Usage:
#   rawcli_ingress_ack_submit.sh "REQUEST_TEXT" [OWNER_AGENT] [EXECUTOR_TOOL] [TASK_ID] [TIMEOUT_OVERRIDE]

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
REPORT_ACK_DIR="/home/yarizakurahime/claw/Report/acks"
INGRESS_EVENTS="$BEATLESS/metrics/ingress-events.jsonl"
ROUTER="$SCRIPTS/route_task.sh"
DISPATCH_SUBMIT="$SCRIPTS/dispatch_submit.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"REQUEST_TEXT\" [OWNER_AGENT] [EXECUTOR_TOOL] [TASK_ID] [TIMEOUT_OVERRIDE]" >&2
  exit 2
fi

REQUEST_TEXT="$1"
OWNER_AGENT="${2:-}"
EXECUTOR_TOOL="${3:-}"
TASK_ID="${4:-BT-RAWCLI-$(date +%Y%m%d-%H%M%S)-$RANDOM}"
TIMEOUT_OVERRIDE="${5:-}"

mkdir -p "$REPORT_ACK_DIR" "$BEATLESS/metrics" "$BEATLESS/logs"

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
    "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" "$TIMEOUT_OVERRIDE" >/dev/null
  else
    "$DISPATCH_SUBMIT" "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$REQUEST_TEXT" >/dev/null
  fi
  QUEUE_STATE="queued"
else
  QUEUE_STATE="accepted_no_executor"
fi

printf 'ACK_RECEIVED task_id=%s owner_agent=%s executor_tool=%s state=%s ack_file=%s\n' \
  "$TASK_ID" "${OWNER_AGENT:-}" "${EXECUTOR_TOOL:-}" "$QUEUE_STATE" "$ACK_FILE"
