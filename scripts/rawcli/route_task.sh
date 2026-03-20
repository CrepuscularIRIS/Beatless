#!/usr/bin/env bash
set -euo pipefail

# route_task_v2.sh
# Usage: route_task_v2.sh "task text"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"task text\"" >&2
  exit 2
fi

TASK_TEXT="$*"
CFG="${HOME}/.openclaw/beatless/ROUTING.yaml"

python3 - "$TASK_TEXT" "$CFG" <<'PY'
import re
import sys
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

text = sys.argv[1]
cfg_path = Path(sys.argv[2])
fallback = {
    "id": "default",
    "owner_agent": "methode",
    "executor_tool": None,
    "priority": 10,
}

if yaml is None or not cfg_path.exists():
    selected = fallback
else:
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        rules = data.get("routing_rules") or []
    except Exception:
        rules = []

    norm = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        norm.append({
            "id": r.get("id", "unknown"),
            "pattern": r.get("pattern", ".*"),
            "owner_agent": r.get("owner_agent", "methode"),
            "executor_tool": r.get("executor_tool", None),
            "priority": int(r.get("priority", 0) or 0),
        })

    norm.sort(key=lambda x: x["priority"], reverse=True)
    selected = None
    for r in norm:
        try:
            if re.search(r["pattern"], text):
                selected = r
                break
        except re.error:
            continue
    if selected is None:
        selected = fallback

print(f"rule_id={selected['id']}")
print(f"owner_agent={selected['owner_agent']}")
et = selected.get('executor_tool')
print(f"executor_tool={'' if et is None else et}")
print(f"priority={selected['priority']}")
PY
