#!/usr/bin/env bash
# test-run.sh — Shell-orchestrated blog-maintenance pipeline
#
# Architecture: Shell is the orchestrator.
# Uses claude in interactive mode (not --print) so it can use Agent tool
# to spawn codex:codex-rescue and gemini:gemini-consult subagents.
#
# Usage: bash test-run.sh
# Monitor: tmux attach -t blog-maintenance
# Logs: ~/.hermes/shared/logs/blog-maintenance-<timestamp>.log

set -euo pipefail

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_DIR="/home/yarizakurahime/claw/.openclaw/hermes/logs"
LOG_FILE="${LOG_DIR}/blog-maintenance-${TIMESTAMP}.log"
RESULT_FILE="${LOG_DIR}/blog-maintenance-${TIMESTAMP}.result"
SESSION_NAME="blog-maintenance"

mkdir -p "$LOG_DIR"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

echo "[$TIMESTAMP] Starting blog-maintenance pipeline"
echo "  Log: $LOG_FILE"
echo "  Monitor: tmux attach -t $SESSION_NAME"
echo "  Result: $RESULT_FILE"

tmux new-session -d -s "$SESSION_NAME" bash -c "
  export HOME=/home/yarizakurahime
  export PATH=/home/yarizakurahime/.bun/bin:/home/yarizakurahime/.local/bin:/home/yarizakurahime/.cargo/bin:/usr/local/bin:/usr/bin:/bin
  export GH_CONFIG_DIR=/home/yarizakurahime/.config/gh
  cd \$HOME/blog

  echo '=== blog-maintenance pipeline started at $(date -u) ===' | tee '$LOG_FILE'

  timeout 3600 /home/yarizakurahime/.bun/bin/claude \
    --dangerously-skip-permissions \
    --verbose \
    --add-dir $HOME/blog \
    -p 'Execute the blog-maintenance skill: audit existing posts in ~/blog/src/content/blogs/, research trending AI/ML topics using Gemini (gemini:gemini-consult agent), write 2 new posts and rewrite 1, verify build with pnpm build, then run quality review using both Codex (codex:codex-rescue agent) and Gemini IN PARALLEL. Both must actually run. Commit if build passes and reviews are acceptable. Do NOT push.' \
    2>&1 | tee -a '$LOG_FILE'

  EXIT_CODE=\$?
  END_TS=\$(date -u +'%Y-%m-%dT%H:%M:%SZ')

  echo '' | tee -a '$LOG_FILE'
  echo \"=== Pipeline finished at \$END_TS (exit=\$EXIT_CODE) ===\" | tee -a '$LOG_FILE'

  cat > '$RESULT_FILE' <<EOF
{
  \"pipeline\": \"blog-maintenance\",
  \"status\": \"\$([ \$EXIT_CODE -eq 0 ] && echo 'DONE' || echo 'FAILED')\",
  \"exit_code\": \$EXIT_CODE,
  \"started_at\": \"$TIMESTAMP\",
  \"finished_at\": \"\$END_TS\",
  \"log_file\": \"$LOG_FILE\"
}
EOF

  echo 'Result written to $RESULT_FILE'
"

echo ""
echo "tmux session '$SESSION_NAME' launched."
echo "  Attach:  tmux attach -t $SESSION_NAME"
echo "  Tail:    tail -f $LOG_FILE"
echo "  Check:   cat $RESULT_FILE"
