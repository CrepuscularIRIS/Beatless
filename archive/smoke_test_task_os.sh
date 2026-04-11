#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/init_task_os.py >/dev/null

JOB_ID="smoke-$(date +%s)"
JOB_DIR="$ROOT/runtime/jobs/$JOB_ID"
mkdir -p "$JOB_DIR"

python3 - <<'PY'
import json
import time
from pathlib import Path

root = Path.cwd()
example = json.loads((root / "schemas" / "task_contract.example.json").read_text(encoding="utf-8"))
job_id = f"smoke-{int(time.time())}"
example["id"] = job_id
example["goal"] = "Smoke validation of Beatless Task OS W1 scheduler direct-pass mode."
example["editable_paths"] = ["Beatless/docs", "Beatless/scripts"]
job_dir = root / "runtime" / "jobs" / job_id
job_dir.mkdir(parents=True, exist_ok=True)
(job_dir / "contract.json").write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
print(job_id)
PY

LATEST_JOB="$(ls -1 runtime/jobs | sort | tail -n 1)"
CONTRACT_PATH="runtime/jobs/$LATEST_JOB/contract.json"

python3 scripts/validate_task_contract.py "$CONTRACT_PATH"
ORCHESTRATION_MODE=legacy python3 scripts/task_os_scheduler.py --once

STATE_PATH="runtime/jobs/$LATEST_JOB/state.json"
python3 - <<'PY'
import json
from pathlib import Path

state_path = Path("runtime/jobs") / sorted([p.name for p in Path("runtime/jobs").iterdir() if p.is_dir()])[-1] / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if state.get("status") != "done":
    raise SystemExit(f"smoke failed: expected done, got {state.get('status')}")
print(f"smoke passed: {state_path}")
PY
