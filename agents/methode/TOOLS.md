# TOOLS.md - StepClaw3-Methode

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
- `claude_code_cli` (rc / rc_code): primary build lane. All implementation flows through rc.
  Codex review happens inside ClaudeCode when the prompt triggers it — no separate plugin needed.

## Build Modes (triggered via rc prompt wording)
| Prompt contains | Mode |
|-----------------|------|
| default | single-lane direct build |
| `直到通过 / 反复迭代 / ralph` | ralph-loop iterative build |
| `并行 / 分流 / parallel` | agent-teams parallel build |
| `审查 / review / codex` | Codex review gate |

## Model
- Main dialogue: stepfun/step-3.5-flash
- Execution channel: claude_code_cli → claude-sonnet-4-6

## GSD Commands (via rc) — Default Tool / Override matrix

| Command | Purpose | Default Tool | Override Condition |
|---------|---------|--------------|--------------------|
| `/gsd-execute-phase` | Run PLAN.md wave | Codex (strict execution) | — |
| `/gsd-execute-phase --gaps-only` | Close remaining gaps | Codex | — |
| `/gsd-do <task>` | Single-task execute | Codex | — |
| `/codex:rescue --resume` | Continue blocked fix | Codex (same approach) | — |
| `/codex:rescue --fresh` | Restart failing fix | Codex (new approach) | — |
| `/gsd-add-tests <target>` | TDD test generation | Codex | — |

Methode is the execution specialist. Other GSD phases (plan/research/review/deliver) typically flow through other agents, but Methode can invoke them directly in an emergency.

## AgentTeam Spawning (wave-based parallel execution)

When executing a phase, I invoke GSD commands that internally fan out via Claude Code's `Task(subagent_type=...)` with fresh 100% context per subagent.

| rc command | Spawns | Pattern |
|-----------|--------|---------|
| `rc "/gsd-execute-phase"` | gsd-executor × N (one per plan in wave) | Full phase wave execution |
| `rc "/gsd-execute-phase --gaps-only"` | gsd-executor × N (gap plans only) | Gap closure after verify-work |
| `rc "/gsd-execute-phase --wave 2"` | gsd-executor × N (filtered to wave 2) | Staged rollout / quota pacing |
| `rc "/gsd-quick"` | gsd-planner (quick) → gsd-executor | Fast track for small scoped work |
| `rc "/gsd-do <task>"` | Single gsd-executor | Single-task execution |
| `rc "/gsd-debug <issue>"` | gsd-debugger (isolated context) | Root-cause investigation |
| `rc "/gsd-add-tests <target>"` | gsd-executor (TDD mode) | Test generation before fix |

**Wave-based execution protocol:**
1. Orchestrator analyzes plan dependencies → groups into waves
2. Each wave: spawn N parallel gsd-executor subagents (one per independent plan)
3. Collect results → next wave when all complete
4. Retry on failure: `rc "/codex:rescue --resume"` (same approach) or `--fresh` (restart)
5. Two consecutive failures → escalate to Kouka for stop-loss

**Model inheritance**: Subagents inherit `claude-sonnet-4-6` from rawcli-router. Override only for heavy reasoning (model="claude-opus-4-6") in the command file.

## AgentTeam via Claude Code `--agents` (for issue discovery + parallel work)

For tasks requiring multiple parallel workers (e.g. repo scanning, issue hunting), spawn a Claude Code team session:

```bash
# Direct team spawn via exec (preferred for issue discovery):
exec: cd /home/yarizakurahime/workspace/ghsim/<repo> && claude \
  --permission-mode bypassPermissions --print \
  --agents '{"scanner":{"description":"Scans test output for real bugs","prompt":"Run tests, find failures, trace to source code"},"analyst":{"description":"Reads GitHub issues and cross-refs with code","prompt":"Compare open issues against actual codebase state"},"patcher":{"description":"Writes minimal fix patches","prompt":"Given a confirmed bug, write the smallest correct fix"}}' \
  "Create a team with scanner, analyst, and patcher. Scanner: run go test ./... and report failures. Analyst: check open GitHub issues. Patcher: if a real bug is confirmed, produce a patch."
```

**When to use AgentTeam vs single agent:**
| Scenario | Approach |
|----------|----------|
| Single repo, single task | Single `claude_code_cli` call |
| Single repo, discovery + fix | AgentTeam (scanner + analyst + patcher) |
| Multiple repos, same task | Parallel `exec` calls (one per repo) + AgentTeam inside each |
| Issue validation (known issue) | Single `claude_code_cli` with explicit issue URL |

**tmux session management for long-running teams:**
```bash
# Start team in tmux for monitoring
exec: tmux new-session -d -s methode-team "cd /path/to/repo && claude --permission-mode bypassPermissions --agents '{...}' 'team prompt'"

# Monitor
exec: tmux capture-pane -t methode-team -p | tail -30

# Check if done
exec: tmux has-session -t methode-team 2>/dev/null && echo "running" || echo "done"

# Kill if stuck
exec: tmux kill-session -t methode-team
```

## Execution Contract
Every task must produce a verifiable artifact: file diff / test result / config change.
Cannot mark done without evidence.

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


## MiniMax Asset Output Paths

All MiniMax-generated assets MUST be saved to the dedicated output directory. Never scatter files in working directories.

| Asset Type | Output Path | Model (from .env) |
|-----------|-------------|-------------------|
| Images | `/home/yarizakurahime/claw/output/minimax/images/` | MINIMAX_IMAGE_MODEL |
| TTS Audio | `/home/yarizakurahime/claw/output/minimax/audio/tts/` | MINIMAX_TTS_MODEL / _HD / _TURBO |
| Music | `/home/yarizakurahime/claw/output/minimax/audio/music/` | MINIMAX_MUSIC_MODEL |
| Video | `/home/yarizakurahime/claw/output/minimax/video/` | MINIMAX_VIDEO_MODEL_T2V / _I2V / _SEF / _S2V |
| Documents | `/home/yarizakurahime/claw/output/minimax/documents/` | MiniMax DOCX/PDF/XLSX skills |

**Naming convention**: `<date>-<agent>-<slug>.<ext>` (e.g. `2026-04-10-kouka-blog-hero.png`)

**Example usage** (via exec):
```bash
# TTS
bash .openclaw/workspace-snowdrop/skills/minimax-multimodal-toolkit/scripts/tts/generate_voice.sh tts "<text>" -o /home/yarizakurahime/claw/output/minimax/audio/tts/2026-04-10-kouka-blog-intro.mp3

# Image
bash .openclaw/skills/minimax-multimodal/scripts/image/generate_image.sh --prompt "<prompt>" -o /home/yarizakurahime/claw/output/minimax/images/2026-04-10-kouka-hero.png

# Music
bash .openclaw/skills/minimax-multimodal/scripts/music/generate_music.sh --prompt "<prompt>" -o /home/yarizakurahime/claw/output/minimax/audio/music/2026-04-10-snowdrop-ambient.mp3
```

