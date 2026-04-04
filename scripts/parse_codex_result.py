#!/usr/bin/env python3
import json
import re
import sys


def parse_codex_result(text: str) -> dict:
    lower = text.lower()

    negation_patterns = [
        r"no\s+blocking\s+(issues|findings)",
        r"without\s+blocking\s+(issues|findings)",
    ]

    blocking_patterns = [
        r"severity:\s*blocking",
        r"critical\s+(issue|finding|bug)",
        r"must\s+fix\s+before",
    ]

    has_negation = any(re.search(p, lower) for p in negation_patterns)

    hits = 0
    for p in blocking_patterns:
        if re.search(p, lower):
            hits += 1

    if has_negation and hits == 0:
        hits = 0

    verdict = "PASS" if hits == 0 else "FAIL"
    return {
        "blocking_count": hits,
        "verdict": verdict,
        "raw_length": len(text),
    }


def main() -> None:
    text = sys.stdin.read()
    result = parse_codex_result(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
