#!/usr/bin/env bash
set -euo pipefail

# dispatch_submit.sh
# Usage:
#   dispatch_submit.sh TASK_ID OWNER_AGENT EXECUTOR_TOOL PROMPT [TIMEOUT_OVERRIDE]

BEATLESS="${HOME}/.openclaw/beatless"
QUEUE="$BEATLESS/dispatch-queue.jsonl"

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 TASK_ID OWNER_AGENT EXECUTOR_TOOL PROMPT [TIMEOUT_OVERRIDE]" >&2
  exit 2
fi

TASK_ID="$1"
OWNER_AGENT="$2"
EXECUTOR_TOOL="$3"
PROMPT="$4"
TIMEOUT_OVERRIDE="${5:-}"

case "$OWNER_AGENT" in
  lacia|kouka|methode|satonus|snowdrop) ;;
  *) echo "invalid owner_agent: $OWNER_AGENT" >&2; exit 2 ;;
esac

case "$EXECUTOR_TOOL" in
  codex_cli|claude_opus_cli|claude_sonnet_cli|gemini_cli) ;;
  *) echo "invalid executor_tool: $EXECUTOR_TOOL" >&2; exit 2 ;;
esac

mkdir -p "$BEATLESS/dispatch-results" "$BEATLESS/logs"
touch "$QUEUE"

python3 - "$TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$PROMPT" "$TIMEOUT_OVERRIDE" >> "$QUEUE" <<'PY'
import json,sys
obj = {
  "task_id": sys.argv[1],
  "owner_agent": sys.argv[2],
  "executor_tool": sys.argv[3],
  "prompt": sys.argv[4],
  "timeout_override": int(sys.argv[5]) if sys.argv[5].isdigit() else None,
}
print(json.dumps(obj, ensure_ascii=False))
PY

echo "queued: $TASK_ID -> $EXECUTOR_TOOL"
