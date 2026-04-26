"""Research Host — Hermes cron driver for /research-host autonomous pipeline.

Per user directive 2026-04-26: ClaudeCode should be triggered proactively on a
schedule, not require the user to sit in a chat window. Hermes is the second
brain that hands the right prompt to ClaudeCode.

Pipeline (mirrors daily-evolution.py pattern):

  Phase 1 — Python: detect active research workspace + plugin readiness.
            Build a state file with:
              - workspace path + git status
              - sprint.yaml summary
              - last 10 ledger rows
              - last decision_trace events per niche
              - plugin status (codex, gemini, gsd, planning-with-files)
              - halt-condition pre-check
  Phase 2 — Invoke `claude -p --model sonnet "/research-host <state-file>"`.
            ClaudeCode runs the autonomous loop; Sonnet 4.6 is the orchestrator
            (per Regulations.md), peer Tasks for niche dispatch, Codex/Gemini for
            convergence/divergence, Sonnet-fresh for red-team. Stdin closed.
  Phase 3 — Capture stdout, write status JSON, optionally git commit ledger
            artifacts (NOT the train.py — that's the researcher's branch).

Schedule recommendation: every 360m (6h). Long enough for one or two cycles per
fire, short enough that a missed cycle isn't catastrophic. Adjust per workspace
in sprint.yaml `cron_minutes`.

Stdin discipline: claude -p is invoked with stdin closed (subprocess.run already
defaults to stdin=PIPE without sending data; we explicitly pass `stdin=DEVNULL`
to be safe — Codex/Gemini sub-invocations made BY Claude are inside that
process, so the discipline propagates).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESEARCH_ROOT = Path(os.path.expanduser("~/research"))
STATE_DIR = Path("/tmp")
STATUS_FILE = Path(os.path.expanduser("~/.hermes/shared/.last-research-host-status"))
LOG_PATH = Path(os.path.expanduser("~/.hermes/shared/research-host-log.jsonl"))

CYCLE_TIMEOUT = int(os.environ.get("RESEARCH_HOST_TIMEOUT", "10800"))   # 3h default
MAX_TURNS = 60   # /research-host is allowed plenty of internal turns


def append_log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def detect_workspace(arg_path: str | None) -> Path | None:
    """Find the active research workspace.

    Priority: --workspace arg → first ~/research/<dir> with both Plan.md and
    contracts/constitution.*.yaml → None.
    """
    if arg_path:
        p = Path(arg_path).expanduser().resolve()
        if (p / "Plan.md").exists() or (p / "program.md").exists():
            return p
        return None
    if not RESEARCH_ROOT.exists():
        return None
    candidates = []
    for d in sorted(RESEARCH_ROOT.iterdir()):
        if not d.is_dir():
            continue
        has_plan = (d / "Plan.md").exists() or (d / "program.md").exists()
        has_constitution = any(d.glob("contracts/constitution.*.yaml"))
        # Highest priority: workspaces with constitution AND plan
        if has_plan and has_constitution:
            candidates.append((2, d))
        elif has_plan:
            candidates.append((1, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def plugin_readiness() -> dict:
    """One-shot tool-availability test. Returns {plugin: 'ok'|'fail'|'missing'}."""
    out = {}

    # Codex
    if not shutil.which("codex"):
        out["codex"] = "missing"
    else:
        try:
            r = subprocess.run(
                ["codex", "exec", "--skip-git-repo-check",
                 "Reply with the word OK and nothing else."],
                capture_output=True, text=True, timeout=60,
                stdin=subprocess.DEVNULL,
            )
            out["codex"] = "ok" if "OK" in (r.stdout or "") else "fail"
        except Exception as e:
            out["codex"] = f"error: {str(e)[:80]}"

    # Gemini
    if not shutil.which("gemini"):
        out["gemini"] = "missing"
    else:
        try:
            r = subprocess.run(
                ["gemini", "--yolo", "-p", "Reply with the word OK and nothing else."],
                capture_output=True, text=True, timeout=60,
                stdin=subprocess.DEVNULL,
            )
            out["gemini"] = "ok" if "OK" in (r.stdout or "") else "fail"
        except Exception as e:
            out["gemini"] = f"error: {str(e)[:80]}"

    # claude (must be present — we ARE about to invoke it)
    out["claude"] = "ok" if shutil.which("claude") else "missing"
    return out


def gather_state(workspace: Path) -> dict:
    """Phase 1 — collect everything ClaudeCode needs to resume / start."""
    state: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "plugin_readiness": plugin_readiness(),
    }

    # Git state
    try:
        r = subprocess.run(["git", "-C", str(workspace), "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        state["git_branch"] = (r.stdout or "").strip() or "(none)"
        r = subprocess.run(["git", "-C", str(workspace), "status", "--short"],
                           capture_output=True, text=True, timeout=10)
        state["git_dirty"] = bool((r.stdout or "").strip())
    except Exception:
        state["git_branch"] = "(no-git)"
        state["git_dirty"] = False

    # Plan / program
    for f in ("Plan.md", "program.md", "Idea.md"):
        p = workspace / f
        if p.exists():
            state[f] = p.read_text(encoding="utf-8", errors="ignore")[:6000]

    # Constitution + sprint
    cons = list(workspace.glob("contracts/constitution.*.yaml"))
    if cons:
        state["constitution_path"] = str(cons[0])
        state["constitution_head"] = cons[0].read_text(encoding="utf-8", errors="ignore")[:3000]
    sprints = list(workspace.glob("ledgers/*/sprint.yaml"))
    if sprints:
        # most recent
        sprints.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        state["sprint_path"] = str(sprints[0])
        state["sprint_yaml"] = sprints[0].read_text(encoding="utf-8", errors="ignore")[:3000]
        # ledger tail
        ledger = sprints[0].parent / "results.tsv"
        if ledger.exists():
            lines = ledger.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            state["ledger_tail"] = "\n".join(lines[-10:])

    # Decision trace tail
    trace = workspace / "traces" / "decision_trace.jsonl"
    if trace.exists():
        try:
            lines = trace.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            state["trace_tail"] = lines[-15:]
        except Exception:
            state["trace_tail"] = []

    # Progress.md (resume marker)
    progress = workspace / "progress.md"
    if progress.exists():
        state["progress"] = progress.read_text(encoding="utf-8", errors="ignore")[:2000]
        state["resuming"] = True
    else:
        state["resuming"] = False

    return state


def build_prompt(state_file: Path) -> str:
    """The prompt invokes /research-host with the state file as its argument
    PLUS explicit reminders to use Superpowers + planning-with-files + delegation
    discipline. /research-host.md itself defines the loop; this prompt just sets
    the entrypoint and makes plugin assumptions explicit.
    """
    return (
        f"/research-host {state_file}\n\n"
        f"Operational discipline (these are constitutional anchors — see "
        f"~/claw/plan/Regulations.md § Three Core Principles):\n"
        f"  1. Use the `superpowers:dispatching-parallel-agents` skill for niche "
        f"dispatch. Use `superpowers:verification-before-completion` before any "
        f"`keep` claim.\n"
        f"  2. Use `planning-with-files:plan` for the sprint-level TODO file "
        f"(task_plan.md / findings.md / progress.md). Update progress.md after "
        f"every cycle so the next cron tick can resume from disk.\n"
        f"  3. Codex (gpt-5.4-mini) handles convergence: surgical code edits, "
        f"correctness review (P2 Pass 1). Always invoke with stdin closed "
        f"(`</dev/null` if shell, or `subagent_type=codex:codex-rescue` from a "
        f"Task call which manages stdin internally).\n"
        f"  4. Gemini (3.1-pro-preview) handles divergence: literature search, "
        f"assumption-challenge (P2 Pass 2), alternative-root-cause probing.\n"
        f"  5. Sonnet 4.6 in a fresh Task context handles red-team (P2 Pass 3) — "
        f"NEVER the same context that generated the proposal.\n"
        f"  6. NEVER ask 'should I continue?' — this is a cron-triggered run; "
        f"the human is not present. Halt only on the 6 enumerated halt "
        f"conditions in /research-host. Otherwise loop.\n"
        f"  7. State on disk: every ledger row, decision_trace event, progress "
        f"entry persisted before next phase. Next cron tick must be able to "
        f"resume by reading disk only.\n"
        f"  8. Final line of your reply must be `=== HOST HALTED: <reason> ===` "
        f"so the cron driver can log the halt reason.\n"
    )


def invoke_claude(workspace: Path, state_file: Path, dry_run: bool, model: str) -> dict:
    """Phase 2 — fire ClaudeCode."""
    if dry_run:
        return {"status": "dry-run", "note": "skipped claude invocation"}

    prompt = build_prompt(state_file)
    try:
        r = subprocess.run(
            ["claude", "-p",
             "--model", model,
             "--dangerously-skip-permissions",
             prompt],
            capture_output=True, text=True,
            timeout=CYCLE_TIMEOUT,
            cwd=str(workspace),
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "limit_s": CYCLE_TIMEOUT}
    except Exception as e:
        return {"status": "exec-error", "error": str(e)[:300]}

    out = (r.stdout or "").strip()
    halt_match = re.search(r"=== HOST HALTED:\s*(.+?)\s*===", out)
    halt_reason = halt_match.group(1) if halt_match else "unknown"
    return {
        "status": "ok" if r.returncode == 0 else "exit-error",
        "exit_code": r.returncode,
        "halt_reason": halt_reason,
        "stdout_tail": out[-2000:],
        "stderr_tail": (r.stderr or "")[-500:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="", help="research workspace path; auto-detect if empty")
    ap.add_argument("--dry-run", action="store_true", help="gather state + build prompt, skip claude")
    ap.add_argument("--model", default="sonnet", help="claude model (sonnet | claude-opus-4-7)")
    args = ap.parse_args()

    workspace = detect_workspace(args.workspace)
    if not workspace:
        msg = f"no workspace found (looked in {RESEARCH_ROOT})"
        print(json.dumps({"status": "no-workspace", "error": msg}))
        return 1

    print(f"Workspace: {workspace}")
    print(f"Mode:      {'dry-run' if args.dry_run else 'live'}")
    print(f"Model:     {args.model}")
    print(f"Timeout:   {CYCLE_TIMEOUT}s")
    print()

    print("Phase 1: gather state ...", end=" ", flush=True)
    state = gather_state(workspace)
    state_file = STATE_DIR / f"research-host-state-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    print(f"ok ({state_file.stat().st_size} bytes → {state_file})")
    print(f"  plugin_readiness: {state['plugin_readiness']}")

    # Refuse to fire if Codex or Gemini are dead — Principle 2 (triple-review) cannot be honored
    pr = state["plugin_readiness"]
    if pr.get("codex") != "ok" or pr.get("gemini") != "ok":
        record = {
            "status": "plugin-unready",
            "plugin_readiness": pr,
            "workspace": str(workspace),
        }
        append_log(record)
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(record, indent=2))
        print(f"\n  ✗ refusing to fire — codex/gemini not ready (P2 cannot be honored)")
        print(f"  details: {pr}")
        return 2

    print(f"\nPhase 2: invoke claude -p /research-host ...", flush=True)
    result = invoke_claude(workspace, state_file, args.dry_run, args.model)
    print(f"  → {result.get('status')}, halt_reason={result.get('halt_reason','n/a')}")

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "model": args.model,
        "dry_run": args.dry_run,
        **result,
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    append_log(summary)

    print()
    print(json.dumps({k: v for k, v in summary.items() if k != "stdout_tail"},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
