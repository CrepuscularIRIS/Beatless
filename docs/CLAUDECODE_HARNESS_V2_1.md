# ClaudeCode Harness V2.1 (Beatless)

Date: 2026-04-04
Status: executable baseline

## Scope
This document upgrades V2 with deterministic trigger resolution, measurable build-mode switching, and machine-checkable gates.

## Key Changes
- Single trigger source: `config/claudecode_plugin_trigger_matrix.v2.yaml` (`trigger_rules_v21`).
- Deterministic conflict solver: score + requires-count + id tie-break.
- Build orchestration selector script added.
- Codex result parser added for gate verdict.
- Stage gate script added (`plan/implement/verify/review/publish`).
- Scheduler supports `--dry-run` and emits `ORCHESTRATION_MODE`.
- Scheduler harness mode executes staged gates with retry/escalation logic.

## Implementation Files
- `scripts/resolve_trigger.py`
- `scripts/build_mode_selector.py`
- `scripts/parse_codex_result.py`
- `scripts/verify_gates.sh`
- `scripts/smoke_trigger_v21.sh`
- `schemas/trigger_rule.schema.json`
- `runtime/templates/verify.sh`

## Trigger Event Examples
- Single-lane:
  - `python3 scripts/resolve_trigger.py --prompt "修复 OpenRoom/src/mcp.ts 中的类型错误" --contract schemas/task_contract.example.json`
- Ralph loop:
  - `python3 scripts/resolve_trigger.py --prompt "反复迭代修复 MCP 桥接直到测试通过" --contract schemas/task_contract.example.json`
- Agent teams:
  - `python3 scripts/resolve_trigger.py --prompt "并行开发三个模块并迭代直到通过" --contract schemas/task_contract.example.json`

## Smoke
Run:
- `bash scripts/smoke_trigger_v21.sh`
- `bash scripts/smoke_task_os_closed_loop_v21.sh`

Expected:
- S1/S2/S3/S4/S7/S8/S9 all PASS.
- Closed-loop: one task reaches `done`, one task reaches `escalated` with hints.
