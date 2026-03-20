# Beatless RawCli Architecture Report (2026-03-20)

## Scope
This report captures the current Beatless architecture state after the RawCli migration and summarizes the remaining gap to the target/ideal shape.

## Current State (Verified)

### 1. Core Topology
- Runtime pattern is now: `owner_agent (5 core)` + `executor_tool (RawCli pool)`.
- OpenClaw agent list is reduced to 5 core agents only: `lacia/kouka/methode/satonus/snowdrop`.
- Wrapper-agent dispatch path is no longer the primary execution path.

### 2. RawCli Tool Pool
- Tool definitions are centralized in `~/.openclaw/beatless/TOOL_POOL.yaml`.
- Active tools:
  - `codex_cli`
  - `claude_sonnet_cli`
  - `claude_opus_cli`
  - `gemini_cli`
- Codex command shape has been corrected to non-interactive execution (`codex exec ...`), with prompt mode compatibility.

### 3. Hook/Event Runtime
- Dispatch runtime is event-driven (`dispatch-queue.jsonl` -> tmux hook -> per-task pane -> result JSON).
- Hook loop is active under `beatless-v2` session and writing result artifacts.
- Dead-pane cleanup and fallback execution are now enabled in hook dispatch.

### 4. End-to-End Runtime Evidence
- Successful RawCli dispatch proof tasks:
  - `BT-RAWCLI2-CODEX-20260320-151143`
  - `BT-RAWCLI2-CLAUDE-20260320-151143`
  - `BT-RAWCLI-SMOKE3-20260320-154701`
- Both produced:
  - `dispatch-results/<task>.json` with `status=success`
  - `/home/yarizakurahime/claw/Report/<task>-cli-output.md`
- Event metrics are now written to:
  - `~/.openclaw/beatless/metrics/dispatch-events.jsonl`

### 5. Skills/Agents Readiness
- Claude workflow plugins remain installed and enabled (high-frequency set intact).
- Codex agents (`explorer/reviewer/docs-researcher`) remain available.
- Codex skill aliases have been normalized (`quality-gate/code-review/refactor-clean/verify/...`) to match operational naming.

## What Was Adapted in This Round
- Added prompt mode routing in hook execution (`positional` vs `-p`) for CLI compatibility.
- Updated tool pool command for Codex RawCli correctness.
- Synced implementation bundle copies in `openclaw/docs/beatless-v2-rawcli/IMPLEMENTATION_BUNDLE`.
- Updated active memory terminology to RawCli naming (`codex_cli/claude_sonnet_cli/claude_opus_cli`).
- Cleaned active TASKS wording for wrapper-name drift (without rewriting historical session keys).
- Added runtime hardening scripts:
  - `rawcli_supervisor.sh`, `rawcli_healthcheck.sh`
- Added observability scripts:
  - `rawcli_metrics_rollup.sh`, `rawcli_alert_check.sh`, `rawcli_monitor_snapshot.sh`
- Added ingress ACK script:
  - `rawcli_ingress_ack_submit.sh`
- Added CI governance:
  - `.github/workflows/rawcli-governance.yml`
  - `scripts/ci/validate_rawcli_contracts.py`

## Gap to Ideal Shape

### Ideal Shape Definition
- Single-path execution: all external model work goes through RawCli tool pool.
- Deterministic routing contract: owner/executor split with no naming ambiguity.
- Fully observable runtime: each dispatch has stable logs, timings, and quality verdict linkage.
- Low drift memory/config docs: no legacy wrapper terms in active policy files.
- Operational hardening: one-command bootstrap, health checks, and CI validation for routing/hook flow.

### Estimated Distance (as of 2026-03-20, post-hardening)
- Overall completion toward ideal shape: **~88%**
- Remaining gap: **~12%**

Breakdown (estimation):
- Architecture migration completeness: **92%** (core design stabilized)
- Runtime reliability/hardening: **86%** (self-healing + health checks in place)
- Observability/diagnostics: **82%** (events/metrics/alerts landed; external paging pending)
- Config/memory consistency: **80%** (active files aligned, historical data remains mixed)
- Automation/CI enforcement: **84%** (contract checks in CI, replay tests still pending)

## Priority Next Steps (to close the 12%)
1. Add provider-specific failure subcodes and retry matrix binding.
2. Add active notifier (Feishu/Telegram) for warning/critical alerts.
3. Add fixture replay tests for queue->hook->result lifecycle in CI.
4. Continue legacy naming cleanup in non-archival task history.

## Conclusion
RawCli architecture is now operationally hardened and CI-governed. Remaining work is mainly alert routing depth and automated replay testing rather than architecture-level redesign.
