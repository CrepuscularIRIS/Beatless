#!/usr/bin/env bash
set -euo pipefail

# codex_state_repair.sh
# Repairs Codex state DB migration mismatch warnings by backing up and recreating state sqlite files.

CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
REPORT_DIR="/home/yarizakurahime/claw/Report"
OUT="${TMPDIR:-/tmp}/codex_state_probe.out"
NOW="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$CODEX_HOME_DIR/backups/state-repair-$NOW"
REPORT_FILE="$REPORT_DIR/codex-state-repair-latest.md"
FORCE="${CODEX_STATE_REPAIR_FORCE:-false}"
PATTERN='migration [0-9]+ was previously applied but is missing in the resolved migrations'

mkdir -p "$REPORT_DIR" "$CODEX_HOME_DIR/backups"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex_state_repair: codex binary not found" >&2
  exit 2
fi

probe_codex() {
  codex exec -m gpt-5.3-codex --skip-git-repo-check "Output exactly one line: codex_state_probe_ok" >"$OUT" 2>&1 || true
}

probe_codex

if ! grep -Eq "$PATTERN" "$OUT" && [[ "$FORCE" != "true" ]]; then
  cat > "$REPORT_FILE" <<RPT
# Codex State Repair

- time: $(date -Iseconds)
- status: skipped
- reason: no migration mismatch warning detected
- output_probe: $OUT
RPT
  echo "codex_state_repair: no mismatch detected"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
for f in \
  state_5.sqlite state_5.sqlite-shm state_5.sqlite-wal \
  logs_1.sqlite logs_1.sqlite-shm logs_1.sqlite-wal
do
  if [[ -f "$CODEX_HOME_DIR/$f" ]]; then
    cp -f "$CODEX_HOME_DIR/$f" "$BACKUP_DIR/$f"
    rm -f "$CODEX_HOME_DIR/$f"
  fi
done

probe_codex

if grep -Eq "$PATTERN" "$OUT"; then
  status="failed"
  note="warning still present after state reset"
  exit_code=1
else
  status="repaired"
  note="warning cleared after state reset"
  exit_code=0
fi

cat > "$REPORT_FILE" <<RPT
# Codex State Repair

- time: $(date -Iseconds)
- status: $status
- note: $note
- backup_dir: $BACKUP_DIR
- output_probe: $OUT

## Probe Output (head)

\`\`\`text
$(sed -n '1,40p' "$OUT")
\`\`\`
RPT

echo "codex_state_repair: $status"
exit "$exit_code"
