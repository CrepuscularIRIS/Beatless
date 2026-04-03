# Acceptance Checklist (2026-04-03)

## A. OpenClaw Runtime
- [x] Gateway health OK
- [x] 5 MainAgent IDs present (`lacia/methode/kouka/snowdrop/satonus`)
- [x] Default model baseline is Step 3.5 Flash
- [x] RawCli router tools available (`architect/build/review/search/research`)

## B. Routing and Tools
- [x] `search_cli` routed to MiniMax M2.7 search lane
- [x] `codex_review_cli` routed to GPT-5.3-Codex
- [x] `claude_architect_cli` and `claude_build_cli` lanes available
- [x] `gemini_research_cli` lane available

## C. Automation
- [x] Maintenance-Daily-Lacia
- [x] Github-Explore-Snowdrop
- [x] PR-Cycle-Methode
- [x] CI-Guard-Satonus
- [x] Manual smoke run: all above jobs reached `lastRunStatus=ok`

## D. OpenRoom Bridge
- [x] `/api/openclaw-agent` bridge request returns `ok`
- [x] ChatPanel default router mode enabled
- [x] No local LLM config auto-falls back to OpenClaw router
- [x] Aoi shell context injected before routing to each main agent
