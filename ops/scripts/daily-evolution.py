"""Daily Evolution Loop — Phase 4 of autonomous-research-os roadmap.

Per /home/lingxufeng/claw/plan/Evolution.md §2 (offline self-evolution loop)
and user directive 2026-04-25: ONLY produce a detailed audit report — do NOT fix.
Writes report as a blog post and commits it to the local blog repo (no push).

Workflow:
  1. Python: gather objective state — gh mailbox, cron health, blog drafts,
     translate/draft logs, error logs, P0 download state.
  2. Claude (via `claude -p --model sonnet`): analyze + write detailed report.
     Audit dimensions: GitHub mail issues, blog quality, cron health, root cause
     hypotheses, recommendations. NOT autonomous fixes.
  3. Python: save report to ~/claw/blog/src/content/blogs/daily-evolution-YYYY-MM-DD/
     and git commit (do NOT push — user reviews + pushes manually).

Architectural constraints (Evolution.md §10):
  - Generator and auditor are separate. The cron jobs that produce content use
    Hermes-routed models (Kimi/Step/MMX). This audit job uses CLAUDE — different
    model family — so we don't have one model judging itself.
  - No autonomous fixes. Report only. User fixes manually.
  - Read-only on production state (gh mailbox, cron status, blog).
  - Write-only to the blog draft path + git commit.

Schedule: every 1440m (every 24h).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BLOG_REPO = Path.home() / "claw" / "blog"
BLOG_POSTS = BLOG_REPO / "src" / "content" / "blogs"
# Post-F2 (2026-04-27): drafts now live at the canonical Astro path with
# `draft: true` frontmatter. obsidian-vault/blog-drafts/ is deprecated;
# evolution metrics must reflect canonical-path activity.
DRAFTS_DIR = BLOG_POSTS
HERMES_LOGS = Path.home() / ".hermes" / "logs"
HERMES_SHARED = Path.home() / ".hermes" / "shared"
STATUS_JSON = HERMES_SHARED / ".last-daily-evolution-status"


def gather_state() -> dict:
    """Phase 1: collect objective signals from the autonomous system."""
    state = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date_local": datetime.now().strftime("%Y-%m-%d"),
    }

    # GitHub mailbox — last 30 notifications
    try:
        r = subprocess.run(
            ["gh", "api", "notifications",
             "--jq", "[.[] | {repo: .repository.full_name, type: .subject.type, "
                     "title: .subject.title, reason: .reason, updated: .updated_at}]"],
            capture_output=True, text=True, timeout=30,
        )
        state["gh_notifications"] = json.loads(r.stdout) if r.returncode == 0 else []
    except Exception as e:
        state["gh_notifications"] = []
        state["gh_notifications_error"] = str(e)[:200]

    # Open PRs by author
    try:
        r = subprocess.run(
            ["gh", "search", "prs", "--author=CrepuscularIRIS", "--state=open",
             "--json", "number,title,repository,updatedAt,reviewDecision,statusCheckRollup",
             "--limit=20"],
            capture_output=True, text=True, timeout=30,
        )
        state["open_prs"] = json.loads(r.stdout) if r.returncode == 0 else []
    except Exception as e:
        state["open_prs"] = []
        state["open_prs_error"] = str(e)[:200]

    # Hermes cron health
    try:
        r = subprocess.run(["hermes", "cron", "list"],
                           capture_output=True, text=True, timeout=20)
        state["cron_list_raw"] = (r.stdout or "")[:6000]
    except Exception as e:
        state["cron_list_raw"] = f"ERROR: {e}"

    # Blog drafts state
    state["drafts_count"] = len(list(DRAFTS_DIR.glob("*"))) if DRAFTS_DIR.exists() else 0
    if DRAFTS_DIR.exists():
        recent = sorted(DRAFTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        state["drafts_recent_24h"] = sum(
            1 for d in recent
            if (datetime.now().timestamp() - d.stat().st_mtime) < 86400
        )
        state["drafts_recent_names"] = [d.name for d in recent[:15]]

    # Live blog state
    if BLOG_POSTS.exists():
        state["blog_posts_total"] = sum(1 for d in BLOG_POSTS.iterdir() if d.is_dir())
        state["blog_zh_pairs"] = sum(
            1 for d in BLOG_POSTS.iterdir()
            if d.is_dir() and d.name.endswith("-zh")
        )
    else:
        state["blog_posts_total"] = 0
        state["blog_zh_pairs"] = 0

    # Recent translate/draft job logs (last 24h)
    for name, path in [("translate", "blog-translate-log.jsonl"),
                       ("draft", "blog-draft-log.jsonl")]:
        log = HERMES_SHARED / path
        if log.exists():
            lines = log.read_text(encoding="utf-8").strip().splitlines()
            recent = []
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            for ln in lines[-200:]:
                try:
                    rec = json.loads(ln)
                    if rec.get("ts", "") > cutoff:
                        recent.append(rec)
                except Exception:
                    continue
            state[f"{name}_log_24h"] = recent
            state[f"{name}_24h_total"] = len(recent)
            state[f"{name}_24h_ok"] = sum(1 for r in recent if r.get("status") == "ok")
            state[f"{name}_24h_errors"] = sum(
                1 for r in recent if r.get("status") not in ("ok", "ok-with-flags", "dry-run")
            )

    # Hermes errors.log tail
    err_log = HERMES_LOGS / "errors.log"
    if err_log.exists():
        state["errors_log_tail"] = err_log.read_text(encoding="utf-8")[-3000:]

    # Hermes blog audit (the audit-only cron)
    audit = HERMES_SHARED / ".blog-audit.md"
    if audit.exists():
        state["blog_audit"] = audit.read_text(encoding="utf-8")[:4000]

    return state


def claude_analyze(state: dict, dry_run: bool = False) -> str:
    """Phase 2: Claude Code session runs /audit-evolution command on state file.

    Per user directive 2026-04-25-late: use a proper ClaudeCode command, not an
    inline prompt. The command file at ~/.claude/commands/audit-evolution.md
    encodes the regulation checklist + heterogeneous review rules. The script
    just gathers state, persists to /tmp, and invokes the command.
    """
    if dry_run:
        return ("---\ntitle: Daily Evolution Report (DRY RUN)\n---\n\n"
                "(skipped Claude call in dry-run)\n")

    # Persist state to a file the command can read
    state_file = Path("/tmp") / f"evolution-state-{state['date_local']}.json"
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Invoke the /audit-evolution command via claude -p, passing the state file path
    prompt = f"/audit-evolution {state_file}"

    try:
        r = subprocess.run(
            ["claude", "-p", "--model", "claude-opus-4-7",
             "--dangerously-skip-permissions",
             prompt],
            capture_output=True, text=True, timeout=5400,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return f"---\ntitle: Daily Evolution Report (TIMEOUT)\n---\n\nClaude (Opus 4.7) call timed out after 90 min.\n"
    except Exception as e:
        return f"---\ntitle: Daily Evolution Report (ERROR)\n---\n\nClaude call failed: {e}\n"

    output = (r.stdout or "").strip()
    # Strip leading session banners; keep from first '---'
    m = re.search(r"^---\s*$", output, re.MULTILINE)
    if m:
        output = output[m.start():]
    # Strip trailing END_REPORT marker
    output = re.sub(r"\n?END_REPORT\s*$", "\n", output)
    return output


def save_and_commit(report_mdx: str, date_str: str, dry_run: bool = False) -> dict:
    """Phase 3: write to blog, git add + commit (no push)."""
    slug = f"daily-evolution-{date_str}"
    out_dir = BLOG_POSTS / slug
    out_path = out_dir / "index.mdx"

    if dry_run:
        return {"slug": slug, "out": str(out_path), "wrote_chars": 0, "committed": False}

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_mdx, encoding="utf-8")

    # Git commit (no push)
    committed = False
    commit_sha = ""
    try:
        subprocess.run(["git", "-C", str(BLOG_REPO), "add", str(out_path)],
                       capture_output=True, text=True, timeout=30)
        cm = subprocess.run(
            ["git", "-C", str(BLOG_REPO), "commit", "-m",
             f"meta(evolution): daily report {date_str} (autonomous audit, no fixes)"],
            capture_output=True, text=True, timeout=30,
        )
        committed = cm.returncode == 0
        if committed:
            sha = subprocess.run(
                ["git", "-C", str(BLOG_REPO), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            commit_sha = (sha.stdout or "").strip()
    except Exception as e:
        return {"slug": slug, "out": str(out_path),
                "wrote_chars": len(report_mdx), "committed": False, "git_error": str(e)[:300]}

    return {
        "slug": slug,
        "out": str(out_path),
        "wrote_chars": len(report_mdx),
        "committed": committed,
        "commit_sha": commit_sha,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="gather state and write a stub report; skip Claude call + git commit")
    args = ap.parse_args()

    print(f"Daily Evolution Loop — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("Phase 1: gather system state ...", end=" ", flush=True)
    state = gather_state()
    print(f"ok ({len(json.dumps(state, default=str))} bytes)")

    print(f"Phase 2: Claude audits ...{' (dry-run)' if args.dry_run else ''}", flush=True)
    report = claude_analyze(state, dry_run=args.dry_run)
    print(f"  report length: {len(report)} chars")

    print(f"Phase 3: save + git commit{' (dry-run)' if args.dry_run else ''} ...", flush=True)
    result = save_and_commit(report, state["date_local"], dry_run=args.dry_run)
    print(f"  {result}")

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": "audit-only",
        "dry_run": args.dry_run,
        "report_chars": len(report),
        **result,
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
