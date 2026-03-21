#!/usr/bin/env bash
set -euo pipefail

# pce_cycle.sh
# Minimal Planner-Critic-Executor pipeline over TASKS.yaml.
# Usage: pce_cycle.sh [TASK_ID] [EXEC_MODE]

BEATLESS="${HOME}/.openclaw/beatless"
TASKS="$BEATLESS/TASKS.yaml"
SCRIPTS="$BEATLESS/scripts"
REPORT_DIR="/home/yarizakurahime/claw/Report/pce"
DEFAULT_EXEC_MODE="${2:-daily}"
TASK_ID_ARG="${1:-}"

mkdir -p "$REPORT_DIR" "$BEATLESS/metrics"

if [[ ! -f "$TASKS" ]]; then
  echo "TASKS.yaml not found: $TASKS" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 required" >&2
  exit 1
fi

readarray -t PICK < <(python3 - "$TASKS" "$TASK_ID_ARG" "$DEFAULT_EXEC_MODE" <<'PY'
import json
import pathlib
import sys

try:
    import yaml
except Exception:
    print("ERR")
    raise

tasks_path = pathlib.Path(sys.argv[1])
arg_task_id = sys.argv[2].strip()
exec_mode = sys.argv[3].strip() or "daily"

data = yaml.safe_load(tasks_path.read_text(encoding='utf-8')) or {}
queues = data.get('queues') or {}
ready_ids = []
for item in (queues.get('ready') or []):
    if isinstance(item, dict):
        tid = item.get('id')
    else:
        tid = item
    if tid:
        ready_ids.append(str(tid))

by_id = {}
for t in (data.get('tasks') or []):
    if isinstance(t, dict) and t.get('id'):
        by_id[str(t['id'])] = t

pick_id = arg_task_id or (ready_ids[0] if ready_ids else "")
if not pick_id:
    print("NO_TASK")
    raise SystemExit(0)

t = by_id.get(pick_id, {'id': pick_id, 'title': pick_id, 'description': '', 'type': 'maintenance', 'priority': 'medium'})
owner_agent = str(t.get('owner_agent') or t.get('assigned_agent') or 'methode')
executor_tool = str(t.get('executor_tool') or '')
if not executor_tool:
    typ = str(t.get('type') or 'maintenance')
    if typ in {'research','explore'}:
        executor_tool = 'codex_cli'
    else:
        executor_tool = 'claude_generalist_cli'

run_id = f"PCE-{pick_id}-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}"
trace_id = f"trace-{run_id}"

print(pick_id)
print(t.get('title') or pick_id)
print((t.get('description') or '').replace('\n','\\n'))
print(owner_agent)
print(executor_tool)
print(exec_mode)
print(run_id)
print(trace_id)
PY
)

if [[ "${PICK[0]:-}" == "NO_TASK" ]]; then
  echo "pce_cycle: no ready task"
  exit 0
fi

TASK_ID="${PICK[0]}"
TASK_TITLE="${PICK[1]}"
TASK_DESC="${PICK[2]//\\n/$'\n'}"
OWNER_AGENT="${PICK[3]}"
EXECUTOR_TOOL="${PICK[4]}"
EXEC_MODE="${PICK[5]}"
RUN_ID="${PICK[6]}"
TRACE_ID="${PICK[7]}"

PLAN_TASK_ID="${RUN_ID}-plan"
EXEC_TASK_ID="${RUN_ID}-execute"
CRITIC_TASK_ID="${RUN_ID}-critic"

PLAN_PROMPT="You are planner for task ${TASK_ID}. Output short plan with 3-5 steps. Include line: PCE_PLAN_OK"
EXEC_PROMPT="Task ${TASK_ID}: ${TASK_TITLE}\n\n${TASK_DESC}\n\nDeliver concise result and evidence pointers."
CRITIC_PROMPT="Review execution quality for task ${TASK_ID}. Check if result is coherent and actionable. Output exactly one line starting with CRITIC_VERDICT:" 

# move task to in_progress (best-effort)
python3 - "$TASKS" "$TASK_ID" "$EXEC_MODE" <<'PY' || true
import pathlib, sys
try:
    import yaml
except Exception:
    raise SystemExit(0)
p = pathlib.Path(sys.argv[1])
task_id = sys.argv[2]
exec_mode = sys.argv[3]
d = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
queues = d.setdefault('queues', {})
ready = queues.get('ready') or []
new_ready = []
for item in ready:
    tid = item.get('id') if isinstance(item, dict) else item
    if str(tid) != task_id:
        new_ready.append(item)
queues['ready'] = new_ready
in_progress = queues.get('in_progress') or []
if task_id not in [x.get('id') if isinstance(x, dict) else x for x in in_progress]:
    in_progress.append(task_id)
queues['in_progress'] = in_progress
for t in d.get('tasks') or []:
    if isinstance(t, dict) and str(t.get('id')) == task_id:
        t['status'] = 'in_progress'
        t['exec_mode'] = exec_mode
        t['run_id'] = t.get('run_id') or ''
        t['iteration'] = int(t.get('iteration', 0) or 0) + 1
p.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
PY

"$SCRIPTS/dispatch_submit.sh" "$PLAN_TASK_ID" "lacia" "claude_architect_opus_cli" "$PLAN_PROMPT" "" "PCE_PLAN_OK" "" "" "$RUN_ID" "plan" "$TRACE_ID" >/dev/null || true
"$SCRIPTS/dispatch_submit.sh" "$EXEC_TASK_ID" "$OWNER_AGENT" "$EXECUTOR_TOOL" "$EXEC_PROMPT" "" "" "" "" "$RUN_ID" "execute" "$TRACE_ID" >/dev/null
"$SCRIPTS/dispatch_submit.sh" "$CRITIC_TASK_ID" "satonus" "gemini_cli" "$CRITIC_PROMPT" "300" "CRITIC_VERDICT:" "" "" "$RUN_ID" "critic" "$TRACE_ID" >/dev/null || true

cat > "$REPORT_DIR/${RUN_ID}.md" <<RPT
# PCE Cycle

- task_id: $TASK_ID
- run_id: $RUN_ID
- trace_id: $TRACE_ID
- owner_agent: $OWNER_AGENT
- executor_tool: $EXECUTOR_TOOL
- exec_mode: $EXEC_MODE
- submitted:
  - $PLAN_TASK_ID
  - $EXEC_TASK_ID
  - $CRITIC_TASK_ID
RPT

echo "pce_cycle: queued run_id=$RUN_ID task_id=$TASK_ID"
