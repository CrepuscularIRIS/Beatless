---
name: codex-router
description: Delegate a task to OpenAI Codex CLI (`codex exec`). Preset for terminal debugging, running test suites, code-correctness review, and shell-driven fix loops. Returns structured pass/fail with evidence.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [routing, codex, debugging, testing, correctness]
    related_skills: [claude-code-router, gemini-router]
---

# codex-router

When to use: tasks where Codex's strength shines — **iterative shell loops** (`run test → read failure → fix → rerun`), **correctness review** of an existing diff, or **environment debugging** where the LLM needs to actually exec commands and read outputs.

## Inputs

- `task` — action-oriented prompt
- `working_dir` — absolute path; Codex starts here
- `model` — defaults to `gpt-5.4-codex` for review, `gpt-5.3-codex` for debug rescue (per memory `feedback_model_routing`)
- `effort` — `low` / `medium` / `high`, defaults to `medium`
- `timeout_seconds` — defaults to `1200`

## Invocation recipe

```bash
TASK="${1:?task required}"
WORKING_DIR="${2:?working_dir required}"
MODEL="${MODEL:-gpt-5.4-codex}"
EFFORT="${EFFORT:-medium}"
TIMEOUT="${TIMEOUT_SECONDS:-1200}"

cd "$WORKING_DIR" || { echo "FAILED: cannot cd $WORKING_DIR"; exit 2; }

timeout "$TIMEOUT" codex exec \
  --model "$MODEL" \
  --effort "$EFFORT" \
  "$TASK" </dev/null
```

## Output contract

Codex output ends with one of:

- `RESULT: ok` — task succeeded
- `RESULT: fail — <reason>` — task failed (caller surfaces reason)
- `RESULT: needs-human` — Codex hit a block it can't resolve

Numeric scores (for review tasks): `SCORE: <0-10>` on a final line.

## When to choose this over claude-code-router

| Need | Pick |
|---|---|
| Run tests + fix failures iteratively | codex-router |
| Edit many files based on a spec | claude-code-router |
| Review correctness of a written diff | codex-router |
| Author PR description + commit | claude-code-router |
| Debug "why does this command fail" | codex-router |

## Anti-patterns

- ❌ Do NOT use Codex to JUDGE Codex's own output (per Regulations § Three Core Principles — no model family judges itself)
- ❌ Do NOT remove `</dev/null` — same hang issue as Claude Code
