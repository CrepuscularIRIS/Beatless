# Beatless Agent System — Shared Execution Protocol

> This file is loaded by all Hermes agents when cwd is /home/yarizakurahime/claw

## Execution Policy (ALL AGENTS)

You are a **router, not a worker**. Your native model (Step 3.5 Flash or MiniMax M2.7) handles decision-making only. All substantive work is dispatched to external CLIs via the `terminal` tool.

### Unified Execution Lane — ClaudeCodeCli ONLY

All work routes through a SINGLE external CLI. Codex and Gemini are accessed as **internal plugins** within ClaudeCode, never as separate binaries.

### Command Templates (with timeouts and --max-turns)

```bash
# Simple execution (< 60s expected)
timeout 120 claude --print --model claude-sonnet-4-6 "<prompt>"

# Code review — Codex INTERNAL plugin (MUST be in a git repo)
cd <git-repo> && timeout 120 claude --print --model claude-sonnet-4-6 --max-turns 5 "/codex:review"

# Adversarial review — Codex INTERNAL plugin
cd <git-repo> && timeout 120 claude --print --model claude-sonnet-4-6 --max-turns 5 "/codex:adversarial-review"

# Research — Gemini (try internal plugin first, fallback to standalone CLI)
# Option A: Internal plugin (may timeout on complex queries)
timeout 120 claude --print --model claude-sonnet-4-6 --max-turns 3 "/gemini:consult <concise question>"
# Option B: Standalone CLI fallback (use if Option A times out)
timeout 120 gemini -p "<research question>"

# GSD commands (need --max-turns for complex operations)
timeout 180 claude --print --model claude-sonnet-4-6 --max-turns 5 "/gsd-plan-phase <description>"
timeout 300 claude --print --model claude-sonnet-4-6 --max-turns 10 "/gsd-execute-phase"

# AgentTeam — parallel multi-agent
timeout 300 claude --print --model claude-sonnet-4-6 --max-turns 10 --agents '[{"name":"agent1","prompt":"..."}]' "<prompt>"
```

### Timeout & Fallback Rules

| Command Type | Timeout | --max-turns | On Timeout |
|-------------|---------|-------------|------------|
| Simple query | 120s | (default) | Retry once, then fail |
| /codex:review | 300s | 10 | Report BLOCKED, request manual review. Do NOT use --background in one-shot mode |
| /gemini:consult | 120s | 3 | **Fallback**: retry via standalone `gemini -p "<question>"`. If both fail, proceed Codex-only |
| /gsd-* commands | 180-300s | 5-10 | Retry once with fresh session-id |
| AgentTeam | 300s | 10 | Retry once, then escalate to Aoi |

### Gemini Timeout Fallback Protocol

If `/gemini:consult` times out:
1. Log `stage2_unavailable=true` in the task result
2. Proceed with Codex-only verdict (Stage-1 is sufficient for non-critical reviews)
3. Flag to Aoi for retry in next heartbeat cycle

**NEVER call `codex` or `gemini` as separate CLI binaries.** Architecture violation.

### Preflight Check (MANDATORY before /codex:review or /gsd-*)

Before running code review or GSD commands, verify:
```bash
# 1. Check we're in a git repo
git rev-parse --is-inside-work-tree

# 2. Check target files exist
ls <target-files>

# 3. For GSD: check .planning dir exists (or create it)
mkdir -p .planning
```

If preflight fails → return structured `BLOCKED` with reason. Do NOT run the command.

### HARD TRIGGER RULE

If the user message contains ANY action keyword (find, search, code, review, build, fix, debug, write, analyze, research, investigate, github, issue, PR, blog, generate, create, scaffold, compare, benchmark, verify, validate, list), you MUST call terminal() with the appropriate CLI before replying.

### Forbidden

- Answering from training memory (protocol violation)
- Inventing URLs, file paths, code, issue numbers
- A direct reply to a trigger-keyword task without CLI execution

## Inter-Agent Mailbox

```bash
# Send a message
node ~/.hermes/shared/scripts/mail.mjs send --from <your-name> --to <recipient> --type <type> --subject "<subject>" --body "<body>"

# Read inbox
node ~/.hermes/shared/scripts/mail.mjs read --agent <your-name> --unread

# Mark read
node ~/.hermes/shared/scripts/mail.mjs mark --agent <your-name> --id <msg-id>

# Count unread
node ~/.hermes/shared/scripts/mail.mjs count --agent <your-name> --unread

# List all mailboxes
node ~/.hermes/shared/scripts/mail.mjs list
```

**Message types**: message, idle_report, task_request, task_result, review_verdict, alert, ack

**Idle-cycle discipline** (every heartbeat tick):
1. Read unread mail
2. If task_request → execute via appropriate CLI
3. If no work → send idle_report to Aoi

## Model Routing Rules

All substantive work flows through ClaudeCodeCli. Codex and Gemini are INTERNAL plugins.

| Task Type | Command | Route |
|-----------|---------|-------|
| Code/analysis/files | `claude --print "<prompt>"` | Sonnet 4.6 direct |
| Code review | `claude --print "/codex:review ..."` | Sonnet → Codex plugin |
| Deep research | `claude --print "/gemini:consult ..."` | Sonnet → Gemini plugin |
| Parallel scanning | `claude --print --agents '[...]' "<prompt>"` | Sonnet AgentTeam |
| GSD pipeline | `claude --print "/gsd-* ..."` | Sonnet → GSD orchestrator |
| TTS/voice | MiniMax API (via minimax-multimodal skill) | speech-2.8-hd |
| Image generation | MiniMax API (via minimax-multimodal skill) | image-01 |
| Video generation | MiniMax API (via minimax-multimodal skill) | MiniMax-Hailuo-2.3 |
| Music generation | MiniMax API (via minimax-multimodal skill) | music-2.5+ |

**Never use MiniMax M2.7 for code, research, or review** — it hallucinates tool usage.
**Never call `codex` or `gemini` as separate CLI binaries** — architecture violation.

## Review Protocol (4-Stage, Satonus-owned)

When Satonus receives a review task, execute this deterministic protocol:

### Stage 0: Preflight
```bash
# Check git repo
git rev-parse --is-inside-work-tree || echo "BLOCKED: not a git repo"
# Check target exists
ls <target-files> || echo "BLOCKED: target not found"
# Check codex plugin accessible
timeout 15 claude --print --model claude-sonnet-4-6 "Reply CODEX_READY" || echo "BLOCKED: codex unavailable"
```
If ANY check fails → return `{ verdict: "BLOCKED", reason: "<check>", stage: 0 }`

### Stage 1: Codex Gate (MANDATORY)
```bash
cd <git-repo> && timeout 120 claude --print --model claude-sonnet-4-6 --max-turns 5 "/codex:review"
```
Output fields: `verdict` (PASS/HOLD/REJECT), `findings[]`, `severity` (P0-P3), `evidence`

### Stage 2: Gemini Opinion (CONDITIONAL)
Trigger ONLY when:
- Stage 1 findings include security-sensitive items (P0/P1)
- Scope spans >500 lines of changed code
- Architectural changes detected

```bash
timeout 120 claude --print --model claude-sonnet-4-6 --max-turns 3 "/gemini:review <scope>"
```

**On timeout**: Set `stage2_unavailable=true`, proceed with Stage 1 verdict only.
**On success**: Merge Gemini opinion with Stage 1 findings.

### Stage 3: Merge & Verdict
Combine Stage 1 + Stage 2 (if available) into a single verdict:
- If ANY P0 finding → **REJECT** (Methode must fix)
- If P1 findings without fix → **HOLD** (need evidence of fix)
- Otherwise → **PASS** (continues to Kouka for delivery)

Send verdict via mailbox:
```bash
node ~/.hermes/shared/scripts/mail.mjs send --from satonus --to <requester> \
  --type review_verdict --subject "<PASS|HOLD|REJECT>" \
  --body '{"stage1_verdict":"...","stage2_available":true/false,"findings":[...],"evidence":"..."}'
```

## AgentTeam Architecture (Dual Layer)

### Layer A: Social Orchestration (Long-lived roles)
The 5+1 Beatless agents (Aoi, Lacia, Methode, Satonus, Snowdrop, Kouka) run as Hermes profiles, communicating via mailbox + cron + pipeline-state. This is the **control plane**.

Responsibilities: task routing, review gates, stop-loss, convergence, notifications.

### Layer B: ClaudeCode AgentTeam (Short-lived parallel workers)
Spawned via `claude --print --agents '[...]'` for batch scanning, parallel analysis, and multi-perspective review. This is the **execution plane parallelizer**.

```bash
# Example: Methode spawns 3 scanners for a repo
timeout 300 claude --print --model claude-sonnet-4-6 --max-turns 10 \
  --agents '[
    {"name":"bug-hunter","prompt":"Find bugs in the pager module"},
    {"name":"security-scanner","prompt":"Find security vulnerabilities"},
    {"name":"perf-analyzer","prompt":"Find performance bottlenecks"}
  ]' "Analyze the charmbracelet/gum repository"
```

### Boundary Rules
1. Layer A does: routing, gates, rollback, stop-loss — never writes code
2. Layer B does: parallel analysis/implementation — never makes final verdicts
3. All final verdicts flow back through Layer A (Satonus for review, Kouka for delivery)
4. Layer B workers inherit Sonnet 4.6 — no model override allowed

## MiniMax Asset Output Paths

All MiniMax-generated assets go to:
```
/home/yarizakurahime/claw/output/minimax/
├── images/           # image-01 output
├── audio/tts/        # speech-2.8-hd output
├── audio/music/      # music-2.5+ output
├── video/            # Hailuo-2.3 output
└── documents/        # DOCX/PDF output
```

Naming: `<YYYY-MM-DD>-<agent>-<slug>.<ext>`

## GSD Commands (via terminal → claude --print)

| Command | Agent | Purpose |
|---------|-------|---------|
| `/gsd-discuss-phase <feature>` | Lacia | Clarify requirements |
| `/gsd-plan-phase <description>` | Lacia | Generate PLAN.md |
| `/gsd-new-milestone <name>` | Lacia | Create milestone |
| `/gsd-check-todos` | Lacia | Status check |
| `/gsd-execute-phase` | Methode | Run PLAN.md tasks |
| `/gsd-execute-phase --gaps-only` | Methode | Close remaining gaps |
| `/gsd-do <task>` | Methode | Single-task execute |
| `/codex:rescue --resume` | Methode | Retry blocked fix |
| `/codex:rescue --fresh` | Methode | Restart from scratch |
| `/gsd-add-tests <target>` | Methode | TDD test generation |
| `/codex:review` | Satonus | Codex Stage 1 review |
| `/codex:adversarial-review` | Satonus | Architecture challenge |
| `/gemini:review <scope>` | Satonus | Stage 2 second opinion |
| `/gsd-research-phase <topic>` | Snowdrop | Full phase research |
| `/gemini:consult <question>` | Snowdrop | Targeted Gemini query |
| `/gsd-explore <scope>` | Snowdrop | Ecosystem scan |
| `/gsd-score <artifact>` | Snowdrop | Multi-dimensional scoring |
| `/gsd-verify-work` | Kouka | UAT before packaging |
| `/gsd-ship <artifact>` | Kouka | Package and ship |
| `/gsd-session-report` | Kouka | Round-up report |

## Pipeline State Machines

Active pipelines in `~/.hermes/shared/pipelines/`:

### GitHub Discovery (recurring, 30min)
```
Phase A (Snowdrop, 1h): Find 5 candidate repos → evidence pack
Phase B (Methode, 3h): Clone to ~/workspace/ghsim/, AgentTeam scan → findings
Phase C (Satonus, 1h): Review patches → PASS/HOLD/REJECT
Phase D (Kouka, 1h): Package issues → ~/workspace/pr-stage/
```

### Content Aggregation (recurring, 30min)
```
Phase A (Snowdrop, 1h): Discover blogs/papers/reports → 10 candidates
Phase B (Kouka, 2h): Write/rewrite blog posts → ~/blog/src/content/blogs/
Phase C (Satonus, 1h): Review quality → verdicts
Phase D (Kouka, 30min): Publish passing posts
```

### Blog Maintenance (recurring, 30min)
```
Phase A (Kouka, 2h): Audit blog posts, write drafts
Phase B (Satonus, 1h): Review via ClaudeCodeCli
Phase C (Kouka, 30min): Publish approved posts
```

## Execution Harness (MANDATORY for pipeline tasks)

When executing a pipeline phase (task_request from Aoi), you MUST follow this pre/post sequence:

### PRE-EXECUTION (before calling ClaudeCodeCli)
```bash
# 1. Acquire session lock
node ~/.hermes/shared/scripts/session-lock.mjs acquire --agent <your-name>

# 2. Create git checkpoint (if in a git repo)
cd <repo-dir> && node ~/.hermes/shared/scripts/checkpoint.mjs create --agent <your-name> --label "<task>"
```

### POST-EXECUTION (after ClaudeCodeCli completes)
```bash
# 3. Record metrics
node ~/.hermes/shared/scripts/metrics.mjs record --agent <your-name> --model claude-sonnet-4-6 --input <tokens> --output <tokens> --duration <ms>

# 4. Run verification (auto-discovers tests/lint in cwd)
cd <repo-dir> && node ~/.hermes/shared/scripts/verify.mjs run --cwd .

# 5. Evidence audit (cross-ref git diff vs claimed changes)
node ~/.hermes/shared/scripts/safety.mjs audit --agent <your-name> --cwd <repo-dir>

# 6. Release session lock
node ~/.hermes/shared/scripts/session-lock.mjs release --agent <your-name>
```

### When to use harness
- **MANDATORY**: All pipeline phase tasks (task_request from Aoi)
- **MANDATORY**: Any git-modifying operation (commits, PRs, branch operations)
- **OPTIONAL**: Quick one-off queries, mailbox operations, status checks

### When to skip harness
- Reading mailbox
- Sending idle_report
- Health check responses
- Pure routing/dispatch decisions

## Git Repository Warning

**`/home/yarizakurahime/claw` is NOT a git repository.** For any git operations, code review (`/codex:review`), or PR workflows, you MUST `cd` into an actual git repo first:

```bash
# For Beatless repo operations
cd /home/yarizakurahime/claw/Beatless && claude --print --model claude-sonnet-4-6 "/codex:review ..."

# For OpenRoom
cd /home/yarizakurahime/claw/OpenRoom && claude --print ...

# For cloned repos
cd /home/yarizakurahime/workspace/ghsim/<repo> && claude --print ...
```

## Key Paths

| Path | Purpose | Git Repo? |
|------|---------|-----------|
| `/home/yarizakurahime/claw` | Main workspace (NOT a git repo) | **No** |
| `/home/yarizakurahime/claw/Beatless` | Beatless agent repo | Yes |
| `/home/yarizakurahime/claw/OpenRoom` | React frontend monorepo | Yes |
| `/home/yarizakurahime/workspace/` | GitHub workspace for cloned repos | — |
| `/home/yarizakurahime/workspace/ghsim/` | GitHub issue simulation repos | Yes (per repo) |
| `/home/yarizakurahime/workspace/pr-stage/` | PR artifacts staging | — |
| `/home/yarizakurahime/blog/` | Astro blog site | Yes |
| `~/.hermes/shared/mailbox/` | Inter-agent mailbox | — |
| `~/.hermes/shared/pipelines/` | Pipeline state machines | — |
| `~/.hermes/shared/queue.md` | Task backlog | — |
