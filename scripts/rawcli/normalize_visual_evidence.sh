#!/usr/bin/env bash
set -euo pipefail

# normalize_visual_evidence.sh
# Normalize screenshot/web evidence into Report/screenshots with a manifest.

REPORT_DIR="/home/yarizakurahime/claw/Report/screenshots"
MANIFEST_JSON="$REPORT_DIR/manifest-latest.json"
MANIFEST_MD="$REPORT_DIR/manifest-latest.md"

SRC_DIRS=(
  "/home/yarizakurahime/.openclaw/workspace/screenshots"
  "/home/yarizakurahime/.openclaw/workspace-lacia/screenshots"
  "/home/yarizakurahime/.openclaw/workspace-kouka/screenshots"
  "/home/yarizakurahime/.openclaw/workspace-methode/screenshots"
)

mkdir -p "$REPORT_DIR"

python3 - "$REPORT_DIR" "$MANIFEST_JSON" "$MANIFEST_MD" "${SRC_DIRS[@]}" <<'PY'
import hashlib
import json
import pathlib
import shutil
import sys
from datetime import datetime

report_dir = pathlib.Path(sys.argv[1])
manifest_json = pathlib.Path(sys.argv[2])
manifest_md = pathlib.Path(sys.argv[3])
sources = [pathlib.Path(p) for p in sys.argv[4:]]

report_dir.mkdir(parents=True, exist_ok=True)
entries = []
seen_hash = set()

for src in sources:
    if not src.exists():
        continue
    for p in sorted(src.glob('*.png')):
        try:
            data = p.read_bytes()
        except Exception:
            continue
        h = hashlib.sha256(data).hexdigest()
        if h in seen_hash:
            continue
        seen_hash.add(h)
        dst = report_dir / p.name
        if not dst.exists():
            try:
                shutil.copy2(p, dst)
            except Exception:
                continue
        entries.append({
            'name': p.name,
            'sha256': h,
            'source': str(p),
            'normalized_path': str(dst),
            'size_bytes': dst.stat().st_size if dst.exists() else 0,
            'mtime': datetime.fromtimestamp(dst.stat().st_mtime).astimezone().isoformat() if dst.exists() else '',
        })

entries = sorted(entries, key=lambda x: x.get('mtime', ''), reverse=True)
payload = {
    'generated_at': datetime.now().astimezone().isoformat(),
    'count': len(entries),
    'entries': entries[:200],
}
manifest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lines = [
    '# Screenshot Evidence Manifest',
    '',
    f"- generated_at: {payload['generated_at']}",
    f"- count: {payload['count']}",
    '',
    '## Latest',
]
for e in entries[:30]:
    lines.append(f"- {e['name']} -> {e['normalized_path']}")
manifest_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(str(manifest_json))
PY
