# V3 Sidecar Integration

## Scope

This document defines V3 sidecar integration for:

- `meta-harness-tbench2-artifact` as benchmark/experiment runner
- NotebookLM as research digest sidecar

Both run as sidecars and do **not** replace Main Agent runtime.

## 1) Meta-Harness Sidecar

- Script: `scripts/meta_harness_sidecar_run.sh`
- Mode:
  - `--dry-run`: integration smoke only
  - real run: requires `META_HARNESS_COMMAND`
- Isolation: each run uses dedicated git worktree under `runtime/worktrees/`
- Outputs:
  - `runtime/meta_harness/<run_id>/result.json`
  - `runtime/meta_harness/<run_id>/patch.diff`
  - `runtime/meta_harness/<run_id>/verify_report.json`
  - `runtime/meta_harness/<run_id>/env_snapshot.json`

Smoke:

```bash
bash scripts/smoke_meta_harness_sidecar.sh
```

## 2) NotebookLM Sidecar

- Script: `scripts/notebooklm_sidecar_sync.sh`
- Input: research markdown file
- Output: normalized digest under `runtime/nlm/YYYY-MM-DD-<topic>.md`
- Optional remote sync:
  - set `NLM_NOTEBOOK_ID`
  - omit `--dry-run`
  - script writes NotebookLM note via `nlm note create`

Smoke:

```bash
bash scripts/smoke_notebooklm_sidecar.sh
```

## 3) Guardrails

- Main Agents remain `stepfun/step-3.5-flash`.
- Sidecar outputs must be bounded and reviewable.
- NotebookLM writeback is local-first, remote sync optional.
- No direct injection of full sidecar content into live main context.

## 4) Recommended Workflow

1. Run Task OS / soak in normal mode.
2. Run sidecar experiments in isolated worktrees.
3. Persist artifacts under `runtime/meta_harness/` and `runtime/nlm/`.
4. Route only concise digest (`<=500 tokens`) to Lacia heartbeat.
