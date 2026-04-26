"""Data collectors for Beatless dashboard.

Each collector reads local state files / CLI output and returns plain dicts.
No display logic here — the API layer decides what to expose.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BEATLESS_ROOT = Path(__file__).resolve().parent.parent.parent
HOME = Path.home()
HERMES_SHARED = HOME / ".hermes" / "shared"
WORKSPACE = HOME / "workspace"
RESEARCH_DIR = HOME / "research"

AGENTS = [
    {"id": "lacia", "name": "Lacia", "role": "strategy", "model": "Kimi K2.6", "color": "#facc15"},
    {"id": "methode", "name": "Methode", "role": "execute", "model": "Step 3.5 Flash", "color": "#22d3ee"},
    {"id": "satonus", "name": "Satonus", "role": "review", "model": "Claude Code", "color": "#f87171"},
    {"id": "snowdrop", "name": "Snowdrop", "role": "research", "model": "Claude Code", "color": "#c084fc"},
    {"id": "kouka", "name": "Kouka", "role": "deliver", "model": "MiniMax M2.7", "color": "#fbbf24"},
    {"id": "aoi", "name": "Aoi", "role": "dispatch", "model": "Control Plane", "color": "#60a5fa"},
]

PIPELINES = [
    {
        "id": "pr-followup",
        "name": "GH Response",
        "interval": "1h",
        "agent": "methode",
        "state_file": str(BEATLESS_ROOT / "pipelines" / "pr-followup" / "state.json"),
        "status_file": None,
    },
    {
        "id": "github-pr",
        "name": "GH PR Pipeline",
        "interval": "2.5h",
        "agent": "satonus",
        "state_file": None,
        "status_file": str(HERMES_SHARED / ".last-github-pr"),
    },
    {
        "id": "auto-research",
        "name": "Auto Research",
        "interval": "4h",
        "agent": "snowdrop",
        "state_file": None,
        "status_file": str(HERMES_SHARED / ".last-auto-research-status"),
    },
    {
        "id": "blog-maintenance",
        "name": "Blog Maintenance",
        "interval": "12h",
        "agent": "kouka",
        "state_file": None,
        "status_file": None,
    },
]


def _read_json(path: str | Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def collect_agents() -> list[dict]:
    """Return agent list with live status inferred from tmux / process state."""
    tmux_raw = _run(["tmux", "list-sessions", "-F", "#{session_name}"])
    active_sessions = set(tmux_raw.splitlines()) if tmux_raw else set()

    result = []
    for agent in AGENTS:
        status = "idle"
        current_task = None

        for sess in active_sessions:
            if agent["id"] in sess.lower():
                status = "active"
                current_task = sess
                break

        result.append({
            **agent,
            "status": status,
            "currentTask": current_task,
        })
    return result


def collect_pipelines() -> list[dict]:
    """Return pipeline status from state files."""
    result = []
    for pipe in PIPELINES:
        data: dict[str, Any] = {
            "id": pipe["id"],
            "name": pipe["name"],
            "interval": pipe["interval"],
            "agent": pipe["agent"],
            "status": "unknown",
            "lastRun": None,
            "lastResult": None,
        }

        if pipe["state_file"]:
            state = _read_json(pipe["state_file"])
            if state:
                data["status"] = state.get("status", "unknown").lower()
                data["lastRun"] = state.get("last_run")
                data["lastResult"] = state.get("description") or state.get("last_verdict")

        if pipe["status_file"]:
            status = _read_json(pipe["status_file"])
            if status:
                data["status"] = status.get("status", "unknown").lower()
                data["lastRun"] = status.get("timestamp")
                data["lastResult"] = status.get("detail", "")[:120]

        result.append(data)
    return result


def collect_recent_activity(limit: int = 20) -> list[dict]:
    """Gather recent activity from git log + status files."""
    events: list[dict] = []

    git_log = _run([
        "git", "-C", str(BEATLESS_ROOT),
        "log", "--oneline", "--format=%H|%aI|%s", f"-{limit}",
    ])
    for line in git_log.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            events.append({
                "type": "commit",
                "timestamp": parts[1],
                "message": parts[2],
                "sha": parts[0][:8],
            })

    for pipe in PIPELINES:
        for path_key in ("state_file", "status_file"):
            path = pipe.get(path_key)
            if not path:
                continue
            data = _read_json(path)
            if not data:
                continue
            ts = data.get("timestamp") or data.get("last_run")
            if not ts:
                continue
            status = data.get("status", "")
            detail = data.get("detail", "")[:100]
            events.append({
                "type": "pipeline",
                "timestamp": ts,
                "pipeline": pipe["name"],
                "status": status,
                "detail": detail,
            })

    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events[:limit]


def collect_experiments() -> list[dict]:
    """Scan ~/research for experiment workspaces."""
    experiments = []
    if not RESEARCH_DIR.exists():
        return experiments

    for spec in list(RESEARCH_DIR.glob("**/Task.md")) + list(RESEARCH_DIR.glob("**/program.md")):
        ws = spec.parent
        progress_file = ws / "progress.md"
        results_file = ws / "results.tsv"

        exp: dict[str, Any] = {
            "name": ws.name,
            "path": str(ws.relative_to(RESEARCH_DIR)),
            "mode": "full" if spec.name == "Task.md" else "quick",
            "status": "idle",
            "currentRound": None,
            "bestMetric": None,
        }

        if progress_file.exists():
            try:
                text = progress_file.read_text()
                rounds = re.findall(r"[Rr]ound\s+(\d+)", text)
                if rounds:
                    exp["currentRound"] = max(int(r) for r in rounds)
                if "running" in text.lower() or "in progress" in text.lower():
                    exp["status"] = "running"
                elif "halt" in text.lower() or "stopped" in text.lower():
                    exp["status"] = "halted"
                else:
                    exp["status"] = "paused"
            except OSError:
                pass

        if results_file.exists():
            try:
                lines = results_file.read_text().strip().splitlines()
                if len(lines) > 1:
                    last_line = lines[-1].split("\t")
                    if len(last_line) >= 2:
                        try:
                            exp["bestMetric"] = float(last_line[1])
                        except ValueError:
                            pass
            except OSError:
                pass

        experiments.append(exp)

    return experiments


def collect_system_stats() -> dict:
    """Basic system health."""
    hermes_running = False
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "hermes-gateway"],
            capture_output=True, text=True, timeout=5,
        )
        hermes_running = r.stdout.strip() == "active"
    except (OSError, subprocess.TimeoutExpired):
        pass

    gpu_info = None
    nvidia = _run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"])
    if nvidia:
        parts = [p.strip() for p in nvidia.split(",")]
        if len(parts) >= 4:
            gpu_info = {
                "name": parts[0],
                "utilization": int(parts[1]),
                "memoryUsed": int(parts[2]),
                "memoryTotal": int(parts[3]),
            }

    return {
        "hermesGateway": hermes_running,
        "gpu": gpu_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_all() -> dict:
    """Single call to gather everything."""
    return {
        "agents": collect_agents(),
        "pipelines": collect_pipelines(),
        "activity": collect_recent_activity(),
        "experiments": collect_experiments(),
        "system": collect_system_stats(),
        "collectedAt": datetime.now(timezone.utc).isoformat(),
    }
