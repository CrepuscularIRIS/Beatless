# Beatless — Autonomous Agent System (Hermes v2.1)

6-agent autonomous system for GitHub issue hunting, blog maintenance, and research automation. Built on Hermes Agent framework with ClaudeCode as the execution engine.

## Architecture

```
User (StepFun APP / OpenRoom)
  ↓
Aoi (MiniMax M2.7) — dispatcher only
  ↓ task_request via mailbox
5 MainAgents (Step 3.5 Flash) — thin consumers
  ↓ claude --print "/command"
ClaudeCode (Sonnet 4.6) — execution engine
  ├── Agent tool (parallel scanning)
  ├── /codex:review (code audit)
  └── /gemini:consult (research + architecture)
```

### Design Principles

1. **Aoi is the only scheduler** — 30-min heartbeat, dispatches pipelines
2. **Mailbox is 2-step only** — task_request → task_result, no multi-hop
3. **Each MainAgent = 1 ClaudeCode command** — receive task, run `claude --print`, report result
4. **ClaudeCode owns complexity** — AgentTeam, GSD, Codex/Gemini all run inside ClaudeCode
5. **Triple review** — Claude (primary) + Codex (audit) + Gemini (research)

## Agents

| Agent | Role | Model | Key Commands |
|-------|------|-------|-------------|
| **Aoi** | Dispatcher / control plane | MiniMax M2.7 | Pipeline scheduling, mailbox routing |
| **Lacia** | Strategy / planning | Step 3.5 Flash → Sonnet | `/gsd-discuss-phase`, `/gsd-plan-phase` |
| **Methode** | Execution / implementation | Step 3.5 Flash → Sonnet | `/gsd-execute-phase`, AgentTeam scanning |
| **Satonus** | Review gate | Step 3.5 Flash → Sonnet | `/codex:review`, `/gemini:consult` |
| **Snowdrop** | Research / discovery | Step 3.5 Flash → Sonnet | `/github-hunt`, `/gemini:consult` |
| **Kouka** | Delivery / publishing | Step 3.5 Flash → Sonnet | `/blog-maintenance`, `/gsd-ship` |

## Pipelines

### GitHub Issue Hunter (`/github-hunt`)

Discovers 1K-10K star agent/LLM repos, deep scans with triple review, outputs validated issue proposals.

- **Interval**: every 8 hours
- **Output**: `~/workspace/pr-stage/<date>-<repo>-finding-<N>.md`
- **Quality bar**: P0/P1 only, 2/3 reviewers must agree, no auto-submit

### Blog Maintenance (`/blog-maintenance`)

Audits existing posts, researches trending topics (Big Three AI, agent engineering, BCI), writes new posts.

- **Interval**: every 12 hours
- **Output**: `~/blog/src/content/blogs/<slug>/index.mdx`
- **Topics**: Anthropic/OpenAI/DeepMind reports, agent frameworks, BCI research

## File Structure

```
agents/
├── aoi/SOUL.md          # Dispatcher protocol
├── lacia/SOUL.md         # Strategy worker
├── methode/SOUL.md       # Execution worker
├── satonus/SOUL.md       # Review gate worker
├── snowdrop/SOUL.md      # Research worker
└── kouka/SOUL.md         # Delivery worker

pipelines/
├── github-hunt.md        # ClaudeCode command for issue hunting
└── blog-maintenance.md   # ClaudeCode command for blog maintenance

scripts/
├── heartbeat-driver.sh   # Pipeline scheduler (checks schedules, launches tmux)
├── cron-driver.sh        # Cron entry point (calls heartbeat-driver)
└── session-watcher.sh    # Zombie process cleanup for AgentTeam

docs/
├── architecture-v2-simplification.md      # Original v2 proposal
├── architecture-v2-simplification-v2.md   # v2.1 hardening
└── openroom-alignment.md                  # OpenRoom integration plan

archive/                  # Old OpenClaw-era files (reference only)
```

## Runtime Setup

### Prerequisites

- Hermes Agent installed at `~/claw/hermes-agent/venv/`
- Claude Code CLI (`claude`)
- Codex CLI (`codex`)
- Gemini CLI (`gemini`)
- GitHub CLI (`gh`, authenticated)
- StepFun bridge at `~/.hermes/shared/scripts/stepfun-bridge.mjs`

### Start the system

```bash
# 1. Start cron daemon (30-min heartbeat)
nohup bash /tmp/hermes-cron-daemon.sh >> ~/.hermes/shared/cron-daemon.log 2>&1 &

# 2. Start StepFun bridge (mobile interface)
node ~/.hermes/shared/scripts/stepfun-bridge.mjs --probe

# 3. Manual pipeline trigger
bash ~/.hermes/shared/pipelines/github-hunt/test-run.sh
bash ~/.hermes/shared/pipelines/blog-maintenance/test-run.sh
```

### Monitor

```bash
tmux attach -t github-hunt        # Watch pipeline output
tmux attach -t blog-maintenance    # Watch pipeline output
tail -f ~/.hermes/shared/logs/heartbeat.log  # Watch scheduler
```

## Validated Results (2026-04-11)

| Pipeline | Duration | Output |
|----------|----------|--------|
| github-hunt | 52 min | 3 PASS proposals (TOCTOU race, 2x panic bugs), Codex+Gemini verified |
| blog-maintenance | 40 min | 2 new posts (1500+ words), 1 rewrite, pnpm build PASS |
