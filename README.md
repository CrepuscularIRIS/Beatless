# Beatless (OpenClaw 5-MainAgent Baseline)

This repository is reset to the new Beatless baseline aligned with the live OpenClaw runtime.

## Baseline Scope
- 5 Main Agents: `lacia`, `methode`, `kouka`, `snowdrop`, `satonus`
- Main model baseline: `stepfun/step-3.5-flash`
- External lanes (via rawcli router plugin):
  - `claude_architect_cli` (Opus 4.6)
  - `claude_build_cli` (Kimi K2.5)
  - `codex_review_cli` (GPT-5.3-Codex)
  - `search_cli` (MiniMax M2.7)
  - `gemini_research_cli` (Gemini 3.1 Pro Preview)

## Directory
- `agents/<id>/` : exported workspace contracts (`AGENTS.md`, `SOUL.md`, `TOOLS.md`, etc.)
- `config/openclaw.redacted.json` : runtime config snapshot with secrets removed
- `config/cron.jobs.snapshot.json` : current cron automation snapshot
- `config/agents.snapshot.json` : current agent list snapshot
- `config/claudecode_plugin_trigger_matrix.v2.yaml` : ClaudeCode plugin trigger routing policy v2.1 (single-source rules)
- `schemas/` : Task OS schemas (`task_contract`, `state`, `envelope`)
- `runtime/` : Task OS runtime (`jobs`, `state`, `scheduler`) with harness mode
- `docs/` : acceptance and OpenRoom integration design
- `docs/CLAUDECODE_HARNESS_V2.md` : Claude-first execution harness strategy for V2
- `docs/CLAUDECODE_HARNESS_V2_1.md` : executable V2.1 trigger/gate baseline
- `scripts/validate_baseline.py` : baseline + runtime skeleton validation
- `scripts/validate_task_contract.py` : minimal TaskContract validator
- `scripts/task_os_scheduler.py` : scheduler with harness stage machine + legacy direct-pass mode
- `scripts/smoke_test_task_os.sh` : W1 smoke test
- `scripts/smoke_task_os_closed_loop_v21.sh` : V2.1 closed-loop smoke (success + escalation paths)
- `scripts/resolve_trigger.py` : deterministic trigger resolver
- `scripts/build_mode_selector.py` : single/ralph/teams mode selector
- `scripts/parse_codex_result.py` : codex gate parser (PASS/FAIL)
- `scripts/verify_gates.sh` : stage gate checker
- `scripts/smoke_trigger_v21.sh` : trigger/gate smoke

## CI
`beatless-baseline-validate` checks:
1. all 5 agents exist
2. key contract files exist
3. redacted config is parseable and includes 5-agent list
4. cron snapshot is parseable
5. task-os runtime skeleton files exist

## Task OS W1
Initialize:
`python3 scripts/init_task_os.py`

Validate contract:
`python3 scripts/validate_task_contract.py schemas/task_contract.example.json`

Run scheduler once:
`python3 scripts/task_os_scheduler.py --once`

Run V2.1 closed-loop smoke:
`bash scripts/smoke_task_os_closed_loop_v21.sh`

Run smoke:
`bash scripts/smoke_test_task_os.sh`
