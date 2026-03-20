#!/usr/bin/env python3
"""Validate Beatless RawCLI contracts.

Checks:
1) ROUTING rules enforce owner_agent/executor_tool schema.
2) TOOL_POOL tools have required fields and valid prompt_mode.
3) No wrapper-agent names appear in owner/executor route fields.
4) Hook script keeps queue/result/events contract strings.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG_DIR = ROOT / "config" / "rawcli"
SCRIPTS_DIR = ROOT / "scripts" / "rawcli"

ROUTING_PATH = CFG_DIR / "ROUTING.yaml"
TOOL_POOL_PATH = CFG_DIR / "TOOL_POOL.yaml"
HOOK_PATH = SCRIPTS_DIR / "dispatch_hook_loop.sh"
INGRESS_PATH = SCRIPTS_DIR / "rawcli_ingress_ack_submit.sh"

ALLOWED_OWNERS = {"lacia", "kouka", "methode", "satonus", "snowdrop"}
WRAPPER_NAME_PATTERNS = {
    "codex-builder",
    "gemini-researcher",
    "claude-generalist",
    "claude-architect",
    "claude-architect-opus",
    "claude-architect-sonnet",
}


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def require(path: pathlib.Path) -> None:
    if not path.exists():
        fail(f"missing file: {path}")


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    require(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"yaml root must be object: {path}")
    return data


def validate_tool_pool(pool: dict[str, Any]) -> set[str]:
    tools = pool.get("tools")
    if not isinstance(tools, dict) or not tools:
        fail("TOOL_POOL.tools must be non-empty mapping")

    required_tools = {"codex_cli", "claude_sonnet_cli", "claude_opus_cli", "gemini_cli"}
    missing = sorted(required_tools - set(tools.keys()))
    if missing:
        fail(f"TOOL_POOL missing required tools: {missing}")

    for tool_id, cfg in tools.items():
        if not isinstance(cfg, dict):
            fail(f"tool config must be mapping: {tool_id}")
        if not cfg.get("command"):
            fail(f"tool missing command: {tool_id}")
        if cfg.get("prompt_mode") not in {"positional", "dash_p"}:
            fail(f"tool has invalid prompt_mode: {tool_id}")
        timeout = cfg.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            fail(f"tool timeout_seconds must be positive int: {tool_id}")

    return set(tools.keys())


def validate_routing(routing: dict[str, Any], tool_ids: set[str]) -> None:
    rules = routing.get("routing_rules")
    if not isinstance(rules, list) or not rules:
        fail("ROUTING.routing_rules must be non-empty list")

    for i, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            fail(f"rule#{i} must be object")

        owner = rule.get("owner_agent")
        executor = rule.get("executor_tool")
        pattern = rule.get("pattern")

        if owner not in ALLOWED_OWNERS:
            fail(f"rule#{i} invalid owner_agent={owner!r}")
        if executor is not None and executor != "" and executor not in tool_ids:
            fail(f"rule#{i} invalid executor_tool={executor!r}")
        if not isinstance(pattern, str) or not pattern:
            fail(f"rule#{i} missing pattern")

        try:
            re.compile(pattern)
        except re.error as err:
            fail(f"rule#{i} invalid regex pattern: {err}")

        owner_l = str(owner).lower()
        exec_l = "" if executor is None else str(executor).lower()
        for wrapper in WRAPPER_NAME_PATTERNS:
            if wrapper in owner_l or wrapper in exec_l:
                fail(f"rule#{i} contains wrapper name in owner/executor: {wrapper}")


def validate_script_contracts() -> None:
    require(HOOK_PATH)
    text = HOOK_PATH.read_text(encoding="utf-8")
    must_have = [
        "dispatch-queue.jsonl",
        "dispatch-results",
        "dispatch-events.jsonl",
        "executor_tool",
    ]
    for token in must_have:
        if token not in text:
            fail(f"dispatch hook contract token missing: {token}")

    require(INGRESS_PATH)
    ingress = INGRESS_PATH.read_text(encoding="utf-8")
    for token in ["route_task.sh", "dispatch_submit.sh", "ACK_RECEIVED"]:
        if token not in ingress:
            fail(f"ingress script contract token missing: {token}")


def main() -> None:
    routing = load_yaml(ROUTING_PATH)
    tool_pool = load_yaml(TOOL_POOL_PATH)
    tool_ids = validate_tool_pool(tool_pool)
    validate_routing(routing, tool_ids)
    validate_script_contracts()

    print("[PASS] rawcli contracts validated")


if __name__ == "__main__":
    main()
