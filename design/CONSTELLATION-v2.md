# Constellation v2 — Hermes Heartbeat + ClaudeCode Execution

> Version 0.2 — Revised Design
> Supersedes: CONSTELLATION.md v0.1 (over-estimated Hermes native capability)

## Problem with v0.1

v0.1 tried to make 5 Hermes instances (Kimi/Step/MiniMax) do the actual work. Reality:

- **Kimi K2.6, Step 3.5 Flash, MiniMax M2.7 are not stable** for complex multi-step tasks
- **ClaudeCode (Opus/Sonnet) + Codex (5.3) + Gemini (3.1 Pro)** is the real execution tier
- Complex jobs (PR pipelines, blog writing, research) need ClaudeCode's full ecosystem: slash commands, MCP servers, GSD pipeline, agent spawning, git worktrees
- Making Hermes call `terminal() → claude --print` is a wasteful middle layer

## Architecture: Heartbeat Trigger + ClaudeCode Executor

```
┌──────────────────────────────────────────────────────┐
│                   TRIGGER LAYER                       │
│                                                       │
│  Hermes Gateway (hermes gateway start)                │
│  ├── Cron tick every 60s                              │
│  ├── Telegram/Discord inbound (human commands)        │
│  └── Wake-gate scripts (conditional trigger)          │
│                                                       │
│  OR: systemd timer / bash cron (simpler, more robust) │
└───────────────────┬──────────────────────────────────┘
                    │ triggers
                    ▼
┌──────────────────────────────────────────────────────┐
│                  EXECUTION LAYER                      │
│                                                       │
│  ClaudeCode (claude --print / claude CLI)              │
│  ├── Model: Sonnet 4.6 / Opus 4.6                    │
│  ├── Codex plugin: code review, adversarial review    │
│  ├── Gemini plugin: 1M context research               │
│  ├── GSD commands: plan, execute, verify, ship        │
│  ├── MCP servers: GitHub, Zotero, Playwright          │
│  └── Agent spawning: parallel subagents               │
└───────────────────┬──────────────────────────────────┘
                    │ results
                    ▼
┌──────────────────────────────────────────────────────┐
│                  DELIVERY LAYER                       │
│                                                       │
│  Hermes Gateway → Telegram / Discord / Email          │
│  OR: mail.mjs → task queue for next job               │
│  OR: gh pr create (direct from ClaudeCode)            │
└──────────────────────────────────────────────────────┘
```

## The 4 Jobs

Only 4 complex jobs. Each is a self-contained ClaudeCode session.

### Job 1: Auto-Research (Snowdrop)

**What**: Monitor experiment progress, analyze results, suggest next steps.

**Trigger**: Every 4h via cron, or on-demand via Telegram.

**Execution**:
```bash
cd ~/claw/<experiment-repo> && \
claude --print --model claude-sonnet-4-6 --max-turns 30 \
  -p "snowdrop" \
  "Check experiment status. Read latest logs, analyze metrics, compare against baselines. If results are ready, generate analysis report. If stuck, diagnose and suggest fixes."
```

**What ClaudeCode does inside**:
- Reads experiment logs and metrics via file tools
- Runs `/analyze-results` skill for statistical analysis
- Spawns parallel subagents for multi-metric comparison
- Uses `/gemini:consult` for literature context if needed
- Outputs structured report

**Delivery**: Telegram notification with summary.

---

### Job 2: GitHub Auto-Response (Saturnus + Methode)

**What**: Monitor PRs for maintainer feedback, respond to review comments, iterate on fixes.

**Trigger**: Every 30min via cron.

**Execution**:
```bash
cd ~/claw/Beatless && \
claude --print --model claude-sonnet-4-6 --max-turns 25 \
  -p "saturnus" \
  "Check all open PRs by <your-github-user> for new maintainer comments. For each: \
   1. Read the comment thread \
   2. If actionable feedback: implement fix, push, reply \
   3. If question: answer with evidence from code \
   4. If approved: thank and confirm merge readiness \
   Skip PRs with no new activity."
```

**What ClaudeCode does inside**:
- `gh pr list --author <your-github-user> --state open`
- For each PR: `gh pr view <N> --comments`
- If fix needed: checkout branch, implement, `/codex:review`, push
- Reply with `gh pr comment`

**Delivery**: Telegram alert only when action was taken.

---

### Job 3: GitHub PR Pipeline (Snowdrop → Methode → Saturnus → Kouka)

**What**: Full 12-phase pipeline. Discover issues, implement fixes, review, submit PRs.

**Trigger**: Every 2.5h via cron.

**Execution**: Single long ClaudeCode session with internal phase management:
```bash
cd ~/workspace && \
claude --print --model claude-sonnet-4-6 --max-turns 50 \
  --system-prompt "$(cat ~/claw/Beatless/pipelines/github-pr.md)" \
  "Execute the GitHub PR pipeline. Follow all 12 phases. \
   Phase 1-2 (Snowdrop): Discover and claim an issue. \
   Phase 3 (Lacia): Evaluate repo, read CONTRIBUTING.md. \
   Phase 4-8 (Methode): Setup, reproduce, debug, implement, verify. \
   Phase 9-10 (Saturnus): Triple review with /codex:review + /gemini:consult. \
   Phase 11-12 (Kouka): Submit PR, monitor initial response."
```

**What ClaudeCode does inside**:
- The entire pipeline runs as one ClaudeCode session
- Phase transitions are just prompt sections, not agent switches
- Uses agent spawning for parallel review (correctness + architecture + security)
- Uses `/codex:review` and `/gemini:consult` at review stage
- Uses `gh` CLI for all GitHub operations

**Delivery**: Telegram with PR URL on success, or failure report.

---

### Job 4: Blog Maintenance (Kouka)

**What**: Audit blog, write/edit posts, verify build, commit.

**Trigger**: Every 12h via cron.

**Execution**:
```bash
cd ~/claw/blog && \
claude --print --model claude-sonnet-4-6 --max-turns 30 \
  -p "kouka" \
  "Blog maintenance cycle: \
   1. Audit: check for broken links, outdated content, missing posts \
   2. Write: if there's a topic in the queue, write a new post \
   3. Verify: pnpm build must exit 0 \
   4. Commit: git add, commit, push \
   Only publish verified, reviewed content."
```

**What ClaudeCode does inside**:
- Reads blog directory structure
- Checks git log for recent posts
- Writes new content using `/gsd-do` for focused writing
- Runs `pnpm build` to verify
- Git commit and push

**Delivery**: Telegram with post URL on publish.

---

## Where the 5 Names Live

The Beatless names are NOT separate processes. They're **personality contexts** loaded into ClaudeCode via `--system-prompt` or personality files:

| Name | Role in Pipeline | Loaded as |
|------|-----------------|-----------|
| **Lacia** | Planning phases (decomposition, strategy) | `--system-prompt` with Lacia's constitutional powers |
| **Kouka** | Delivery phases (blog, PR submission, stop-loss) | `--system-prompt` or `-p kouka` personality |
| **Methode** | Execution phases (implement, debug, verify) | `--system-prompt` or `-p methode` personality |
| **Snowdrop** | Research phases (discovery, scanning, alternatives) | `--system-prompt` or `-p snowdrop` personality |
| **Saturnus** | Review phases (code review, evidence audit) | `--system-prompt` or `-p saturnus` personality |

Within a single ClaudeCode session (like Job 3), different phases invoke different personality traits — but it's one continuous session, not 5 separate agents passing messages.

---

## Trigger Options (Pick One)

### Option A: Hermes Cron (via Gateway)

**Pros**: Delivery to Telegram built-in, skill loading, web UI management.
**Cons**: Tied to gateway process, extra Kimi/Step token cost per tick.

```bash
# Start gateway (includes cron ticker)
hermes gateway start

# Jobs configured via Telegram or hermes cron add:
hermes cron add "auto-research" --every 4h --deliver telegram \
  --script ~/.hermes/scripts/auto-research.py
hermes cron add "github-response" --every 30m --deliver telegram \
  --script ~/.hermes/scripts/github-response.py
hermes cron add "github-pr-pipeline" --every 150m --deliver telegram \
  --script ~/.hermes/scripts/github-pr.py
hermes cron add "blog-maintenance" --every 12h --deliver telegram \
  --script ~/.hermes/scripts/blog-maintenance.py
```

Each `--script` is a Python script that:
1. Checks if there's work to do (wake-gate: `{"wakeAgent": false}` to skip)
2. Runs `claude --print ...` via subprocess
3. Outputs the result (Hermes delivers it)

This way, the Hermes agent (Kimi/Step) is NEVER invoked for the actual work. The script does the ClaudeCode call directly. Hermes just handles scheduling + delivery.

### Option B: systemd Timer + Simple Script (Most Robust)

**Pros**: Zero dependency on Hermes, survives crashes, dead simple.
**Cons**: No Telegram delivery built-in (need to add it manually).

```bash
# /etc/systemd/system/beatless-heartbeat.timer
[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

[Install]
WantedBy=timers.target
```

```bash
# /etc/systemd/system/beatless-heartbeat.service
[Service]
Type=oneshot
User=<your-user>
ExecStart=$HOME/claw/Beatless/scripts/heartbeat.sh
```

### Option C: Hermes Cron with `script` Field (Recommended Hybrid)

Use Hermes cron's `script` field to bypass the AI agent entirely:

```python
# ~/.hermes/scripts/github-pr.py
"""Wake-gate + ClaudeCode execution for the GitHub PR pipeline."""
import subprocess, json, sys

# 1. Check if there's work to do
result = subprocess.run(
    ["gh", "search", "issues", "--label=good-first-issue", "--state=open", "--limit=5"],
    capture_output=True, text=True
)
if not result.stdout.strip():
    # No issues found — tell Hermes to skip this tick
    print(json.dumps({"wakeAgent": False}))
    sys.exit(0)

# 2. Run ClaudeCode for the actual work
result = subprocess.run(
    ["claude", "--print", "--model", "claude-sonnet-4-6", "--max-turns", "50",
     "Execute GitHub PR pipeline..."],
    capture_output=True, text=True, timeout=3600,
    cwd="$HOME/workspace"
)

# 3. Output result for Hermes to deliver
print(result.stdout)
```

When the script returns `{"wakeAgent": false}`, Hermes skips the AI agent entirely — zero token cost. When it returns content, Hermes just delivers it (still no AI agent needed for delivery).

**This is the sweet spot**: Hermes handles scheduling + delivery + Telegram interface. ClaudeCode does all the real work. The scripts are the glue.

---

## Mailbox: Keep It Simple

Drop the JSONL mailbox system from v2.1. Replace with a simple task queue file:

```
~/.hermes/shared/queue.md
```

Format:
```markdown
## Pending

- [ ] [2026-04-22 14:30] github-pr: Fix auth token refresh in marvin#950 (from: auto-discovery)
- [ ] [2026-04-22 16:00] blog: Write post on Hermes Agent architecture (from: manual)

## In Progress

- [~] [2026-04-22 12:00] github-response: Reply to marvin#1326 review comment (started: 12:05)

## Done

- [x] [2026-04-22 10:00] blog: Published "BCI Research Update" (completed: 10:45, PR: #47)
- [x] [2026-04-21 22:00] github-pr: Submitted marvin#1326 (completed: 23:15, score: 8.1)
```

Each cron job reads the queue at start, picks up pending items, moves them to "In Progress", and marks "Done" when finished. That's it. No envelope types, no correlation IDs, no message routing. Just a markdown checklist that ClaudeCode can read and write with file tools.

---

## Startup

```bash
# 1. Start Hermes gateway (for Telegram + cron)
hermes gateway start

# 2. Add the 4 jobs (one-time setup)
hermes cron add "Auto Research" --every 4h --deliver telegram \
  --script ~/.hermes/scripts/auto-research.py
hermes cron add "GitHub Response" --every 30m --deliver telegram \
  --script ~/.hermes/scripts/github-response.py
hermes cron add "GitHub PR Pipeline" --every 150m --deliver telegram \
  --script ~/.hermes/scripts/github-pr.py
hermes cron add "Blog Maintenance" --every 12h --deliver telegram \
  --script ~/.hermes/scripts/blog-maintenance.py

# 3. Monitor
hermes cron list
hermes cron output <job-id>  # see last output
```

Or talk to Hermes via Telegram:
```
You: "Run the PR pipeline now"
Hermes: triggers the github-pr script immediately
Hermes: delivers result when done
```

---

## vs v0.1: What Changed

| Aspect | v0.1 (Constellation) | v0.2 (Heartbeat + ClaudeCode) |
|--------|---------------------|-------------------------------|
| Agent processes | 5 Hermes profiles | 1 Hermes gateway + ClaudeCode on demand |
| Execution model | Kimi/Step native | ClaudeCode (Opus/Sonnet/Codex/Gemini) |
| Scheduling | 5 cron daemons | 1 Hermes cron (or systemd timer) |
| Job count | 5 agents * N cron jobs | 4 jobs total |
| Mailbox | 6 JSONL files + message types | 1 queue.md file |
| Token cost idle | 5 agents * 48 ticks/day | 0 (wake-gate skips when no work) |
| Token cost active | Kimi/Step + ClaudeCode | ClaudeCode only |
| Reliability | 5 processes to keep alive | 1 gateway + systemd |
| Self-evolution | Hermes skill system per profile | ClaudeCode learns via MEMORY.md |
| Inter-agent comms | Mailbox routing | Queue.md (read by ClaudeCode) |
| Beatless names | Separate processes | Personality contexts within ClaudeCode |

---

## Open Questions

1. **Hermes gateway reliability**: Does `hermes gateway start` stay alive 24/7, or does it need a process supervisor (systemd/pm2)?

2. **Script timeout**: The cron `script` field has a 120s default timeout. Our ClaudeCode runs can take 30-60 minutes. Need to set `HERMES_CRON_SCRIPT_TIMEOUT=3600` or use a different execution model.

3. **ClaudeCode session persistence**: When `claude --print` runs a 50-turn PR pipeline, does it maintain context across all turns, or does it need `--resume`?

4. **Hermes as notification relay only**: Could we strip Hermes down to JUST gateway + cron (no AI agent at all for cron ticks), using only the `script` + wake-gate path?
