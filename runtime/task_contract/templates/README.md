# Task Contract Templates

Use `schemas/task_contract.example.json` as the baseline template.

Minimal workflow:
1. copy example contract
2. set `id`, `goal`, `editable_paths`, `acceptance`
3. validate via `python3 scripts/validate_task_contract.py <contract>`
4. place as `runtime/jobs/<job_id>/contract.json`
