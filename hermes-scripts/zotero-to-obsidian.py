"""Zotero → Obsidian bridge.

Pulls items from the user's Zotero Web API and emits one Markdown note per
paper into `~/obsidian-vault/papers/literature/@<citekey>.md`.

Per the rule-library architecture (plan/2026-04-23-rule-library-architecture.md):
  - PDFs stay in Zotero (we NEVER copy them into the vault).
  - The note contains only metadata, Zotero web link, and a RULE block placeholder.
  - The citekey is derived from first-author-lastname + year + first-title-word,
    lowercased, ascii-only — stable across re-runs.
  - Incremental: re-runs skip files that already exist unless --force is passed.

Not a cron job (yet). Manual runs for now; the user wanted to see something in
the vault. Schedule later once workflow is stable.

Usage:
    set -a; source /home/lingxufeng/claw/.env; set +a
    python3 zotero-to-obsidian.py              # incremental sync
    python3 zotero-to-obsidian.py --force      # regenerate all notes
    python3 zotero-to-obsidian.py --collection VXXHVU7P  # scope to one collection
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ZOT_KEY = os.environ.get("ZOTERO_API_KEY", "")
ZOT_USER = os.environ.get("ZOTERO_USER_ID", "")
VAULT = Path(os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")))
LITERATURE_DIR = VAULT / "papers" / "literature"

UA = "zotero-to-obsidian/0.1 (CrepuscularIRIS)"


def slugify(s, maxlen=40):
    """ASCII-only lowercase slug."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen]


def derive_citekey(data):
    """Build a stable citekey: <firstauthorlast><year><firsttitleword>.

    e.g. smith2026attention
    """
    creators = data.get("creators") or []
    last = "unknown"
    for c in creators:
        if c.get("creatorType") in ("author", "editor"):
            last = c.get("lastName") or c.get("name") or "unknown"
            break
    year = ""
    d = data.get("date") or ""
    m = re.search(r"(19|20)\d{2}", d)
    if m:
        year = m.group(0)
    title_word = ""
    for w in re.split(r"\s+", (data.get("title") or "")):
        w = re.sub(r"[^A-Za-z0-9]", "", w).lower()
        # skip stopwords; take first content word
        if w and w not in {"a", "an", "the", "on", "of", "for", "to", "and", "or",
                           "in", "is", "are", "with", "via", "at", "by", "from"}:
            title_word = w
            break
    return (slugify(last, 20) + year + slugify(title_word, 20)) or "paper"


def zot_paginate(path, params=None):
    """Yield every item from a paginated Zotero endpoint."""
    params = dict(params or {})
    start = 0
    while True:
        q = {"limit": 100, "start": start, "format": "json", **params}
        url = f"https://api.zotero.org/users/{ZOT_USER}/{path}?{urllib.parse.urlencode(q)}"
        req = urllib.request.Request(url, headers={"Zotero-API-Key": ZOT_KEY, "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                total = int(r.headers.get("Total-Results", "0"))
                batch = json.loads(r.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            print(f"zot fetch error at start={start}: {e}")
            break
        if not batch:
            break
        for it in batch:
            yield it
        start += 100
        if start >= total:
            break
        time.sleep(0.5)


def render_note(item, citekey):
    """Emit the literature-note markdown body."""
    d = item.get("data", {})
    title = (d.get("title") or "<no title>").replace("\n", " ").strip()
    # Escape double-quotes in title for YAML safety
    safe_title = title.replace('"', "'")
    abstract = (d.get("abstractNote") or "").strip()

    authors = []
    for c in (d.get("creators") or []):
        if c.get("creatorType") not in ("author", "editor"):
            continue
        name = (c.get("firstName", "") + " " + c.get("lastName", "")).strip() or c.get("name", "")
        if name:
            authors.append(name.strip())

    tags = [t.get("tag") for t in (d.get("tags") or []) if t.get("tag")]
    direction = next((t.split(":", 1)[1] for t in tags if t.startswith("topic:")), "unsorted")

    source = "zotero"
    archive_id = d.get("archiveID") or ""
    if archive_id.startswith("arXiv:"):
        source = "arxiv"
    elif any(t.startswith(("iclr", "icml", "neurips", "cvpr")) for t in tags):
        source = "conference"

    url = d.get("url") or ""
    zotero_key = item.get("key", "")
    zotero_web_url = f"https://www.zotero.org/lingxufeng/items/{zotero_key}" if zotero_key else ""

    fm_lines = [
        "---",
        f'title: "{safe_title}"',
        f"citekey: {citekey}",
        f"source: {source}",
        f"zotero_key: {zotero_key}",
        f"zotero_url: {zotero_web_url}",
    ]
    if archive_id:
        fm_lines.append(f"archive_id: {archive_id}")
    if url:
        fm_lines.append(f"url: {url}")
    fm_lines += [
        f'date: "{d.get("date", "")}"',
        "status: unread",
        f"direction: {direction}",
        "tags:",
    ]
    fm_lines += [f"  - {t}" for t in sorted(set(tags))[:12]]
    fm_lines += [
        'hook: ""  # fill during curation — "why this matters to me"',
        "---",
        "",
        f"# {title}",
        "",
    ]
    if authors:
        fm_lines += ["**Authors:** " + ", ".join(authors[:10]) + ("" if len(authors) <= 10 else f" …(+{len(authors) - 10})"), ""]
    if archive_id.startswith("arXiv:"):
        aid = archive_id.split(":", 1)[1]
        fm_lines += [f"**arXiv:** [{aid}](https://arxiv.org/abs/{aid})  "]
    if zotero_web_url:
        fm_lines += [f"**Zotero:** [open]({zotero_web_url})  "]
    fm_lines += ["", "## Abstract", ""]
    fm_lines += [abstract or "_(no abstract)_"]
    fm_lines += ["", "## Hook", "", "_fill in during curation_", ""]
    fm_lines += ["## Rules extracted", ""]
    fm_lines += ["_no rules yet — extract during reading (see plan/rule-library-architecture §2)_", ""]
    return "\n".join(fm_lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="regenerate even if note exists")
    # Default to A-Tier collection so cron runs pull quality-guaranteed papers only.
    # Pass "" or "ALL" to sync whole library.
    ap.add_argument("--collection", default="5CD5RDNA",
                    help="collection key (default '5CD5RDNA' = A-Tier). "
                         "Pass 'ALL' to sync entire library.")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N items (debug)")
    args = ap.parse_args()
    if (args.collection or "").upper() == "ALL":
        args.collection = None

    if not ZOT_KEY or not ZOT_USER:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID must be exported")
        return 1

    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)

    path = "items"
    if args.collection:
        path = f"collections/{args.collection}/items"

    seen_citekeys = {}
    created = 0
    skipped = 0
    written = 0
    errors = []

    for i, item in enumerate(zot_paginate(path)):
        if args.limit and i >= args.limit:
            break
        data = item.get("data", {})
        if data.get("itemType") in ("attachment", "note"):
            continue
        try:
            citekey = derive_citekey(data)
            # resolve collisions by appending a char
            base = citekey
            n = 0
            while seen_citekeys.get(citekey) and seen_citekeys[citekey] != item.get("key"):
                n += 1
                citekey = f"{base}{chr(ord('a') + min(n-1, 25))}"
            seen_citekeys[citekey] = item.get("key")

            out_path = LITERATURE_DIR / f"@{citekey}.md"
            if out_path.exists() and not args.force:
                skipped += 1
                continue
            body = render_note(item, citekey)
            out_path.write_text(body, encoding="utf-8")
            written += 1
            if not out_path.exists():
                created += 1
        except Exception as e:
            errors.append({"zotero_key": item.get("key"), "error": str(e)[:200]})

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vault": str(VAULT),
        "literature_dir": str(LITERATURE_DIR),
        "collection": args.collection or "ALL",
        "written": written,
        "skipped_existing": skipped,
        "errors": errors[:20],
        "error_count": len(errors),
    }
    status_path = os.path.expanduser("~/.hermes/shared/.last-zotero-obsidian-sync")
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
