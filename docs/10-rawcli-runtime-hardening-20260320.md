# Beatless RawCli Runtime Hardening Report (2026-03-20)

## Scope
This delivery lands the remaining runtime hardening, observability, and governance items for the Beatless `RawCli + tmux` architecture.

## Delivered

### 1) Runtime hardening
- Added supervisor self-healing loop:
  - `scripts/rawcli/rawcli_supervisor.sh`
- Added contract/health checker:
  - `scripts/rawcli/rawcli_healthcheck.sh`
- Hardened hook dispatch behavior:
  - dead pane cleanup before split
  - fallback to live pane or background execution
  - failure typing (`auth_error`, `missing_binary`, `cli_argument_error`, `unknown_tool`)
  - file: `scripts/rawcli/dispatch_hook_loop.sh`

### 2) Observability
- Added unified metrics rollup (JSON + Prometheus textfile format):
  - `scripts/rawcli/rawcli_metrics_rollup.sh`
- Added threshold-based alert evaluator:
  - `scripts/rawcli/rawcli_alert_check.sh`
- Added monitor snapshot for tmux watch:
  - `scripts/rawcli/rawcli_monitor_snapshot.sh`

### 3) Immediate ACK + async execution path
- Added ingress script that writes ACK evidence first, then queues execution:
  - `scripts/rawcli/rawcli_ingress_ack_submit.sh`

### 4) CI governance
- Added contract validator:
  - `scripts/ci/validate_rawcli_contracts.py`
- Added GitHub Actions workflow:
  - `.github/workflows/rawcli-governance.yml`
- Enforced checks:
  - `owner_agent` in 5-core set
  - `executor_tool` in tool-pool set
  - no wrapper-name leakage in routing
  - hook/ingress script contract tokens

## Open-source references used
- **tmux event-driven worker model**: session/window/pane isolation for process separation.
- **Prometheus textfile collector pattern**: `.prom` metrics emission for scraping/alerting compatibility.
- **SRE probe style**: periodic healthcheck + thresholded restart guardrail.

## Current runtime state target
- `cron` is not the control loop.
- Dispatch path is event-driven: `dispatch-queue.jsonl -> hook -> tmux pane -> result/event files`.
- Wrapper indirection is removed from execution path; tools execute as raw CLI commands.

## Remaining gaps to ideal state

### A) Failure taxonomy depth (medium)
- Current: core classes are present, but not yet provider-specific subcodes.
- Gap: add `provider_error_code`, `network_error`, and retry policy binding.

### B) Alert integration depth (medium)
- Current: local alert reports + log records + Prometheus-format metrics.
- Gap: integrate alert routing to Feishu/Telegram for active paging.

### C) Governance depth (low-medium)
- Current: CI validates routing/tool contracts and script compatibility.
- Gap: add replay tests with mocked queue/result fixtures in CI.

## Suggested next actions
1. Add provider-specific failure map and retry matrix in `dispatch_hook_loop.sh`.
2. Add notifier adapter for alert escalation (`warning`/`critical`).
3. Add fixture-based CI tests for queue->result lifecycle.
