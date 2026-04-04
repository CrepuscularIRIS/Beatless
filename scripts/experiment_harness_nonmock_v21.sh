#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/init_task_os.py >/dev/null

TS="$(date +%s)"
PASS_COUNT=4
FAIL_COUNT=3

python3 - <<PY
import json
from pathlib import Path

root = Path("$ROOT")
example = json.loads((root / "schemas" / "task_contract.example.json").read_text(encoding="utf-8"))

pass_count = $PASS_COUNT
fail_count = $FAIL_COUNT
prefix = f"expnm-{int($TS)}"

created = {"pass": [], "fail": []}

for i in range(pass_count):
    cid = f"{prefix}-pass-{i+1}"
    c = dict(example)
    c["id"] = cid
    c["goal"] = f"Non-mock pass path experiment job {i+1}"
    c["editable_paths"] = ["Beatless/docs"]
    c["acceptance"] = {
        "must_pass": ["test -d Beatless", "true"],
        "smoke": ["state reaches done"]
    }
    c["budget"] = {"max_iterations": 12, "max_wall_clock_minutes": 60, "max_retry": 1}

    j = root / "runtime" / "jobs" / cid
    (j / "artifacts").mkdir(parents=True, exist_ok=True)
    (j / "contract.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (j / "artifacts" / "changed_files.txt").write_text("Beatless/docs/AUTO_IMPL_PASS.md\n", encoding="utf-8")
    (j / "artifacts" / "codex_result.md").write_text(
        "## Review complete\nNo blocking issues found. Minor style suggestions only.\n",
        encoding="utf-8",
    )
    handoff = j / "handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    for name in ["CHANGELOG.md", "PR_DESCRIPTION.md", "ROLLBACK.md"]:
        (handoff / name).write_text(f"# {name}\n\nNon-mock experiment artifact.\n", encoding="utf-8")
    created["pass"].append(cid)

for i in range(fail_count):
    cid = f"{prefix}-fail-{i+1}"
    c = dict(example)
    c["id"] = cid
    c["goal"] = f"Non-mock fail path experiment job {i+1}"
    c["editable_paths"] = ["Beatless/docs"]
    c["acceptance"] = {
        "must_pass": ["false"],
        "smoke": ["state reaches escalated"]
    }
    c["budget"] = {"max_iterations": 12, "max_wall_clock_minutes": 60, "max_retry": 2}

    j = root / "runtime" / "jobs" / cid
    (j / "artifacts").mkdir(parents=True, exist_ok=True)
    (j / "contract.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (j / "artifacts" / "changed_files.txt").write_text("Beatless/docs/AUTO_IMPL_FAIL.md\n", encoding="utf-8")
    created["fail"].append(cid)

(root / "runtime" / "state" / f"experiment_nonmock_{prefix}.json").write_text(
    json.dumps(created, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(prefix)
PY

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
state_dir = root / "runtime" / "state"
manifest = sorted(state_dir.glob("experiment_nonmock_expnm-*.json"))[-1]
created = json.loads(manifest.read_text(encoding="utf-8"))

errors = []

for jid in created["pass"]:
    sp = root / "runtime" / "jobs" / jid / "state.json"
    st = json.loads(sp.read_text(encoding="utf-8"))
    if st.get("status") != "done":
        errors.append(f"{jid}: expected done, got {st.get('status')}")
    if st.get("current_iteration", 0) < 5:
        errors.append(f"{jid}: expected >=5 iterations, got {st.get('current_iteration')}")

for jid in created["fail"]:
    sp = root / "runtime" / "jobs" / jid / "state.json"
    st = json.loads(sp.read_text(encoding="utf-8"))
    if st.get("status") != "escalated":
        errors.append(f"{jid}: expected escalated, got {st.get('status')}")
    hints = (st.get("last_checkpoint") or {}).get("mode_hints") or []
    if not hints:
        errors.append(f"{jid}: expected mode_hints after repeated failures")

if errors:
    print("EXPERIMENT FAIL")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)

print("EXPERIMENT PASS")
print("Pass jobs:", len(created["pass"]))
print("Fail jobs:", len(created["fail"]))
print("Manifest:", manifest)
PY
