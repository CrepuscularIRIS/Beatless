---
name: gemini-router
description: Delegate a task to Gemini CLI (`gemini -p`). Preset for long-context reading, research, translation review, and adversarial second-opinion passes. The 1M+ context window is its key affordance.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [routing, gemini, research, translation, long-context]
    related_skills: [claude-code-router, codex-router]
---

# gemini-router

When to use: tasks whose **input is huge** (entire codebase audit, full paper PDF, long transcripts) OR tasks that need an **independent third opinion** distinct from Anthropic + OpenAI model families (per Regulations § Triple-Heterogeneous Review).

## Inputs

- `task` — prompt
- `model` — defaults to `gemini-3.1-pro`; use `gemini-3-flash` for cheap research
- `working_dir` — optional; if set, Gemini's tool calls run from there
- `effort` — `low` / `medium` / `high`, defaults to `medium`
- `timeout_seconds` — defaults to `1500`

## Invocation recipe

```bash
TASK="${1:?task required}"
WORKING_DIR="${2:-$PWD}"
MODEL="${MODEL:-gemini-3.1-pro}"
EFFORT="${EFFORT:-medium}"
TIMEOUT="${TIMEOUT_SECONDS:-1500}"

cd "$WORKING_DIR" 2>/dev/null

timeout "$TIMEOUT" gemini -p "$TASK" \
  --model "$MODEL" \
  --effort "$EFFORT" </dev/null
```

## Output contract

- `VERDICT: <pass|fail|flag|ambiguous>` on the final line
- Optional `EVIDENCE: <one-paragraph>` for review tasks

## When to choose this over the others

| Need | Pick |
|---|---|
| Cross-check a translation for fluency | gemini-router |
| Read 200k-token codebase to find a pattern | gemini-router |
| Adversarial third pass on a Codex-reviewed PR | gemini-router |
| Author code | claude-code-router |
| Run + fix tests | codex-router |

## Anti-patterns

- ❌ Do NOT use Gemini for code authoring — its tool-use loop is weaker than Claude Code / Codex on this workload
- ❌ Do NOT remove `</dev/null`
