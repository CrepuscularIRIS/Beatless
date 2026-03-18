# V4 Slim Protocol Implementation (2026-03-18)

## Scope
This document records what is already implemented in runtime for Beatless V4 prompt refactor.

## Implemented

### 1) Protocol extraction (single source)
Runtime path: `~/.openclaw/beatless/protocols/`

- `CORE_PROTOCOL.md`
- `ROUTING_PROTOCOL.md`
- `RECEIPT_PROTOCOL.md`
- `FAILURE_PROTOCOL.md`

Result:
- Rules are no longer duplicated across AGENTS/payload/policies.
- AGENTS files now reference protocol files instead of embedding long repeated blocks.

### 2) AGENTS slimming
Implemented workspaces:

- `workspace-lacia/AGENTS.md` (84 lines)
- `workspace-methode/AGENTS.md`
- `workspace-satonus/AGENTS.md`
- `workspace-claude-generalist/AGENTS.md`
- `workspace-codex-builder/AGENTS.md`
- `workspace-gemini-researcher/AGENTS.md`
- `workspace-claude-architect-opus/AGENTS.md`
- `workspace-claude-architect-sonnet/AGENTS.md`

Result:
- Role prompts are compact and focused.
- Dispatch contracts are explicit and reusable.

### 3) Cron payload slimming
Runtime path: `~/.openclaw/cron/jobs.json`

Current payload sizes:
- START: 320 chars
- CHECK: 499 chars
- CLOSE: 377 chars
- REPLAY: 405 chars

Result:
- Removed long instruction soup from cron payloads.
- Behavior now points to protocol files and decision-tree execution.

### 4) Queue drift fix (implemented)
Runtime script: `~/.openclaw/beatless/scripts/queue_cycle.sh`

Fix summary:
- Syncs `queues.backlog` (dict entries) with `tasks[]`.
- Auto-materializes missing backlog tasks into `tasks[]`.
- Rebuilds queue views from `tasks.status` after each cycle.
- Prevents "backlog has items but script reports 0" drift.

Validation:
- `queues` and `tasks.status` counts now align after cycle.

### 5) Memory distill enabled
Runtime file: `~/.openclaw/cron/jobs.json`

Job:
- `Beatless Memory DISTILL`
- enabled: `true`
- schedule: `15 */4 * * *` (Asia/Shanghai)
- timeout: `600s`

Result:
- MEMORY can now be periodically distilled instead of staying seed-only.

### 6) Routing behavior aligned to preferences
Runtime files:
- `~/.openclaw/beatless/scripts/route_task.sh`
- `~/.openclaw/beatless/MODEL_ROUTING.yaml`

Result:
- Router now reads YAML rules dynamically.
- Search/repro lane priority set to Codex-first.

### 7) Minimal controlled auto task discovery + scoring
Runtime scripts:
- `~/.openclaw/beatless/scripts/task_discovery_minimal.sh`
- `~/.openclaw/beatless/scripts/task_value_score.sh`
- integrated into `~/.openclaw/beatless/scripts/queue_cycle.sh`

Behavior:
- Discovery is guarded (small, deterministic, deduplicated).
- Max new tasks per run is limited by policy (`max_new_per_run`, default `1`).
- Scoring computes value score and reasons for backlog candidates.
- Queue promotion now runs after discovery/scoring, with report fields:
  - `discovery_status`
  - `discovered_new_tasks`
  - `scoring_status`

Validation snapshot:
- Discovery added a single controlled task (`BT-AUTO-20260318-R1`) under guard.
- Scoring report generated (`task-value-score-latest.md`).
- Quality gate remains PASS.

## Validation status

Mandatory checks (latest):
- `quality_gate.sh`: PASS
- `heartbeat_check.sh`: PASS
- queue cycle: PASS
- route tests for codex/gemini/claude-opus/claude-generalist: PASS

## Notes
- This repo stores architecture and operating docs.
- Runtime truth remains under `~/.openclaw/`.
