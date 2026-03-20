#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
QUEUE="$BEATLESS/dispatch-queue.jsonl"
RESULTS="$BEATLESS/dispatch-results"
HEALTH_JSON="$BEATLESS/metrics/healthcheck-latest.json"
METRICS_JSON="$BEATLESS/metrics/rawcli-metrics-latest.json"
ALERTS_JSON="$BEATLESS/metrics/rawcli-alerts-latest.json"

queue_depth="$(awk 'NF && $0 !~ /^#/' "$QUEUE" 2>/dev/null | wc -l | tr -d ' ' || echo 0)"

echo "=== RAWCLI SNAPSHOT ==="
echo "time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "queue_depth: $queue_depth"

echo
echo "=== dispatch-results ==="
if [ -d "$RESULTS" ]; then
  ls "$RESULTS"/*.json 2>/dev/null | wc -l | awk '{print "files:", $1}'
  python3 - "$RESULTS" <<'PY'
import json
import pathlib
import sys
from collections import Counter

root = pathlib.Path(sys.argv[1])
c = Counter()
for f in root.glob('*.json'):
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        continue
    c[str(d.get('status', 'unknown'))] += 1
for k in sorted(c):
    print(f"{k}: {c[k]}")
PY
else
  echo "files: 0"
fi

echo
echo "=== health ==="
if [ -f "$HEALTH_JSON" ]; then
  python3 - "$HEALTH_JSON" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text(encoding='utf-8'))
print('verdict:', d.get('verdict', 'unknown'))
print('pass:', d.get('pass', 0), 'warn:', d.get('warn', 0), 'fail:', d.get('fail', 0))
PY
else
  echo "verdict: unknown"
fi

echo
echo "=== alerts ==="
if [ -f "$ALERTS_JSON" ]; then
  python3 - "$ALERTS_JSON" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text(encoding='utf-8'))
print('severity:', d.get('severity', 'ok'))
print('fail_rate:', d.get('fail_rate', 0.0))
print('window_events_total:', d.get('window_events_total', 0))
PY
else
  echo "severity: unknown"
fi

echo
echo "=== events tail ==="
tail -n 5 "$BEATLESS/metrics/dispatch-events.jsonl" 2>/dev/null || echo "(no events)"
