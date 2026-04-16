#!/usr/bin/env bash
# Auto PR Pipeline — runs on heartbeat, discovers and submits PRs
# Replaces github-hunt. Interval: 2.5h (controlled by pipeline state + heartbeat)
set -euo pipefail

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_DIR="/home/yarizakurahime/claw/.openclaw/hermes/logs"
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

ANTI-DUPLICATE RULES (CRITICAL — check these FIRST before any other work):
A. Run: gh api graphql -f query="{ search(query: \"author:CrepuscularIRIS is:pr is:open\", type: ISSUE, first: 100) { issueCount } }"
   If open PR count >= 30: STOP immediately, do not submit more. Report existing PR count and exit.
B. Before selecting ANY repo, check: gh pr list --repo <owner/repo> --author CrepuscularIRIS --state open
   If ANY open PR exists from CrepuscularIRIS in that repo: SKIP that entire repo.
C. ONE PR per repo per run. Never submit multiple PRs to the same repository.
D. Right before gh pr create, re-check for competing PRs on the same issue. If one appeared: ABORT.
E. Check ~/workspace/pr-stage/ — if a directory for this repo exists from the last 48h, SKIP it.

RULES:
1. Find ONE fixable issue (good-first-issue / help-wanted / confirmed bug) in an agent/LLM/devtool repo.
2. PREFER small-to-medium repos (<100MB clone).
3. SKIP these repos (already done/exhausted/have open PRs): terrazzo, llama_index, marvin, pydantic-ai, crewAI, dspy, langgraph, openai-python, chroma, vllm, litellm, agno, letta, aider, logfire, instructor, mem0, sglang, authentik, promptfoo, guardrails, litgpt, fasthtml, sqlite-utils.
4. Complete ALL phases including Phase 2.5 (issue comment), fork workflow, Phase 9b iterative improvement.
5. Git identity: CrepuscularIRIS <serenitygp@qq.com>
6. Fork to CrepuscularIRIS/<repo>, push to fork, create PR via gh pr create --head CrepuscularIRIS:<branch>.
7. Phase 10 pre-flight must ALL pass before creating PR.
8. If no suitable issue found after checking 30+ issues, exit cleanly with a report explaining why.
9. If bug cannot be reproduced dynamically, skip and try next issue.
10. Maximum 1 PR per run. NEVER more than 1.

Save results to ~/workspace/pr-stage/<repo-name>/pr-report.md with chain verification section.'

tmux new-session -d -s "$SESSION_NAME" bash -c "
  export HOME=/home/yarizakurahime
  export PATH=/home/yarizakurahime/.bun/bin:/home/yarizakurahime/.local/bin:/home/yarizakurahime/.cargo/bin:/usr/local/bin:/usr/bin:/bin
  export GH_CONFIG_DIR=/home/yarizakurahime/.config/gh
  cd \$HOME

  echo '=== auto-pr started at $(date -u) ===' | tee '$LOG_FILE'

  timeout 5400 /home/yarizakurahime/.bun/bin/claude \
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
