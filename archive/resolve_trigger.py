#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve v2.1 trigger routes")
    parser.add_argument("--prompt", required=True, help="Prompt text to match")
    parser.add_argument("--contract", required=True, help="Path to task contract JSON")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "claudecode_plugin_trigger_matrix.v2.yaml"),
        help="Path to trigger matrix YAML",
    )
    parser.add_argument(
        "--stage",
        default="implement",
        choices=["plan", "implement", "verify", "review", "publish"],
        help="Current scheduler stage",
    )
    parser.add_argument(
        "--has-prior-codex-session",
        choices=["auto", "true", "false"],
        default="auto",
        help="Override prior codex session signal",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_yaml(path: str) -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def count_dirs(paths: List[str]) -> int:
    roots = set()
    for p in paths:
        pp = p.strip("/")
        roots.add(pp.split("/")[0] if pp else pp)
    return len([x for x in roots if x != ""])


def has_open_word(goal: str) -> bool:
    flags = ["探索", "调研", "比较方案", "brainstorm", "方案比较"]
    return any(k in goal for k in flags)


def parse_comp(expr: str, actual: int) -> bool:
    m = re.match(r"^(<=|>=|<|>|==)\s*(\d+)$", str(expr).strip())
    if not m:
        return False
    op, num = m.group(1), int(m.group(2))
    if op == "<=":
        return actual <= num
    if op == ">=":
        return actual >= num
    if op == "<":
        return actual < num
    if op == ">":
        return actual > num
    return actual == num


def infer_prior_codex(flag: str) -> bool:
    if flag == "true":
        return True
    if flag == "false":
        return False
    # auto mode: check if codex plugin cache exists as minimal signal
    return (Path.home() / ".claude" / "plugins" / "cache" / "openai-codex").exists()


def meets_requires(rule: Dict[str, Any], contract: Dict[str, Any], prior_codex: bool) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    req = rule.get("requires", {}) or {}

    editable = contract.get("editable_paths", []) or []
    file_count = len(editable)
    dir_count = count_dirs(editable)
    must_pass = (contract.get("acceptance", {}) or {}).get("must_pass", []) or []
    goal = str(contract.get("goal", ""))

    for key, val in req.items():
        if key == "file_count":
            if not parse_comp(str(val), file_count):
                reasons.append(f"require file_count {val}, actual={file_count}")
        elif key == "has_testable_criteria":
            actual = len(must_pass) > 0
            if bool(val) != actual:
                reasons.append(f"require has_testable_criteria {val}, actual={actual}")
        elif key == "decomposable":
            actual = dir_count >= 3
            if bool(val) != actual:
                reasons.append(f"require decomposable {val}, actual={actual}")
        elif key == "has_prior_codex_session":
            if bool(val) != prior_codex:
                reasons.append(f"require has_prior_codex_session {val}, actual={prior_codex}")
        else:
            reasons.append(f"unknown require key={key}")

    banned_by_goal = rule.get("id") == "build_iterative_loop" and has_open_word(goal)
    if banned_by_goal:
        reasons.append("goal contains open exploration keyword")

    return (len(reasons) == 0), reasons


def text_matches(rule: Dict[str, Any], prompt: str) -> bool:
    match = rule.get("match", {}) or {}
    any_of = match.get("any_of", []) or []
    none_of = match.get("none_of", []) or []
    if not any(k in prompt for k in any_of):
        return False
    if any(k in prompt for k in none_of):
        return False
    return True


def stage_allows(group: str, stage: str) -> bool:
    # Implement stage should not run review_mode triggers.
    if stage == "implement" and group == "review_mode":
        return False
    if stage in {"review", "verify"} and group in {"build_mode", "planning_mode"}:
        return False
    if stage == "plan" and group not in {"planning_mode", "research_mode"}:
        return False
    return True


def choose_winner(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    # higher score wins; tie -> more requires; tie -> id alphabetical
    rules_sorted = sorted(
        rules,
        key=lambda r: (-int(r.get("score", 0)), -len((r.get("requires", {}) or {})), str(r.get("id", ""))),
    )
    return rules_sorted[0]


def resolve(prompt: str, contract: Dict[str, Any], config: Dict[str, Any], stage: str, prior_codex: bool) -> Dict[str, Any]:
    rules = config.get("trigger_rules_v21", []) or []
    default_route = (config.get("conflict_resolution", {}) or {}).get("default_route", {}) or {}

    candidates: List[Dict[str, Any]] = []
    rejections: List[Dict[str, Any]] = []

    for rule in rules:
        if not stage_allows(str(rule.get("exclusive_group", "")), stage):
            rejections.append({"id": rule.get("id"), "reason": "stage filtered"})
            continue
        if not text_matches(rule, prompt):
            rejections.append({"id": rule.get("id"), "reason": "text mismatch"})
            continue
        ok, reasons = meets_requires(rule, contract, prior_codex)
        if not ok:
            rejections.append({"id": rule.get("id"), "reason": "; ".join(reasons)})
            continue
        candidates.append(rule)

    if not candidates:
        return {
            "selected": [
                {
                    "id": default_route.get("id", "build_simple"),
                    "mode": default_route.get("mode", "single_lane"),
                    "group": "build_mode",
                }
            ],
            "fallback_default": True,
            "rejections": rejections,
        }

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        groups.setdefault(str(c.get("exclusive_group", "ungrouped")), []).append(c)

    selected = []
    for group, rules_in_group in groups.items():
        winner = choose_winner(rules_in_group)
        selected.append(
            {
                "id": winner.get("id"),
                "mode": winner.get("mode"),
                "group": group,
                "score": winner.get("score", 0),
                "route": winner.get("route", {}),
            }
        )

    selected = sorted(selected, key=lambda x: (x["group"], -int(x.get("score", 0)), x.get("id", "")))
    return {"selected": selected, "fallback_default": False, "rejections": rejections}


def main() -> None:
    args = parse_args()
    contract = load_json(args.contract)
    config = load_yaml(args.config)
    prior_codex = infer_prior_codex(args.has_prior_codex_session)

    result = resolve(args.prompt, contract, config, args.stage, prior_codex)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    modes = [x.get("mode", "") for x in result.get("selected", [])]
    primary = modes[0] if modes else "single_lane"
    print(f"primary_mode={primary}")
    print("selected_rules=" + ",".join(x.get("id", "") for x in result.get("selected", [])))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
