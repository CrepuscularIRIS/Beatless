#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  verify_gates.sh --stage <plan|implement|verify|review|publish> --contract <path> [--job-dir <path>] [--plan-json <path>] [--codex-result <path>]
EOF
}

STAGE=""
CONTRACT=""
JOB_DIR=""
PLAN_JSON=""
CODEX_RESULT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage)
      STAGE="$2"; shift 2 ;;
    --contract)
      CONTRACT="$2"; shift 2 ;;
    --job-dir)
      JOB_DIR="$2"; shift 2 ;;
    --plan-json)
      PLAN_JSON="$2"; shift 2 ;;
    --codex-result)
      CODEX_RESULT="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ -z "$STAGE" || -z "$CONTRACT" ]]; then
  usage
  exit 2
fi

if [[ ! -f "$CONTRACT" ]]; then
  echo "contract not found: $CONTRACT" >&2
  exit 2
fi

case "$STAGE" in
  plan)
    if [[ -z "$PLAN_JSON" || ! -f "$PLAN_JSON" ]]; then
      echo "plan gate requires --plan-json <file>" >&2
      exit 2
    fi
    python3 - <<PY
import json
from pathlib import Path
p = Path("$PLAN_JSON")
d = json.loads(p.read_text())
stages = d.get("stages", [])
assert isinstance(stages, list) and len(stages) >= 1
for s in stages:
    assert "stage" in s and "lane" in s and "sub_tasks" in s and "editable_paths" in s
print("gate:plan_completeness PASS")
PY
    ;;

  implement)
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "implement gate requires git worktree" >&2
      exit 2
    fi

    DIFF_STAT=$(git diff --stat)
    if [[ -z "$DIFF_STAT" ]]; then
      echo "gate:diff_exists FAIL (no diff)" >&2
      exit 1
    fi
    echo "gate:diff_exists PASS"

    python3 - <<PY
import json
import subprocess
from pathlib import Path
contract = json.loads(Path("$CONTRACT").read_text())
allowed = contract.get("editable_paths", [])
changed = subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
violations = []
for f in changed:
    if not any(f.startswith(p.rstrip("/") + "/") or f == p.rstrip("/") for p in allowed):
        violations.append(f)
if violations:
    print("gate:path_compliance FAIL")
    print("violations:")
    for v in violations:
        print(" -", v)
    raise SystemExit(1)
print("gate:path_compliance PASS")
PY
    ;;

  verify)
    python3 - <<PY
import json
import shlex
import subprocess
from pathlib import Path
contract = json.loads(Path("$CONTRACT").read_text())
must_pass = contract.get("acceptance", {}).get("must_pass", [])
if not must_pass:
    print("gate:must_pass_all FAIL (no commands)")
    raise SystemExit(1)
for cmd in must_pass:
    print("run:", cmd)
    code = subprocess.call(cmd, shell=True)
    if code != 0:
      print("gate:must_pass_all FAIL")
      raise SystemExit(code)
print("gate:must_pass_all PASS")
PY
    ;;

  review)
    if [[ -z "$CODEX_RESULT" || ! -f "$CODEX_RESULT" ]]; then
      echo "review gate requires --codex-result <file>" >&2
      exit 2
    fi
    python3 /home/yarizakurahime/claw/Beatless/scripts/parse_codex_result.py < "$CODEX_RESULT" > /tmp/codex_gate.json
    cat /tmp/codex_gate.json
    if grep -q '"verdict": "PASS"' /tmp/codex_gate.json; then
      echo "gate:codex_verdict PASS"
    else
      echo "gate:codex_verdict FAIL" >&2
      exit 1
    fi
    ;;

  publish)
    if [[ -z "$JOB_DIR" ]]; then
      echo "publish gate requires --job-dir <path>" >&2
      exit 2
    fi
    test -f "$JOB_DIR/handoff/CHANGELOG.md"
    test -f "$JOB_DIR/handoff/PR_DESCRIPTION.md"
    test -f "$JOB_DIR/handoff/ROLLBACK.md"
    echo "gate:handoff_exists PASS"
    ;;

  *)
    echo "unknown stage: $STAGE" >&2
    exit 2
    ;;
esac
