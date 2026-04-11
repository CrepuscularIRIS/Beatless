# Beatless Architecture v2: Two-Layer Simplification

> Date: 2026-04-11 | Status: PROPOSAL | Author: System Architect

---

## 1. Problem Statement

### Current State (v1: Hermes Mailbox Orchestration)

Hermes Agent runs 6 profiles (Aoi + 5 MainAgents) on a 30-minute cron heartbeat. Each agent independently ticks, reads its mailbox, decides what to do, calls external CLIs, and sends results back via mailbox.

**Observed failures:**
- Step-3.5-Flash is too weak for multi-step mailbox protocol (read→parse→decide→CLI→parse→send)
- 37 task_result messages in Aoi's mailbox, but most are `idle_report` — no real work
- Only Snowdrop completed one actual GitHub discovery; Kouka generated one auto-digest post
- Zero GitHub Issues filed, zero PRs submitted, zero repos archived
- content-aggregation pipeline has never run (permanently IDLE)
- Each mailbox roundtrip adds latency and a failure point with no retry mechanism
- All real work happens inside ClaudeCode (Sonnet 4.6) — Step-3.5-Flash is just an unreliable middleman

### Root Cause

The architecture requires a weak model (Step-3.5-Flash) to orchestrate complex multi-step workflows. This is the wrong layer to put intelligence. ClaudeCode (Sonnet 4.6) already has AgentTeam, GSD, Codex, and Gemini built in — the 5 MainAgents should be thin dispatchers to ClaudeCode, not complex orchestrators themselves.

---

## 2. Target Architecture (v2: Two-Layer Dispatch)

### Design Principles

1. **Aoi is the only human interface** — user talks to Aoi via StepFun, Aoi dispatches
2. **Mailbox is 2-step only** — Aoi sends task_request → Agent replies task_result. No multi-hop chains
3. **Each MainAgent = 1 ClaudeCode command** — receive task, run `claude --print`, report result
4. **ClaudeCode owns complexity** — AgentTeam parallelism, GSD orchestration, Codex/Gemini review all happen inside ClaudeCode
5. **Long tasks self-report** — agents send progress updates via heartbeat, final result when done
6. **Kill MainAgent cron jobs** — only Aoi has a heartbeat schedule

### System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 0: Human Interface                                    │
│                                                              │
│  StepFun APP (手机)  ←──WebSocket──→  stepfun-bridge.mjs     │
│                                           │                  │
│  User sends: "@aoi 帮我找几个高质量 GitHub repo"              │
│  User sends: "@lacia 更新一下博客"                            │
│  User sends: "@methode 修一下 OpenRoom 的 bug"               │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  Layer 1: Aoi (MiniMax M2.7) — Dispatcher                    │
│                                                              │
│  Roles:                                                      │
│  - Parse user intent → select pipeline or agent              │
│  - Write task_request to target agent's mailbox              │
│  - Monitor task_result replies                               │
│  - Forward results/progress to user via StepFun              │
│  - Heartbeat: check for stale tasks, nudge agents            │
│                                                              │
│  Does NOT do:                                                │
│  - Any actual work (no code, no research, no writing)        │
│  - Multi-step mailbox choreography                           │
│  - Pipeline state machine management                         │
│                                                              │
│  Schedule: */30 cron (heartbeat check only)                  │
└────────┬──────────┬──────────┬──────────┬──────────┬─────────┘
         │          │          │          │          │
    ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼───┐
    │ Lacia  │ │Methode │ │Satonus │ │Snowdrop│ │ Kouka │
    │Strategy│ │Execute │ │Review  │ │Research│ │Deliver│
    └────┬───┘ └────┬───┘ └───┬────┘ └───┬────┘ └───┬───┘
         │          │         │          │          │
         └──────────┴─────────┴──────────┴──────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  Layer 2: ClaudeCode (Sonnet 4.6) — Execution Engine         │
│                                                              │
│  Each MainAgent calls ONE claude --print command.            │
│  Inside ClaudeCode, all complexity is handled:               │
│                                                              │
│  ┌─────────────┐  ┌──────────┐  ┌───────────┐               │
│  │  AgentTeam   │  │   GSD    │  │   Codex   │               │
│  │  (parallel   │  │  (plan → │  │  (review  │               │
│  │   scanning)  │  │  execute │  │   gate)   │               │
│  └─────────────┘  │  → verify)│  └───────────┘               │
│                   └──────────┘                               │
│  ┌─────────────┐  ┌──────────┐                               │
│  │   Gemini    │  │  GitHub   │                               │
│  │  (research  │  │  CLI (gh) │                               │
│  │   consult)  │  │  (issues, │                               │
│  └─────────────┘  │   PRs)   │                               │
│                   └──────────┘                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Role Definitions (v2)

### Aoi — Dispatcher & User Proxy

```
Model: MiniMax M2.7
Trigger: StepFun inbound message / 30-min heartbeat
Input: User message OR heartbeat tick
Output: task_request to mailbox OR progress report to user

Heartbeat logic:
  1. Check all 5 agent mailboxes for task_result replies
  2. Forward any results to user via StepFun
  3. Check for stale tasks (>2h no reply) → send reminder
  4. No new work needed → do nothing (no idle_report spam)
```

### Lacia — Strategy & Planning

```
Model: Step-3.5-Flash (decision) → ClaudeCode Sonnet 4.6 (execution)
Specialty: Planning, strategy review, milestone management
Trigger: task_request from Aoi

Typical commands:
  claude --print --model claude-sonnet-4-6 --max-turns 15 \
    "/gsd-discuss-phase <feature>"
  claude --print --model claude-sonnet-4-6 --max-turns 10 \
    "/gsd-plan-phase <description>"

User can also talk to Lacia directly via "@lacia <message>"
```

### Methode — Execution & Unblocking

```
Model: Step-3.5-Flash (decision) → ClaudeCode Sonnet 4.6 (execution)
Specialty: Code implementation, bug fixing, pipeline execution
Trigger: task_request from Aoi

Typical commands:
  claude --print --model claude-sonnet-4-6 --max-turns 25 \
    "/gsd-execute-phase"
  claude --print --model claude-sonnet-4-6 --max-turns 25 \
    --agents '[{"name":"scanner","prompt":"..."}]' "<task>"

User can also talk to Methode directly via "@methode <message>"
```

### Satonus — Review Gate

```
Model: Step-3.5-Flash (decision) → ClaudeCode Sonnet 4.6 (execution)
Specialty: Code review, quality gate, security audit
Trigger: task_request from Aoi (after Methode produces artifacts)

Typical commands:
  cd <repo> && claude --print --model claude-sonnet-4-6 --max-turns 10 \
    "/codex:review"
  claude --print --model claude-sonnet-4-6 --max-turns 5 \
    "/gemini:consult <risk question>"
```

### Snowdrop — Research & Discovery

```
Model: Step-3.5-Flash (decision) → ClaudeCode Sonnet 4.6 (execution)
Specialty: GitHub discovery, literature review, ecosystem scanning
Trigger: task_request from Aoi

Typical commands:
  claude --print --model claude-sonnet-4-6 --max-turns 20 \
    "Search GitHub for repos with 5K-30K stars in <domain>, clone top 3 to
     ~/workspace/archive/, scan for unreported issues using AgentTeam"
  claude --print --model claude-sonnet-4-6 --max-turns 15 \
    "/gemini:consult <research question>"
```

### Kouka — Delivery & Publishing

```
Model: Step-3.5-Flash (decision) → ClaudeCode Sonnet 4.6 (execution)
Specialty: Blog writing, artifact packaging, PR submission
Trigger: task_request from Aoi (after review passes)

Typical commands:
  claude --print --model claude-sonnet-4-6 --max-turns 25 \
    "Write a blog post about <topic> at ~/blog/src/content/blogs/<slug>/index.mdx,
     run pnpm build to verify, git commit"
  cd <repo> && claude --print --model claude-sonnet-4-6 --max-turns 15 \
    "Create PR for the changes: gh pr create --title '...' --body '...'"
```

---

## 4. Mailbox Protocol (v2: Two-Step Only)

### Message Flow

```
Aoi                    MainAgent
 │                        │
 │── task_request ───────>│  (1 message: what to do)
 │                        │
 │                        │── [runs claude --print internally]
 │                        │
 │<── progress_update ────│  (optional: for tasks >30min)
 │<── progress_update ────│  (optional: periodic updates)
 │                        │
 │<── task_result ────────│  (1 message: what was done + evidence)
 │                        │
```

### Message Schema

**task_request** (Aoi → Agent):
```json
{
  "type": "task_request",
  "subject": "GitHub Issue Hunt — AI Agent Repos",
  "body": {
    "pipeline": "github-hunt",
    "claude_command": "claude --print --model claude-sonnet-4-6 --max-turns 25 '<prompt>'",
    "timeout_minutes": 30,
    "report_to": "aoi"
  }
}
```

**progress_update** (Agent → Aoi, optional for long tasks):
```json
{
  "type": "progress_update",
  "subject": "GitHub Hunt — 2/5 repos scanned",
  "body": {
    "pipeline": "github-hunt",
    "progress": "40%",
    "current_step": "Scanning repo 3/5: charmbracelet/gum",
    "eta_minutes": 15
  }
}
```

**task_result** (Agent → Aoi):
```json
{
  "type": "task_result",
  "subject": "GitHub Hunt Complete — 3 issues filed, 1 PR submitted",
  "body": {
    "pipeline": "github-hunt",
    "status": "SUCCESS",
    "artifacts": [
      "/home/yarizakurahime/workspace/pr-stage/20260411-charmbracelet-gum.md",
      "https://github.com/charmbracelet/gum/issues/456",
      "https://github.com/user/gum/pull/1"
    ],
    "summary": "Scanned 5 repos, filed 3 issues, submitted 1 PR",
    "duration_minutes": 22,
    "tokens_used": 45000
  }
}
```

### Rules

1. **No multi-hop chains** — Aoi never forwards a task_result to another agent as a task_request. If a pipeline needs sequential steps (scan → review → publish), Aoi sends separate task_requests
2. **Agent replies exactly once** — task_result is the terminal message. Plus optional progress_updates for long tasks
3. **Stale detection** — if Aoi doesn't receive task_result within 2x timeout, mark task as STALE and notify user
4. **User forwarding** — Aoi forwards all task_result summaries to user via StepFun

---

## 5. Pipeline Definitions (v2)

### Pipeline 1: GitHub Issue Hunter

**Goal:** Find 5K-30K star repos → clone → scan for unreported issues → file Issues → submit PRs

**Schedule:** Every 8 hours (3x/day), or on-demand via user command

**Execution flow (all inside ONE ClaudeCode session):**

```
1. Snowdrop receives task_request from Aoi
2. Snowdrop calls:
   claude --print --model claude-sonnet-4-6 --max-turns 30 \
     "GitHub Issue Hunter Pipeline:

      PHASE 1 - DISCOVERY
      - Use gh CLI to search repos: gh search repos --stars=5000..30000 --language=<lang> --sort=updated
      - Filter: active (pushed in last 30 days), has issues enabled, not archived
      - Select top 3 repos not previously processed

      PHASE 2 - CLONE & SCAN
      - Clone each to ~/workspace/archive/<repo-name>/
      - For each repo, spawn AgentTeam with 3 scanners:
        - bug-hunter: find bugs, race conditions, edge cases
        - security-scanner: find security vulnerabilities
        - improvement-finder: find missing features, UX issues
      - Each scanner produces structured findings

      PHASE 3 - ISSUE QUALITY FILTER
      - Deduplicate findings across scanners
      - Check existing issues (gh issue list) to avoid duplicates
      - Score each finding: severity x reproducibility x clarity
      - Keep only top findings (score > 7/10)

      PHASE 4 - FILE & PR
      - For each high-quality finding:
        a. Create GitHub issue: gh issue create --repo <repo> --title '...' --body '...'
        b. If fix is clear and < 50 lines:
           - Fork: gh repo fork <repo> --clone
           - Create branch, apply fix, commit
           - Submit PR: gh pr create --title '...' --body '...'
      - Save all evidence to ~/workspace/pr-stage/

      PHASE 5 - REPORT
      - Generate summary: repos scanned, issues filed, PRs submitted
      - Include URLs for all created issues/PRs"

3. Snowdrop sends task_result to Aoi with summary + URLs
4. Aoi forwards summary to user via StepFun
```

### Pipeline 2: Blog Maintenance

**Goal:** Audit existing posts → clean up low-quality → write high-quality new posts

**Schedule:** Every 12 hours (2x/day), or on-demand

**Execution flow:**

```
1. Kouka receives task_request from Aoi
2. Kouka calls:
   claude --print --model claude-sonnet-4-6 --max-turns 30 \
     "Blog Maintenance Pipeline at ~/blog/:

      PHASE 1 - AUDIT
      - Read all posts in src/content/blogs/
      - Classify: keep / rewrite / delete
      - Criteria: word count > 800, has code examples, not auto-generated filler
      - List posts to clean up

      PHASE 2 - CLEANUP
      - For posts marked 'rewrite': improve content, fix formatting
      - For posts marked 'delete': move to drafts (isDraft: true)
      - Fix broken links, missing images, formatting issues

      PHASE 3 - RESEARCH & WRITE
      - Use /gemini:consult to find 3 trending topics in AI/ML/Systems
      - Write 2 new high-quality posts (1500+ words, with code examples)
      - Follow Astro MDX format, proper frontmatter
      - Save to src/content/blogs/<slug>/index.mdx

      PHASE 4 - VERIFY & COMMIT
      - Run: pnpm build (must exit 0)
      - Git commit with conventional commits format
      - Report: posts audited, cleaned, written, build status"

3. Kouka sends task_result to Aoi
4. Aoi forwards to user
```

### Pipeline 3: Research Assistant (Future)

**Goal:** Automated literature review, experiment tracking, paper writing support

**Schedule:** On-demand via user command, with daily summary

```
User: "@aoi 帮我调研 EEG-to-speech 最新进展"

Aoi dispatches to Snowdrop:
  claude --print --model claude-sonnet-4-6 --max-turns 30 \
    "Research Pipeline: EEG-to-speech decoding
     1. Search arXiv (last 30 days) via /gemini:consult
     2. Use AgentTeam (3 reviewers) to evaluate top 10 papers
     3. Generate structured literature review with:
        - Key findings table
        - Method comparison
        - Research gaps
        - Potential directions
     4. Save to ~/research/eeg-speech/review-$(date +%Y%m%d).md"
```

---

## 6. What to Keep, Kill, or Modify

### Keep (unchanged)

| Component | Reason |
|-----------|--------|
| Aoi profile + SOUL.md | Rewrite SOUL.md for dispatcher role |
| stepfun-bridge.mjs | User interface, working well |
| mail.mjs | 2-step mailbox still useful for async communication |
| harness scripts (checkpoint, metrics, verify, safety) | Wrap around ClaudeCode calls for audit trail |
| All 5 MainAgent profiles | Keep as identity + prompt templates |
| ~/.hermes/shared/skills/ | Skills loaded by agents |
| StepFun WebSocket connection | Primary user channel |

### Kill

| Component | Reason |
|-----------|--------|
| 5 MainAgent cron jobs | Agents should be event-driven (mailbox), not polling |
| Pipeline state machine (4-phase) | Replace with single-step execution |
| idle_report protocol | No more idle — agents only speak when they have results |
| Multi-hop mailbox chains | Replace with 2-step only |
| HEARTBEAT.md per workspace | Consolidated into Aoi's heartbeat |

### Modify

| Component | Change |
|-----------|--------|
| Aoi SOUL.md | Rewrite for pure dispatcher role |
| cron-driver.sh | Only tick Aoi; Aoi checks for scheduled pipelines |
| 5 MainAgent SOUL.md files | Simplify to: receive task → call claude --print → reply result |
| Pipeline state files | Simplify to: `{ status: IDLE/RUNNING/DONE, last_run, next_run }` |
| notify-user.sh | Fix StepFun push (currently depends on openclaw-local) |

---

## 7. User Interaction Model

### Direct Chat (via StepFun)

```
User → "@aoi 现在项目进展如何？"
  Aoi checks all pipelines, summarizes, replies via StepFun

User → "@lacia 帮我规划一下 OpenRoom 的重构"
  stepfun-bridge routes directly to Lacia
  Lacia calls claude --print "/gsd-discuss-phase OpenRoom refactoring"
  Lacia replies result via StepFun

User → "@methode 修一下 ClawRoom 的 API 超时问题"
  stepfun-bridge routes directly to Methode
  Methode calls claude --print in ClawRoom repo
  Methode replies result via StepFun
```

### Scheduled Automation

```
Every 8h:  Aoi triggers Pipeline 1 (GitHub Hunt) → dispatches to Snowdrop
Every 12h: Aoi triggers Pipeline 2 (Blog Maintenance) → dispatches to Kouka
On-demand: User triggers Pipeline 3 (Research) → Aoi dispatches to Snowdrop

Progress: MainAgent sends progress_update every 10 minutes for long tasks
Completion: MainAgent sends task_result → Aoi forwards to user
Failure: MainAgent sends task_result with status=FAILED → Aoi alerts user
```

### Proactive Reporting

Each MainAgent, upon completing a task, includes in task_result:
- What was accomplished (with URLs/paths)
- Token usage and duration
- Suggested next steps
- Any blockers or warnings

Aoi aggregates daily at 22:00:
- Tasks completed today
- Artifacts produced
- Issues/PRs filed
- Blog posts written
- Errors encountered

---

## 8. Implementation Plan

### Phase 1: Simplify Agent Roles (Day 1)

- [ ] Rewrite Aoi SOUL.md — pure dispatcher protocol
- [ ] Rewrite 5 MainAgent SOUL.md files — receive task → claude --print → reply
- [ ] Kill 5 MainAgent cron jobs (remove from cron-driver.sh)
- [ ] Simplify pipeline state.json to 3-field schema

### Phase 2: Pipeline Commands (Day 1-2)

- [ ] Write GitHub Hunt pipeline prompt (tested manually first)
- [ ] Write Blog Maintenance pipeline prompt (tested manually first)
- [ ] Create pipeline schedule config for Aoi

### Phase 3: Integration Testing (Day 2)

- [ ] Manual test: trigger Pipeline 1 via StepFun
- [ ] Manual test: trigger Pipeline 2 via StepFun
- [ ] Verify: Aoi receives results and forwards to user
- [ ] Verify: artifacts produced in correct locations

### Phase 4: Automation (Day 3)

- [ ] Enable Aoi cron with pipeline scheduling
- [ ] Run 8-hour burn-in test (16 heartbeat cycles)
- [ ] Monitor and fix any failures

### Phase 5: GSD Integration (Day 4+)

- [ ] Create custom GSD skills for each pipeline
- [ ] Integrate AgentTeam into pipeline prompts
- [ ] Add Codex/Gemini review gates inside pipeline execution
- [ ] Build research pipeline for academic workflow

---

## 9. Future: GSD2 Integration Points

The v2 architecture is designed to integrate with GSD2 once stabilized:

| GSD2 Feature | Integration Point |
|-------------|-------------------|
| `/gsd-autonomous` | Methode wraps entire pipeline in GSD autonomous mode |
| `/gsd-plan-phase` + `/gsd-execute-phase` | Lacia plans, Methode executes, within single ClaudeCode session |
| AgentTeam (`--agents`) | Snowdrop uses for parallel repo scanning |
| `/codex:review` | Satonus uses as review gate inside ClaudeCode |
| `/gemini:consult` | Snowdrop uses for research inside ClaudeCode |
| `/gsd-verify-work` | Kouka uses before publishing |

The key insight: GSD2 commands run INSIDE ClaudeCode, not outside. MainAgents don't need to understand GSD — they just pass the right command string.

---

## 10. Success Criteria

After v2 is deployed, these metrics should be met within 1 week:

| Metric | Target |
|--------|--------|
| GitHub Issues filed per day | >= 3 |
| PRs submitted per day | >= 1 |
| Repos archived | >= 3/day |
| Blog posts written per day | >= 1 high-quality |
| Pipeline success rate | >= 80% |
| User notification latency | < 5 min after task completion |
| Zero idle_report spam | 0 idle messages |
| Stale task detection | < 2h |
