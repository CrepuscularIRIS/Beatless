# OpenRoom × Hermes v2.1 Alignment Plan

> Date: 2026-04-11 | Status: DRAFT | Depends on: architecture-v2-simplification-v2.md

---

## 1. Goal

Replace StepFun APP as the primary human interface with OpenRoom (self-hosted browser-based desktop).

After alignment:
- User opens OpenRoom in browser → chats with Aoi/agents directly
- Pipeline results (github-hunt, blog-maintenance) display as notifications/cards
- All Hermes agent communication goes through OpenRoom, not StepFun
- StepFun remains as mobile fallback channel

---

## 2. Current State

### OpenRoom (existing code at `claw/OpenRoom/`)

- **Stack**: React + TypeScript + Vite monorepo (Turborepo)
- **Apps**: `apps/webuiapps/` — multiple "apps" running in a desktop-like environment
- **Modified files** (uncommitted):
  - ChatPanel — agent chat UI
  - mcpBridgeTools — MCP server connection
  - agentOwnership — agent identity system
  - openclawAgentTools — OpenClaw integration (OUTDATED — was for old architecture)
  - PostEditor, Blog — blog-related apps
- **Architecture**: Apps communicate with AI backend via action system (Operation/Mutation/Refresh/System)

### ClawRoom (existing code at `claw/ClawRoom/`)

- **Purpose**: Bridge/adapter API connecting OpenClaw to OpenRoom
- **Status**: Built for old OpenClaw architecture → needs full rewrite for Hermes v2.1
- **Recommendation**: Archive and rebuild as thin adapter

### What needs to change

| Component | Old (OpenClaw) | New (Hermes v2.1) |
|-----------|---------------|-------------------|
| Backend API | ClawRoom REST+SSE | Direct `claude --print` or Hermes CLI |
| Agent routing | OpenClaw gateway port 18789 | Mailbox + `claude --print "/command"` |
| Chat protocol | Custom WebSocket | Standard chat + SSE for streaming |
| Pipeline results | None (manual check) | Push notifications + result cards |
| Agent identity | OpenClaw agent names | Hermes profile names (same: aoi, lacia, etc.) |

---

## 3. Architecture Options

### Option A: Thin HTTP Adapter (Recommended)

```
OpenRoom (Browser)
  ↕ REST/SSE
New ClawRoom (Node.js, ~200 lines)
  ↕ child_process
claude --print --model claude-sonnet-4-6 "/command"
```

- ClawRoom becomes a thin HTTP server that:
  - POST `/chat` → spawn `claude --print` → stream response via SSE
  - POST `/pipeline/:name` → launch pipeline in tmux → return task ID
  - GET `/pipeline/:name/status` → read state.json
  - GET `/agents` → list Hermes profiles
  - POST `/mailbox/send` → call mail.mjs
  - GET `/mailbox/:agent` → read agent's mailbox

- Advantages: Simple, reuses everything we built, no new protocols
- Disadvantages: Each chat message spawns a new claude process (cold start ~5s)

### Option B: Long-Running Claude Session via WebSocket

```
OpenRoom (Browser)
  ↕ WebSocket
ClawRoom (Node.js)
  ↕ stdin/stdout pipe
claude (interactive mode, long-running)
```

- ClawRoom spawns one `claude` interactive session and pipes messages
- Advantages: No cold start, conversational context preserved
- Disadvantages: Complex stdin/stdout management, session lifecycle issues

### Option C: Direct MCP Integration

```
OpenRoom (Browser)
  ↕ MCP Protocol
Claude Desktop/Web (built-in MCP client)
  ↕ MCP Servers
Hermes tools (mailbox, pipelines, etc.)
```

- Use MCP protocol to connect OpenRoom as an MCP client
- Advantages: Standard protocol, Claude handles all AI logic
- Disadvantages: OpenRoom needs MCP client implementation

**Recommendation**: Start with Option A (simplest), evolve to B or C later.

---

## 4. Implementation Phases

### Phase 1: Archive + Fresh Start

- [ ] Archive current OpenRoom changes: `cd OpenRoom && git stash`
- [ ] Archive ClawRoom: `mv ClawRoom ~/workspace/archive/ClawRoom-v1`
- [ ] Fresh pull OpenRoom from upstream (if applicable)
- [ ] Document what OpenRoom apps exist and their purpose

### Phase 2: New ClawRoom Adapter (~200 lines)

- [ ] Create new `ClawRoom/` with Express.js
- [ ] Endpoints:
  - `POST /api/chat` — body: `{ agent, message }` → spawn claude --print → SSE response
  - `POST /api/pipeline/run` — body: `{ name }` → launch test-run.sh → return ID
  - `GET /api/pipeline/:name/status` → read state.json
  - `GET /api/mailbox/:agent` → read mailbox via mail.mjs
  - `POST /api/mailbox/send` — body: `{ from, to, type, subject, body }`
- [ ] SSE streaming for long-running claude responses
- [ ] CORS for OpenRoom dev server

### Phase 3: OpenRoom Chat Integration

- [ ] Create/update ChatPanel app to use new ClawRoom API
- [ ] Agent selector (dropdown: aoi, lacia, methode, satonus, snowdrop, kouka)
- [ ] Message display with markdown rendering
- [ ] Pipeline trigger buttons (Run GitHub Hunt, Run Blog Maintenance)
- [ ] Pipeline status dashboard (real-time state.json polling)

### Phase 4: Pipeline Results Display

- [ ] Notification system for completed pipelines
- [ ] Result card component showing: repos scanned, findings, verdicts
- [ ] Blog post preview from blog-maintenance output
- [ ] Link to full report files

### Phase 5: StepFun → OpenRoom Migration

- [ ] Keep StepFun bridge as mobile fallback
- [ ] Add OpenRoom WebSocket channel to stepfun-bridge.mjs (or separate bridge)
- [ ] Unified notification: both StepFun and OpenRoom get pipeline results

---

## 5. Hermes Skills Cleanup

Skills to KEEP in shared/:
- agent-mailbox, claude-code-cli, execution-harness, github-mcp, anti-injection
- minimax-multimodal (TTS/image/video for OpenRoom media apps)

Skills to REMOVE from Aoi's symlinks (built-in Hermes skills, not useful):
- apple, gaming, leisure, smart-home, gifs, feeds, social-media
- dogfood, red-teaming (internal Hermes testing)
- email (not configured)

Skills to KEEP in Aoi's symlinks:
- autonomous-ai-agents, beatless, creative, data-science, devops
- domain, github, inference-sh, mcp, media, mlops
- note-taking, productivity, research, software-development, diagramming

---

## 6. Success Criteria

After alignment:
1. User can chat with any agent via OpenRoom browser UI
2. `/github-hunt` and `/blog-maintenance` can be triggered from OpenRoom
3. Pipeline results appear as notifications in OpenRoom
4. StepFun continues to work as mobile fallback
5. OpenRoom dev server runs alongside blog dev server
