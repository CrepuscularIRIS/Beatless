# TOOLS.md - StepClaw5-Snowdrop

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
- `claude_code_cli` (rc / rc_code): primary research lane.
  Include `外部大脑 / 深度调研 / deep research` in the prompt — rawcli-router auto-delegates to Gemini.
  Fallback: ClaudeCode direct research if Gemini times out.

## Model
- Main dialogue: stepfun/step-3.5-flash
- Research channel: claude_code_cli → Gemini 3.1 Pro Preview (keyword-routed)

## GSD Commands (via rc) — Default Tool / Override matrix

| Command | Purpose | Default Tool | Override Condition |
|---------|---------|--------------|--------------------|
| `/gsd-research-phase <topic>` | Full phase research | Gemini (1M context, search grounding) | Codex if pure code/architecture, no web search |
| `/gemini:consult <question>` | Targeted external question | Gemini (primary) | — |
| `/gsd-explore <scope>` | Ecosystem scan | Gemini (broad) | — |
| `/gsd-map-codebase` | Repo structure map | Gemini (1M window) | — |
| `/gsd-intel` | Intel collection | Gemini | — |
| `/gsd-plant-seed <idea>` | Early research notes | Gemini | — |

Short/quick lookups → include `外部大脑` or `deep research` keyword in any rc prompt — auto-routes to gemini-bridge.

Every research output must be packaged as EVIDENCE_PACK ≤500 tokens: evidence | counter-evidence | alternatives | unknowns. See gsd-research-synthesizer for dual-source (Gemini primary + Codex accuracy check).

## AgentTeam Research Spawning

Research commands internally spawn parallel Task() subagents on different domains (stack, features, architecture, pitfalls) then merge via gsd-research-synthesizer.

| rc command | Spawns | Pattern |
|-----------|--------|---------|
| `rc "/gsd-research-phase <topic>"` | gsd-phase-researcher | Deep single-topic research with Gemini grounding |
| `rc "/gsd-new-project <name>"` | 4 parallel gsd-project-researcher (STACK/FEATURES/ARCHITECTURE/PITFALLS) → gsd-research-synthesizer | Greenfield ecosystem scan |
| `rc "/gsd-plan-milestone-gaps"` | Parallel gap-research subagents | Multi-phase gap analysis |
| `rc "/gsd-explore <scope>"` | Explore subagent (Claude Code native) | Codebase exploration |
| `rc "/gsd-intel"` | gsd-intel-updater | Intel refresh |

All research subagents use Gemini-first routing per `<researcher_configuration>` in the command files. Final synthesis via gsd-research-synthesizer runs dual-source (Gemini primary + optional Codex accuracy check).

## Chief Scoring Officer — Assertive Scoring System

Snowdrop owns the multi-dimensional assertive scoring system (`Beatless/docs/ASSERTIVE_SCORING_SYSTEM.md`).

| rc command | Purpose | Spawns |
|-----------|---------|--------|
| `rc "/gsd-score <artifact>"` | Multi-dimensional scoring | gsd-scorer (Snowdrop-persona) |
| `rc "/gsd-score <artifact> --dimensions=blog"` | Blog content scoring | gsd-scorer with blog dimension set |
| `rc "/gsd-score <artifact> --dimensions=pr_review"` | PR review scoring | gsd-scorer with pr_review dimension set |

**Dimension sets available:**
- `code_review` (default): correctness 30% / quality 25% / aesthetics 15% / compliance 20% / overlap 10%
- `blog`: accuracy 25% / readability 25% / engagement 20% / seo 15% / originality 15%
- `pr_review`: correctness 35% / security 25% / performance 20% / compatibility 20%

**Verdict thresholds (literal):** ≥80 PASS | 60-80 HOLD | <60 REJECT

**Adversarial validation** always runs: extreme variance (>30 diff between any two dims), high overlap (>50% dup), cross-dimension conflicts (security/compliance overrides).

**Persistence:** scores append to `runtime/scores/YYYYMMDD-scores.jsonl` for later weight calibration.

## Output Contract
Every research turn must produce an EVIDENCE_PACK ≤500 tokens:
```
[研究发现 | topic]
证据: {source/link/quote}
反例: {counter-evidence}
替代: {alternative paths}
不确定: {explicitly unknown}
```
If no reliable source found, output: `结论: 未找到可靠证据` + what was tried.

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

