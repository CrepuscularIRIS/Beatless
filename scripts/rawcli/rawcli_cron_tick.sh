#!/usr/bin/env bash
set -euo pipefail

# rawcli_cron_tick.sh
# Periodic automation tick: dual-loop cycle + experiment batch + screenshot normalization.

BEATLESS="${BEATLESS_ROOT:-${HOME}/.openclaw/beatless}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$BEATLESS/scripts"
if [[ ! -d "$SCRIPTS" ]]; then
  SCRIPTS="$SCRIPT_DIR"
fi
LOCK="$BEATLESS/locks/automation-tick.lock"
LOG="$BEATLESS/logs/automation-tick.log"
RUN_STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BEATLESS/locks" "$BEATLESS/logs"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] skip: automation tick already running" >> "$LOG"
  exit 0
fi

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

log "automation tick start"

if [[ "${AUTOMATION_RUN_DUAL_LOOP:-true}" == "true" && -x "$SCRIPTS/dual_loop_runner.sh" ]]; then
  DUAL_LOOP_CYCLES="${AUTOMATION_DUAL_LOOP_CYCLES:-1}" DUAL_LOOP_EXEC_MODE="${AUTOMATION_EXEC_MODE:-daily}" \
    bash "$SCRIPTS/dual_loop_runner.sh" "${AUTOMATION_DUAL_LOOP_CYCLES:-1}" >> "$LOG" 2>&1 || true
fi

if [[ "${AUTOMATION_RUN_EXPERIMENTS:-true}" == "true" && -x "$SCRIPTS/rawcli_experiment_batch.sh" ]]; then
  EXPERIMENT_DRY_RUN="${AUTOMATION_EXPERIMENT_DRY_RUN:-false}" \
    bash "$SCRIPTS/rawcli_experiment_batch.sh" "AUTOEXP-${RUN_STAMP}" >> "$LOG" 2>&1 || true
fi

if [[ -x "$SCRIPTS/normalize_visual_evidence.sh" ]]; then
  bash "$SCRIPTS/normalize_visual_evidence.sh" >> "$LOG" 2>&1 || true
fi

if [[ "${AUTOMATION_RUN_CODEX_REPAIR:-false}" == "true" && -x "$SCRIPTS/codex_state_repair.sh" ]]; then
  bash "$SCRIPTS/codex_state_repair.sh" >> "$LOG" 2>&1 || true
fi

log "automation tick done"
