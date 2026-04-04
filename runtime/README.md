# Task OS Runtime (W2.1)

This directory contains runnable Task OS runtime state for the Beatless harness loop.

## Layout
- `task_contract/templates/` : task contract templates
- `jobs/<job_id>/` : per-job state and artifacts
- `worktrees/<job_id>/` : isolated working trees (reserved for W2+)
- `state/queue.json` : file-backed queue snapshot
- `state/metrics.json` : basic runtime metrics
- `scheduler/config.json` : scheduler runtime config
- `scheduler/config.json` : scheduler config (`harness` or `direct-pass`)
- `meta_harness/<run_id>/` : sidecar benchmark artifacts (result/patch/env snapshot)
- `nlm/` : NotebookLM sidecar local digests and sync status

## W2.1 behavior
Scheduler executes one gated stage per pass:
- `queued -> planned -> implementing -> verifying -> reviewing -> done`
- writes `iteration/<n>/summary.json` and `trigger_event.json`
- applies retry/escalation policy from TaskContract budget + circuit breaker
- supports deterministic simulation with `MOCK_WORKER=1`

Legacy compatibility:
- `ORCHESTRATION_MODE=legacy` forces direct-pass behavior for old smoke tests.
