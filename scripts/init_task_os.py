#!/usr/bin/env python3
import json
from pathlib import Path


def ensure_json(path: Path, payload: dict) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = root / "runtime"

    dirs = [
        runtime / "task_contract" / "templates",
        runtime / "jobs",
        runtime / "worktrees",
        runtime / "state",
        runtime / "scheduler",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    ensure_json(runtime / "state" / "queue.json", {"jobs": []})
    ensure_json(
        runtime / "state" / "metrics.json",
        {
            "jobs_total": 0,
            "jobs_done": 0,
            "jobs_blocked": 0,
            "jobs_escalated": 0,
            "updated_at": None,
        },
    )
    ensure_json(
        runtime / "scheduler" / "config.json",
        {
            "poll_interval_seconds": 30,
            "mode": "harness",
            "direct_pass_stages": [
                "planned",
                "implementing",
                "verifying",
                "reviewing",
                "done",
            ],
            "checkpoint_every_transition": True,
        },
    )

    print("task os runtime initialized")


if __name__ == "__main__":
    main()
