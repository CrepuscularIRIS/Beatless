#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
expected_agents = ["lacia", "methode", "kouka", "snowdrop", "satonus"]
required_files = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "HEARTBEAT.md", "BOOTSTRAP.md"]

for agent in expected_agents:
    base = root / "agents" / agent
    if not base.exists():
        raise SystemExit(f"missing agent dir: {base}")
    for name in required_files:
        p = base / name
        if not p.exists() or p.stat().st_size == 0:
            raise SystemExit(f"missing/empty contract: {p}")

cfg = json.loads((root / "config" / "openclaw.redacted.json").read_text())
agent_ids = [a.get("id") for a in cfg.get("agents", {}).get("list", [])]
if set(expected_agents) - set(agent_ids):
    raise SystemExit(f"agent ids mismatch: {agent_ids}")

cron = json.loads((root / "config" / "cron.jobs.snapshot.json").read_text())
if "jobs" not in cron:
    raise SystemExit("cron snapshot missing jobs")

runtime_required = [
    root / "runtime" / "state" / "queue.json",
    root / "runtime" / "state" / "metrics.json",
    root / "runtime" / "scheduler" / "config.json",
    root / "schemas" / "task_contract.schema.json",
    root / "schemas" / "task_contract.example.json",
    root / "schemas" / "trigger_rule.schema.json",
    root / "config" / "claudecode_plugin_trigger_matrix.v2.yaml",
    root / "scripts" / "resolve_trigger.py",
    root / "scripts" / "build_mode_selector.py",
    root / "scripts" / "parse_codex_result.py",
    root / "scripts" / "verify_gates.sh",
    root / "scripts" / "meta_harness_sidecar_run.sh",
    root / "scripts" / "smoke_meta_harness_sidecar.sh",
    root / "scripts" / "notebooklm_sidecar_sync.sh",
    root / "scripts" / "smoke_notebooklm_sidecar.sh",
    root / "docs" / "V3_SIDECAR_INTEGRATION.md",
]
for p in runtime_required:
    if not p.exists() or p.stat().st_size == 0:
        raise SystemExit(f"missing/empty task-os file: {p}")

json.loads((root / "runtime" / "state" / "queue.json").read_text())
json.loads((root / "runtime" / "state" / "metrics.json").read_text())
json.loads((root / "runtime" / "scheduler" / "config.json").read_text())
json.loads((root / "schemas" / "task_contract.schema.json").read_text())
json.loads((root / "schemas" / "task_contract.example.json").read_text())
json.loads((root / "schemas" / "trigger_rule.schema.json").read_text())

trigger_cfg = yaml.safe_load((root / "config" / "claudecode_plugin_trigger_matrix.v2.yaml").read_text())
if not isinstance(trigger_cfg, dict) or "trigger_rules_v21" not in trigger_cfg:
    raise SystemExit("trigger matrix missing trigger_rules_v21")

model_baseline = (root / "docs" / "MODEL_BASELINE.md").read_text(encoding="utf-8")
if "（V3）" not in model_baseline:
    raise SystemExit("model baseline is not V3")

print("baseline validation passed")
