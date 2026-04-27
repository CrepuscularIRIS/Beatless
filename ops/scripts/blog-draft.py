"""Blog Draft — T2 (multi-stage pipeline, leverages each model's strength).

Per user directive 2026-04-25-evening:
  Pipeline: Obsidian → Step (extract) → MMX (write per template) → drafts.

Stages:
  1. Python: read source paper note from ~/obsidian-vault/papers/literature/
  2. Step 3.5 Flash: structured extraction (fast, cheap, JSON-out)
     - title, authors, arxiv_id, key_results, limitations, hook
  3. MiniMax M2.7: bilingual Paper Spotlight from extracted struct
     - en + zh written from scratch (NOT translated)
     - Strict template adherence
  4. Python: validate frontmatter + save to ~/claw/blog/src/content/blogs/<slug>/
     and <slug>-zh/ with draft:true (canonical path, F2 fix). Old
     ~/obsidian-vault/blog-drafts/ is deprecated.

Why multi-stage beats single-call:
  - Step is fast at extraction (structured task, cheap)
  - MMX writes better prose with clean input than raw paper note
  - Each stage logged independently → easier to debug

Usage:
    python3 blog-draft.py                       # auto-pick 1 uncovered paper
    python3 blog-draft.py --paper @<citekey>    # specific paper
    python3 blog-draft.py --dry-run             # plan only
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PAPERS_DIR = Path.home() / "obsidian-vault" / "papers" / "literature"
BLOG_DIR = Path.home() / "claw" / "blog" / "src" / "content" / "blogs"
# F2 fix (2026-04-27): see blog-translate.py for rationale.
DRAFTS_DIR = BLOG_DIR
HERO_DIR = Path.home() / "claw" / "blog" / "src" / "assets" / "hIE"
STATUS_JSON = Path.home() / ".hermes" / "shared" / ".last-blog-draft-status"
LOG_PATH = Path.home() / ".hermes" / "shared" / "blog-draft-log.jsonl"

EXTRACT_TIMEOUT = 180   # 3 min — Step is fast
WRITE_TIMEOUT = 600     # 10 min — MMX is slower
MAX_TURNS_EXTRACT = 5
MAX_TURNS_WRITE = 15

# 5-hIE taxonomy per ~/claw/plan/blog-taxonomy-hIE.md
HIE_CATEGORIES = {
    "snowdrop": "paper-spotlight",   # high-quality papers, breakthroughs, novel methods
    "kouka":    "signal",             # time-sensitive news, launches, breaking events
    "saturnus": "meta",               # audits, regulation reports, system health
    "methode":  "engineering",        # tool builds, infrastructure, framework dives
    "lacia":    "bundle",             # paper bundles, weekly digests, longform synthesis
}


def pick_hero_image(hie: str) -> str:
    """Round-robin pick a hero image from assets/hIE/<hie>/.
    Falls back to _shared/ group shot if <hie>/ is empty."""
    import random
    candidates_dir = HERO_DIR / hie
    if not candidates_dir.exists() or not any(candidates_dir.iterdir()):
        # Fallback to _shared (e.g. saturnus gap)
        candidates_dir = HERO_DIR / "_shared"
    files = sorted(p for p in candidates_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not files:
        return ""
    chosen = random.choice(files)
    # Astro-relative path under src/assets/
    rel = chosen.relative_to(Path.home() / "claw" / "blog" / "src" / "assets")
    return f"/assets/{rel}"


def find_uncovered_paper() -> Path | None:
    """Most recent paper note with no matching blog draft."""
    if not PAPERS_DIR.exists():
        return None
    existing_slugs: set[str] = set()
    # Only count slugs whose <dir>/index.mdx exists with real content.
    # Empty dirs from a failed earlier tick must NOT block fresh drafting
    # (codex audit P1: blog-draft.py:87 — collision-prone prefix check).
    for d in (DRAFTS_DIR, BLOG_DIR):
        if not d.exists():
            continue
        for x in d.iterdir():
            if not x.is_dir():
                continue
            idx = x / "index.mdx"
            if idx.is_file() and idx.stat().st_size > 200:
                existing_slugs.add(x.name)
    for note in sorted(PAPERS_DIR.glob("@*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        cite = note.stem.lstrip("@")
        # Exact match (or trailing-letter collision-suffix as in luo2025beyondb).
        # The old `slug.startswith(cite[:20])` collided across different papers
        # by the same author/year (e.g. wang2026fracturegs vs wang2026quadratic).
        if cite in existing_slugs:
            continue
        # Tolerate at most one trailing letter suffix added by prior collision-resolve.
        if any(s == cite or (s.startswith(cite) and len(s) - len(cite) == 1 and s[-1].isalpha())
               for s in existing_slugs):
            continue
        return note
    return None


def slug_from_paper(paper_path: Path) -> str:
    cite = paper_path.stem.lstrip("@")
    return re.sub(r"[^a-z0-9-]", "-", cite.lower()).strip("-")[:60]


def append_log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def call_hermes(model_or_provider: str, prompt: str, timeout: int, max_turns: int,
                skill: str = "") -> tuple[int, str]:
    """Run hermes chat -Q. For Step use -m alias; for others use --provider.

    Step is in config's model_aliases but NOT in the CLI's --provider allowlist,
    so we route via -m instead. MiniMax + Kimi are in the allowlist.
    """
    hermes_bin = os.environ.get("HERMES_BIN", "/home/lingxufeng/.local/bin/hermes")
    cmd = [hermes_bin, "chat", "-Q", "--max-turns", str(max_turns)]
    if model_or_provider == "step":
        cmd += ["-m", "step"]   # uses config model_aliases.step
    else:
        cmd += ["--provider", model_or_provider]
    if skill:
        cmd += ["-s", skill]
    cmd += ["-q", prompt]
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(Path.home() / ".local" / "bin"), env.get("PATH", "")])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(Path.home()), env=env)
        return r.returncode, r.stdout or ""
    except subprocess.TimeoutExpired:
        return 124, ""


# ─── Stage 2: Step extracts structured info ─────────────────────────────
EXTRACT_PROMPT = """You are extracting structured info from a Zotero paper note.

Source note:
```
{note_text}
```

Return ONLY a JSON object (no prose, no code-block fences) with these fields:
{{
  "title": "<paper title, English>",
  "authors_short": "<first-author et al.>",
  "arxiv_id": "<id like 2509.12345 or empty>",
  "url": "<paper URL or empty>",
  "date": "<YYYY-MM or empty>",
  "one_line_hook": "<your judgment in one sentence — why this paper matters; English>",
  "key_results": ["<short bullet>", "<bullet>", "<bullet>"],
  "limitations": ["<short bullet>", "<bullet>"],
  "method_intuition": "<2-3 sentence plain-language explanation; English>",
  "hIE": "<one of: snowdrop | kouka | saturnus | methode | lacia>"
}}

hIE selection rule (5-way Beatless taxonomy from ~/claw/plan/blog-taxonomy-hIE.md):
- snowdrop  → novel methods, paradigm-challenging research, breakthrough findings (DEFAULT for most papers)
- kouka     → time-sensitive announcements, product launches (rare for papers — usually for news)
- saturnus  → meta-research about evaluation, governance, audits, AI safety oversight
- methode   → engineering systems, infrastructure, frameworks, tool papers
- lacia     → surveys, synthesis, longform connecting multiple subfields

Rules:
- If a field can't be determined from the note, use empty string or empty list.
- Don't fabricate numbers. If no concrete result is in the note, write "no concrete numbers in source".
- The hIE field is mandatory — pick one even if the paper straddles categories. When in doubt, default to "snowdrop".
- Output ONLY the JSON object, nothing else.
"""


def stage2_extract(paper_path: Path) -> dict:
    """Step 3.5 Flash extracts structured info from the paper note."""
    note_text = paper_path.read_text(encoding="utf-8")[:8000]
    prompt = EXTRACT_PROMPT.format(note_text=note_text)
    rc, stdout = call_hermes("step", prompt, EXTRACT_TIMEOUT, MAX_TURNS_EXTRACT)
    if rc != 0:
        return {"_error": f"step exit {rc}", "_stdout_tail": stdout[-300:]}
    # Strip session_id banner + extract JSON
    cleaned = re.sub(r"^\s*session_id:.*?\n", "", stdout, flags=re.MULTILINE).strip()
    # Find JSON block
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return {"_error": "no JSON in step output", "_stdout_tail": stdout[-300:]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_error": f"JSON parse: {e}", "_stdout_tail": stdout[-300:]}


# ─── Stage 3: MMX writes bilingual Paper Spotlight ──────────────────────
WRITE_PROMPT_TEMPLATE = """Write a bilingual Paper Spotlight blog post pair from this extracted info.

Extracted (from Step 3.5 Flash earlier in the pipeline):
```json
{extracted_json}
```

Source note path: {paper_path}
Today's date: {today}
Slug: {slug}
hIE category: {hie}    (per ~/claw/plan/blog-taxonomy-hIE.md)
hero image:   {hero}    (use this exact path in frontmatter — Python picked it round-robin)

The blog-draft skill is loaded for this session. Follow its rules and the AI 策展博客写作模板指南.md template.

Workflow:
1. Write the ENGLISH Paper Spotlight to: {en_path}
2. Write the CHINESE Paper Spotlight to: {zh_path}
3. Both written from scratch (NOT translated from each other), in their target language's natural prose.
4. Use the 6-section Paper Spotlight template:
   - One-Line Summary (the hook from extracted)
   - Why This Is Worth Your Time (your curatorial judgment, 1-2 angles)
   - Core Method (3-Minute Version) (use the method_intuition + your own framing)
   - Key Results (bullets from extracted; if empty, say "no concrete numbers in source")
   - Limits and Unanswered Questions (from extracted limitations)
   - Further Reading (1-3 related lines if obvious; else omit this section)
5. Frontmatter (both files) — MUST include the hIE taxonomy fields:
   - title (translated for zh, original-meaning for en)
   - description (one-line hook)
   - publishDate: "{today}"
   - category: <map from hIE: snowdrop→paper-spotlight, kouka→signal, saturnus→meta, methode→engineering, lacia→bundle>
   - hIE: {hie}                    ← REQUIRED, exact value
   - hero_image: {hero}            ← REQUIRED, exact path provided above
   - tags: [paper, ...]
   - language: en (or zh)
   - draft: true
   - sources: [URL or empty]
   - confidence: medium
   - status: draft

Style commandments (from the loaded skill):
1. Hook on first sentence, NEVER "Recently" / "近日" / "随着AI的发展"
2. Curatorial judgment, not enumeration
3. Explain technical terms or assume reader knows them — don't pad
4. Paragraphs ≤4 lines, bold key numbers
5. Honest about uncertainty

BANNED phrases (will be audited): 近日 日前 引发了广泛关注 意义重大 赋能 数智化 业界普遍认为
                                  "in recent times" "lately," "of great significance" "empower"

Write to disk via write_file. Don't paste content into chat. Final line: `DONE: {slug}` or `FAILED: <reason>`.
"""


def stage3_write(slug: str, paper_path: Path, extracted: dict) -> tuple[Path, Path, int]:
    """MiniMax M2.7 writes bilingual draft pair."""
    today = datetime.now().strftime("%Y-%m-%d")
    en_path = DRAFTS_DIR / slug / "index.mdx"
    zh_path = DRAFTS_DIR / f"{slug}-zh" / "index.mdx"
    en_path.parent.mkdir(parents=True, exist_ok=True)
    zh_path.parent.mkdir(parents=True, exist_ok=True)
    # Resolve hIE + hero in Python (deterministic, doesn't burn LLM tokens)
    hie = (extracted.get("hIE") or "snowdrop").lower().strip()
    if hie not in HIE_CATEGORIES:
        hie = "snowdrop"
    hero = pick_hero_image(hie)
    prompt = WRITE_PROMPT_TEMPLATE.format(
        extracted_json=json.dumps(extracted, ensure_ascii=False, indent=2),
        paper_path=paper_path,
        today=today,
        slug=slug,
        hie=hie,
        hero=hero,
        en_path=en_path,
        zh_path=zh_path,
    )
    rc, _ = call_hermes("minimax", prompt, WRITE_TIMEOUT, MAX_TURNS_WRITE,
                        skill="blog-draft")
    return en_path, zh_path, rc


# ─── Orchestration ──────────────────────────────────────────────────────
def draft_paper_pipelined(paper_path: Path, dry_run: bool = False) -> dict:
    slug = slug_from_paper(paper_path)
    en_path = DRAFTS_DIR / slug / "index.mdx"
    zh_path = DRAFTS_DIR / f"{slug}-zh" / "index.mdx"

    if dry_run:
        return {"slug": slug, "status": "dry-run",
                "out": [str(en_path), str(zh_path)],
                "stages": ["1.read", "2.step-extract", "3.mmx-write"]}

    print(f"  Stage 2/3: Step extracts...", end=" ", flush=True)
    extracted = stage2_extract(paper_path)
    if "_error" in extracted:
        print(f"FAILED ({extracted['_error']})")
        return {"slug": slug, "status": "stage2-failed", **extracted}
    print(f"ok ({len(json.dumps(extracted))} bytes)")

    print(f"  Stage 3/3: MMX writes en+zh...", end=" ", flush=True)
    en_p, zh_p, rc = stage3_write(slug, paper_path, extracted)
    en_ok = en_p.exists() and en_p.stat().st_size > 200
    zh_ok = zh_p.exists() and zh_p.stat().st_size > 200
    if en_ok and zh_ok:
        status = "ok"
    elif en_ok or zh_ok:
        status = "partial"
    elif rc == 0:
        status = "agent-failed"
    elif rc == 124:
        status = "timeout"
    else:
        status = "exit-error"
    print(f"{status} (en={en_p.stat().st_size if en_ok else 0}b, zh={zh_p.stat().st_size if zh_ok else 0}b)")

    # Cleanup empty pre-created dirs on failure (codex audit P1: blog-draft.py:247).
    # An empty <slug>/ on disk would block future picks via find_uncovered_paper's
    # existing-slugs check, so we remove any empty dirs the failed write left behind.
    for p in (en_p, zh_p):
        try:
            if not p.exists() and p.parent.is_dir() and not any(p.parent.iterdir()):
                p.parent.rmdir()
        except OSError:
            pass

    return {
        "slug": slug,
        "status": status,
        "extracted": {k: v for k, v in extracted.items() if not k.startswith("_")},
        "en_chars": en_p.stat().st_size if en_ok else 0,
        "zh_chars": zh_p.stat().st_size if zh_ok else 0,
        "stage3_exit": rc,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--paper", default="", help="specific @citekey")
    args = ap.parse_args()

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.paper:
        cite = args.paper.lstrip("@")
        target = PAPERS_DIR / f"@{cite}.md"
        if not target.exists():
            print(f"ERROR: paper note not found: {target}")
            return 1
    else:
        target = find_uncovered_paper()
        if target is None:
            print("No uncovered papers — every literature/@*.md already has a blog draft or post.")
            return 0

    print(f"Pipeline: Obsidian → Step (extract) → MMX (write per template)")
    print(f"Target: {target.name}")
    print(f"Output: {DRAFTS_DIR}")
    print()

    print(f"[1/1] {target.name}:")
    r = draft_paper_pipelined(target, dry_run=args.dry_run)
    append_log(r)

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": "multi-stage-pipeline",
        "stages": "step-extract→mmx-write",
        "dry_run": args.dry_run,
        "total": 1,
        "ok": 1 if r["status"] == "ok" else 0,
        "partial": 1 if r["status"] == "partial" else 0,
        "errors": 1 if r["status"] not in ("ok", "partial", "dry-run") else 0,
        "drafts_dir": str(DRAFTS_DIR),
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
