---
description: Check experiment workspace readiness. Detects quick/full mode, verifies GPU, data, branch, planning files, and plugin availability. Run before any exp-* command.
allowed-tools: Bash, Read, Glob, Grep, Agent, Skill, mcp__plugin_gsd_gsd__*
---

# Experiment Status

Fast readiness diagnostic for the current workspace.

## Checks

### 1. Repo and Branch
```bash
git rev-parse --is-inside-work-tree
git branch --show-current
git status --short
```

### 2. Mode Detection
- If `Task.md` exists in project root → **Full Mode** (dual-GPU, long budget)
- If `program.md` + `train.py` exist → **Quick Mode** (single-GPU, short budget)
- If both exist → Full Mode takes precedence
- If neither → report "no experiment spec found"

### 3. GPU State
```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
```
- Quick mode: need at least 1 idle GPU
- Full mode: need 2 idle GPUs (GPU0 + GPU1)

### 4. Runtime
```bash
command -v uv && uv run python --version
command -v python && python --version
```

### 5. Data/Cache
- Check paths referenced in Task.md or program.md
- Common: `~/.cache/autoresearch/data`, `~/.cache/autoresearch/tokenizer`
- Project-specific: read Task.md for data paths

### 6. Planning Files
- `task_plan.md` — current plan (exists? stale?)
- `findings.md` — accumulated knowledge
- `progress.md` — run history
- `results.tsv` — experiment ledger (header valid?)

### 7. Integration Availability
Test each integration non-destructively. Report available/unavailable:

| Integration | How to check | Role |
|-------------|-------------|------|
| Codex CLI | Agent tool responds with subagent_type "codex-cli" | Code edits |
| Gemini CLI | Agent tool responds with subagent_type "gemini-cli" | Literature + review |
| Superpowers | Skill tool "superpowers:brainstorming" loads | Parallel brainstorming |
| GSD | MCP tools mcp__plugin_gsd_gsd__* accessible | Verification + metrics |
| Planning-with-files | Skill "planning-with-files:status" loads | State persistence |

For Codex CLI and Gemini CLI, invoke only a lightweight Agent readiness prompt:
```
Readiness check only. Verify the local CLI bridge is usable. Do not edit files.
```
Do not run experiments or code edits during status checks.

### 8. Session Continuity
- If progress.md exists with running PIDs → check if still alive
- If results.tsv has entries → report last experiment and best metric
- If previous session crashed → report recovery instructions
- If progress.md or findings.md says HALT / halted / smoke rule satisfied, report `Next: none`
  unless the user explicitly asks to create a new experiment workspace.

## Output Format

Compact table:

```
Experiment Status — <project-name>
Mode:    [Quick / Full / Unknown]
Branch:  [name or detached]

| Check            | Status | Detail                    |
|------------------|--------|---------------------------|
| GPU              | PASS   | 2x RTX 4090 48GB idle     |
| Data             | PASS   | cache valid                |
| Planning files   | WARN   | progress.md missing        |
| Results ledger   | PASS   | 12 experiments, best 0.89  |
| Codex CLI        | PASS   | available                  |
| Gemini CLI       | FAIL   | timeout                    |
| Superpowers      | PASS   | available                  |
| GSD              | PASS   | MCP connected              |
| Planning-w-files | PASS   | available                  |

Blocking: [none / list with fix commands]
Next: [/exp-init / /exp-run resume / none if halted]
```
