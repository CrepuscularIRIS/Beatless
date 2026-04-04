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

## E. Task OS W1
- [x] `runtime/` skeleton initialized
- [x] `schemas/task_contract.schema.json` + example present
- [x] `scripts/validate_task_contract.py` executable and passing on example
- [x] `scripts/task_os_scheduler.py --once` transitions queued job to done (direct-pass)
- [x] `scripts/smoke_test_task_os.sh` passing

## E2. Task OS W2.1 Closed Loop
- [x] scheduler `harness` mode enabled (`runtime/scheduler/config.json`)
- [x] staged execution produces `iteration/<n>/trigger_event.json`
- [x] closed-loop smoke success path reaches `done`
- [x] closed-loop smoke failure path reaches `escalated` with mode hints
- [x] `MOCK_WORKER=1 bash scripts/smoke_task_os_closed_loop_v21.sh` passing

## F. ClaudeCode Harness V2
- [x] `config/claudecode_plugin_trigger_matrix.v2.yaml` present and parseable
- [x] `docs/CLAUDECODE_HARNESS_V2.md` published
- [x] 5 agents `TOOLS.md` include V2 harness policy references
- [x] Plugin smoke:
  - [x] `/codex:status --all`
  - [x] `/ralph-loop:help`
  - [x] `/agent-teams:team-status --json`

## G. Trigger V2.1
- [x] single-source rules `trigger_rules_v21` present
- [x] `scripts/resolve_trigger.py` available
- [x] `scripts/build_mode_selector.py` available
- [x] `scripts/parse_codex_result.py` available
- [x] `scripts/verify_gates.sh` available
- [x] `scripts/smoke_trigger_v21.sh` passing

## H. V3 Soak Quality Metrics
- [x] `scripts/soak_harness_v21_8h.sh` emits cycle metrics (`diff_lines`, `test_count`, `file_touched`)
- [x] false-pass detection enabled (`false_pass` field in soak JSONL)
- [x] soak summary includes `false_pass_cycles`

## I. Sidecar Integration
- [x] Meta-harness sidecar runner present (`scripts/meta_harness_sidecar_run.sh`)
- [x] Meta-harness sidecar smoke passing (`scripts/smoke_meta_harness_sidecar.sh`)
- [x] NotebookLM sidecar runner present (`scripts/notebooklm_sidecar_sync.sh`)
- [x] NotebookLM sidecar smoke passing (`scripts/smoke_notebooklm_sidecar.sh`)
- [x] Sidecar integration doc present (`docs/V3_SIDECAR_INTEGRATION.md`)
