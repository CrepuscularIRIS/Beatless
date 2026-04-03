#!/usr/bin/env python3
import json
from pathlib import Path

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

print("baseline validation passed")
