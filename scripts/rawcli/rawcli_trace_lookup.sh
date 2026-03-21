#!/usr/bin/env bash
set -euo pipefail

# rawcli_trace_lookup.sh
# Lookup end-to-end trace chain: ingress -> submit -> dispatch result -> receipt gate.
# Usage: rawcli_trace_lookup.sh <task_id_or_trace_id>

BEATLESS="${HOME}/.openclaw/beatless"
ARG="${1:-}"
if [[ -z "$ARG" ]]; then
  echo "Usage: $0 <task_id_or_trace_id>" >&2
  exit 2
fi

INGRESS="$BEATLESS/metrics/ingress-events.jsonl"
SUBMIT="$BEATLESS/metrics/dispatch-submit-events.jsonl"
DISPATCH="$BEATLESS/metrics/dispatch-events.jsonl"
RECEIPT="$BEATLESS/metrics/receipt-gate-events.jsonl"
RESULTS="$BEATLESS/dispatch-results"
OUT_JSON="$BEATLESS/metrics/trace-lookup-latest.json"
OUT_MD="/home/yarizakurahime/claw/Report/trace-lookup-latest.md"

mkdir -p "$BEATLESS/metrics" "/home/yarizakurahime/claw/Report"

python3 - "$ARG" "$INGRESS" "$SUBMIT" "$DISPATCH" "$RECEIPT" "$RESULTS" "$OUT_JSON" "$OUT_MD" <<'PY'
import json
import pathlib
import sys

needle = sys.argv[1]
ingress_p = pathlib.Path(sys.argv[2])
submit_p = pathlib.Path(sys.argv[3])
dispatch_p = pathlib.Path(sys.argv[4])
receipt_p = pathlib.Path(sys.argv[5])
results_dir = pathlib.Path(sys.argv[6])
out_json = pathlib.Path(sys.argv[7])
out_md = pathlib.Path(sys.argv[8])

def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for ln in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            rows.append(json.loads(s))
        except Exception:
            continue
    return rows

ingress = load_jsonl(ingress_p)
submit = load_jsonl(submit_p)
dispatch = load_jsonl(dispatch_p)
receipt = load_jsonl(receipt_p)

cand_task_ids = set()
cand_trace_ids = set()
for src in (ingress, submit, dispatch, receipt):
    for r in src:
        if str(r.get('task_id', '')) == needle:
            cand_task_ids.add(needle)
            if r.get('trace_id'):
                cand_trace_ids.add(str(r.get('trace_id')))
        if str(r.get('trace_id', '')) == needle:
            cand_trace_ids.add(needle)
            if r.get('task_id'):
                cand_task_ids.add(str(r.get('task_id')))

if not cand_task_ids and not cand_trace_ids and results_dir.exists():
    result_file = results_dir / f"{needle}.json"
    if result_file.exists():
        try:
            d = json.loads(result_file.read_text(encoding='utf-8'))
            if d.get('task_id'):
                cand_task_ids.add(str(d['task_id']))
            if d.get('trace_id'):
                cand_trace_ids.add(str(d['trace_id']))
        except Exception:
            pass

if not cand_task_ids and not cand_trace_ids:
    payload = {'query': needle, 'found': False}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    out_md.write_text("# Trace Lookup\n\n- query: " + needle + "\n- found: false\n", encoding='utf-8')
    print(str(out_json))
    raise SystemExit(1)

def filt(rows):
    out = []
    for r in rows:
        tid = str(r.get('task_id', ''))
        trid = str(r.get('trace_id', ''))
        if (tid and tid in cand_task_ids) or (trid and trid in cand_trace_ids):
            out.append(r)
    return out

matches = {
    'ingress': filt(ingress),
    'submit': filt(submit),
    'dispatch': filt(dispatch),
    'receipt_gate': filt(receipt),
}

result_files = []
for tid in sorted(cand_task_ids):
    p = results_dir / f"{tid}.json"
    if p.exists():
        try:
            result_files.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass

payload = {
    'query': needle,
    'found': True,
    'task_ids': sorted(cand_task_ids),
    'trace_ids': sorted(cand_trace_ids),
    'matches': matches,
    'results': result_files,
}
out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

lines = [
    "# Trace Lookup",
    "",
    f"- query: {needle}",
    f"- found: true",
    f"- task_ids: {', '.join(sorted(cand_task_ids)) if cand_task_ids else 'none'}",
    f"- trace_ids: {', '.join(sorted(cand_trace_ids)) if cand_trace_ids else 'none'}",
    "",
    "## Stage Counts",
]
for k in ('ingress','submit','dispatch','receipt_gate'):
    lines.append(f"- {k}: {len(matches[k])}")

if result_files:
    lines += ["", "## Result Status"]
    for r in result_files:
        lines.append(f"- {r.get('task_id')}: {r.get('status')} (trace_id={r.get('trace_id','')})")

out_md.write_text("\n".join(lines) + "\n", encoding='utf-8')
print(str(out_json))
PY
