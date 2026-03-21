#!/usr/bin/env bash
set -euo pipefail

# backlog_groomer.sh — lightweight auto task discovery + scoring.

BEATLESS="${HOME}/.openclaw/beatless"
TASKS="$BEATLESS/TASKS.yaml"
LOG="$BEATLESS/logs/backlog-groomer.log"
GROOMER_ENABLED="${GROOMER_ENABLED:-false}"
SCAN_ROOT="${GROOMER_SCAN_ROOT:-/home/yarizakurahime/claw}"
MAX_CANDIDATES="${GROOMER_MAX_CANDIDATES:-8}"
PROMOTE_SCORE="${GROOMER_PROMOTE_SCORE:-40}"
MAX_NEW="${GROOMER_MAX_NEW:-3}"

if [[ "$GROOMER_ENABLED" != "true" ]]; then
  echo "Groomer disabled (GROOMER_ENABLED=$GROOMER_ENABLED)"
  exit 0
fi

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
log "groomer started"

python3 - "$TASKS" "$SCAN_ROOT" "$MAX_CANDIDATES" "$PROMOTE_SCORE" "$MAX_NEW" <<'PY'
import pathlib
import re
import sys
from datetime import datetime

try:
    import yaml
except Exception:
    raise SystemExit(0)

tasks_path = pathlib.Path(sys.argv[1])
scan_root = pathlib.Path(sys.argv[2])
max_candidates = max(1, int(sys.argv[3]))
promote_score = int(sys.argv[4])
max_new = max(1, int(sys.argv[5]))

if not tasks_path.exists():
    print("groomer: tasks file missing")
    raise SystemExit(0)

data = yaml.safe_load(tasks_path.read_text(encoding='utf-8')) or {}
queues = data.setdefault("queues", {})
backlog = queues.setdefault("backlog", [])
tasks = data.setdefault("tasks", [])

existing_ids = set()
for t in tasks:
    if isinstance(t, dict) and t.get("id"):
        existing_ids.add(str(t["id"]))
for item in backlog:
    if isinstance(item, dict) and item.get("id"):
        existing_ids.add(str(item["id"]))
    elif isinstance(item, str):
        existing_ids.add(item)

pattern = re.compile(r"(TODO|FIXME|BUG|HACK)", re.IGNORECASE)
candidates = []
for path in scan_root.rglob("*"):
    if not path.is_file():
        continue
    if any(part.startswith(".git") for part in path.parts):
        continue
    if path.suffix.lower() in {".png",".jpg",".jpeg",".webp",".zip",".sqlite",".db"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    m = pattern.search(text)
    if not m:
        continue
    score = 20
    if "FIXME" in text[:20000]:
        score += 15
    if "BUG" in text[:20000]:
        score += 20
    if "TODO" in text[:20000]:
        score += 10
    rel = str(path)
    score += min(20, rel.count("/") * 2)
    candidates.append((score, path))
    if len(candidates) >= max_candidates:
        break

candidates.sort(key=lambda x: x[0], reverse=True)
added = 0
for score, path in candidates:
    if score < promote_score or added >= max_new:
        continue
    stem = path.stem[:40].replace(" ", "-")
    task_id = f"BT-GROOM-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{added+1}"
    if task_id in existing_ids:
        continue
    title = f"Auto-discovered cleanup: {stem}"
    desc = f"Detected TODO/FIXME marker in {path}. Please inspect and resolve."
    item = {
        "id": task_id,
        "title": title,
        "type": "maintenance",
        "mode": "daily",
        "priority": "medium",
        "source": "groomer",
        "created_at": datetime.now().astimezone().isoformat(),
        "value_score": int(score),
        "value_band": "high" if score >= 70 else "medium",
        "value_reasons": [f"marker:{path.name}"],
        "suggested_agent": "methode",
        "suggested_executor_tool": "codex_cli",
    }
    backlog.append(item)
    tasks.append({
        "id": task_id,
        "title": title,
        "description": desc,
        "type": "maintenance",
        "priority": "medium",
        "status": "backlog",
        "owner_agent": "methode",
        "executor_tool": "codex_cli",
        "created_at": datetime.now().astimezone().isoformat(),
        "value_score": int(score),
    })
    existing_ids.add(task_id)
    added += 1

if added:
    data.setdefault("meta", {})["updated_at"] = datetime.now().astimezone().isoformat()
    tasks_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"groomer: added={added}")
PY

log "groomer finished"
echo "groomer: done"
