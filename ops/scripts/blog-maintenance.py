"""Blog Maintenance — AUDIT-ONLY.

Per roadmap Phase 2.4 decision (2026-04-23):
  - The blog no longer auto-writes posts from cron.
  - Writing is human-triggered via /blog-curate (deferred until user
    hands over the 3-section template spec).
  - This cron's only job is to produce an audit report that flags:
      (a) English posts missing their -zh Chinese pair
      (b) Posts older than STALE_DAYS (60) that might need refresh

The audit file lands at ~/.hermes/shared/.blog-audit.md for human review.
A tiny status JSON goes to ~/.hermes/shared/.last-blog-maintenance-status.

Does NOT spawn claude -p. Returns {"wakeAgent": false} so Hermes runs
its own lightweight summary loop rather than a full agent tick.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BLOG_DIR = Path.home() / "claw" / "blog"
BLOG_POSTS = BLOG_DIR / "src" / "content" / "blogs"

AUDIT_MD = Path(os.path.expanduser("~/.hermes/shared/.blog-audit.md"))
STATUS_JSON = Path(os.path.expanduser("~/.hermes/shared/.last-blog-maintenance-status"))

STALE_DAYS = 60


def _has_real_content(d: Path) -> bool:
    """True iff <d>/index.mdx exists with at least 200 bytes (drops empty dirs
    left by failed translate ticks — codex audit P1: blog-maintenance.py:40)."""
    idx = d / "index.mdx"
    return idx.is_file() and idx.stat().st_size > 200


def _post_mtime(d: Path) -> float:
    """Use the post file's mtime, not the directory's. Astro normal edits
    update the file, not the parent dir (codex audit P1:45)."""
    idx = d / "index.mdx"
    if idx.is_file():
        return idx.stat().st_mtime
    return d.stat().st_mtime


def audit_blog():
    """Return (missing_zh_list, stale_list)."""
    if not BLOG_POSTS.exists():
        return [], []
    entries = [d for d in BLOG_POSTS.iterdir() if d.is_dir()]
    # Only count -zh siblings as "translated" if they have real content.
    translated_bases = {
        d.name[:-3]
        for d in entries
        if d.name.endswith("-zh") and _has_real_content(d)
    }

    missing_zh = [
        d for d in entries
        if not d.name.endswith("-zh")
        and d.name not in translated_bases
        and _has_real_content(d)   # don't report empty source dirs as missing zh
    ]
    missing_zh.sort(key=_post_mtime, reverse=True)

    now = datetime.now().timestamp()
    cut = now - STALE_DAYS * 86400
    stale = [d for d in entries
             if not d.name.endswith("-zh") and _post_mtime(d) < cut]
    stale.sort(key=_post_mtime)
    return missing_zh, stale


def render_audit_md(missing_zh, stale):
    """Human-readable report for the user to review before any writing happens."""
    ts = datetime.now(timezone.utc).isoformat()
    out = [
        "# Blog Audit Report",
        "",
        f"_Generated: {ts}_",
        "",
        f"**Vault**: `{BLOG_POSTS}`",
        f"**Stale threshold**: {STALE_DAYS} days",
        "",
        "## English posts missing a `-zh` Chinese pair",
        "",
    ]
    if missing_zh:
        out.append(f"{len(missing_zh)} post(s) need translation:")
        out.append("")
        for d in missing_zh[:60]:
            age = int((datetime.now().timestamp() - d.stat().st_mtime) / 86400)
            out.append(f"- [ ] `{d.name}`  ({age}d old)")
        if len(missing_zh) > 60:
            out.append(f"- _…and {len(missing_zh) - 60} more_")
    else:
        out.append("_(none — all English posts have `-zh` pairs)_")
    out += ["", "## Posts older than 60 days (rewrite candidates)", ""]
    if stale:
        for d in stale[:60]:
            age = int((datetime.now().timestamp() - d.stat().st_mtime) / 86400)
            out.append(f"- [ ] `{d.name}`  ({age}d old)")
        if len(stale) > 60:
            out.append(f"- _…and {len(stale) - 60} more_")
    else:
        out.append("_(none — blog is fresh)_")
    out += [
        "",
        "---",
        "",
        "## What this report is NOT",
        "",
        "- This is an audit. No posts are written automatically.",
        "- To write/translate: open Claude Code, run `/blog-curate` (once implemented),",
        "  pick an item from this list, get a draft, commit it yourself.",
        "- The 3-section template for posts is still pending the user's spec.",
    ]
    return "\n".join(out) + "\n"


def main():
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    if not BLOG_DIR.exists():
        status = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "mode": "audit-only", "status": "no-blog-dir",
                  "blog_dir": str(BLOG_DIR)}
        STATUS_JSON.write_text(json.dumps(status, indent=2))
        print(json.dumps({"wakeAgent": False}))
        return 0

    missing_zh, stale = audit_blog()
    AUDIT_MD.write_text(render_audit_md(missing_zh, stale))
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "audit-only",
        "status": "ok",
        "blog_dir": str(BLOG_DIR),
        "audit_md": str(AUDIT_MD),
        "missing_zh_count": len(missing_zh),
        "stale_count": len(stale),
        "stale_days_threshold": STALE_DAYS,
        "note": "no posts written — writing deferred to /blog-curate",
    }
    STATUS_JSON.write_text(json.dumps(status, indent=2))
    # Return wakeAgent: false — Hermes runs its own lightweight summary
    # instead of a full claude -p execution.
    print(json.dumps({"wakeAgent": False}))
    print(f"audit-md: {AUDIT_MD}  missing-zh: {len(missing_zh)}  stale: {len(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
