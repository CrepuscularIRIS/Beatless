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
from pathlib import Path
from datetime import datetime, timezone

MARKER = os.path.expanduser("~/.hermes/shared/.last-research-analysis")
STATUS_FILE = os.path.expanduser("~/.hermes/shared/.last-auto-research-status")
RESEARCH_DIR = os.path.expanduser("~/research")


def find_workspaces():
    """Find experiment workspaces under ~/research.

    A workspace is a directory containing Task.md or program.md (the
    two spec files /exp-init writes). We return workspaces that either:
      (a) have new outputs/ entries since the last marker, or
      (b) have progress.md indicating unfinished work.
    """
    research = Path(RESEARCH_DIR)
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

        # (c) user just ran /exp-init and wants the loop started
        if not reason and (ws / "findings.md").exists() and not outputs:
            reason = "bootstrap"

        if reason:
            actionable.append((str(ws), reason))

    return actionable


def write_status(payload):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def main():
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)

    workspaces = find_workspaces()
    if not workspaces:
        write_status({
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    prompt = (
        f"/exp-run resume\n\n"
        f"Wake-gate selected workspace: {cwd}\n"
        f"Trigger reason: {reason}\n\n"
        f"Per /exp-run spec:\n"
        f"- Auto-detect mode (Task.md = full dual-GPU, program.md = quick single-GPU).\n"
        f"- If progress.md records higher rounds, never restart from round 1.\n"
        f"- Run until halt condition; do NOT ask 'should I continue?'\n"
        f"- All state on disk (progress.md, findings.md, results.tsv).\n"
        f"- Use codex:codex-rescue for implementation, gemini:gemini-consult for literature checks.\n"
    )

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet",
         "--dangerously-skip-permissions",
         prompt],
        capture_output=True, text=True,
        timeout=7200,
        cwd=cwd,
    )

    if result.returncode == 0:
        open(MARKER, "w").close()

    write_status({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": cwd,
        "trigger": reason,
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
