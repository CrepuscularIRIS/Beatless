#!/usr/bin/env bash
set -euo pipefail

# rawcli_alert_notify.sh
# Send critical/warning alert notifications with cooldown + dedup.

BEATLESS="${HOME}/.openclaw/beatless"
ALERTS_JSON="${1:-$BEATLESS/metrics/rawcli-alerts-latest.json}"
STATE_JSON="$BEATLESS/metrics/alert-notify-state.json"
REPORT_MD="/home/yarizakurahime/claw/Report/rawcli-alert-latest.md"
LOG="$BEATLESS/logs/rawcli-alert-notify.log"

ALERT_NOTIFY_ENABLED="${ALERT_NOTIFY_ENABLED:-true}"
ALERT_NOTIFY_WARN_ENABLED="${ALERT_NOTIFY_WARN_ENABLED:-false}"
ALERT_NOTIFY_CHAT_ID="${ALERT_NOTIFY_CHAT_ID:-${FEISHU_TARGET_CHAT_ID:-}}"
CRIT_COOLDOWN_SEC="${ALERT_CRIT_COOLDOWN_SEC:-600}"
WARN_COOLDOWN_SEC="${ALERT_WARN_COOLDOWN_SEC:-900}"
OPENCLAW_BIN="${OPENCLAW_BIN:-}"

mkdir -p "$BEATLESS/metrics" "$BEATLESS/logs" "/home/yarizakurahime/claw/Report"

if [[ "$ALERT_NOTIFY_ENABLED" != "true" ]]; then
  exit 0
fi
if [[ ! -f "$ALERTS_JSON" ]]; then
  exit 0
fi
if [[ -z "$ALERT_NOTIFY_CHAT_ID" ]]; then
  exit 0
fi

if [[ -z "$OPENCLAW_BIN" ]]; then
  if command -v openclaw >/dev/null 2>&1; then
    OPENCLAW_BIN="$(command -v openclaw)"
  elif [[ -x "${HOME}/.local/bin/openclaw" ]]; then
    OPENCLAW_BIN="${HOME}/.local/bin/openclaw"
  fi
fi
if [[ -z "$OPENCLAW_BIN" ]]; then
  printf '[%s] skip: openclaw binary not found\n' "$(date -Iseconds)" >> "$LOG"
  exit 0
fi

plan="$(python3 - "$ALERTS_JSON" "$STATE_JSON" "$CRIT_COOLDOWN_SEC" "$WARN_COOLDOWN_SEC" "$ALERT_NOTIFY_WARN_ENABLED" "$REPORT_MD" <<'PY'
import json
import pathlib
import sys
from datetime import datetime, timezone

alerts_path = pathlib.Path(sys.argv[1])
state_path = pathlib.Path(sys.argv[2])
crit_cooldown = int(sys.argv[3])
warn_cooldown = int(sys.argv[4])
warn_enabled = sys.argv[5].lower() == "true"
report_md = pathlib.Path(sys.argv[6])

alerts = json.loads(alerts_path.read_text(encoding='utf-8'))
severity = str(alerts.get('severity', 'ok')).lower()
if severity not in {'critical', 'warning'}:
    print(json.dumps({'send': False, 'reason': 'severity_not_actionable'}))
    raise SystemExit(0)
if severity == 'warning' and not warn_enabled:
    print(json.dumps({'send': False, 'reason': 'warning_disabled'}))
    raise SystemExit(0)

state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except Exception:
        state = {}

now = int(datetime.now(timezone.utc).timestamp())
reasons = alerts.get('reasons') or []
sig = {
    'severity': severity,
    'reasons': sorted(str(r) for r in reasons),
    'fail_rate': round(float(alerts.get('fail_rate', 0.0) or 0.0), 3),
    'queue_depth': int(alerts.get('queue_depth', 0) or 0),
}
fingerprint = json.dumps(sig, ensure_ascii=False, sort_keys=True)

last = (state.get('last') or {}).get(severity, {})
last_ts = int(last.get('ts', 0) or 0)
last_fp = str(last.get('fingerprint', ''))
cd = crit_cooldown if severity == 'critical' else warn_cooldown
if last_fp == fingerprint and (now - last_ts) < cd:
    print(json.dumps({'send': False, 'reason': 'cooldown_dedup'}))
    raise SystemExit(0)

state.setdefault('last', {})[severity] = {'ts': now, 'fingerprint': fingerprint}
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

title = f"Beatless Alert {severity.upper()}"
msg = [
    title,
    f"fail_rate={float(alerts.get('fail_rate', 0.0) or 0.0):.3f}",
    f"queue_depth={int(alerts.get('queue_depth', 0) or 0)}",
    f"window_events_total={int(alerts.get('window_events_total', 0) or 0)}",
]
if reasons:
    msg.append("reasons=" + ", ".join(str(r) for r in reasons[:4]))
msg.append(f"evidence_path={report_md}")
print(json.dumps({'send': True, 'message': " | ".join(msg), 'severity': severity}, ensure_ascii=False))
PY
)"

send="$(printf '%s' "$plan" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("true" if d.get("send") else "false")')"
if [[ "$send" != "true" ]]; then
  printf '[%s] skip: %s\n' "$(date -Iseconds)" "$(printf '%s' "$plan" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason","no_reason"))')" >> "$LOG"
  exit 0
fi
msg="$(printf '%s' "$plan" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("message",""))')"

"$OPENCLAW_BIN" message send --channel feishu -t "$ALERT_NOTIFY_CHAT_ID" -m "$msg" >/dev/null 2>&1 || true
printf '[%s] sent: %s\n' "$(date -Iseconds)" "$msg" >> "$LOG"
