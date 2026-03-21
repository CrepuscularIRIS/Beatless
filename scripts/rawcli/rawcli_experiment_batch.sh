#!/usr/bin/env bash
set -euo pipefail

# rawcli_experiment_batch.sh
# Runs 3 experiment groups (rawcli dispatch, receipt schema, screenshot chain).
# Usage: rawcli_experiment_batch.sh [RUN_ID]

BEATLESS="${BEATLESS_ROOT:-${HOME}/.openclaw/beatless}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$BEATLESS/scripts"
if [[ ! -x "$SCRIPTS/dispatch_submit.sh" ]]; then
  SCRIPTS="$SCRIPT_DIR"
fi
REPORT_ROOT="/home/yarizakurahime/claw/Report/experiments"
METRICS_FILE="$BEATLESS/metrics/experiment-batches.jsonl"
RUN_ID="${1:-EXP-$(date +%Y%m%d-%H%M%S)}"
DRY_RUN="${EXPERIMENT_DRY_RUN:-false}"
CAPTURE_SCRIPT="/home/yarizakurahime/.openclaw/workspace-lacia/skills/visual-proof/scripts/capture_url.sh"
RECEIPT_FIXTURE_TEST="${RECEIPT_FIXTURE_TEST:-$SCRIPT_DIR/../ci/test_receipt_schema_gate.sh}"

mkdir -p "$REPORT_ROOT" "$BEATLESS/metrics"
REPORT_FILE="$REPORT_ROOT/${RUN_ID}.md"

log_report() {
  printf '%s\n' "$*" >> "$REPORT_FILE"
}

record_metric() {
  local status="$1"
  local group="$2"
  printf '{"ts":"%s","run_id":"%s","group":"%s","status":"%s","dry_run":%s}\n' \
    "$(date -Iseconds)" "$RUN_ID" "$group" "$status" "$([[ "$DRY_RUN" == "true" ]] && echo true || echo false)" >> "$METRICS_FILE"
}

wait_result() {
  local task_id="$1"
  local result="$BEATLESS/dispatch-results/${task_id}.json"
  for _ in $(seq 1 180); do
    [[ -f "$result" ]] || { sleep 1; continue; }
    local st
    st="$(jq -r '.status // empty' "$result" 2>/dev/null || true)"
    if [[ "$st" == "success" || "$st" == "failed" || "$st" == "timeout" ]]; then
      echo "$st"
      return 0
    fi
    sleep 1
  done
  echo "timeout_wait"
  return 1
}

cat > "$REPORT_FILE" <<RPT
# RawCli Experiment Batch

- run_id: $RUN_ID
- time: $(date -Iseconds)
- dry_run: $DRY_RUN
RPT

# Group A: 3 RawCli dispatch probes.
if [[ "$DRY_RUN" == "true" ]]; then
  log_report ""
  log_report "## Group A (RawCli Dispatch)"
  log_report "- status: skipped (dry-run)"
  record_metric "skipped" "group_a_dispatch"
elif [[ ! -x "$SCRIPTS/dispatch_submit.sh" ]]; then
  log_report ""
  log_report "## Group A (RawCli Dispatch)"
  log_report "- status: skipped (dispatch_submit.sh not found)"
  record_metric "skipped" "group_a_dispatch"
else
  log_report ""
  log_report "## Group A (RawCli Dispatch)"
  declare -a A_TASKS=(
    "$RUN_ID-codex|methode|codex_cli|Return exactly one line: exp_codex_ok|exp_codex_ok"
    "$RUN_ID-claude|methode|claude_generalist_cli|Return exactly one line: exp_claude_ok|exp_claude_ok"
    "$RUN_ID-gemini|snowdrop|gemini_cli|Return exactly one line: exp_gemini_ok|exp_gemini_ok"
  )
  a_fail=0
  for row in "${A_TASKS[@]}"; do
    IFS='|' read -r task owner tool prompt expect <<<"$row"
    bash "$SCRIPTS/dispatch_submit.sh" "$task" "$owner" "$tool" "$prompt" "240" "" "$expect" "" "$RUN_ID" "experiment" "trace-$RUN_ID" >/dev/null || true
    st="$(wait_result "$task" || true)"
    log_report "- $task: $st"
    if [[ "$st" != "success" ]]; then
      a_fail=$((a_fail+1))
    fi
  done
  if [[ "$a_fail" -eq 0 ]]; then
    record_metric "pass" "group_a_dispatch"
  else
    record_metric "fail" "group_a_dispatch"
  fi
fi

# Group B: receipt schema regression fixtures.
log_report ""
log_report "## Group B (Receipt Schema Fixtures)"
if [[ -x "$RECEIPT_FIXTURE_TEST" ]] && bash "$RECEIPT_FIXTURE_TEST" >/dev/null 2>&1; then
  log_report "- status: pass"
  record_metric "pass" "group_b_receipt"
else
  log_report "- status: fail"
  record_metric "fail" "group_b_receipt"
fi

# Group C: screenshot evidence chain.
log_report ""
log_report "## Group C (Screenshot Chain)"
if [[ "$DRY_RUN" == "true" ]]; then
  log_report "- status: skipped (dry-run)"
  record_metric "skipped" "group_c_screenshot"
elif [[ -x "$CAPTURE_SCRIPT" ]]; then
  if bash "$CAPTURE_SCRIPT" "https://example.com" "$RUN_ID" "example" >/tmp/${RUN_ID}-capture.out 2>&1; then
    png="$(rg -o '/home/[^ ]+\.png' -N /tmp/${RUN_ID}-capture.out | tail -n 1 || true)"
    [[ -n "$png" ]] || png="/home/yarizakurahime/claw/Report/screenshots/${RUN_ID}-example.png"
    log_report "- status: pass"
    log_report "- screenshot: $png"
    record_metric "pass" "group_c_screenshot"
  else
    log_report "- status: fail"
    log_report "- note: capture_url.sh returned non-zero"
    record_metric "fail" "group_c_screenshot"
  fi
else
  log_report "- status: skipped"
  log_report "- note: capture_url.sh not found"
  record_metric "skipped" "group_c_screenshot"
fi

echo "rawcli_experiment_batch: run_id=$RUN_ID report=$REPORT_FILE"
