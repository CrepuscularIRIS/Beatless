#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP_CONTRACT="$ROOT/runtime/meta_harness/smoke-contract.json"
mkdir -p "$ROOT/runtime/meta_harness"

cat > "$TMP_CONTRACT" <<'EOF'
{
  "id": "job-meta-harness-smoke",
  "created_at": "2026-04-05T00:00:00+08:00",
  "priority": "p2",
  "goal": "Smoke test meta-harness sidecar runner integration path.",
  "context_refs": ["docs/V3_SIDECAR_INTEGRATION.md"],
  "editable_paths": ["Beatless/docs"],
  "non_goals": ["Do not touch production secrets"],
  "acceptance": {
    "must_pass": ["test -d .", "true"],
    "artifacts": ["runtime/meta_harness/*/result.json"],
    "smoke": ["meta-harness sidecar dry-run"]
  },
  "routing": {
    "planner": "claude_architect_cli",
    "builder": "claude_build_cli",
    "reviewer": "codex_review_cli",
    "search": "search_cli",
    "research": "gemini_research_cli"
  },
  "budget": {
    "max_iterations": 2,
    "max_wall_clock_minutes": 10,
    "max_retry": 0
  },
  "escalation": ["Need elevated privileges"],
  "handoff": {
    "required_files": ["result.json"],
    "summary_format": "findings-first"
  }
}
EOF

OUT="$(bash scripts/meta_harness_sidecar_run.sh --dry-run --contract "$TMP_CONTRACT")"
echo "$OUT"

RESULT_JSON="$(echo "$OUT" | sed -n 's/^RESULT_JSON=//p' | tail -n1)"
if [[ -z "$RESULT_JSON" || ! -f "$RESULT_JSON" ]]; then
  echo "[smoke-meta-harness] missing result json" >&2
  exit 1
fi

python3 - "$RESULT_JSON" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not result.get("verify_pass", False):
    raise SystemExit("verify_pass=false")
if "run_id" not in result:
    raise SystemExit("missing run_id")
print("[smoke-meta-harness] PASS", result["run_id"])
PY
