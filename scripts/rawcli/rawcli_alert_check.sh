#!/usr/bin/env bash
set -euo pipefail

BEATLESS="${HOME}/.openclaw/beatless"
SCRIPTS="$BEATLESS/scripts"
METRICS_JSON="$BEATLESS/metrics/rawcli-metrics-latest.json"
ALERTS_JSON="$BEATLESS/metrics/rawcli-alerts-latest.json"
REPORT_MD="/home/yarizakurahime/claw/Report/rawcli-alert-latest.md"
ALERT_LOG="$BEATLESS/logs/rawcli-alerts.log"
ALERT_NOTIFY="$SCRIPTS/rawcli_alert_notify.sh"
WINDOW_MINUTES="${ALERT_WINDOW_MINUTES:-15}"

MIN_SAMPLE="${ALERT_MIN_SAMPLE:-6}"
WARN_FAIL_RATE="${ALERT_WARN_FAIL_RATE:-0.25}"
CRIT_FAIL_RATE="${ALERT_CRIT_FAIL_RATE:-0.50}"
WARN_TIMEOUT="${ALERT_WARN_TIMEOUT:-3}"
CRIT_AUTH="${ALERT_CRIT_AUTH_ERRORS:-2}"
CRIT_MISSING_BIN="${ALERT_CRIT_MISSING_BINARY:-1}"

mkdir -p "$BEATLESS/logs" "$(dirname "$REPORT_MD")"

SESSION_NAME="${SESSION_NAME:-beatless-v2}" bash "$SCRIPTS/rawcli_metrics_rollup.sh" "$WINDOW_MINUTES" >/dev/null

python3 - "$METRICS_JSON" "$ALERTS_JSON" "$REPORT_MD" "$MIN_SAMPLE" "$WARN_FAIL_RATE" "$CRIT_FAIL_RATE" "$WARN_TIMEOUT" "$CRIT_AUTH" "$CRIT_MISSING_BIN" <<'PY'
import json
import pathlib
import sys
from datetime import datetime

metrics_path = pathlib.Path(sys.argv[1])
alerts_path = pathlib.Path(sys.argv[2])
report_path = pathlib.Path(sys.argv[3])
min_sample = int(sys.argv[4])
warn_fail_rate = float(sys.argv[5])
crit_fail_rate = float(sys.argv[6])
warn_timeout = int(sys.argv[7])
crit_auth = int(sys.argv[8])
crit_missing_bin = int(sys.argv[9])

metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
window = metrics.get('window', {})
status = window.get('status', {})
failures = window.get('failure_type', {})

window_total = int(window.get('events_total', 0) or 0)
fail_rate = float(window.get('fail_rate', 0.0) or 0.0)
timeout_count = int(window.get('timeout_count', 0) or 0)
auth_errors = int(failures.get('auth_error', 0) or 0)
missing_bin = int(failures.get('missing_binary', 0) or 0)

severity = 'ok'
reasons = []

if window_total >= min_sample and fail_rate >= crit_fail_rate:
    severity = 'critical'
    reasons.append(f'fail_rate={fail_rate:.3f} >= {crit_fail_rate:.3f}')

if auth_errors >= crit_auth:
    severity = 'critical'
    reasons.append(f'auth_error={auth_errors} >= {crit_auth}')

if missing_bin >= crit_missing_bin:
    severity = 'critical'
    reasons.append(f'missing_binary={missing_bin} >= {crit_missing_bin}')

if severity != 'critical':
    if window_total >= min_sample and fail_rate >= warn_fail_rate:
        severity = 'warning'
        reasons.append(f'fail_rate={fail_rate:.3f} >= {warn_fail_rate:.3f}')
    if timeout_count >= warn_timeout:
        severity = 'warning'
        reasons.append(f'timeout_count={timeout_count} >= {warn_timeout}')

if not reasons:
    reasons.append('within_thresholds')

payload = {
    'generated_at': datetime.now().astimezone().isoformat(),
    'severity': severity,
    'window_minutes': metrics.get('window_minutes'),
    'queue_depth': metrics.get('queue_depth'),
    'running_count': metrics.get('running_count'),
    'window_events_total': window_total,
    'task_id': window.get('last_task_id', ''),
    'fail_rate': fail_rate,
    'status_counts': status,
    'failure_type_counts': failures,
    'reasons': reasons,
}
alerts_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lines = [
    '# RawCli Alert Check',
    '',
    f"- generated_at: {payload['generated_at']}",
    f"- severity: **{severity.upper()}**",
    f"- window_minutes: {payload['window_minutes']}",
    f"- queue_depth: {payload['queue_depth']}",
    f"- running_count: {payload['running_count']}",
    f"- window_events_total: {window_total}",
    f"- fail_rate: {fail_rate:.3f}",
    '',
    '## Reasons',
]
lines.extend(f'- {r}' for r in reasons)
lines += ['', '## Status Counts']
lines.extend(f'- {k}: {v}' for k, v in sorted(status.items()))
lines += ['', '## Failure Type Counts']
lines.extend(f'- {k}: {v}' for k, v in sorted(failures.items()))
report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

print(severity)
PY

severity="$(python3 - "$ALERTS_JSON" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
print(json.loads(p.read_text(encoding='utf-8')).get('severity', 'ok'))
PY
)"

if [[ -x "$ALERT_NOTIFY" ]]; then
  "$ALERT_NOTIFY" "$ALERTS_JSON" >/dev/null 2>&1 || true
fi

if [ "$severity" = "critical" ]; then
  printf '[%s] severity=%s report=%s\n' "$(date -Iseconds)" "$severity" "$REPORT_MD" >> "$ALERT_LOG"
  exit 2
fi

if [ "$severity" = "warning" ]; then
  printf '[%s] severity=%s report=%s\n' "$(date -Iseconds)" "$severity" "$REPORT_MD" >> "$ALERT_LOG"
fi

exit 0
