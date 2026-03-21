#!/usr/bin/env bash
set -euo pipefail

# rawcli_observability_panel.sh
# Build unified local observability panel from runtime metrics.

BEATLESS="${HOME}/.openclaw/beatless"
METRICS="$BEATLESS/metrics/rawcli-metrics-latest.json"
HEALTH="$BEATLESS/metrics/healthcheck-latest.json"
ALERTS="$BEATLESS/metrics/rawcli-alerts-latest.json"
TRACE="$BEATLESS/metrics/trace-lookup-latest.json"
SCREENSHOT_MANIFEST="/home/yarizakurahime/claw/Report/screenshots/manifest-latest.json"
EXPERIMENT_EVENTS="$BEATLESS/metrics/experiment-batches.jsonl"
OUT_MD="/home/yarizakurahime/claw/Report/rawcli-observability-latest.md"
OUT_JSON="$BEATLESS/metrics/rawcli-observability-latest.json"

mkdir -p "$BEATLESS/metrics" "/home/yarizakurahime/claw/Report"

python3 - "$METRICS" "$HEALTH" "$ALERTS" "$TRACE" "$SCREENSHOT_MANIFEST" "$EXPERIMENT_EVENTS" "$OUT_JSON" "$OUT_MD" <<'PY'
import json
import pathlib
import sys
from datetime import datetime

metrics_p = pathlib.Path(sys.argv[1])
health_p = pathlib.Path(sys.argv[2])
alerts_p = pathlib.Path(sys.argv[3])
trace_p = pathlib.Path(sys.argv[4])
shot_p = pathlib.Path(sys.argv[5])
exp_p = pathlib.Path(sys.argv[6])
out_json = pathlib.Path(sys.argv[7])
out_md = pathlib.Path(sys.argv[8])

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

m = load(metrics_p)
h = load(health_p)
a = load(alerts_p)
t = load(trace_p)
s = load(shot_p)
exp_latest = {}
if exp_p.exists():
    for ln in exp_p.read_text(encoding='utf-8', errors='ignore').splitlines()[::-1]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            exp_latest = json.loads(ln)
        except Exception:
            exp_latest = {}
        if exp_latest:
            break

payload = {
    'generated_at': datetime.now().astimezone().isoformat(),
    'metrics': {
        'queue_depth': m.get('queue_depth', 0),
        'fail_rate': (m.get('window') or {}).get('fail_rate', 0.0),
        'ack_latency_ms_p95': m.get('ack_latency_ms_p95', 0.0),
        'dispatch_duration_sec_p95': m.get('dispatch_duration_sec_p95', 0.0),
        'queue_lag_ms_p95': m.get('queue_lag_ms_p95', 0.0),
        'mode': m.get('mode', 'daily'),
    },
    'health': {
        'verdict': h.get('verdict', 'unknown'),
        'pass': h.get('pass', 0),
        'warn': h.get('warn', 0),
        'fail': h.get('fail', 0),
    },
    'alert': {
        'severity': a.get('severity', 'ok'),
        'reasons': a.get('reasons', []),
        'task_id': a.get('task_id', ''),
    },
    'trace_lookup': {
        'query': t.get('query', ''),
        'found': t.get('found', False),
        'task_ids': t.get('task_ids', []),
        'trace_ids': t.get('trace_ids', []),
    },
    'screenshots': {
        'count': s.get('count', 0),
        'latest': ((s.get('entries') or [{}])[0] if s.get('entries') else {}),
    },
    'experiments': {
        'latest_run_id': exp_latest.get('run_id', ''),
        'latest_group': exp_latest.get('group', ''),
        'latest_status': exp_latest.get('status', ''),
        'latest_ts': exp_latest.get('ts', ''),
    },
}
out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

lines = [
    '# RawCli Observability Panel',
    '',
    f"- generated_at: {payload['generated_at']}",
    '',
    '## Runtime Metrics',
    f"- mode: {payload['metrics']['mode']}",
    f"- queue_depth: {payload['metrics']['queue_depth']}",
    f"- fail_rate: {payload['metrics']['fail_rate']:.3f}",
    f"- ack_latency_ms_p95: {payload['metrics']['ack_latency_ms_p95']:.1f}",
    f"- dispatch_duration_sec_p95: {payload['metrics']['dispatch_duration_sec_p95']:.2f}",
    f"- queue_lag_ms_p95: {payload['metrics']['queue_lag_ms_p95']:.1f}",
    '',
    '## Health',
    f"- verdict: {payload['health']['verdict']}",
    f"- pass/warn/fail: {payload['health']['pass']}/{payload['health']['warn']}/{payload['health']['fail']}",
    '',
    '## Alert',
    f"- severity: {payload['alert']['severity']}",
    f"- task_id: {payload['alert']['task_id'] or 'n/a'}",
]
if payload['alert']['reasons']:
    lines.append('- reasons: ' + ', '.join(str(r) for r in payload['alert']['reasons']))

lines += [
    '',
    '## Trace Snapshot',
    f"- query: {payload['trace_lookup']['query'] or 'n/a'}",
    f"- found: {payload['trace_lookup']['found']}",
]
if payload['trace_lookup']['task_ids']:
    lines.append('- task_ids: ' + ', '.join(payload['trace_lookup']['task_ids']))
if payload['trace_lookup']['trace_ids']:
    lines.append('- trace_ids: ' + ', '.join(payload['trace_lookup']['trace_ids']))

lines += [
    '',
    '## Visual Evidence',
    f"- screenshots_count: {payload['screenshots']['count']}",
]
if payload['screenshots']['latest']:
    lines.append(f"- latest_png: {payload['screenshots']['latest'].get('normalized_path', 'n/a')}")

lines += [
    '',
    '## Experiment Batch',
    f"- latest_run_id: {payload['experiments']['latest_run_id'] or 'n/a'}",
    f"- latest_group/status: {(payload['experiments']['latest_group'] or 'n/a')}/{(payload['experiments']['latest_status'] or 'n/a')}",
]

out_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(str(out_json))
PY
