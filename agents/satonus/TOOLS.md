# TOOLS.md - StepClaw4-Satonus

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
- `claude_code_cli` (rc / rc_code): used for review and audit operations only.
  Include `审查 / review / codex` in the prompt to route Codex review internally.

## Model
- Main dialogue: minimax/MiniMax-M2.7
- Review channel: claude_code_cli → claude-sonnet-4-6 (Codex gate internally)

## GSD Commands (via rc) — Default Tool / Override matrix

| Command | Purpose | Default Tool | Override Condition |
|---------|---------|--------------|--------------------|
| `/codex:review --background` | Async P0-P3 review | Codex (primary gate) | — |
| `/codex:adversarial-review` | Architecture challenge | Codex (strict) | — |
| `/gsd-code-review <phase>` | GSD-native full review | Codex (via gsd-code-reviewer agent) | Gemini if phase scope >200K tokens |
| `/gemini:review <scope>` | Second-opinion review | Gemini (1M context) | Used when Stage 1 PASS but security-sensitive, or Methode disputes P1 |
| `/gsd-validate-phase <p>` | Phase assumption validation | Codex | Gemini for cross-domain pattern check |
| `/gsd-audit-fix <target>` | Audit + targeted fix | Codex | — |
| `/gsd-secure-phase <p>` | Security audit | Codex | Gemini for SOTA vulnerability check |

Dual-source audit protocol: Codex-primary Stage 1 → optional Gemini Stage 2. See `research/get-shit-done/sdk/prompts/shared/audit-protocol.md`.

## AgentTeam Review Spawning

Review commands internally spawn `Task(subagent_type="gsd-code-reviewer")` with the Codex-native P0-P3 literal-genie persona.

| rc command | Spawns | Pattern |
|-----------|--------|---------|
| `rc "/gsd-code-review <phase>"` | gsd-code-reviewer (Codex-native) | Strict P0-P3 review with PASS/HOLD/REJECT verdict |
| `rc "/gsd-audit-uat"` | Verification subagents | UAT gap analysis |
| `rc "/gsd-audit-milestone"` | Parallel audit subagents | Multi-phase milestone audit |
| `rc "/gsd-audit-fix <target>"` | gsd-code-reviewer → gsd-executor (fix loop) | Audit + targeted fix cycle |

Each spawned reviewer gets fresh 100% context, reads only files in scope, returns structured REVIEW.md + verdict. I merge multiple reviewer outputs per audit-protocol.md Stage 1/Stage 2 rules.

## Verdict Protocol
| Verdict | Meaning | Required |
|---------|---------|----------|
| PASS | Meets standard, no known risk | — |
| REJECT | Does not meet standard | Single-line reason + fix suggestion |
| NEEDS_INFO | Insufficient evidence | Specify exactly what is missing |

Output format:
```
verdict: PASS|REJECT|NEEDS_INFO
risk: LOW|MEDIUM|HIGH
reason: {one line}
```

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

