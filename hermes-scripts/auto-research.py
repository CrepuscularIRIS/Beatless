"""Auto Research — wake-gate + ClaudeCode execution.

Scans ~/research for experiment workspaces (detected by program.md or Task.md)
that have in-progress state (progress.md with unfinished rounds, OR new
outputs/ since last visit).

When work is detected, runs ClaudeCode with /exp-run resume — the current
autonomous experiment loop (combined rewrite of the deprecated /autoresearch
+ /research-analyze pair). /exp-run auto-detects quick vs full mode from the
workspace and continues from the last round.

Working directory: ~/research/<workspace>
"""
import json
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone

from beatless_config import CONFIG

MARKER = str(CONFIG.shared_file(".last-research-analysis"))
STATUS_FILE = str(CONFIG.shared_file(".last-auto-research-status"))
RESEARCH_DIR = str(CONFIG.research_dir)


def find_workspaces(research_dir=RESEARCH_DIR):
    """Find experiment workspaces under ~/research.

    A workspace is a directory containing Task.md or program.md (the
    two spec files /exp-init writes). We return workspaces that either:
      (a) have new outputs/ entries since the last marker, or
      (b) have progress.md indicating unfinished work.
    """
    research = Path(research_dir)
    if not research.exists():
        return []

    candidates = []
    for spec in list(research.glob("**/Task.md")) + list(research.glob("**/program.md")):
        ws = spec.parent
        if ws in candidates:
            continue
        candidates.append(ws)

    if not candidates:
        return []

    marker_time = os.path.getmtime(MARKER) if os.path.exists(MARKER) else 0.0

    actionable = []
    for ws in candidates:
        reason = None

        # (a) new outputs since last visit
        outputs = list(ws.glob("outputs/*/")) + list(ws.glob("runs/*/"))
        newer_outputs = [o for o in outputs if os.path.getmtime(o) > marker_time]
        if newer_outputs:
            reason = f"new-outputs={len(newer_outputs)}"

        # (b) progress.md with unfinished rounds
        progress = ws / "progress.md"
        if progress.exists() and progress.stat().st_mtime > marker_time:
            reason = reason or "progress-updated"

        # (c) user just ran /exp-init and wants the loop started. Once
        # progress.md exists, a successful run should not bootstrap forever.
        if not reason and (ws / "findings.md").exists() and not progress.exists() and not outputs:
            reason = "bootstrap"

        if reason:
            actionable.append((str(ws), reason))

    return actionable


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="detect actionable research workspaces without invoking Claude",
    )
    parser.add_argument(
        "--research-dir",
        default=RESEARCH_DIR,
        help=f"research root to scan (default: {RESEARCH_DIR})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=7200,
        help="maximum seconds to wait for the Claude execution path (default: 7200)",
    )
    return parser.parse_args()


def write_status(payload):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)

    workspaces = find_workspaces(args.research_dir)
    if not workspaces:
        write_status({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "research_dir": args.research_dir,
            "actionable_count": 0,
            "note": "no research workspaces with unfinished work",
        })
        print(json.dumps({"wakeAgent": False}))
        return

    # One run per wake-gate tick — pick the most-recently-touched workspace
    workspaces.sort(
        key=lambda wr: os.path.getmtime(wr[0]),
        reverse=True,
    )
    cwd, reason = workspaces[0]

    if args.dry_run:
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "research_dir": args.research_dir,
            "actionable_count": len(workspaces),
            "selected_workspace": cwd,
            "selected_trigger": reason,
            "workspaces": [
                {"workspace": workspace, "trigger": trigger}
                for workspace, trigger in workspaces
            ],
            "note": "dry-run only; Claude was not invoked",
        }
        write_status(status)
        print(json.dumps({
            "wakeAgent": False,
            "dryRun": True,
            "actionableCount": len(workspaces),
            "selectedWorkspace": cwd,
            "selectedTrigger": reason,
        }, ensure_ascii=False))
        return

    prompt = (
        f"/exp-run resume\n\n"
        f"Wake-gate selected workspace: {cwd}\n"
        f"Trigger reason: {reason}\n\n"
        f"Per /exp-run spec:\n"
        f"- Auto-detect mode (Task.md = full dual-GPU, program.md = quick single-GPU).\n"
        f"- If progress.md records higher rounds, never restart from round 1.\n"
        f"- Run until halt condition; do NOT ask 'should I continue?'\n"
        f"- All state on disk (progress.md, findings.md, results.tsv).\n"
        f"- Use Agent subagent_type codex-cli for implementation, gemini-cli for literature checks.\n"
    )

    try:
        result = subprocess.run(
            [CONFIG.claude_bin, "-p", "--model", CONFIG.claude_model,
             "--dangerously-skip-permissions",
             prompt],
            capture_output=True, text=True,
            timeout=args.timeout_seconds,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        write_status({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workspace": cwd,
            "trigger": reason,
            "timeout_seconds": args.timeout_seconds,
            "returncode": "timeout",
            "stderr_tail": ((exc.stderr or "") if isinstance(exc.stderr, str) else "")[-400:],
        })
        print(f"ClaudeCode timed out after {args.timeout_seconds}s")
        return 124

    if result.returncode == 0:
        open(MARKER, "w").close()

    write_status({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": cwd,
        "trigger": reason,
        "timeout_seconds": args.timeout_seconds,
        "returncode": result.returncode,
        "stderr_tail": (result.stderr or "")[-400:],
    })

    output = result.stdout.strip()
    if output:
        print(output[-4000:] if len(output) > 4000 else output)
    else:
        print(f"ClaudeCode exited {result.returncode}: {(result.stderr or '')[:500]}")


if __name__ == "__main__":
    main()
