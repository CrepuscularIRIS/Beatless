"""Blog Translation — T1 (Hermes Agent driver, NOT direct API call).

Per user directive 2026-04-25-late:
  - Cron jobs invoke Hermes Agent (with tools), NOT one-shot MMX API.
  - Agent loads the blog-translate skill (rules + path conventions).
  - Agent has access to: browser_navigate, read_file, write_file, terminal.
  - Agent decides workflow: read source → translate → write draft → self-audit.

Pattern (mirrors github-pr.py but using `hermes chat` instead of `claude -p`):
  1. Python script does discovery (which posts need translating)
  2. Script invokes `hermes chat -Q -s blog-translate -q <rich prompt>`
  3. Hermes Agent (Kimi K2.6 orchestrator) handles the actual work
  4. Output drafts land in ~/claw/blog/src/content/blogs/<slug>-zh/index.mdx
     with draft:true frontmatter (canonical path, F2 fix). Old
     ~/obsidian-vault/blog-drafts/ is deprecated.

Why this beats direct MMX API:
  - Agent can fetch URLs to enrich translations (e.g. confirm linked content)
  - Agent can read sibling files for context
  - Agent self-audits using tools (grep, read its own output)
  - Skill rules are loaded once and influence all turns

Usage:
    python3 blog-translate.py                    # translate up to 3 untranslated
    python3 blog-translate.py --limit 5          # cap to 5
    python3 blog-translate.py --slug some-post   # specific post
    python3 blog-translate.py --dry-run          # plan only, no agent call
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BLOG_DIR = Path.home() / "claw" / "blog" / "src" / "content" / "blogs"
# F2 fix (2026-04-27): drafts are written to canonical Astro path with draft:true
# in frontmatter. Astro skips draft:true in prod build, so writes are safe and the
# blog-maintenance audit no longer false-positives missing-zh on translated drafts.
# Old path ~/obsidian-vault/blog-drafts is deprecated.
DRAFTS_DIR = BLOG_DIR
HERO_DIR = Path.home() / "claw" / "blog" / "src" / "assets" / "hIE"
STATUS_JSON = Path.home() / ".hermes" / "shared" / ".last-blog-translate-status"
LOG_PATH = Path.home() / ".hermes" / "shared" / "blog-translate-log.jsonl"

PER_POST_TIMEOUT = 600   # 10 min per post — agent + thinking + write
MAX_TURNS = 15           # agent turn budget per post

# 5-hIE taxonomy (mirrors blog-draft.py — see ~/claw/plan/blog-taxonomy-hIE.md)
HIE_VALUES = {"snowdrop", "kouka", "saturnus", "methode", "lacia"}


def pick_hero_image(hie: str) -> str:
    """Round-robin pick from assets/hIE/<hie>/, fallback to _shared/."""
    import random
    candidates_dir = HERO_DIR / hie
    if not candidates_dir.exists() or not any(candidates_dir.iterdir()):
        candidates_dir = HERO_DIR / "_shared"
    files = sorted(p for p in candidates_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not files:
        return ""
    chosen = random.choice(files)
    rel = chosen.relative_to(Path.home() / "claw" / "blog" / "src" / "assets")
    return f"/assets/{rel}"


def extract_hie_from_source(src_path: Path) -> tuple[str, str]:
    """Read source frontmatter; return (hIE, hero_image).
    If source has hIE field, use it. Else default to 'snowdrop' (most papers fit).
    If source has hero_image field, preserve it. Else pick fresh."""
    text = src_path.read_text(encoding="utf-8", errors="ignore")
    fm_end = text.find("---", 4) if text.startswith("---") else 0
    fm = text[: fm_end + 3] if fm_end > 0 else text[:2000]
    hie_m = re.search(r"^hIE:\s*[\"']?(\w+)", fm, re.MULTILINE)
    hero_m = re.search(r"^hero_image:\s*[\"']?(/assets/\S+)", fm, re.MULTILINE)
    hie = (hie_m.group(1).lower() if hie_m else "snowdrop")
    if hie not in HIE_VALUES:
        hie = "snowdrop"
    hero = (hero_m.group(1) if hero_m else pick_hero_image(hie))
    return hie, hero


def find_untranslated() -> list[Path]:
    """English post dirs without a <slug>-zh sibling. Skip already-Chinese sources."""
    if not BLOG_DIR.exists():
        return []
    entries = [d for d in BLOG_DIR.iterdir() if d.is_dir()]
    names = {d.name for d in entries}
    untranslated = []
    for d in entries:
        if d.name.endswith("-zh"):
            continue
        # Tighter guard: a -zh sibling counts as translated only if it has a
        # non-empty index.mdx. Bare/empty -zh dirs (left over from a failed
        # earlier tick) used to falsely block re-translation forever.
        zh_sibling = BLOG_DIR / (d.name + "-zh")
        if zh_sibling.is_dir():
            zh_idx = zh_sibling / "index.mdx"
            if zh_idx.is_file() and zh_idx.stat().st_size > 200:
                continue
        idx = d / "index.mdx"
        if not idx.exists():
            continue
        text = idx.read_text(encoding="utf-8", errors="ignore")
        fm_end = text.find("---", 4) if text.startswith("---") else 0
        fm_block = text[: fm_end + 3] if fm_end > 0 else text[:2000]
        if re.search(r"^language:\s*[\"']?zh", fm_block, re.MULTILINE):
            continue
        untranslated.append(d)
    untranslated.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return untranslated


def append_log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def translate_one(src_dir: Path, dry_run: bool = False) -> dict:
    """Invoke Hermes Agent with the blog-translate skill loaded."""
    slug = src_dir.name
    src_path = src_dir / "index.mdx"
    out_dir = DRAFTS_DIR / f"{slug}-zh"
    out_path = out_dir / "index.mdx"

    if dry_run:
        return {"slug": slug, "status": "dry-run", "out": str(out_path)}

    # Resolve hIE + hero_image for the Chinese pair (preserve from source or default)
    hie, hero = extract_hie_from_source(src_path)

    prompt = (
        f"Translate the English blog post at `{src_path}` into Chinese.\n\n"
        f"Apply the rules in the blog-translate skill that's loaded for this session "
        f"(read /home/lingxufeng/claw/plan/AI博客写作模板指南.md for full style guide).\n\n"
        f"Workflow:\n"
        f"1. Read the source mdx with read_file.\n"
        f"2. Translate to Chinese, preserving frontmatter EXCEPT:\n"
        f"   - language: ALWAYS set to 'zh' (override source).\n"
        f"   - draft: ALWAYS set to 'true' (override source even if source is draft: false — "
        f"     Chinese translation is unreviewed and must NOT auto-publish).\n"
        f"3. ENSURE these hIE taxonomy fields are in the Chinese frontmatter "
        f"(per ~/claw/plan/blog-taxonomy-hIE.md):\n"
        f"     hIE: {hie}\n"
        f"     hero_image: {hero}\n"
        f"   If the source already has these, preserve identically. If not, ADD these exact values.\n"
        f"4. Substitute banned phrases per the skill rules.\n"
        f"5. If any links in the source point at external sites you're unsure about, "
        f"   you may use browser_navigate to verify ONE of them — but don't get distracted.\n"
        f"6. Write the result to `{out_path}` (use write_file). Create parent dir if needed.\n"
        f"7. Self-audit: grep your output for banned phrases. If any found, fix and rewrite.\n"
        f"8. Final line of your response must be: `DONE: {out_path}` or `FAILED: <reason>`.\n\n"
        f"Output the file ONLY via write_file. Don't paste the translated content into chat — "
        f"you'll waste tokens. Just confirm completion."
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["hermes", "chat", "-Q",
             "--provider", "minimax",   # writing model per user spec
             "-s", "blog-translate",
             "--max-turns", str(MAX_TURNS),
             "-q", prompt],
            capture_output=True, text=True,
            timeout=PER_POST_TIMEOUT,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return {"slug": slug, "status": "timeout", "limit_s": PER_POST_TIMEOUT}
    except Exception as e:
        return {"slug": slug, "status": "exec-error", "error": str(e)[:300]}

    stdout_tail = (result.stdout or "")[-1500:]
    success = out_path.exists() and out_path.stat().st_size > 200
    status = "ok" if success else ("agent-failed" if result.returncode == 0 else "exit-error")
    # Cleanup pre-created empty dir on failure: leaving an empty <slug>-zh
    # behind would falsely flag the post as translated on the next tick
    # (codex audit P1, blog-translate.py:96 — dir-only-check trap).
    if not success:
        try:
            if out_dir.is_dir() and not any(out_dir.iterdir()):
                out_dir.rmdir()
        except OSError:
            pass
    return {
        "slug": slug,
        "status": status,
        "out": str(out_path),
        "exit_code": result.returncode,
        "wrote_chars": out_path.stat().st_size if out_path.exists() else 0,
        "agent_tail": stdout_tail[-400:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=3, help="cap N posts per run (default 3)")
    ap.add_argument("--slug", default="", help="specific post slug")
    args = ap.parse_args()

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.slug:
        candidates = [BLOG_DIR / args.slug]
        if not candidates[0].exists():
            print(f"ERROR: slug not found: {candidates[0]}")
            return 1
    else:
        candidates = find_untranslated()[: args.limit]

    print(f"Mode: hermes chat -s blog-translate (Hermes Agent + skill + tools)")
    print(f"Targets: {len(candidates)} post(s)")
    print(f"Output: {DRAFTS_DIR}")
    print()

    results = []
    for i, src in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {src.name} ...", end=" ", flush=True)
        r = translate_one(src, dry_run=args.dry_run)
        results.append(r)
        append_log(r)
        print(f"{r['status']}", end="")
        if r.get("wrote_chars"):
            print(f"  ({r['wrote_chars']} bytes)")
        else:
            print()

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": "hermes-chat-skill",
        "skill": "blog-translate",
        "dry_run": args.dry_run,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "errors": sum(1 for r in results if r["status"] != "ok" and r["status"] != "dry-run"),
        "drafts_dir": str(DRAFTS_DIR),
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
