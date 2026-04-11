# OpenClaw → Hermes Agent: Complete Migration Status

> Date: 2026-04-10 | All components audited and classified

---

## Executive Summary

| Category | Migrated | Replaced | Deferred | Ignored | Total |
|----------|----------|----------|----------|---------|-------|
| Infrastructure | 7 | 0 | 0 | 0 | 7 |
| Skills (Enabled) | 5 | 2 | 0 | 2 | 9 |
| Skills (Disabled) | 4 | 0 | 0 | 18 | 22 |
| Plugins/Extensions | 2 | 2 | 1 | 1 | 6 |
| Agent Workspaces | 5 | 0 | 0 | 0 | 5 |
| Harness Scripts | 8 | 0 | 0 | 0 | 8 |
| Gateway/Channels | 1 | 0 | 1 | 5 | 7 |
| **Total** | **32** | **4** | **2** | **26** | **64** |

---

## 1. Core Infrastructure

| Component | OpenClaw | Hermes | Status | Notes |
|-----------|----------|--------|--------|-------|
| Agent orchestration | 5 agents, openclaw.json | 6 profiles (Aoi + 5 MainAgents) | **MIGRATED** | Added Aoi as MiniMax M2.7 orchestrator |
| Model routing | Per-agent in openclaw.json | Per-profile config.yaml | **MIGRATED** | StepFun custom provider + MiniMax-CN |
| Inter-agent mailbox | mail.mjs → .openclaw/mailbox/ | mail.mjs → shared/mailbox/ | **MIGRATED** | Path-fixed, 6 agents, E2E verified |
| Cron scheduling | croner (5 jobs, 30min) | croniter (6 jobs, */30 * * * *) | **MIGRATED** | Added Aoi heartbeat job |
| Pipeline state machine | pipeline-state.json | shared/pipelines/*/state.json | **MIGRATED** | 3 pipelines: github-discovery, content-aggregation, blog-maintenance |
| Task queue | Queue.md | shared/queue.md | **MIGRATED** | Append-only format preserved |
| Shared context | workspace-*/TOOLS.md | HERMES.md (symlinked to cwd) | **MIGRATED** | Loaded by all agents via Hermes context-files |

---

## 2. Enabled Skills

| Skill | Lines | OpenClaw | Hermes | Status | Notes |
|-------|-------|----------|--------|--------|-------|
| **agent-mailbox** | 150 | Active | shared/skills/agent-mailbox | **MIGRATED** | Rewritten for Hermes mail.mjs path |
| **claude-code-cli** (rc) | — | rawcli-router plugin | shared/skills/claude-code-cli | **MIGRATED** | v3.0: Codex/Gemini as INTERNAL plugins, not separate CLIs |
| **minimax-multimodal-toolkit** | 649 | Active + scripts/ | shared/skills/minimax-multimodal | **MIGRATED** | Scripts copied, env vars configured |
| **minimax-multimodal** | 649 | Active (duplicate) | (merged into above) | **MIGRATED** | Single skill, no duplication |
| **github-mcp** | 329 | Active | shared/skills/github-mcp | **MIGRATED** | Hermes also has bundled GitHub skill |
| **anti-injection-skill** | 100+ | Active | shared/skills/anti-injection | **MIGRATED** | OWASP LLM Top 10 defense |
| **execution-harness** | — | harness.mjs (script) | shared/skills/execution-harness | **MIGRATED** | NEW: Wraps checkpoint/metrics/verify/safety |
| **memory-manager** | 309 | Active + scripts/ | — | **REPLACED** | Hermes built-in SQLite FTS5 memory is superior |
| **todo-management** | 100 | Active + scripts/ | — | **REPLACED** | Hermes built-in todo tool |

---

## 3. Disabled Skills (Document Generation)

| Skill | Lines | OpenClaw | Hermes | Status | Notes |
|-------|-------|----------|--------|--------|-------|
| **minimax-docx** | 79 | Disabled | shared/skills/minimax-docx | **MIGRATED** | Requires .NET 9.0 SDK + OpenXML |
| **minimax-pdf** | 471 | Disabled | shared/skills/minimax-pdf | **MIGRATED** | Requires Paged.js |
| **minimax-xlsx** | 324 | Disabled | shared/skills/minimax-xlsx | **MIGRATED** | Requires LibreOffice headless |
| **pptx-generator** | 389 | Disabled | shared/skills/pptx-generator | **MIGRATED** | python-pptx, 5 themes |

---

## 4. Disabled Skills (Not Migrated — Intentionally Ignored)

| Skill | Lines | Reason for Ignoring |
|-------|-------|---------------------|
| adaptive-reasoning | 112 | Experimental, not production-tested |
| agent-autopilot | 463 | Replaced by Aoi's heartbeat orchestration |
| agent-orchestration-multi-agent-optimize | 239 | Replaced by Hermes profile + mailbox model |
| api-gateway | 673 | Not needed — Hermes has native gateway |
| close-loop | 43 | Trivial, integrated into harness skill |
| gemini-deep-research | 69 | DISABLED per architecture — research via /gemini:consult plugin |
| metacognition | 91 | Experimental |
| multi-agent-collab | 80 | Replaced by mailbox protocol |
| notebooklm-cli | 203 | External service dependency, low priority |
| ontology | 232 | Experimental knowledge graph |
| openclaw-backup | 68 | Replaced by Hermes session persistence |
| openclaw-config | 123 | Replaced by Hermes config.yaml |
| openclaw-security-audit | 151 | Covered by anti-injection + safety.mjs |
| openclaw-server-secure-skill | 128 | OpenClaw-specific, not applicable |
| playwright-mcp | 165 | Browser tools disabled per Beatless architecture |
| skill-vetter | 138 | Development tool, not production |

---

## 5. Plugins / Extensions

| Plugin | Version | OpenClaw | Hermes | Status | Notes |
|--------|---------|----------|--------|--------|-------|
| **openclaw-rawcli-router** | 0.1.0 | Single-mode Claude router | claude-code-cli skill | **REPLACED** | Skill-based; Codex/Gemini as internal plugins |
| **openclaw-stepfun** | 0.2.14 | WebSocket bot API | stepfun-bridge.mjs | **MIGRATED** | Bridge script: StepFun WS → Hermes CLI |
| **lossless-claw** | 0.5.2 | DAG-based context mgmt | — | **REPLACED** | Hermes native context compression |
| **opik-openclaw** | 0.2.9 | Observability tracing | — | **DEFERRED** | Enhancement, not blocking |
| **openclaw-openroom-bridge** | 0.1.0 | OpenRoom LLM proxy | — | **DEFERRED** | Can add when OpenRoom is needed |
| **openclaw-codex-app-server** | 0.5.0 | Codex Desktop bridge | — | **IGNORED** | Codex accessed via /codex: plugin |

---

## 6. Agent Workspaces

| Agent | Model | SOUL.md | Context | Skills | Cron | Status |
|-------|-------|---------|---------|--------|------|--------|
| **Aoi** | MiniMax M2.7 | ✅ Dispatcher protocol | HERMES.md | 8 shared | heartbeat (*/30) | **MIGRATED** |
| **Lacia** | Step 3.5 Flash | ✅ Convergence authority | HERMES.md | 8 shared | strategy-review (*/30) | **MIGRATED** |
| **Methode** | Step 3.5 Flash | ✅ Execution specialist | HERMES.md | 8 shared | pr-cycle (*/30) | **MIGRATED** |
| **Satonus** | Step 3.5 Flash | ✅ Review gate | HERMES.md | 8 shared | ci-guard (*/30) | **MIGRATED** |
| **Snowdrop** | Step 3.5 Flash | ✅ Research + scoring | HERMES.md | 8 shared | github-explore (*/30) | **MIGRATED** |
| **Kouka** | Step 3.5 Flash | ✅ Delivery + stop-loss | HERMES.md | 8 shared | blog-maintenance (*/30) | **MIGRATED** |

### Per-Agent Workspace Files Migration

| File | OpenClaw | Hermes | Status |
|------|----------|--------|--------|
| SOUL.md | Per workspace (personality + execution contract) | profiles/*/SOUL.md | **MIGRATED** |
| TOOLS.md | Per workspace (6K-10K lines, detailed routing) | HERMES.md (shared, ~200 lines core) | **MIGRATED** (condensed) |
| AGENTS.md | Per workspace (role definition) | Merged into SOUL.md | **MIGRATED** |
| HEARTBEAT.md | Per workspace (status reporting) | Aoi SOUL.md + cron protocol | **MIGRATED** |
| IDENTITY.md | Per workspace (identity card) | Merged into SOUL.md | **MIGRATED** |
| BOOTSTRAP.md | Per workspace (startup sequence) | Not needed — Hermes profile handles init | **REPLACED** |
| USER.md | Satonus/Snowdrop only | Hermes built-in USER.md memory | **REPLACED** |
| memory/*.md | Per workspace (timestamped) | Hermes SQLite FTS5 sessions | **REPLACED** |

---

## 7. Harness Scripts (GSD2 Runtime)

| Script | Lines | Purpose | Location | Status |
|--------|-------|---------|----------|--------|
| **mail.mjs** | 245 | Inter-agent mailbox | shared/scripts/ | **MIGRATED** (path-fixed) |
| **harness.mjs** | 186 | Pre/post execution wrapper | shared/scripts/ | **MIGRATED** |
| **checkpoint.mjs** | 173 | Git checkpoint refs | shared/scripts/ | **MIGRATED** |
| **session-lock.mjs** | 209 | O_EXCL agent locking | shared/scripts/ | **MIGRATED** |
| **metrics.mjs** | 157 | Token/cost ledger | shared/scripts/ | **MIGRATED** |
| **verify.mjs** | 154 | Post-execution tests | shared/scripts/ | **MIGRATED** |
| **safety.mjs** | 205 | Evidence audit | shared/scripts/ | **MIGRATED** |
| **worktree.mjs** | 268 | Per-agent git worktrees | shared/scripts/ | **MIGRATED** |
| **notify-user.sh** | 39 | StepFun push | shared/scripts/ | **STALE** (depends on openclaw-local binary) |

---

## 8. Gateway / Channels

| Channel | OpenClaw | Hermes | Status | Notes |
|---------|----------|--------|--------|-------|
| **StepFun** (AppId: 346623) | openclaw-stepfun plugin (WebSocket) | stepfun-bridge.mjs | **MIGRATED** | Bridge: WS → Hermes CLI, @agent routing |
| **Feishu** | Configured but disabled | — | **IGNORED** | Was disabled in OpenClaw |
| **Discord** | Configured but disabled | Available in Hermes gateway | **IGNORED** | Can enable later |
| **Telegram** | Configured but disabled | Available in Hermes gateway | **IGNORED** | Can enable later |
| **Slack** | Configured but disabled | Available in Hermes gateway | **IGNORED** | Can enable later |
| **WhatsApp** | Configured but disabled | Available in Hermes gateway | **IGNORED** | Can enable later |
| **Webhook** | Not configured | Available in Hermes gateway | **DEFERRED** | For GitHub/external events |

---

## 9. Toolset Configuration (Beatless Architecture)

### Enabled Tools (per profile)
- `terminal` — Shell execution (primary: routes to ClaudeCodeCli)
- `file` — Read/write/search files
- `memory` — Hermes built-in memory (SQLite FTS5)
- `todo` — Task tracking
- `skills` — Skill discovery and execution
- `cronjob` — Cron management (Aoi only, effectively)

### Disabled Tools (per Beatless architecture)
- `web` — Web search/extract (research routes through /gemini:consult)
- `browser` — Browser automation (not used)
- `delegate` — Hermes subagent spawning (we use mailbox instead)
- `code_execution` — Sandbox code (not needed, terminal covers this)
- `send_message` — Cross-platform messaging (bridge handles this)
- `homeassistant` — Smart home (not applicable)
- `tts` — Hermes TTS (MiniMax skill used instead)
- `image_generation` — Hermes image gen (MiniMax skill used instead)
- `transcription` — Audio transcription (not needed)

---

## 10. GSD Pipeline Status

| Component | Status | Verification |
|-----------|--------|-------------|
| ClaudeCodeCli invocation | **WORKING** | E2E: Lacia/Snowdrop/Satonus all successfully call `claude --print` |
| /codex:review (internal plugin) | **AVAILABLE** | Routed through ClaudeCodeCli prompt prefix |
| /gemini:consult (internal plugin) | **AVAILABLE** | Routed through ClaudeCodeCli prompt prefix |
| /gsd-execute-phase | **AVAILABLE** | Via `claude --print "/gsd-execute-phase"` |
| /gsd-research-phase | **AVAILABLE** | Via `claude --print "/gsd-research-phase <topic>"` |
| /gsd-score | **AVAILABLE** | Via `claude --print "/gsd-score <artifact>"` |
| AgentTeam (--agents) | **AVAILABLE** | Via `claude --print --agents '[...]' "<task>"` |
| Wave-based execution | **AVAILABLE** | Methode's SOUL.md documents protocol |
| Pipeline state machine | **WORKING** | E2E: Aoi dispatches → Snowdrop receives → executes → returns results |

---

## 11. MiniMax Multimodal Status

| Capability | Model | Skill | Env Vars | Output Dir | Status |
|------------|-------|-------|----------|------------|--------|
| TTS | speech-2.8-hd | minimax-multimodal | MINIMAX_TTS_MODEL | output/minimax/audio/tts/ | **CONFIGURED** |
| TTS HD | speech-02-hd | minimax-multimodal | MINIMAX_TTS_MODEL_HD | output/minimax/audio/tts/ | **CONFIGURED** |
| Voice Clone | voice_clone | minimax-multimodal | — | output/minimax/audio/ | **CONFIGURED** |
| Image Gen | image-01 | minimax-multimodal | MINIMAX_IMAGE_MODEL | output/minimax/images/ | **CONFIGURED** |
| Video T2V | MiniMax-Hailuo-2.3 | minimax-multimodal | MINIMAX_VIDEO_MODEL_T2V | output/minimax/video/ | **CONFIGURED** |
| Music Gen | music-2.5+ | minimax-multimodal | MINIMAX_MUSIC_MODEL | output/minimax/audio/music/ | **CONFIGURED** |
| DOCX Gen | — | minimax-docx | — | output/minimax/documents/ | **SKILL READY** (disabled, needs .NET) |
| PDF Gen | — | minimax-pdf | — | output/minimax/documents/ | **SKILL READY** (disabled, needs Paged.js) |
| XLSX Gen | — | minimax-xlsx | — | output/minimax/documents/ | **SKILL READY** (disabled, needs LibreOffice) |
| PPTX Gen | — | pptx-generator | — | output/minimax/documents/ | **SKILL READY** (needs python-pptx) |

---

## 12. StepFun App Connection

| Feature | Status | Implementation |
|---------|--------|----------------|
| WebSocket connection | **READY** | stepfun-bridge.mjs (auto-reconnect + heartbeat) |
| Message receiving | **READY** | JSON parse + @agent routing |
| Agent invocation | **READY** | hermes -p <agent> chat -q "<prompt>" -Q |
| Response delivery | **READY** | WS send back to StepFun |
| HeartBeat (30s) | **BUILT-IN** | Bridge sends heartbeat every 30s |
| Tmux session | **NOT CONFIGURED** | Can run bridge in tmux for persistence |

### Start the bridge:
```bash
# In tmux session for persistence
tmux new -s stepfun-bridge
cd /home/yarizakurahime/claw
source hermes-agent/venv/bin/activate
node ~/.hermes/shared/scripts/stepfun-bridge.mjs
```

### Agent routing:
```
@lacia plan this feature     → routes to Lacia profile
@methode fix this bug        → routes to Methode profile
@snowdrop research agents    → routes to Snowdrop profile
just a message               → routes to default (Lacia)
```

---

## 13. File Layout

```
~/.hermes/
├── .env                                    # Global API keys
├── profiles/
│   ├── aoi/      (config.yaml, SOUL.md, .env, skills/, cron/)
│   ├── lacia/    (config.yaml, SOUL.md, .env, skills/, cron/)
│   ├── methode/  (config.yaml, SOUL.md, .env, skills/, cron/)
│   ├── satonus/  (config.yaml, SOUL.md, .env, skills/, cron/)
│   ├── snowdrop/ (config.yaml, SOUL.md, .env, skills/, cron/)
│   └── kouka/    (config.yaml, SOUL.md, .env, skills/, cron/)
├── shared/
│   ├── HERMES.md                           # Shared execution protocol (symlinked to cwd)
│   ├── mailbox/  (6 agent .jsonl files)
│   ├── pipelines/ (3 pipeline state.json)
│   ├── queue.md
│   ├── safety/
│   ├── scripts/  (8 harness scripts + stepfun-bridge + node_modules/)
│   └── skills/   (10 skills, symlinked to all profiles)
│       ├── agent-mailbox/
│       ├── anti-injection/
│       ├── claude-code-cli/                # v3.0: Codex/Gemini as internal plugins
│       ├── execution-harness/
│       ├── github-mcp/
│       ├── minimax-multimodal/             # TTS/Image/Video/Music
│       ├── minimax-docx/
│       ├── minimax-pdf/
│       ├── minimax-xlsx/
│       └── pptx-generator/
└── state.db                                # SQLite session store
```

---

## 14. Verification Results

| Test | Result | Timestamp |
|------|--------|-----------|
| Aoi (MiniMax M2.7) responds | AOI_OK | 2026-04-10 15:56 |
| Lacia (Step 3.5 Flash) responds | LACIA_OK | 2026-04-10 15:57 |
| Methode responds | METHODE_OK | 2026-04-10 15:58 |
| Satonus responds | SATONUS_OK | 2026-04-10 15:58 |
| Snowdrop responds | SNOWDROP_OK | 2026-04-10 15:58 |
| Kouka responds | KOUKA_OK | 2026-04-10 15:58 |
| terminal() tool execution | TERMINAL_WORKS | 2026-04-10 15:59 |
| Mailbox send (Methode → Aoi) | Message delivered | 2026-04-10 16:01 |
| Mailbox E2E (Satonus → Aoi via agent) | idle_report received | 2026-04-10 16:06 |
| HERMES.md context loaded | GSD commands visible | 2026-04-10 16:35 |
| Aoi reads all mailboxes | 3 messages found | 2026-04-10 16:37 |
| Aoi dispatches to Snowdrop | task_request delivered | 2026-04-10 16:39 |
| Snowdrop executes via ClaudeCodeCli | 3 repos with real URLs | 2026-04-10 16:41 |
| StepFun bridge starts | WebSocket connects | 2026-04-10 16:58 |
