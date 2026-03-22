#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
QUEUE="$BEATLESS/dispatch-queue.jsonl"
RESULTS="$BEATLESS/dispatch-results"
TOOL_POOL="$BEATLESS/TOOL_POOL.yaml"
EVENTS="$BEATLESS/metrics/dispatch-events.jsonl"
SUBMIT_EVENTS="$BEATLESS/metrics/dispatch-submit-events.jsonl"
REPORT_DIR="/home/yarizakurahime/claw/Report"
OUT_MD="$REPORT_DIR/rawcli-healthcheck-latest.md"
OUT_JSON="$BEATLESS/metrics/healthcheck-latest.json"
SESSION="${SESSION_NAME:-beatless-v2}"
QUEUE_LAG_THRESHOLD_SEC="${QUEUE_LAG_THRESHOLD_SEC:-45}"

mkdir -p "$REPORT_DIR" "$BEATLESS/metrics"

pass=0
warn=0
fail=0
TMP_RESULTS="$(mktemp)"

record() {
  local level="$1"
  local name="$2"
  local detail="$3"
  printf '%s|%s|%s\n' "$level" "$name" "$detail" >> "$TMP_RESULTS"
  case "$level" in
    PASS) pass=$((pass + 1)) ;;
    WARN) warn=$((warn + 1)) ;;
    FAIL) fail=$((fail + 1)) ;;
  esac
}

check_passfail() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    record "PASS" "$name" "ok"
  else
    record "FAIL" "$name" "check_failed"
  fi
}

check_passwarn() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    record "PASS" "$name" "ok"
  else
    record "WARN" "$name" "check_warn"
  fi
}

check_passfail "tool_pool_exists" test -f "$TOOL_POOL"
check_passfail "queue_writable" bash -c "touch '$QUEUE' && test -w '$QUEUE'"
check_passfail "results_dir_exists" test -d "$RESULTS"
check_passfail "results_dir_writable" bash -c "mkdir -p '$RESULTS' && tmp='$RESULTS/.hc-write-$$'; echo ok > \"\$tmp\" && rm -f \"\$tmp\""
check_passfail "route_task_exists" test -x "$SCRIPTS/route_task.sh"
check_passfail "dispatch_submit_exists" test -x "$SCRIPTS/dispatch_submit.sh"
check_passfail "dispatch_hook_exists" test -x "$SCRIPTS/dispatch_hook_loop.sh"
check_passwarn "supervisor_exists" test -x "$SCRIPTS/rawcli_supervisor.sh"
check_passwarn "alert_check_exists" test -x "$SCRIPTS/rawcli_alert_check.sh"
check_passwarn "alert_notify_exists" test -x "$SCRIPTS/rawcli_alert_notify.sh"
check_passwarn "metrics_rollup_exists" test -x "$SCRIPTS/rawcli_metrics_rollup.sh"
check_passwarn "trace_lookup_exists" test -x "$SCRIPTS/rawcli_trace_lookup.sh"
check_passwarn "observability_panel_exists" test -x "$SCRIPTS/rawcli_observability_panel.sh"
check_passwarn "automation_tick_exists" test -x "$SCRIPTS/rawcli_cron_tick.sh"

check_passfail "cli_codex_available" command -v codex
check_passfail "cli_claude_available" command -v claude
check_passwarn "cli_gemini_available" command -v gemini

if python3 - <<'PY' >/dev/null 2>&1
import yaml, pathlib
p = pathlib.Path('/home/yarizakurahime/.openclaw/beatless/TOOL_POOL.yaml')
d = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
assert isinstance(d, dict)
required = {'codex_cli','claude_generalist_cli','claude_architect_opus_cli','claude_architect_sonnet_cli','gemini_cli'}
assert required.issubset((d.get('tools') or {}).keys())
for _, tool in (d.get('tools') or {}).items():
    assert tool.get('prompt_mode') in {'positional','dash_p'}
PY
then
  record "PASS" "tool_pool_parse" "ok"
else
  record "FAIL" "tool_pool_parse" "invalid_yaml_or_contract"
fi

if route_out="$($SCRIPTS/route_task.sh '修复API bug并补测试' 2>/dev/null)" && \
   printf '%s\n' "$route_out" | rg -q '^owner_agent=' && \
   printf '%s\n' "$route_out" | rg -q '^executor_tool='; then
  record "PASS" "route_contract_output" "owner+executor_present"
else
  record "FAIL" "route_contract_output" "missing_owner_or_executor"
fi

if rg -q '^\s*owner_agent:' "$BEATLESS/TASKS.yaml" && rg -q '^\s*executor_tool:' "$BEATLESS/TASKS.yaml"; then
  record "PASS" "tasks_contract_fields" "owner/executor_present"
else
  record "WARN" "tasks_contract_fields" "missing_owner_or_executor_on_some_tasks"
fi

check_passwarn "tmux_session_exists" tmux has-session -t "$SESSION"
check_passwarn "hook_process_alive" bash -c "ps -eo cmd | rg -q 'dispatch_hook_loop.sh'"
check_passwarn "events_file_present" test -f "$EVENTS"
check_passwarn "events_file_nonempty" test -s "$EVENTS"
check_passwarn "submit_events_file_present" test -f "$SUBMIT_EVENTS"
check_passwarn "submit_events_nonempty" test -s "$SUBMIT_EVENTS"

if python3 - "$SUBMIT_EVENTS" "$EVENTS" "$RESULTS" "$QUEUE_LAG_THRESHOLD_SEC" <<'PY' >/dev/null 2>&1
import json, sys, pathlib, datetime
submit_p = pathlib.Path(sys.argv[1])
dispatch_p = pathlib.Path(sys.argv[2])
results_dir = pathlib.Path(sys.argv[3])
threshold = int(sys.argv[4])
if not submit_p.exists():
    raise SystemExit(1)
latest_submit = None
for ln in submit_p.read_text(encoding='utf-8', errors='ignore').splitlines():
    ln = ln.strip()
    if not ln:
        continue
    try:
        obj = json.loads(ln)
    except Exception:
        continue
    latest_submit = obj
if not latest_submit:
    raise SystemExit(1)
task_id = str(latest_submit.get("task_id", ""))
if not task_id:
    raise SystemExit(1)
def parse_ts(v):
    if not v:
        return None
    t = str(v)
    if t.endswith("Z"):
        t=t[:-1]+"+00:00"
    try:
        return datetime.datetime.fromisoformat(t)
    except Exception:
        return None
submit_ts = parse_ts(latest_submit.get("ts"))
if submit_ts is None:
    raise SystemExit(1)
if dispatch_p.exists():
    for ln in reversed(dispatch_p.read_text(encoding='utf-8', errors='ignore').splitlines()):
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if str(obj.get("task_id", "")) == task_id:
            raise SystemExit(0)

# Treat existing result row as consumed, even if dispatch event is not yet written.
result_file = results_dir / f"{task_id}.json"
if result_file.exists():
    try:
        result = json.loads(result_file.read_text(encoding='utf-8'))
        status = str(result.get("status", ""))
    except Exception:
        status = ""
    if status in {"running", "success", "failed", "timeout", "skipped"}:
        raise SystemExit(0)

now = datetime.datetime.now(submit_ts.tzinfo)
lag = (now - submit_ts).total_seconds()
if lag > threshold:
    raise SystemExit(2)
raise SystemExit(0)
PY
then
  record "PASS" "queue_consumable_lag" "within_threshold"
else
  rc=$?
  if [[ "$rc" -eq 2 ]]; then
    record "FAIL" "queue_consumable_lag" "submit_without_dispatch_exceeds_threshold"
  else
    record "WARN" "queue_consumable_lag" "insufficient_signal"
  fi
fi

queue_depth="$(awk 'NF && $0 !~ /^#/' "$QUEUE" 2>/dev/null | wc -l | tr -d ' ' || echo 0)"
if [ "$queue_depth" -gt 500 ]; then
  record "WARN" "queue_depth" "high:$queue_depth"
else
  record "PASS" "queue_depth" "value:$queue_depth"
fi

verdict="PASS"
if [ "$fail" -gt 0 ]; then
  verdict="FAIL"
elif [ "$warn" -gt 0 ]; then
  verdict="PARTIAL"
fi

now="$(date -Iseconds)"

{
  echo "# RawCli Healthcheck"
  echo
  echo "- time: $now"
  echo "- session: $SESSION"
  echo "- pass: $pass"
  echo "- warn: $warn"
  echo "- fail: $fail"
  echo "- verdict: **$verdict**"
  echo
  echo "## Checks"
  echo "| level | check | detail |"
  echo "|---|---|---|"
  awk -F'|' '{printf "| %s | %s | %s |\n", $1, $2, $3}' "$TMP_RESULTS"
} > "$OUT_MD"

python3 - "$TMP_RESULTS" "$OUT_JSON" "$now" "$SESSION" "$pass" "$warn" "$fail" "$verdict" <<'PY'
import json
import pathlib
import sys

rows_path = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
now, session = sys.argv[3], sys.argv[4]
pass_n, warn_n, fail_n = int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
verdict = sys.argv[8]
rows = []
for line in rows_path.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    level, name, detail = line.split('|', 2)
    rows.append({'level': level, 'name': name, 'detail': detail})
out_json.write_text(json.dumps({
    'time': now,
    'session': session,
    'pass': pass_n,
    'warn': warn_n,
    'fail': fail_n,
    'verdict': verdict,
    'checks': rows,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

rm -f "$TMP_RESULTS"

if [ "$verdict" = "FAIL" ]; then
  exit 1
fi
