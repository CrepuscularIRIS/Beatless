#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/init_task_os.py >/dev/null

TS="$(date +%s)"
PASS_JOB="closedloop-pass-${TS}"
FAIL_JOB="closedloop-fail-${TS}"

python3 - <<PY
import json
from pathlib import Path

root = Path("$ROOT")
example = json.loads((root / "schemas" / "task_contract.example.json").read_text(encoding="utf-8"))

pass_contract = dict(example)
pass_contract["id"] = "$PASS_JOB"
pass_contract["goal"] = "Closed-loop success path smoke test"
pass_contract["editable_paths"] = ["Beatless/docs"]
pass_contract["acceptance"] = {
    "must_pass": ["true"],
    "smoke": ["state reaches done"]
}
pass_contract["budget"] = {
    "max_iterations": 8,
    "max_wall_clock_minutes": 60,
    "max_retry": 1
}

fail_contract = dict(example)
fail_contract["id"] = "$FAIL_JOB"
fail_contract["goal"] = "Closed-loop failure path smoke test"
fail_contract["editable_paths"] = ["Beatless/docs"]
fail_contract["acceptance"] = {
    "must_pass": ["false"],
    "smoke": ["state reaches escalated"]
}
fail_contract["budget"] = {
    "max_iterations": 8,
    "max_wall_clock_minutes": 60,
    "max_retry": 2
}

for job_id, contract in [("$PASS_JOB", pass_contract), ("$FAIL_JOB", fail_contract)]:
    job_dir = root / "runtime" / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "contract.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

MOCK_WORKER=1 \
TASK_OS_COMMAND_CWD="$(cd "$ROOT/.." && pwd)" \
ORCHESTRATION_MODE=harness \
bash -lc '
for i in $(seq 1 30); do
  OUT=$(python3 scripts/task_os_scheduler.py --drain 2>&1 || true)
  echo "$OUT"
  if ! echo "$OUT" | grep -q "scheduler lock busy"; then
    exit 0
  fi
  sleep 1
done
echo "scheduler lock busy after retries" >&2
exit 1
'

python3 - <<PY
import json
from pathlib import Path

root = Path("$ROOT")
pass_state = json.loads((root / "runtime" / "jobs" / "$PASS_JOB" / "state.json").read_text(encoding="utf-8"))
fail_state = json.loads((root / "runtime" / "jobs" / "$FAIL_JOB" / "state.json").read_text(encoding="utf-8"))

if pass_state.get("status") != "done":
    raise SystemExit(f"PASS path failed: expected done, got {pass_state.get('status')}")
if fail_state.get("status") != "escalated":
    raise SystemExit(f"FAIL path failed: expected escalated, got {fail_state.get('status')}")

hints = (fail_state.get("last_checkpoint") or {}).get("mode_hints") or []
if not hints:
    raise SystemExit("FAIL path expected mode_hints after repeated verify failure")

print("S-CL1 PASS success path -> done")
print("S-CL2 PASS failure path -> escalated with hints")
PY

echo "Closed-loop smoke PASS: $PASS_JOB / $FAIL_JOB"
