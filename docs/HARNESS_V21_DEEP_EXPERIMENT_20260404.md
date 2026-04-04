# Harness V2.1 Deep Experiment Report

Date: 2026-04-04

## Environment Baseline

- Claude Code CLI pinned: `2.1.34`
- Scheduler mode: `harness`
- Legacy compatibility retained via `ORCHESTRATION_MODE=legacy`

## Changes Verified in This Round

1. Claude Code rollback completed to `2.1.34`.
2. Scheduler hardened for concurrency and file safety:
   - atomic JSON write (`tmp -> replace`)
   - corrupted/empty `state.json` self-heal fallback
   - single-instance scheduler lock (`runtime/scheduler/.scheduler.lock`)
   - `--dry-run` no-lock path for compatibility tests
3. Smoke scripts hardened against transient lock contention (bounded retry).

## Test Matrix

### A. Trigger & Gate Smoke

Command:

```bash
bash scripts/smoke_trigger_v21.sh
```

Result:
- `S1/S2/S3/S4/S7/S8/S9/S10`: PASS

### B. Closed Loop Smoke (Mock Worker)

Command:

```bash
bash scripts/smoke_task_os_closed_loop_v21.sh
```

Result:
- Success path -> `done`: PASS
- Failure path -> `escalated` with mode hints: PASS

### C. Non-Mock Deep Experiment (Mixed Batch)

Command:

```bash
bash scripts/experiment_harness_nonmock_v21.sh
```

Workload:
- pass jobs: 4
- fail jobs: 3

Result:
- all pass jobs -> `done`
- all fail jobs -> `escalated`
- mode hints present on fail branch

### D. Empty Queue Stability

Command:

```bash
ORCHESTRATION_MODE=harness python3 scripts/task_os_scheduler.py --drain
```

Result:
- `total_changed_jobs=0`, no error

## Bug Found and Fixed

Issue:
- Concurrent scheduler invocations could cause `JSONDecodeError` while reading partially-written `state.json`.

Fix:
- atomic write for JSON files
- lock-based single scheduler execution
- corrupted state self-heal + metrics fallback
- smoke retry for lock-busy transient

## Conclusion

Harness V2.1 now forms a stable closed loop under:
- normal trigger/gate path
- non-mock mixed workload path
- concurrent start contention path

Current status is ready for next-stage worker integration and longer soak runs.
