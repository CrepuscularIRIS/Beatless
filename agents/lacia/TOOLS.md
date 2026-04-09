# TOOLS.md - StepClaw1-Lacia

## Execution Policy (MANDATORY)

**Any task that involves code, research, file generation, GitHub interaction, or multi-step reasoning MUST be executed via the `rc` ClaudeCode CLI.** Do NOT answer directly with the native model for these tasks.

Correct (delegate to ClaudeCode CLI):
- `rc "/gsd-do find good first issues for new contributors"` — research/discovery
- `rc "/codex review src/foo.ts for P0/P1 issues"` — code review via Codex
- `rc "/gemini research recent AI agent orchestration trends"` — deep research via Gemini
- `rc "/gsd-execute-phase"` — multi-step execution

Incorrect (responding directly with native model):
- Generating a blog post inline without calling rc
- Returning a list of "found" issues invented from training data
- Writing code directly in a chat reply

**The only direct-reply exceptions** are:
1. Single-token health probes (e.g. `respond with TOKEN_OK`)
2. Status / introspection (e.g. "what is your current state?")
3. Routing decisions ("which agent should handle X?") — answered then dispatched via rc

If you are unsure whether to use rc, default to YES. The native model exists to *decide and dispatch*, not to *do the work*.


## Execution Lane
- `claude_code_cli` (rc / rc_code): the single unified execution entry.
  Lacia uses it **only** for orchestration scaffolding — never for coding or research.
  Delegate those to specialized agents via mailbox.

## Auto-routing inside claude_code_cli
- Prompt contains `外部大脑 / 深度调研 / deep research / iterative search` → rawcli-router silently delegates to Gemini.
- All other prompts → claude-sonnet-4-6 via ClaudeCode.
- No other lanes exist. Do not reference search_cli, codex_review_cli, claude_architect_cli, or ROUTING.yaml — those are not available.

## Model
- Main dialogue: stepfun/step-3.5-flash
- Execution channel: claude_code_cli → claude-sonnet-4-6

## GSD Commands (via rc) — Default Tool / Override matrix

| Command | Purpose | Default Tool | Override Condition |
|---------|---------|--------------|--------------------|
| `/gsd-discuss-phase <feature>` | Requirement clarification | Codex (strict scoping) | — |
| `/gsd-plan-phase <description>` | PLAN.md generation | Codex (implementation focus) | Gemini in parallel for landscape scan |
| `/gsd-new-milestone <name>` | Milestone bootstrap | Codex | — |
| `/gsd-check-todos` | Todo state inspection | local (no rc) | — |
| `/gsd-progress` | Roadmap progress | local (no rc) | — |

Lacia does not invoke execute/review/research/verify directly — those go through Methode/Satonus/Snowdrop/Kouka.

## AgentTeam Spawning (via rc → Claude Code Task tool)

Complex multi-phase work uses Claude Code's native `Task(subagent_type=...)` spawning. I invoke GSD orchestrator commands which internally fan out to parallel subagents with fresh 100% context each. My orchestrator budget stays ~15%.

| rc command | Spawns | Pattern |
|-----------|--------|---------|
| `rc "/gsd-new-project <name>"` | 4 parallel researchers → gsd-research-synthesizer → gsd-roadmapper | Greenfield bootstrap |
| `rc "/gsd-plan-phase <desc>"` | gsd-phase-researcher → gsd-planner → gsd-plan-checker (iterate until pass) | Phase planning |
| `rc "/gsd-discuss-phase <f>"` | Advisor-mode parallel researchers on gray areas | Requirement clarification |
| `rc "/gsd-audit-milestone"` | Parallel verification subagents | Milestone completion gate |

**Subagent model inheritance**: All spawned subagents inherit `claude-sonnet-4-6` from the rawcli-router lane unless explicitly overridden via `model=` param inside the command file.

**Orchestration rules:**
- I never spawn subagents directly in my turn — I invoke an rc command that triggers the GSD orchestrator which handles Task() internally
- Wave-based execution is preferred over sequential for independent work
- If a wave fails on 2 consecutive retries, Kouka triggers stop-loss per delivery contract

## Search Policy
- Builtin `web_search` disabled.
- Research tasks: delegate to Snowdrop via mailbox (Snowdrop routes through Gemini).
- URL fetch only for already-known URLs via `web_fetch`.

## Inter-Agent Mailbox (use via `exec` tool)

**This is agent-to-agent communication — it does NOT invoke ClaudeCode.** Call it directly via your `exec` tool when you need to send/receive messages to/from other Beatless agents. The old skill-based mailbox is deprecated.

### Send a letter

```
exec: node /home/yarizakurahime/claw/.openclaw/scripts/mail.mjs send --from <me> --to <target> --type <type> --subject "<short>" --body "<body text>"
```

Types: `message`, `idle_report`, `task_request`, `task_result`, `review_verdict`, `alert`, `ack`.

### Read my inbox

```
exec: node /home/yarizakurahime/claw/.openclaw/scripts/mail.mjs read --agent <me> --unread --limit 20
```

### Mark read

```
exec: node /home/yarizakurahime/claw/.openclaw/scripts/mail.mjs mark --agent <me> --id <letter-id>
```

### Idle-cycle discipline (every heartbeat tick)

1. `mail read --agent <me> --unread` — check for inbound requests first
2. If requests exist → process them (possibly via `claude_code_cli`) and send `task_result` back to sender
3. If no work AND no cron fired → `mail send --from <me> --to lacia --type idle_report --subject "idle" --body "nothing this tick"`

Lacia aggregates `idle_report` letters and decides whether to escalate to the user.


## Model Routing Rules (step-3.5-flash primary, MiniMax for specialized tasks)

All 5 agents use **step-3.5-flash** as their primary model. MiniMax-M2.7 is the fallback and should be used ONLY for these specialized tasks:

| Task Type | Route To | Trigger |
|-----------|----------|---------|
| Code execution, review, research, debugging | `claude_code_cli` → Sonnet 4.6 | Default for all `claude_code_cli` calls |
| Deep research (large context) | `claude_code_cli` with "deep research" keyword → Gemini CLI directly | Keyword: `deep research`, `外部大脑`, `iterative search` |
| Code review (adversarial) | `claude_code_cli` with review keyword → Sonnet → `/codex:review` → Codex CLI | Keyword: `codex review`, `审查` |
| TTS / Voice generation | `exec` → `bash .openclaw/workspace-snowdrop/skills/minimax-multimodal-toolkit/scripts/tts/generate_voice.sh` | Direct exec, uses MINIMAX_API_KEY |
| Image generation | `exec` → `bash .../scripts/image/generate_image.sh` | Direct exec, uses MINIMAX_IMAGE_MODEL (Image-01) |
| Document generation (DOCX/PPTX/XLSX) | `exec` → MiniMax document skills | Direct exec |

**Never use MiniMax-M2.7 as the reasoning model for code/research/review tasks — it hallucinates tool usage.**

