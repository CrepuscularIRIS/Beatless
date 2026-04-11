#!/usr/bin/env python3
import argparse
import json


def parse_bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def decide_build_mode(
    file_count: int,
    dir_count: int,
    has_test: bool,
    has_iter: bool,
    consecutive_verify_fail: int,
    consecutive_no_diff: int,
) -> str:
    if consecutive_verify_fail >= 2 and has_test:
        return "ralph_loop"
    if consecutive_no_diff >= 3:
        return "agent_teams_debug"
    if file_count > 10 or dir_count >= 3:
        return "agent_teams"
    if has_iter and has_test and file_count <= 10:
        return "ralph_loop"
    return "single_lane"


def main() -> None:
    parser = argparse.ArgumentParser(description="Select build orchestration mode")
    parser.add_argument("--file-count", type=int, required=True)
    parser.add_argument("--dir-count", type=int, required=True)
    parser.add_argument("--has-test", required=True)
    parser.add_argument("--has-iter", required=True)
    parser.add_argument("--consecutive-verify-fail", type=int, default=0)
    parser.add_argument("--consecutive-no-diff", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    has_test = parse_bool(args.has_test)
    has_iter = parse_bool(args.has_iter)

    mode = decide_build_mode(
        file_count=args.file_count,
        dir_count=args.dir_count,
        has_test=has_test,
        has_iter=has_iter,
        consecutive_verify_fail=args.consecutive_verify_fail,
        consecutive_no_diff=args.consecutive_no_diff,
    )

    result = {
        "mode": mode,
        "inputs": {
            "file_count": args.file_count,
            "dir_count": args.dir_count,
            "has_test": has_test,
            "has_iter": has_iter,
            "consecutive_verify_fail": args.consecutive_verify_fail,
            "consecutive_no_diff": args.consecutive_no_diff,
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"build_mode={mode}")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
