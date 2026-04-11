#!/usr/bin/env python3
import json
import sys
from pathlib import Path


REQUIRED_TOP = [
    "id",
    "goal",
    "editable_paths",
    "acceptance",
    "budget",
    "routing",
    "escalation",
]
REQUIRED_ROUTING = ["planner", "builder", "reviewer", "search", "research"]


def fail(msg: str) -> None:
    raise SystemExit(f"task contract invalid: {msg}")


def validate_minimal(contract: dict) -> None:
    for key in REQUIRED_TOP:
        if key not in contract:
            fail(f"missing field '{key}'")

    if not isinstance(contract["id"], str) or len(contract["id"]) < 3:
        fail("id must be string with length >= 3")
    if not isinstance(contract["goal"], str) or len(contract["goal"]) < 10:
        fail("goal must be string with length >= 10")

    editable = contract["editable_paths"]
    if not isinstance(editable, list) or not editable or not all(isinstance(p, str) for p in editable):
        fail("editable_paths must be non-empty string array")

    acceptance = contract["acceptance"]
    if not isinstance(acceptance, dict):
        fail("acceptance must be object")
    must_pass = acceptance.get("must_pass")
    if not isinstance(must_pass, list) or not must_pass or not all(isinstance(x, str) for x in must_pass):
        fail("acceptance.must_pass must be non-empty string array")

    budget = contract["budget"]
    if not isinstance(budget, dict):
        fail("budget must be object")
    if not isinstance(budget.get("max_iterations"), int) or budget["max_iterations"] < 1:
        fail("budget.max_iterations must be integer >= 1")
    if not isinstance(budget.get("max_wall_clock_minutes"), int) or budget["max_wall_clock_minutes"] < 5:
        fail("budget.max_wall_clock_minutes must be integer >= 5")

    routing = contract["routing"]
    if not isinstance(routing, dict):
        fail("routing must be object")
    for key in REQUIRED_ROUTING:
        if not isinstance(routing.get(key), str) or not routing[key].strip():
            fail(f"routing.{key} must be non-empty string")

    escalation = contract["escalation"]
    if not isinstance(escalation, list) or not escalation or not all(isinstance(x, str) for x in escalation):
        fail("escalation must be non-empty string array")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_task_contract.py <contract.json>")

    path = Path(sys.argv[1]).resolve()
    if not path.exists():
        fail(f"file not found: {path}")
    contract = json.loads(path.read_text(encoding="utf-8"))
    validate_minimal(contract)
    print(f"task contract valid: {path}")


if __name__ == "__main__":
    main()
