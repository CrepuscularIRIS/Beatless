#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: meta_harness_sidecar_run.sh --contract <task_contract.json> [options]

Options:
  --contract <path>        TaskContract JSON path (required)
  --model <id>             Model id label for result metadata
  --output-dir <dir>       Output dir (default: runtime/meta_harness)
  --timeout-sec <n>        Sidecar command timeout in seconds (default: 1800)
  --dry-run                Do not execute external harness, only run integration path

Environment:
  META_HARNESS_COMMAND     Command to run in isolated worktree when not --dry-run
EOF
}

CONTRACT_PATH=""
MODEL="${META_HARNESS_MODEL:-stepfun/step-3.5-flash}"
OUTPUT_DIR="${META_HARNESS_OUTPUT_DIR:-$ROOT/runtime/meta_harness}"
TIMEOUT_SEC="${META_HARNESS_TIMEOUT_SECONDS:-1800}"
DRY_RUN="${META_HARNESS_DRY_RUN:-0}"
META_HARNESS_COMMAND="${META_HARNESS_COMMAND:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --contract)
      CONTRACT_PATH="${2:-}"; shift 2 ;;
    --model)
      MODEL="${2:-}"; shift 2 ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"; shift 2 ;;
    --timeout-sec)
      TIMEOUT_SEC="${2:-}"; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$CONTRACT_PATH" ]]; then
  echo "missing --contract" >&2
  usage
  exit 1
fi
if [[ ! -f "$CONTRACT_PATH" ]]; then
  echo "contract not found: $CONTRACT_PATH" >&2
  exit 1
fi

python3 scripts/validate_task_contract.py "$CONTRACT_PATH" >/dev/null

RUN_ID="mh-$(date +%Y%m%d-%H%M%S)-$RANDOM"
RUN_DIR="$OUTPUT_DIR/$RUN_ID"
WORKTREE="$ROOT/runtime/worktrees/$RUN_ID"
mkdir -p "$RUN_DIR" "$ROOT/runtime/worktrees"

CLEANUP_WORKTREE=0
cleanup() {
  if [[ "$CLEANUP_WORKTREE" -eq 1 ]]; then
    git -C "$ROOT" worktree remove "$WORKTREE" --force >/dev/null 2>&1 || true
    git -C "$ROOT" worktree prune >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

git -C "$ROOT" worktree add "$WORKTREE" --detach HEAD >/dev/null
CLEANUP_WORKTREE=1

START_TS="$(date +%s)"

python3 - "$CONTRACT_PATH" "$RUN_DIR/contract_snapshot.json" <<'PY'
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
Path(sys.argv[2]).write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

python3 - "$WORKTREE" "$RUN_DIR/env_snapshot.json" <<'PY'
import json
import shutil
import sys
from pathlib import Path

cwd = Path(sys.argv[1])
payload = {
    "cwd": str(cwd),
    "top_level_entries": sorted([p.name for p in cwd.iterdir()])[:80],
    "tool_paths": {
        "python3": shutil.which("python3"),
        "node": shutil.which("node"),
        "bun": shutil.which("bun"),
        "cargo": shutil.which("cargo"),
        "claude": shutil.which("claude"),
        "codex": shutil.which("codex"),
        "gemini": shutil.which("gemini"),
        "nlm": shutil.which("nlm"),
    },
}
Path(sys.argv[2]).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

HARNESS_RC=0
if [[ "$DRY_RUN" -eq 1 ]]; then
  cat > "$RUN_DIR/agent_log.txt" <<EOF
[meta-harness] dry-run mode
run_id=$RUN_ID
model=$MODEL
worktree=$WORKTREE
EOF
else
  if [[ -z "$META_HARNESS_COMMAND" ]]; then
    echo "META_HARNESS_COMMAND is required when not --dry-run" >&2
    exit 1
  fi
  set +e
  timeout "$TIMEOUT_SEC" bash -lc "cd '$WORKTREE' && $META_HARNESS_COMMAND" >"$RUN_DIR/agent_log.txt" 2>&1
  HARNESS_RC=$?
  set -e
fi

python3 - "$CONTRACT_PATH" "$WORKTREE" "$RUN_DIR/verify_report.json" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
worktree = Path(sys.argv[2])
report_path = Path(sys.argv[3])

must_pass = ((contract.get("acceptance") or {}).get("must_pass") or [])
logs = []
verify_pass = True
for cmd in must_pass:
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=str(worktree),
        capture_output=True,
        text=True,
    )
    logs.append({
        "cmd": cmd,
        "code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-800:],
    })
    if proc.returncode != 0:
        verify_pass = False

report = {"verify_pass": verify_pass, "logs": logs}
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("PASS" if verify_pass else "FAIL")
PY

git -C "$WORKTREE" diff --no-ext-diff > "$RUN_DIR/patch.diff" || true

RESULT_JSON="$RUN_DIR/result.json"
END_TS="$(date +%s)"

python3 - "$CONTRACT_PATH" "$RUN_DIR" "$RUN_ID" "$MODEL" "$HARNESS_RC" "$START_TS" "$END_TS" "$DRY_RUN" <<'PY'
import json
import sys
from pathlib import Path

contract_path, run_dir, run_id, model, harness_rc, start_ts, end_ts, dry_run = sys.argv[1:9]
run_dir = Path(run_dir)
contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
verify = json.loads((run_dir / "verify_report.json").read_text(encoding="utf-8"))
patch = (run_dir / "patch.diff").read_text(encoding="utf-8")
diff_lines = len([ln for ln in patch.splitlines() if ln.strip()])
try:
    changed_files = [ln.strip() for ln in (run_dir / "patch.diff").read_text(encoding="utf-8").splitlines() if ln.startswith("+++ b/")]
except Exception:
    changed_files = []

f_codes = []
if int(harness_rc) != 0:
    f_codes.append("F-H05")
if dry_run != "1" and not verify.get("verify_pass", False):
    f_codes.append("F-S01")
if dry_run != "1" and diff_lines == 0:
    f_codes.append("F-S01")

result = {
    "run_id": run_id,
    "goal": contract.get("goal", ""),
    "model": model,
    "verify_pass": bool(verify.get("verify_pass", False)),
    "dry_run": dry_run == "1",
    "harness_rc": int(harness_rc),
    "diff_lines": diff_lines,
    "file_touched": len(changed_files),
    "wall_time_seconds": max(0, int(end_ts) - int(start_ts)),
    "f_codes": sorted(set(f_codes)),
    "artifacts": {
        "contract_snapshot": "contract_snapshot.json",
        "env_snapshot": "env_snapshot.json",
        "verify_report": "verify_report.json",
        "patch": "patch.diff",
        "agent_log": "agent_log.txt",
    },
}
(run_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
PY

echo "RESULT_JSON=$RESULT_JSON"
