#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DURATION_SECONDS="${SOAK_DURATION_SECONDS:-28800}"    # default 8h
INTERVAL_SECONDS="${SOAK_INTERVAL_SECONDS:-300}"      # default 5min
MAX_FAILURES="${SOAK_MAX_FAILURES:-3}"

START_TS="$(date +%s)"
END_TS="$((START_TS + DURATION_SECONDS))"
RUN_ID="soak-$(date +%Y%m%d-%H%M%S)"
SOAK_DIR="$ROOT/runtime/soak"
LOG_DIR="$SOAK_DIR/logs/$RUN_ID"
JSONL="$SOAK_DIR/${RUN_ID}.jsonl"
SUMMARY="$SOAK_DIR/${RUN_ID}-summary.md"

mkdir -p "$LOG_DIR" "$SOAK_DIR"

cleanup_experiment_artifacts() {
  find "$ROOT/runtime/jobs" -maxdepth 1 -mindepth 1 -type d \
    \( -name 'smoke-*' -o -name 'closedloop-*' -o -name 'expnm-*' \) -exec rm -rf {} + || true
  find "$ROOT/runtime/state" -maxdepth 1 -type f -name 'experiment_nonmock_*' -delete || true
  rm -f "$ROOT/runtime/scheduler/.scheduler.lock" || true
}

append_jsonl() {
  local cycle="$1"
  local phase="$2"
  local rc="$3"
  local msg="$4"
  local diff_lines="${5:-0}"
  local test_count="${6:-0}"
  local file_touched="${7:-0}"
  local done_jobs="${8:-0}"
  local escalated_jobs="${9:-0}"
  local blocked_jobs="${10:-0}"
  local false_pass="${11:-0}"
  CYCLE="$cycle" PHASE="$phase" RC="$rc" MSG="$msg" \
  DIFF_LINES="$diff_lines" TEST_COUNT="$test_count" FILE_TOUCHED="$file_touched" \
  DONE_JOBS="$done_jobs" ESCALATED_JOBS="$escalated_jobs" BLOCKED_JOBS="$blocked_jobs" \
  FALSE_PASS="$false_pass" python3 - <<'PY' >> "$JSONL"
import json
import os
import time

payload = {
  "ts": int(time.time()),
  "cycle": int(os.environ["CYCLE"]),
  "phase": os.environ["PHASE"],
  "rc": int(os.environ["RC"]),
  "message": os.environ["MSG"],
  "diff_lines": int(os.environ["DIFF_LINES"]),
  "test_count": int(os.environ["TEST_COUNT"]),
  "file_touched": int(os.environ["FILE_TOUCHED"]),
  "done_jobs": int(os.environ["DONE_JOBS"]),
  "escalated_jobs": int(os.environ["ESCALATED_JOBS"]),
  "blocked_jobs": int(os.environ["BLOCKED_JOBS"]),
  "false_pass": bool(int(os.environ["FALSE_PASS"])),
}

print(json.dumps({
  **payload
}, ensure_ascii=False))
PY
}

run_with_retry_lock() {
  local out_file="$1"
  local cmd="$2"
  local attempts=0
  while true; do
    attempts=$((attempts+1))
    set +e
    bash -lc "$cmd" >"$out_file" 2>&1
    local rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      echo "$rc"
      return 0
    fi
    if grep -q "scheduler lock busy" "$out_file"; then
      if [[ $attempts -ge 30 ]]; then
        echo "$rc"
        return 0
      fi
      sleep 1
      continue
    fi
    echo "$rc"
    return 0
  done
}

collect_cycle_metrics_json() {
  ROOT_DIR="$ROOT" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
metrics_path = root / "runtime" / "state" / "experiment_nonmock_last_metrics.json"
payload = {
  "file_touched": 0,
  "diff_lines": 0,
  "test_count": 0,
  "done_jobs": 0,
  "escalated_jobs": 0,
  "blocked_jobs": 0,
}
if metrics_path.exists():
  try:
    raw = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload.update(
      {
        "file_touched": int(raw.get("file_touched", 0) or 0),
        "diff_lines": int(raw.get("diff_lines_proxy", raw.get("file_touched", 0)) or 0),
        "test_count": int(raw.get("test_count", 0) or 0),
        "done_jobs": int(raw.get("done_jobs", 0) or 0),
        "escalated_jobs": int(raw.get("escalated_jobs", 0) or 0),
        "blocked_jobs": int(raw.get("blocked_jobs", 0) or 0),
      }
    )
  except Exception:
    payload["metrics_parse_error"] = True
print(json.dumps(payload, ensure_ascii=False))
PY
}

# Preflight
python3 scripts/init_task_os.py >/dev/null
python3 scripts/validate_baseline.py >/dev/null
bash scripts/smoke_trigger_v21.sh >/dev/null

success=0
failure=0
cycle=0
false_pass=0

append_jsonl 0 "start" 0 "run_id=$RUN_ID duration=$DURATION_SECONDS interval=$INTERVAL_SECONDS max_failures=$MAX_FAILURES" 0 0 0 0 0 0 0

echo "[soak] run_id=$RUN_ID"
echo "[soak] jsonl=$JSONL"
echo "[soak] summary=$SUMMARY"

while [[ "$(date +%s)" -lt "$END_TS" ]]; do
  cycle=$((cycle+1))
  cycle_log="$LOG_DIR/cycle-${cycle}.log"

  rc=$(run_with_retry_lock "$cycle_log" "cd '$ROOT' && bash scripts/experiment_harness_nonmock_v21.sh")
  metrics_json="$(collect_cycle_metrics_json)"
  diff_lines="$(jq -r '.diff_lines // 0' <<<"$metrics_json")"
  test_count="$(jq -r '.test_count // 0' <<<"$metrics_json")"
  file_touched="$(jq -r '.file_touched // 0' <<<"$metrics_json")"
  done_jobs="$(jq -r '.done_jobs // 0' <<<"$metrics_json")"
  escalated_jobs="$(jq -r '.escalated_jobs // 0' <<<"$metrics_json")"
  blocked_jobs="$(jq -r '.blocked_jobs // 0' <<<"$metrics_json")"
  cycle_false_pass=0
  if [[ "$rc" -eq 0 && ( "$diff_lines" -eq 0 || "$test_count" -eq 0 || "$done_jobs" -eq 0 ) ]]; then
    cycle_false_pass=1
  fi

  if [[ "$rc" -eq 0 ]]; then
    success=$((success+1))
    if [[ "$cycle_false_pass" -eq 1 ]]; then
      false_pass=$((false_pass+1))
      append_jsonl "$cycle" "experiment" 0 "ok_false_pass" "$diff_lines" "$test_count" "$file_touched" "$done_jobs" "$escalated_jobs" "$blocked_jobs" 1
    else
      append_jsonl "$cycle" "experiment" 0 "ok" "$diff_lines" "$test_count" "$file_touched" "$done_jobs" "$escalated_jobs" "$blocked_jobs" 0
    fi
  else
    failure=$((failure+1))
    append_jsonl "$cycle" "experiment" "$rc" "failed" "$diff_lines" "$test_count" "$file_touched" "$done_jobs" "$escalated_jobs" "$blocked_jobs" 0
  fi

  drain_log="$LOG_DIR/cycle-${cycle}-drain.log"
  rc2=$(run_with_retry_lock "$drain_log" "cd '$ROOT' && ORCHESTRATION_MODE=harness python3 scripts/task_os_scheduler.py --drain")
  append_jsonl "$cycle" "drain" "$rc2" "post-cycle drain" 0 0 0 0 0 0 0

  cleanup_experiment_artifacts

  if [[ "$failure" -ge "$MAX_FAILURES" ]]; then
    append_jsonl "$cycle" "abort" 1 "max failures reached" 0 0 0 0 0 0 0
    break
  fi

  now="$(date +%s)"
  if [[ "$now" -ge "$END_TS" ]]; then
    break
  fi
  sleep "$INTERVAL_SECONDS"
done

# Final snapshot
ORCHESTRATION_MODE=harness python3 scripts/task_os_scheduler.py --drain > "$LOG_DIR/final-drain.log" 2>&1 || true
rm -f "$ROOT/runtime/scheduler/.scheduler.lock" || true

cat > "$SUMMARY" <<EOF
# Harness Soak Summary

- run_id: $RUN_ID
- started_at_unix: $START_TS
- ended_at_unix: $(date +%s)
- duration_seconds_target: $DURATION_SECONDS
- interval_seconds: $INTERVAL_SECONDS
- cycles_total: $cycle
- success_cycles: $success
- failure_cycles: $failure
- false_pass_cycles: $false_pass
- jsonl: $JSONL
- logs_dir: $LOG_DIR
EOF

if [[ "$failure" -ge "$MAX_FAILURES" ]]; then
  echo "[soak] FAIL (failure=$failure >= max=$MAX_FAILURES)"
  exit 1
fi

echo "[soak] PASS (success=$success failure=$failure cycles=$cycle)"
