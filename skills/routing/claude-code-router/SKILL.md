---
name: claude-code-router
description: Delegate a coding task to the Claude Code CLI (`claude -p`). Preset for heavy file edits, multi-file refactors, GitHub PR creation, and codebase exploration. The caller passes a working directory + task; this skill spawns a subprocess, captures stdout/stderr, and returns a structured result.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [routing, claude-code, codegen, pr, refactor]
    related_skills: [codex-router, gemini-router]
---

# claude-code-router

When to use: any task that needs **Claude Code's specific tool chain** — `Edit`/`MultiEdit`, `Bash`, GitHub authentication, autonomous PR creation, or long-running file edits across many files.

## Inputs (caller MUST supply)

- `task` — the prompt for Claude Code (one paragraph, action-oriented)
- `working_dir` — absolute path Claude Code should `cd` into
- `model` — optional, defaults to `opus`
- `permission_mode` — optional, defaults to `bypassPermissions` (cron-safe)
- `timeout_seconds` — optional, defaults to `1800`
- `extra_args` — optional, list of additional flags

## Invocation recipe

```bash
TASK="${1:?task required}"
WORKING_DIR="${2:?working_dir required}"
MODEL="${MODEL:-opus}"
PERM="${PERMISSION_MODE:-bypassPermissions}"
TIMEOUT="${TIMEOUT_SECONDS:-1800}"

cd "$WORKING_DIR" || { echo "FAILED: cannot cd $WORKING_DIR"; exit 2; }

# stdin discipline: always </dev/null. Without this, codex/claude can hang waiting for tty input.
timeout "$TIMEOUT" claude -p \
  --model "$MODEL" \
  --permission-mode "$PERM" \
  "$TASK" </dev/null
```

## Output contract

The caller parses stdout looking for:

- `DONE: <summary>` on success
- `FAILED: <reason>` on any explicit failure
- A trailing line of the form `COMMIT_SHA: <sha>` when a commit was made

If neither marker appears, treat exit code as the source of truth.

## Cost discipline

- Default model `opus` — the caller MUST downgrade to `sonnet` or `haiku` for repetitive low-stakes work (e.g., per-issue triage)
- Timeout enforced at 30 min; if a task needs longer, split it into checkpoints

## Anti-patterns

- ❌ Do NOT remove `</dev/null` — Claude Code will hang waiting for tty input in cron runs
- ❌ Do NOT pass secrets in the task string; use env vars + `~/.hermes/.env`
- ❌ Do NOT call this skill in tight loops — it is a heavyweight engine; batch tasks instead
