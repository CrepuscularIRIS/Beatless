"""Blog Maintenance — wake-gate + ClaudeCode execution.

Audits ~/claw/blog (Astro site), surfaces:
  - EN-only posts missing a -zh bilingual pair
  - Posts older than STALE_DAYS that could be refreshed

Invokes /blog-maintenance with MiniMax model override for the actual writing
work. The 3-section bilingual template is pending user spec; until it arrives,
the command relies on the existing writing-anti-ai + MiniMax skill-pack
defaults and calls out "3-SECTION TEMPLATE: PENDING SPEC" in every prompt so
the downstream worker doesn't invent its own format.

Working directory: ~/claw/blog
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

BLOG_DIR = Path.home() / "claw" / "blog"
BLOG_POSTS = BLOG_DIR / "src" / "content" / "blogs"
MARKER = os.path.expanduser("~/.hermes/shared/.last-blog-maintenance")
STATUS_FILE = os.path.expanduser("~/.hermes/shared/.last-blog-maintenance-status")

STALE_DAYS = 60  # posts older than this are rewrite candidates
MAX_WORK_PER_TICK = 3  # don't translate more than 3 posts per 12h cron


def audit_blog():
    """Return (missing_zh, stale_posts) two lists sorted by newest first."""
    if not BLOG_POSTS.exists():
        return [], []

    entries = [d for d in BLOG_POSTS.iterdir() if d.is_dir()]
    names = {d.name for d in entries}

    missing_zh = []
    for d in entries:
        if d.name.endswith("-zh"):
            continue
        if d.name + "-zh" not in names:
            missing_zh.append(d)

    # sort newest first
    missing_zh.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    now = datetime.now().timestamp()
    stale_cut = now - STALE_DAYS * 86400
    stale_posts = [
        d for d in entries
        if not d.name.endswith("-zh")
        and d.stat().st_mtime < stale_cut
    ]
    stale_posts.sort(key=lambda p: p.stat().st_mtime)

    return missing_zh, stale_posts


def write_status(payload):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)


def main():
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)

    if not BLOG_DIR.exists():
        print(json.dumps({"wakeAgent": False}))
        return

    missing_zh, stale_posts = audit_blog()

    write_status({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_posts": len(list(BLOG_POSTS.iterdir())) if BLOG_POSTS.exists() else 0,
        "missing_zh_count": len(missing_zh),
        "stale_count": len(stale_posts),
        "stale_days_threshold": STALE_DAYS,
        "next_translations": [p.name for p in missing_zh[:MAX_WORK_PER_TICK]],
        "next_rewrites": [p.name for p in stale_posts[:MAX_WORK_PER_TICK]],
    })

    if not missing_zh and not stale_posts:
        print(json.dumps({"wakeAgent": False}))
        return

    translate_list = "\n".join(
        f"- {p.name}" for p in missing_zh[:MAX_WORK_PER_TICK]
    ) or "(none)"
    rewrite_list = "\n".join(
        f"- {p.name}  ({int((datetime.now().timestamp() - p.stat().st_mtime) / 86400)}d old)"
        for p in stale_posts[:MAX_WORK_PER_TICK]
    ) or "(none)"

    prompt = (
        f"/blog-maintenance\n\n"
        f"Blog root: {BLOG_DIR}\n"
        f"Content dir: {BLOG_POSTS}\n\n"
        f"QUEUE — needs Chinese bilingual pair ({len(missing_zh)} total, top "
        f"{MAX_WORK_PER_TICK} this tick):\n{translate_list}\n\n"
        f"QUEUE — older than {STALE_DAYS} days, rewrite candidates "
        f"({len(stale_posts)} total, top {MAX_WORK_PER_TICK} this tick):\n"
        f"{rewrite_list}\n\n"
        f"MODEL ROUTING:\n"
        f"- Use MiniMax M2.7 for writing + image generation. The MiniMax skill pack is\n"
        f"  installed at ~/.hermes/skills/minimax-multimodal-toolkit, minimax-docx,\n"
        f"  minimax-pdf, minimax-xlsx, minimax-music-gen — prefer mmx CLI for media.\n"
        f"- Use writing-anti-ai skill on every draft before git add.\n\n"
        f"BILINGUAL PAIR CONVENTION (from existing posts):\n"
        f"- English post: <slug>/index.mdx\n"
        f"- Chinese post: <slug>-zh/index.mdx\n"
        f"- Match structure, frontmatter keys, and asset paths 1:1.\n\n"
        f"3-SECTION TEMPLATE: PENDING SPEC.\n"
        f"The user will provide the exact 3-section structure later. Until then:\n"
        f"- Translate existing EN posts to CN preserving their current sections.\n"
        f"- For rewrites, do NOT force a 3-section mould — keep the post's natural\n"
        f"  sectioning but improve clarity, remove AI-filler, and verify code examples.\n"
        f"- When the spec arrives, this block will be replaced with the exact sections.\n\n"
        f"HARD CONSTRAINTS:\n"
        f"- Never `git push` from this cron. Commit only.\n"
        f"- Max {MAX_WORK_PER_TICK} posts processed per tick.\n"
        f"- Run `pnpm build` after edits; abort commit on build failure.\n"
        f"- No AI-revealing phrasing (as an AI, I will now, etc.).\n"
    )

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet",
         "--dangerously-skip-permissions",
         prompt],
        capture_output=True, text=True,
        timeout=7200,
        cwd=str(BLOG_DIR),
    )

    if result.returncode == 0:
        open(MARKER, "w").close()

    output = (result.stdout or "").strip()
    if output:
        print(output[-4000:] if len(output) > 4000 else output)
    else:
        print(f"ClaudeCode exited {result.returncode}: {(result.stderr or '')[:500]}")


if __name__ == "__main__":
    main()
