#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC="$ROOT/runtime/nlm/smoke-source.md"
mkdir -p "$ROOT/runtime/nlm"
cat > "$SRC" <<'EOF'
# Smoke Source

- Finding 1: Step 3.5 Flash remains main chain.
- Finding 2: MiniMax M2.7 should stay in search side lane.
- Finding 3: NotebookLM writeback must be sidecar and bounded.
- Finding 4: Avoid context pollution in heartbeat.
- Finding 5: Keep acceptance deterministic.
EOF

OUT="$(bash scripts/notebooklm_sidecar_sync.sh --source-file "$SRC" --topic smoke --dry-run)"
echo "$OUT"

SYNC_FILE="$ROOT/runtime/nlm/last_sync.json"
if [[ ! -f "$SYNC_FILE" ]]; then
  echo "[smoke-nlm] missing last_sync.json" >&2
  exit 1
fi

python3 - "$SYNC_FILE" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("sync_status") not in {"local_only", "synced"}:
    raise SystemExit(f"unexpected sync_status={payload.get('sync_status')}")
if not payload.get("sidecar_file"):
    raise SystemExit("missing sidecar_file")
print("[smoke-nlm] PASS", payload["sidecar_file"])
PY
