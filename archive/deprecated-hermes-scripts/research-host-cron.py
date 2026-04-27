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


def gpu_state() -> list[dict]:
    """Per Regulations.md § 4.2 — pre-launch nvidia-smi check.

    Returns one dict per GPU with usage stats. Cron driver uses this to
    detect contention and yield to interactive work (Regulations.md § 4.5).
    """
    if not shutil.which("nvidia-smi"):
        return [{"index": -1, "error": "nvidia-smi not found"}]
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return [{"index": -1, "error": f"nvidia-smi rc={r.returncode}"}]
    except Exception as e:
        return [{"index": -1, "error": f"nvidia-smi exception: {str(e)[:100]}"}]

    out = []
    for line in (r.stdout or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            idx = int(parts[0])
            mem_used = int(parts[1])
            mem_total = int(parts[2])
            util = int(parts[3])
            # Per Regulations.md § 4.2: "busy" if either threshold exceeded
            busy = mem_used > 5 * 1024 or util > 30
            out.append({
                "index": idx,
                "mem_used_mib": mem_used,
                "mem_total_mib": mem_total,
                "util_gpu_pct": util,
                "busy": busy,
            })
        except ValueError:
            continue

    # Also enumerate process owners so the agent knows whose job is running
    try:
        r2 = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
        procs = []
        for line in (r2.stdout or "").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                procs.append({"pid": parts[0], "name": parts[1][:60],
                              "mem_mib": parts[2]})
        if procs:
            for g in out:
                g.setdefault("processes_seen", procs)
    except Exception:
        pass
    return out


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


def download_state(workspace: Path) -> dict:
    """If the workspace has a download orchestrator, peek at its progress
    so the cron driver knows what models/datasets are still arriving.

    Per user 2026-04-26 directive: research-host should NOT block waiting on
    downloads, but it MUST know what's not yet available so it doesn't try
    to launch experiments using missing files.
    """
    out: dict = {"orchestrator": None, "summary": ""}
    for cand in ("download_all.py", "downloads.yaml", "scripts/download_all.py"):
        p = workspace / cand
        if p.exists():
            out["orchestrator"] = str(p)
            break
    # Look for a downloads/cache dir + count partials
    cache_candidates = [
        workspace / "downloads",
        Path.home() / ".cache" / "huggingface",
        Path("/data") / workspace.name,
    ]
    parts = []
    for c in cache_candidates:
        if not c.exists():
            continue
        try:
            partials = sum(1 for _ in c.rglob("*.incomplete"))
            tmps = sum(1 for _ in c.rglob("*.tmp"))
            if partials or tmps:
                parts.append(f"{c}: {partials} .incomplete, {tmps} .tmp")
        except (PermissionError, OSError):
            continue
    out["summary"] = "; ".join(parts) if parts else "no in-progress downloads detected"
    return out


def gather_state(workspace: Path) -> dict:
    """Phase 1 — collect everything ClaudeCode needs to resume / start."""
    state: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "plugin_readiness": plugin_readiness(),
        "gpu_state": gpu_state(),
        "download_state": download_state(workspace),
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
        f"~/claw/plan/Regulations.md § Three Core Principles + § 4 GPU Discipline):\n"
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
        f"  3a. CODEX MULTI-LINE EDIT SAFETY NET: if a code change would be a "
        f"NEW file or > 80 modified lines (e.g. writing a Qwen-VL adapter from "
        f"scratch), DO NOT have Codex commit immediately. Instead: ask Codex to "
        f"output a file-by-file plan first, hand the plan to P2 review (Pass 1 "
        f"correctness check on the PLAN, not the code), then have Codex apply. "
        f"For surgical edits (≤ 80 lines, single function), commit-immediately "
        f"is fine.\n"
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
        f"  8. GPU DISCIPLINE (Regulations.md § 4 — non-negotiable):\n"
        f"     - The state file you were given includes `gpu_state` with current "
        f"per-GPU memory + utilization. Read it before any launch.\n"
        f"     - Any GPU with `busy=true` is OFF-LIMITS for this cycle's experiments. "
        f"Pick an idle GPU or yield (status=yielded-to-interactive).\n"
        f"     - Every launch script MUST set `CUDA_VISIBLE_DEVICES=<single-id>` (no "
        f"comma list, no default). NEVER two experiments on the same GPU.\n"
        f"     - VRAM ceiling: target ≤ 40 GB, hard ≤ 46 GB. If predicted > 40 GB, "
        f"shrink batch / precision FIRST, don't gamble.\n"
        f"     - `nohup ... &` your launches and record PIDs to progress.md so "
        f"next cron tick can `ps -p <PID>` to verify.\n"
        f"  9. DOWNLOAD AWARENESS: state file's `download_state` shows whether "
        f"models/datasets are still arriving. Don't try to launch experiments "
        f"that need a model whose `.incomplete` file still exists. If a niche "
        f"depends on a missing model, mark it `pending=download` in "
        f"decision_trace.jsonl and skip to the next.\n"
        f"  10. Final line of your reply must be `=== HOST HALTED: <reason> ===` "
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

    # Refuse to fire if both GPUs are busy — Regulations.md § 4.5 fairness rule.
    # research-host's research cycle MAY want to launch a training run; if neither GPU
    # is available, the cycle would block on resource contention. Yield instead.
    gpus = state["gpu_state"]
    if gpus and not any(g.get("error") for g in gpus):
        idle = [g for g in gpus if not g.get("busy")]
        if not idle:
            owners = []
            for g in gpus:
                for p in (g.get("processes_seen") or []):
                    owners.append(f"GPU{g['index']}={p.get('pid')}({p.get('name')})")
            record = {
                "status": "yielded-to-interactive",
                "gpu_state": gpus,
                "owners_detected": owners[:10],
                "workspace": str(workspace),
                "note": "All GPUs busy — yielding per Regulations.md § 4.5. "
                        "Will retry next cron tick.",
            }
            append_log(record)
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(json.dumps(record, indent=2))
            print(f"\n  ⏸  yielding — all GPUs busy (Regulations.md § 4.5)")
            for g in gpus:
                print(f"     GPU{g['index']}: {g.get('mem_used_mib','?')} MiB / "
                      f"{g.get('util_gpu_pct','?')}% util, busy={g.get('busy')}")
            return 0  # exit 0 so cron doesn't flag this as failure

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
