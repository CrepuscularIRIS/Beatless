"""Research Cycle — Hermes cron driver for the new 6-stage research pipeline.

Replaces ~/.hermes/scripts/deprecated/auto-research.py (deprecated → /exp-run)
and ~/.hermes/scripts/deprecated/research-host-cron.py (deprecated → /research-host).

Drives the new pipeline:
  init → survey → axiom → propose → dispatch → loop → review

Stage detection: reads ledgers/<tag>/TODO.md to find the next [ ] entry, or
detects the loop phase (dispatch ↔ loop ↔ review repeating per cycle) once
the linear preamble (init→survey→axiom→propose) is done.

Halt conditions (in priority order):
  1. Human halt flag at ~/.hermes/shared/.research-halt
  2. SOTA reached (results.tsv has keep row meeting target_value per sprint.yaml)
  3. Budget exhausted (cycle count >= budget_cycles)
  4. No active sprint (no ledgers/*/sprint.yaml)
  5. Last claude -p invocation reported BLOCK

Each tick fires ONE stage. Cron runs this every 60-120m so each tick is bounded.
For long /research-loop runs (which include 5min training), the script gives
claude -p up to CLAUDE_TIMEOUT (90 min default).

Schedule recommendation: every 90m (gives loop time to complete + reviewer time).

Stdin discipline: claude -p invoked with stdin=DEVNULL (codex/gemini sub-calls
inside Claude inherit this — see codex-academic / gemini-academic SKILL.md).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path

RGMARE_ROOT = Path(os.environ.get("RGMARE_ROOT", os.path.expanduser("~/research/rgmare-lite")))
LEDGERS_ROOT = RGMARE_ROOT / "ledgers"
HALT_FLAG = Path(os.path.expanduser("~/.hermes/shared/.research-halt"))
STATUS_FILE = Path(os.path.expanduser("~/.hermes/shared/.last-research-cycle-status"))
LOG_PATH = Path(os.path.expanduser("~/.hermes/shared/research-cycle-log.jsonl"))

CLAUDE_TIMEOUT = int(os.environ.get("RESEARCH_CYCLE_TIMEOUT", 5400))  # 90min

STAGE_REGEX = re.compile(
    r"^\s*-\s*\[\s*(?P<done>[xX ])\s*\]\s*Stage\s*(?P<num>\d+)"
    r"(?:\s*cycle\s*(?P<cycle>\d+))?\s*:\s*/(?P<cmd>research-\w+)"
)


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return {}


def find_active_sprint() -> Path | None:
    """Latest sprint by sprint.yaml mtime."""
    if not LEDGERS_ROOT.exists():
        return None
    sprints = sorted(
        LEDGERS_ROOT.glob("*/sprint.yaml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return sprints[0].parent if sprints else None


def parse_todo(sprint_dir: Path) -> tuple[list[str], list[str]]:
    """Return (completed_stages, pending_stages) from TODO.md."""
    todo = sprint_dir / "TODO.md"
    if not todo.exists():
        return [], []
    completed, pending = [], []
    for line in todo.read_text().splitlines():
        m = STAGE_REGEX.match(line)
        if not m:
            continue
        cmd = m.group("cmd")
        if m.group("done").lower() == "x":
            completed.append(cmd)
        else:
            pending.append(cmd)
    return completed, pending


def detect_next_stage(sprint_dir: Path) -> tuple[str, str]:
    """Return (next_command, args_or_empty). Raises if undecidable."""
    completed, pending = parse_todo(sprint_dir)

    if pending:
        return (pending[0], "")

    # All baseline stages done — enter loop phase: dispatch → loop → review
    # repeats. Detect the next loop phase by inspecting dispatch/cycle-N/ and
    # reviews/cycle-N.md presence.
    dispatch_dirs = sorted((sprint_dir / "dispatch").glob("cycle-*"))
    review_files = sorted((sprint_dir / "reviews").glob("cycle-*.md"))

    if not dispatch_dirs:
        return ("research-dispatch", "")  # never dispatched — start cycle 1

    last_cycle_n = max(int(d.name.split("-")[1]) for d in dispatch_dirs)
    last_review = sprint_dir / "reviews" / f"cycle-{last_cycle_n}.md"
    last_dispatch = sprint_dir / "dispatch" / f"cycle-{last_cycle_n}"
    last_loop_marker = (last_dispatch / "loop_done.flag")

    if not last_loop_marker.exists():
        # Need to run /research-loop on the latest dispatch
        ranked = last_dispatch / "ranked.jsonl"
        if not ranked.exists() or not ranked.read_text().strip():
            return ("research-dispatch", "")  # dispatch failed; redo
        first_line = ranked.read_text().splitlines()[0]
        try:
            proposal = json.loads(first_line)
            idea = proposal.get("proposal_summary", "continue cycle").replace('"', '\\"')
            return ("research-loop", f'"{idea}"')
        except json.JSONDecodeError:
            return ("research-dispatch", "")  # bad ranked.jsonl; redo
    elif not last_review.exists():
        return ("research-review", f"--cycle {last_cycle_n}")
    else:
        # Cycle complete — start next dispatch
        return ("research-dispatch", "")


def check_halt_flag() -> bool:
    return HALT_FLAG.exists()


def check_sota(sprint_dir: Path) -> bool:
    """results.tsv has any keep row meeting target_value per sprint.yaml."""
    sprint_yaml = read_yaml(sprint_dir / "sprint.yaml")
    target = sprint_yaml.get("target_value")
    metric = sprint_yaml.get("target_metric", "")

    if target is None:
        return False
    try:
        target_f = float(target)
    except (TypeError, ValueError):
        return False

    results_tsv = sprint_dir / "results.tsv"
    if not results_tsv.exists():
        return False

    # Lower-is-better metrics
    LOWER_BETTER = {"val_bpb", "loss", "fid", "perplexity", "ppl", "error_rate"}
    is_lower_better = any(
        metric.lower().endswith(s) or metric.lower() == s
        for s in LOWER_BETTER
    )

    for line in results_tsv.read_text().splitlines()[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) < 4 or parts[3] != "keep":
            continue
        try:
            v = float(parts[1])
        except ValueError:
            continue
        if (is_lower_better and v <= target_f) or (not is_lower_better and v >= target_f):
            return True
    return False


def check_budget(sprint_dir: Path) -> bool:
    """Cycle count >= budget_cycles."""
    sprint_yaml = read_yaml(sprint_dir / "sprint.yaml")
    budget = int(sprint_yaml.get("budget_cycles", 50))
    dispatch_dirs = list((sprint_dir / "dispatch").glob("cycle-*"))
    return len(dispatch_dirs) >= budget


def check_last_block() -> bool:
    """Latest review verdict was BLOCK and not yet resolved."""
    if not LOG_PATH.exists():
        return False
    lines = LOG_PATH.read_text().strip().splitlines()
    if not lines:
        return False
    try:
        last = json.loads(lines[-1])
        return last.get("stage") == "research-review" and last.get("verdict") == "BLOCK"
    except (json.JSONDecodeError, KeyError):
        return False


def invoke_claude(command_with_args: str, working_dir: Path) -> tuple[int, str, str]:
    """Run claude -p in non-interactive mode with stdin closed."""
    cmd = [
        "claude", "-p",
        "--model", "claude-sonnet-4-6",
        "--dangerously-skip-permissions",
        command_with_args,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(working_dir),
            capture_output=True, text=True,
            timeout=CLAUDE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {CLAUDE_TIMEOUT}s"
    except FileNotFoundError:
        return -2, "", "claude CLI not found in PATH"


def append_log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_status(payload: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    STATUS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="detect next stage and report; do not invoke claude -p")
    args = ap.parse_args()

    print(f"Research Cycle — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Halt check
    if check_halt_flag():
        msg = f"HALT flag present at {HALT_FLAG} — skipping"
        print(msg)
        write_status({"status": "halted_by_flag", "halt_flag": str(HALT_FLAG)})
        print(json.dumps({"wakeAgent": False}))
        return 0

    # Active sprint
    sprint_dir = find_active_sprint()
    if not sprint_dir:
        print(f"No active sprint in {LEDGERS_ROOT} — nothing to do")
        write_status({"status": "no_sprint", "ledgers_root": str(LEDGERS_ROOT)})
        print(json.dumps({"wakeAgent": False}))
        return 0

    sprint_tag = sprint_dir.name
    print(f"Active sprint: {sprint_tag} at {sprint_dir}")

    # SOTA check
    if check_sota(sprint_dir):
        print(f"SOTA reached for sprint {sprint_tag} — halting")
        write_status({"status": "sota_reached", "sprint": sprint_tag})
        print(json.dumps({"wakeAgent": False}))
        return 0

    # Budget check
    if check_budget(sprint_dir):
        print(f"Budget exhausted for sprint {sprint_tag} — halting")
        write_status({"status": "budget_exhausted", "sprint": sprint_tag})
        print(json.dumps({"wakeAgent": False}))
        return 0

    # Unrecoverable BLOCK from last review
    if check_last_block():
        print(f"Last review BLOCK not yet resolved — halting; user must review")
        write_status({"status": "blocked_by_review", "sprint": sprint_tag})
        print(json.dumps({"wakeAgent": False}))
        return 0

    # Detect next stage
    try:
        next_cmd, args_str = detect_next_stage(sprint_dir)
    except Exception as e:
        print(f"ERROR detecting next stage: {e}")
        write_status({"status": "stage_detection_error", "error": str(e)[:300]})
        print(json.dumps({"wakeAgent": False}))
        return 1

    full_cmd = f"/{next_cmd}{(' ' + args_str) if args_str else ''}"
    print(f"Next stage: {full_cmd}")

    if args.dry_run:
        write_status({"status": "dry_run", "sprint": sprint_tag, "next_stage": full_cmd})
        print(json.dumps({"wakeAgent": False, "dry_run": True}))
        return 0

    # Invoke claude -p
    rc, stdout, stderr = invoke_claude(full_cmd, RGMARE_ROOT)
    print(f"Stage {next_cmd} → exit {rc}")

    # Try to extract verdict from review output
    verdict = None
    if next_cmd == "research-review":
        # Check the latest review file
        latest_review = sorted((sprint_dir / "reviews").glob("cycle-*.md"))
        if latest_review:
            text = latest_review[-1].read_text()
            m = re.search(r"Final verdict:\s*(PASS|FLAG|BLOCK)", text)
            if m:
                verdict = m.group(1)

    record = {
        "sprint": sprint_tag,
        "stage": next_cmd,
        "args": args_str,
        "exit_code": rc,
        "verdict": verdict,
        "stdout_tail": (stdout or "")[-1500:],
        "stderr_tail": (stderr or "")[-500:],
    }
    append_log(record)

    write_status({
        "status": "ok" if rc == 0 else "error",
        "sprint": sprint_tag,
        "stage_invoked": next_cmd,
        "exit_code": rc,
        "verdict": verdict,
    })

    # Hermes contract: tell the orchestrator whether to wake an agent for summary
    print(json.dumps({"wakeAgent": rc == 0, "stage": next_cmd, "verdict": verdict}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
