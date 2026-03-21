#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
RESULTS_DIR="$BEATLESS/dispatch-results"
QUEUE_FILE="$BEATLESS/dispatch-queue.jsonl"
TOOL_POOL="$BEATLESS/TOOL_POOL.yaml"
EVENTS_FILE="$BEATLESS/metrics/dispatch-events.jsonl"
GRACE_SEC="${RECONCILE_GRACE_SEC:-30}"

mkdir -p "$BEATLESS/metrics" "$RESULTS_DIR"

python3 - "$RESULTS_DIR" "$QUEUE_FILE" "$TOOL_POOL" "$EVENTS_FILE" "$GRACE_SEC" <<'PY'
import datetime as dt
import json
import pathlib
import subprocess
import sys

try:
    import yaml
except Exception:
    yaml = None

results_dir = pathlib.Path(sys.argv[1])
queue_file = pathlib.Path(sys.argv[2])
tool_pool = pathlib.Path(sys.argv[3])
events_file = pathlib.Path(sys.argv[4])
grace_sec = int(sys.argv[5])

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()

def parse_iso(text: str):
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None

tool_timeout = {}
if yaml is not None and tool_pool.exists():
    try:
        data = yaml.safe_load(tool_pool.read_text(encoding="utf-8")) or {}
        for tool_id, meta in (data.get("tools") or {}).items():
            timeout = meta.get("timeout_seconds", 1800)
            try:
                tool_timeout[tool_id] = int(timeout)
            except Exception:
                tool_timeout[tool_id] = 1800
    except Exception:
        pass

queue_timeout = {}
if queue_file.exists():
    for line in queue_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            row = json.loads(s)
        except Exception:
            continue
        task_id = row.get("task_id")
        if not task_id:
            continue
        timeout_override = row.get("timeout_override")
        tool_id = row.get("executor_tool")
        timeout_s = None
        if isinstance(timeout_override, int) and timeout_override > 0:
            timeout_s = timeout_override
        elif isinstance(tool_id, str):
            timeout_s = tool_timeout.get(tool_id, 1800)
        else:
            timeout_s = 1800
        queue_timeout[task_id] = max(1, int(timeout_s))

try:
    ps_out = subprocess.check_output(["ps", "-eo", "cmd"], text=True, stderr=subprocess.DEVNULL)
except Exception:
    ps_out = ""

now = dt.datetime.now(dt.timezone.utc).astimezone()
reconciled = 0

for path in sorted(results_dir.glob("*.json")):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if row.get("status") != "running":
        continue

    task_id = str(row.get("task_id") or path.stem)
    tool_id = str(row.get("tool") or "")
    trace_id = str(row.get("trace_id") or "")
    started_at = parse_iso(str(row.get("started_at") or ""))
    if started_at is None:
        started_at = now - dt.timedelta(hours=24)

    wrapper_token = f"beatless-dispatch-{task_id}.sh"
    if wrapper_token in ps_out:
        continue

    timeout_s = queue_timeout.get(task_id, tool_timeout.get(tool_id, 1800))
    elapsed = int((now - started_at).total_seconds())
    if elapsed <= timeout_s + grace_sec:
        continue

    out_file = f"/home/yarizakurahime/claw/Report/{task_id}-cli-output.md"
    finished = now_iso()
    new_row = {
        "task_id": task_id,
        "trace_id": trace_id,
        "status": "timeout",
        "error": f"orphaned_running_result_reconciled after {elapsed}s",
        "output_path": out_file,
        "finished_at": finished,
    }
    path.write_text(json.dumps(new_row, ensure_ascii=False), encoding="utf-8")
    events_file.parent.mkdir(parents=True, exist_ok=True)
    with events_file.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": finished,
                    "task_id": task_id,
                    "trace_id": trace_id,
                    "tool": tool_id,
                    "status": "timeout",
                    "exit_code": 124,
                    "duration_sec": elapsed,
                    "failure_type": "orphaned_running_reconciled",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    reconciled += 1

print(f"reconciled={reconciled}")
PY
