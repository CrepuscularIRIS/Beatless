#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[S1] single_lane"
python3 scripts/resolve_trigger.py \
  --prompt "修复 OpenRoom/src/mcp.ts 中的类型错误" \
  --contract schemas/task_contract.example.json \
  | grep -q "single_lane"
echo "S1 PASS"

echo "[S2] ralph_loop"
python3 scripts/resolve_trigger.py \
  --prompt "反复迭代修复 MCP 桥接直到测试通过" \
  --contract schemas/task_contract.example.json \
  | grep -q "ralph_loop"
echo "S2 PASS"

echo "[S3] agent_teams"
python3 scripts/resolve_trigger.py \
  --prompt "并行开发三个模块并迭代直到通过" \
  --contract schemas/task_contract.example.json \
  | grep -q "agent_teams"
echo "S3 PASS"

echo "[S4] build_mode_selector"
python3 scripts/build_mode_selector.py \
  --file-count 15 --dir-count 4 --has-test true --has-iter false \
  | grep -q "agent_teams"
echo "S4 PASS"

echo "[S7] codex parser FAIL"
echo -e "## Findings\n- severity: blocking\n- issue: SQL injection" \
  | python3 scripts/parse_codex_result.py \
  | grep -q '"verdict": "FAIL"'
echo "S7 PASS"

echo "[S8] codex parser PASS"
echo -e "## Review complete\nNo blocking issues found." \
  | python3 scripts/parse_codex_result.py \
  | grep -q '"verdict": "PASS"'
echo "S8 PASS"

echo "[S9] scheduler dry-run legacy"
ORCHESTRATION_MODE=legacy python3 scripts/task_os_scheduler.py --dry-run \
  | grep -q "legacy"
echo "S9 PASS"

echo "[S10] scheduler integrated trigger_event"
JOB_DIR="runtime/jobs/job-smoke-v21-trigger"
rm -rf "$JOB_DIR"
mkdir -p "$JOB_DIR"
cp schemas/task_contract.example.json "$JOB_DIR/contract.json"
python3 scripts/task_os_scheduler.py --once >/tmp/smoke_scheduler_once.log
if grep -q "scheduler lock busy" /tmp/smoke_scheduler_once.log; then
  for i in $(seq 1 20); do
    python3 scripts/task_os_scheduler.py --once >/tmp/smoke_scheduler_once.log
    if ! grep -q "scheduler lock busy" /tmp/smoke_scheduler_once.log; then
      break
    fi
    sleep 1
  done
fi
test -f "$JOB_DIR/iteration/1/trigger_event.json"
jq -e '.normalized_stage == "plan"' "$JOB_DIR/iteration/1/trigger_event.json" >/dev/null
jq -e '.resolution.selected[0].id != null' "$JOB_DIR/iteration/1/trigger_event.json" >/dev/null
echo "S10 PASS"
rm -rf "$JOB_DIR"

echo "All trigger smoke tests passed."
