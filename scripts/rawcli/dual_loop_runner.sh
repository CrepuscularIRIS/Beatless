#!/usr/bin/env bash
set -euo pipefail

# dual_loop_runner.sh
# Outer loop + inner PCE loop (minimal production version).
# Usage: dual_loop_runner.sh [cycles]

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
LOG="$BEATLESS/logs/dual-loop.log"
LEDGER="$BEATLESS/metrics/dual-loop-ledger.json"
CYCLES="${1:-${DUAL_LOOP_CYCLES:-3}}"
SLEEP_SEC="${DUAL_LOOP_SLEEP_SEC:-30}"
MODE="${DUAL_LOOP_EXEC_MODE:-daily}"

mkdir -p "$BEATLESS/logs" "$BEATLESS/metrics"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"
}

if ! [[ "$CYCLES" =~ ^[0-9]+$ ]] || [[ "$CYCLES" -lt 1 ]]; then
  echo "invalid cycles: $CYCLES" >&2
  exit 2
fi

log "dual-loop start cycles=$CYCLES mode=$MODE"

python3 - "$LEDGER" "$CYCLES" "$MODE" <<'PY'
import json
import pathlib
import sys
from datetime import datetime

ledger = pathlib.Path(sys.argv[1])
cycles = int(sys.argv[2])
mode = sys.argv[3]
obj = {
    'started_at': datetime.now().astimezone().isoformat(),
    'cycles': cycles,
    'mode': mode,
    'runs': [],
}
ledger.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
PY

for i in $(seq 1 "$CYCLES"); do
  log "cycle=$i outer:start"

  if [[ -x "$SCRIPTS/backlog_groomer.sh" ]]; then
    "$SCRIPTS/backlog_groomer.sh" >> "$LOG" 2>&1 || true
  fi

  inner_out=""
  if [[ -x "$SCRIPTS/pce_cycle.sh" ]]; then
    inner_out="$("$SCRIPTS/pce_cycle.sh" "" "$MODE" 2>&1 || true)"
    log "cycle=$i inner:pce ${inner_out}"
  else
    log "cycle=$i inner:pce missing_script"
  fi

  if [[ -x "$SCRIPTS/context_entropy_compact.sh" ]]; then
    "$SCRIPTS/context_entropy_compact.sh" >> "$LOG" 2>&1 || true
  fi

  python3 - "$LEDGER" "$i" "$inner_out" <<'PY'
import json
import pathlib
import sys
from datetime import datetime

ledger = pathlib.Path(sys.argv[1])
idx = int(sys.argv[2])
inner = sys.argv[3]
obj = json.loads(ledger.read_text(encoding='utf-8'))
obj.setdefault('runs', []).append({
    'cycle': idx,
    'time': datetime.now().astimezone().isoformat(),
    'pce_output': inner,
})
obj['last_updated_at'] = datetime.now().astimezone().isoformat()
ledger.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
PY

  if [[ "$i" -lt "$CYCLES" ]]; then
    sleep "$SLEEP_SEC"
  fi
done

log "dual-loop done"
echo "dual-loop done: ledger=$LEDGER"
