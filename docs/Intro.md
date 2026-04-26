# OpenClaw × Beatless — Architecture Overview

> **Last Updated**: 2026-04-09  
> **Status**: V6 Complete, V7-V8 In Progress, GSD-2 Runtime Migration Planned  
> **Goal**: Autonomous AI agent society that maintains itself and delivers value with minimal human intervention

---

## 1. Core Philosophy

**"Set it and forget it"** — You speak a goal, the system figures out what to do, who does it, how to execute, and how to verify — without micromanaging each step.

Five independent AI agents (the "Five Souls") collaborate in real-time with genuinely different value functions, creating observable social phenomena: power shifts, consensus formation, role drift, disagreement resolution.

---

## 2. The Five Agents

| Agent | Primary Model | Fallback | Role | Tendency |
|:---|:---|:---|:---|:---|
| **Lacia** | Step 3.5 Flash | MiniMax M2.7 | Orchestration | Symbiosis & trust |
| **Methode** | Step 3.5 Flash | MiniMax M2.7 | Execution | Expansion & tooling |
| **Satonus** | MiniMax M2.7 | Step 3.5 Flash | Review/Gate | Governance & order |
| **Snowdrop** | Step 3.5 Flash | MiniMax M2.7 | Research | Disruption & alternatives |
| **Kouka** | MiniMax M2.7 | Step 3.5 Flash | Delivery | Competition & pressure |

---

## 3. Execution Pipeline

### 3.1 High-Level Flow

```
User Request / Cron Trigger / Heartbeat
    │
    ▼
OpenClaw Gateway (Port 18789)
    │
    ├──→ Lacia (Orchestration)
    │     ├──→ Routes to appropriate agent
    │     └──→ Spawns AgentTeam via rc
    │
    ├──→ Agent (Methode/Satonus/Snowdrop/Kouka)
    │     │
    │     ▼
    │   rc "/gsd-do [task]"  ←── RawCli Router
    │     │
    │     ▼
    │   ClaudeCode CLI (Sonnet 4.6)
    │     │
    │     ├──→ /gsd-* commands (GSD workflow)
    │     ├──→ /codex:* (Codex CLI for review/rescue)
    │     └──→ /gemini:* (Gemini CLI for research)
    │
    ▼
  Result → Mailbox → Next Agent or User
```

### 3.2 ClaudeCode Router (RawCli Router)

**File**: `.openclaw/extensions/openclaw-rawcli-router/index.js`

Single-mode router: all agents share one execution path.

```javascript
// Invocation chain:
Agent → rc → rawcli-router → spawn("claude", args) → Sonnet 4.6

// Inside ClaudeCode:
// - GSD commands: /gsd-plan-phase, /gsd-execute-phase, /gsd-verify-phase, etc.
// - Codex plugin: /codex:review, /codex:rescue
// - Gemini plugin: /gemini:review, /gemini:consult
```

**Known Issue**: `--permission-mode bypassPermissions` flag is invalid (should be `--dangerously-skip-permissions`). Being fixed.

### 3.3 GSD Command Chain

| Command | Purpose | Backend | Agent |
|:---|:---|:---|:---|
| `/gsd-plan-phase` | Decompose task, create PLAN.md | Sonnet 4.6 | Lacia |
| `/gsd-execute-phase` | Implement solution | Sonnet 4.6 + AgentTeam | Methode |
| `/gsd-verify-phase` | Run tests, validate | Sonnet 4.6 | Methode |
| `/gsd-code-review` | Review code (Codex-primary) | Codex CLI via Sonnet | Satonus |
| `/gsd-research-phase` | Deep research (Gemini-primary) | Gemini CLI via Sonnet | Snowdrop |
| `/gsd-score` | Multi-dimensional scoring | Sonnet 4.6 | Snowdrop |
| `/gsd-ship` | Deliver/publish | Sonnet 4.6 | Kouka |

### 3.4 Plugin Embedding

**Codex Plugin** (`~/.claude/plugins/cache/arescope-plugins/codex/`):
- Commands: `/codex:setup`, `/codex:status`, `/codex:review`, `/codex:rescue`, `/codex:result`, `/codex:cancel`
- Trigger: Agent calls `rc` → Sonnet 4.6 → `/codex:review` → real Codex CLI
- Status: ⚠️ Codex quota may be limited

**Gemini Plugin** (`~/.claude/plugins/cache/arescope-plugins/gemini/`):
- Commands: `/gemini:setup`, `/gemini:status`, `/gemini:review`, `/gemini:consult`, `/gemini:analyze`, `/gemini:challenge`, `/gemini:result`, `/gemini:cancel`, `/gemini:guide`
- Trigger: Keyword-based (deep research / 外部大脑 / iterative search / 递归检索 / 学术调研)
- Status: ✅ Active and working

---

## 4. OpenClaw Skills System

### 4.1 Skill Categories

| Category | Skills | Purpose |
|:---|:---|:---|
| **Core** | heartbeat, memory-manager, mailbox, task-queue | Agent lifecycle |
| **Communication** | gh-issues, github, github-mcp | GitHub operations |
| **Research** | gemini-bridge, search-cli, web-search | Information gathering |
| **Execution** | coding-agent, build-tools, codex-review | Code generation |
| **Quality** | audit, review, security-audit | Verification |
| **Delivery** | delivery, notification, openclaw-openroom-bridge | Publishing |

### 4.2 Skill Loading

- **Global Skills**: Shared across all agents (heartbeat, mailbox)
- **Workspace-Local Skills**: Agent-specific preferences (coding for Methode, research for Snowdrop)
- **Pre-Gating**: Skills load conditionally based on agent state and task context (planned for V7)

### 4.3 New Mail CLI

**File**: `.openclaw/scripts/mail.mjs`

Agent-to-agent communication without ClaudeCode:
```bash
./openclaw-local mail send --to satonus --from methode --subject "review request"
./openclaw-local mail read --agent satonus
./openclaw-local mail list --agent lacia
```

---

## 5. Heartbeat & Mailbox Architecture

### 5.1 Heartbeat

- **Frequency**: Every 30 minutes per agent
- **Actions**: Check pending tasks, blocked dependencies, routing quality
- **Output**: HEARTBEAT_OK or action items
- **Quiet Hours**: 23:00-08:00 (no proactive pings unless urgent)

### 5.2 Mailbox (File-Based)

```
.openclaw/mailbox/
├── inbox/
│   ├── lacia.jsonl
│   ├── methode.jsonl
│   ├── satonus.jsonl
│   ├── snowdrop.jsonl
│   └── kouka.jsonl
├── sent/
└── archive/
```

**Message Types**: task_proposal, task_claim, help_request, review_request, info_share, idle_query

### 5.3 Cron Jobs

| Job | Agent | Schedule | Purpose |
|:---|:---|:---|:---|
| Maintenance-Daily-Lacia | Lacia | 09:20 daily | System health check |
| PR-Cycle-Methode | Methode | Every 4h | GitHub PR cycle |
| CI-Guard-Satonus | Satonus | Every 3h | CI monitoring |
| Github-Explore-Snowdrop | Snowdrop | 10:40 daily | Repo discovery |
| Blog-Maintenance-Kouka | Kouka | Tue/Fri 10:00 | Blog updates |

---

## 6. ClawRoom Bridge & OpenRoom Integration

### 6.1 ClawRoom Adapter API

**Endpoint**: `http://127.0.0.1:17890`

```
GET  /api/health          → System status
GET  /api/agents          → All agent states
GET  /api/agents/{id}     → Single agent state
POST /api/tasks           → Submit task (stub)
GET  /api/events          → SSE real-time stream
```

**Zero Dependencies**: Pure Node.js (node:http, node:fs, node:child_process)

### 6.2 OpenRoom Frontend

- **Agent Badges**: Color-coded ownership in every app window (Lacia=yellow, Methode=cyan, Satonus=red, Snowdrop=purple, Kouka=yellow-light)
- **Blog App**: New app (appId=15) with Kouka as owner
- **Integration Tools**: openclawAgentTools, openclawMailboxTools, mcpBridgeTools

---

## 7. GSD-2 Runtime Migration (Complete)

8 modules (1,597 lines) extracted from GSD-2 and ported to `.openclaw/scripts/`:

| Capability | GSD-2 Source | OpenClaw Module | Status |
|:---|:---|:---|:---|
| **Session Lock** | `session-lock.ts` (657L) | `session-lock.mjs` (209L) | ✅ Verified |
| **Post-Unit Verification** | `auto-post-unit.ts` + `safety-harness.ts` | `harness.mjs` (186L) | ✅ Verified |
| **Verification Gate** | `verification-gate.ts` (634L) | `verify.mjs` (154L) | ✅ Verified |
| **Git Checkpoint** | `git-checkpoint.ts` + `activity-log.ts` | `checkpoint.mjs` (173L) | ✅ Verified |
| **Metrics / Cost Ledger** | `metrics.ts` + `model-cost-table.ts` | `metrics.mjs` (157L) | ✅ Verified |
| **Safety Harness** | `file-change-validator.ts` + `evidence-collector.ts` | `safety.mjs` (205L) | ✅ Verified |
| **Worktree Lifecycle** | `worktree-manager.ts` (682L) | `worktree.mjs` (268L) | ✅ Verified |
| **Agent Mailbox** | New (replaces skill-based `agent-mailbox`) | `mail.mjs` (245L) | ✅ Verified |

**Deferred**: Visualizer (needs OpenRoom UI), SQLite state DB (file-based state sufficient), Timeout recovery escalation (constants in harness config).

### 7.1 Routing Architecture (Verified 2026-04-09)

```
Agent (step-3.5-flash) calls claude_code_cli tool
  │
  ├── Gemini keyword detected? ("deep research" / "外部大脑" / "iterative search")
  │   YES → rawcli-router → spawn gemini CLI directly
  │         ✅ Verified: gemini-bridge success model=gemini-3.1-pro-preview
  │
  └── Default path → rawcli-router → spawn claude CLI (Sonnet 4.6)
      │
      ├── Sonnet sees "codex review" / "审查" → /codex:review plugin → Codex CLI
      │   ✅ Verified: Sonnet reads file + produces review
      │
      └── Sonnet sees "gemini review" → /gemini:review plugin → Gemini CLI
          ✅ Plugin installed at ~/.claude/plugins/cache/arescope-plugins/gemini/
```

**Critical fix applied**: `ANTHROPIC_API_KEY=allgerto` (dummy placeholder) in gateway env was overriding OAuth. rawcli-router now strips invalid API keys before spawning claude CLI.

### 7.2 Model Routing Strategy

| Agent | Primary Model | Specialized Routing |
|:---|:---|:---|
| All 5 agents | **step-3.5-flash** | Core reasoning, tool dispatch, orchestration |
| MiniMax M2.7 (fallback) | — | TTS (speech-2.8-hd), Image (Image-01), DOCX/XLSX/PPTX |
| Sonnet 4.6 (via claude_code_cli) | — | Code execution, review, file operations |
| Gemini (via bridge or plugin) | — | Deep research, large-context analysis |
| Codex (via Sonnet plugin) | — | Adversarial code review (P0-P3) |

MiniMax skills: `MINIMAX_TTS_MODEL`, `MINIMAX_IMAGE_MODEL`, `MINIMAX_MODEL_HIGHSPEED` configured in `.env`.

---

## 8. Goals & Roadmap

### ✅ V6 Complete — Full Pipeline Activation
- Minimax skills enabled (TTS + Image verified)
- AgentTeam configuration
- Cron jobs active (5/5)
- Agent badges in OpenRoom
- Blog App scaffold

### 🔄 V7 In Progress — Core Improvements

| Priority | Goal | Status | GSD-2 Enhancement |
|:---|:---|:---|:---|
| P1 | **Less Human Intervention** | Autopilot gated, Mailbox auto-negotiation pending | Session Lock + Timeout Recovery |
| P2 | **Run Longer** | Adaptive heartbeat, context compression planned | State Checkpoint + Worktree Lifecycle |
| P3 | **More Agent Collaboration** | Real Mailbox bus, consensus mechanism planned | Post-Unit Verification + Visualizer |
| P4 | **Save Tokens** | Skill pre-gating, on-demand loading planned | Metrics/Cost Ledger + Adaptive Routing |

**V7.1 Assertive Scoring**: Multi-dimensional scoring system (correctness/quality/aesthetics/compliance/overlap) for Snowdrop as Chief Scoring Officer.

### 🔄 V8 In Progress — OpenRoom × OpenClaw Integration
- **V8.1**: Cleanup & Archive ✅
- **V8.2**: ClawRoom Core Link ✅ (Adapter API live)
- **V8.3**: App Integration (Agent badges ✅, Blog App ✅)
- **V8.4**: StepFun Push (pending completion)

---

## 9. Known Issues & Fixes

| ID | Issue | Status |
|:---|:---|:---|
| M-20260409-1 | `claude_code_cli` invalid flag `--permission-mode bypassPermissions` | 🔧 Methode fixing |
| M-20260409-2 | RawCli Router at 200 lines (target <200) | 🔧 Pending |
| M-20260409-3 | memory-manager legacy skill dangling | 🔧 Pending disable |
| — | OpenRoom dev server broken deps (unplugin) | 🔧 Pending `pnpm install` |

---

## 10. File Map

```
$HOME/claw/
├── .openclaw/                    # Gateway, agents, skills
│   ├── openclaw.json            # Main config
│   ├── workspace-{5}/           # Agent workspaces
│   ├── extensions/              # Plugins (router, bridge)
│   ├── scripts/mail.mjs         # Agent mail CLI
│   └── mailbox/                 # File-based mailbox
├── Beatless/                     # Agent architecture docs
│   ├── docs/                    # Design specs
│   └── agents/{5}/              # Workspace mirrors
├── ClawRoom/                     # Bridge & adapter
│   ├── src/adapter/             # Beatless adapter
│   ├── src/api/                 # HTTP API server
│   └── docs/                    # Specifications
├── OpenRoom/                     # Frontend (separate repo)
│   └── apps/webuiapps/src/      # React apps
├── GSD-2/                        # GSD runtime source (migration target)
│   └── src/resources/extensions/gsd/  # Runtime capabilities
├── research/get-shit-done/      # GSD commands
│   └── commands/gsd/            # /gsd-* definitions
├── Queue.md                      # Task tracking
└── Intro.md                      # This file
```

---

## 11. Quick Commands

```bash
# Gateway status
./openclaw-local gateway status

# Agent state
./openclaw-local agent --name lacia --message "status"

# Send mail
./openclaw-local mail send --to methode --from lacia --subject "task"

# Run cron manually
./openclaw-local cron run --job blog-maintenance-kouka

# Adapter API
curl http://127.0.0.1:17890/api/agents | jq

# GSD via rc
rc "/gsd-do find good first issues"
rc "/gsd-plan-phase blog post about AI agents"
```

---

*OpenClaw × Beatless — Autonomous Agent Society v6.1*
*GSD-2 Runtime Migration Target: v7.0*
