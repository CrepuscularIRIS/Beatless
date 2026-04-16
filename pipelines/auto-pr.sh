#!/usr/bin/env bash
# Auto PR Pipeline — runs on heartbeat, discovers and submits PRs
# Replaces github-hunt. Interval: 2.5h (controlled by pipeline state + heartbeat)
set -euo pipefail

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_DIR="$HOME/.hermes/shared/logs"
LOG_FILE="${LOG_DIR}/auto-pr-${TIMESTAMP}.log"
SESSION_NAME="auto-pr"
LOCK_FILE="/tmp/auto-pr.lock"

mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$PID" 2>/dev/null; then
    echo "[$TIMESTAMP] auto-pr already running (PID $PID), skipping"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# Kill stale session
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

echo "[$TIMESTAMP] Starting auto-pr pipeline"
echo "  Log: $LOG_FILE"

PROMPT='Execute the github-pr skill. This is a REAL submission run.

RULES:
1. Find ONE fixable issue (good-first-issue / help-wanted / confirmed bug) in an agent/LLM/devtool repo.
2. PREFER small-to-medium repos (<100MB clone). Skip terrazzo, llama_index, marvin (already done).
3. Complete ALL phases including Phase 2.5 (issue comment), fork workflow, Phase 9b iterative improvement.
4. Git identity: CrepuscularIRIS <serenitygp@qq.com>
5. Fork to CrepuscularIRIS/<repo>, push to fork, create PR via gh pr create --head CrepuscularIRIS:<branch>.
6. Phase 10 pre-flight must ALL pass before creating PR.
7. If no suitable issue found after checking 30+ issues, exit cleanly with a report explaining why.
8. If bug cannot be reproduced dynamically, skip and try next issue.
9. Maximum 1 PR per run.

Save results to ~/workspace/pr-stage/<repo-name>/pr-report.md with chain verification section.'

tmux new-session -d -s "$SESSION_NAME" bash -c "
  echo '=== auto-pr started at $(date -u) ===' | tee '$LOG_FILE'

  timeout 5400 claude \
    --dangerously-skip-permissions \
    --verbose \
    --add-dir $HOME/workspace \
    -p '$PROMPT' \
    2>&1 | tee -a '$LOG_FILE'

  EXIT_CODE=\$?
  END_TS=\$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  echo \"=== auto-pr finished at \$END_TS (exit=\$EXIT_CODE) ===\" | tee -a '$LOG_FILE'
"

echo "tmux session '$SESSION_NAME' launched."
echo "  Attach:  tmux attach -t $SESSION_NAME"
echo "  Tail:    tail -f $LOG_FILE"
