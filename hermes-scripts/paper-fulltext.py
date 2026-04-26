"""Paper Full-Text — download PDFs + extract Markdown body for the KB.

Extends the Zotero→Obsidian pipeline with the missing third stage:

  paper-harvest.py        → Zotero (metadata + URL only — no PDFs)
  zotero-to-obsidian.py   → ~/obsidian-vault/papers/literature/@<citekey>.md  (stub)
  paper-fulltext.py (NEW) → ~/obsidian-vault/papers/full-text/<citekey>.md   (body)

Why this matters (per plan/blog-hIE-TODO.md TODO-9):
  - blog-draft.py currently has only the abstract to work with → spotlights
    re-derive content the LLM has to guess at
  - /exp-discover can't grep across paper bodies for grounding
  - With full-text in vault, both pipelines get to cite + quote primary text

This is the v0 of the database direction. v1 will swap pypdf for MinerU
(better structure preservation: figures, equations, tables) once the basic
download + ingest loop is proven stable. The conversion function is
isolated (`pdf_to_markdown`) so the swap is a one-line replacement.

Source resolution:
  - arXiv URL    → https://arxiv.org/pdf/<id>.pdf
  - OpenReview   → https://openreview.net/pdf?id=<id>
  - ACL Anthology → URL/.pdf
  - Other        → skip (record reason in status)

Usage:
    python3 paper-fulltext.py                    # process up to 5 unread papers
    python3 paper-fulltext.py --limit 20         # cap to 20
    python3 paper-fulltext.py --citekey aali2025ambient  # specific paper
    python3 paper-fulltext.py --dry-run          # plan only, no download
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

VAULT = Path(os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-vault")))
LITERATURE_DIR = VAULT / "papers" / "literature"
FULLTEXT_DIR = VAULT / "papers" / "full-text"
PDF_CACHE = VAULT / "papers" / ".pdf-cache"
STATUS_JSON = Path(os.path.expanduser("~/.hermes/shared/.last-paper-fulltext-status"))
LOG_PATH = Path(os.path.expanduser("~/.hermes/shared/paper-fulltext-log.jsonl"))

PER_PAPER_TIMEOUT = 90      # download + parse cap
DOWNLOAD_TIMEOUT = 60       # per HTTP fetch
UA = "paper-fulltext/0.1 (CrepuscularIRIS academic research)"
MAX_BODY_CHARS = 200_000    # ~50k tokens — cap to keep the vault searchable


def append_log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def resolve_pdf_url(source_url: str) -> tuple[str | None, str]:
    """Return (pdf_url, source_kind) or (None, reason_to_skip)."""
    if not source_url:
        return None, "no-url"
    s = source_url.strip()
    # arXiv: https://arxiv.org/abs/2401.12345  → /pdf/2401.12345.pdf
    m = re.match(r"https?://arxiv\.org/abs/([\w\.\-/]+?)(?:v\d+)?/?$", s)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf", "arxiv"
    # OpenReview: forum?id=XXX  → /pdf?id=XXX
    m = re.match(r"https?://openreview\.net/forum\?id=([\w\-]+)", s)
    if m:
        return f"https://openreview.net/pdf?id={m.group(1)}", "openreview"
    # ACL Anthology: 2025.acl-long.7/  → 2025.acl-long.7.pdf
    m = re.match(r"(https?://aclanthology\.org/[\w\.\-/]+?)/?$", s)
    if m:
        return f"{m.group(1)}.pdf", "acl"
    return None, f"unsupported-host: {s[:60]}"


def download_pdf(pdf_url: str, dest: Path) -> tuple[bool, str]:
    """Fetch PDF to dest. Return (success, message)."""
    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            data = resp.read()
        if len(data) < 1024:
            return False, f"too-small: {len(data)} bytes"
        # Sanity-check it's a real PDF
        if not data.startswith(b"%PDF"):
            return False, f"not-pdf: starts {data[:20]!r}"
        dest.write_bytes(data)
        return True, f"ok ({len(data)} bytes)"
    except urllib.error.HTTPError as e:
        return False, f"http-{e.code}"
    except urllib.error.URLError as e:
        return False, f"url-error: {e.reason}"
    except Exception as e:
        return False, f"download-error: {str(e)[:120]}"


def pdf_to_markdown(pdf_path: Path) -> tuple[str | None, str]:
    """Extract text and minimally structure it as Markdown.

    v0: pypdf page-by-page text extraction. Headings + paragraph breaks are
    inferred from blank-line patterns. v1 will swap to MinerU for better
    structure preservation.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, "pypdf-not-installed"

    try:
        reader = PdfReader(str(pdf_path))
        chunks = []
        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                text = f"<!-- page {i} extract failed: {e} -->"
            text = text.strip()
            if text:
                chunks.append(text)
        body = "\n\n".join(chunks)
        # Normalize: collapse 3+ newlines, strip junky page-number-only lines
        body = re.sub(r"\n{3,}", "\n\n", body)
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + f"\n\n<!-- truncated at {MAX_BODY_CHARS} chars -->"
        return body, f"ok ({len(reader.pages)} pages, {len(body)} chars)"
    except Exception as e:
        return None, f"parse-error: {str(e)[:120]}"


def extract_paper_meta(note_path: Path) -> dict | None:
    """Pull citekey + url + title from an Obsidian literature note."""
    try:
        text = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    fm_m = re.search(r"^---\n(.+?)\n---", text, re.DOTALL | re.M)
    if not fm_m:
        return None
    fm = fm_m.group(1)
    fields = {}
    for line in fm.splitlines():
        m = re.match(r"^([\w_]+):\s*[\"']?(.*?)[\"']?\s*$", line)
        if m and m.group(2).strip():
            fields[m.group(1)] = m.group(2).strip()
    return {
        "citekey":  fields.get("citekey", ""),
        "url":      fields.get("url", ""),
        "title":    fields.get("title", ""),
        "tags":     fields.get("tags", ""),
        "status":   fields.get("status", ""),
    } if fields.get("citekey") else None


def write_fulltext_note(meta: dict, body: str, source_kind: str, pdf_url: str) -> Path:
    """Save the extracted body as ~/obsidian-vault/papers/full-text/<citekey>.md."""
    FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FULLTEXT_DIR / f"{meta['citekey']}.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    front = (
        "---\n"
        f"citekey: {meta['citekey']}\n"
        f"title: \"{meta['title']}\"\n"
        f"source: full-text\n"
        f"source_kind: {source_kind}\n"
        f"pdf_url: {pdf_url}\n"
        f"extracted: {today}\n"
        "extractor: pypdf-v0\n"
        f"linked_from: \"[[@{meta['citekey']}]]\"\n"
        "---\n\n"
        f"# {meta['title']}\n\n"
        f"> Extracted body from {source_kind} PDF. Stub note: [[@{meta['citekey']}]].\n"
        f"> Extractor: pypdf v0 (will swap to MinerU in v1 — see plan/blog-hIE-TODO.md TODO-9).\n\n"
    )
    out_path.write_text(front + body, encoding="utf-8")
    return out_path


def find_unread_with_url(limit: int) -> list[Path]:
    """Pick the most-recently-modified literature notes that don't yet have full-text."""
    if not LITERATURE_DIR.exists():
        return []
    candidates = []
    for note in LITERATURE_DIR.glob("@*.md"):
        meta = extract_paper_meta(note)
        if not meta or not meta.get("url"):
            continue
        ft_path = FULLTEXT_DIR / f"{meta['citekey']}.md"
        if ft_path.exists():
            continue
        candidates.append((note.stat().st_mtime, note))
    candidates.sort(reverse=True)
    return [n for _, n in candidates[:limit]]


def process_one(note_path: Path, dry_run: bool = False) -> dict:
    meta = extract_paper_meta(note_path)
    if not meta:
        return {"note": note_path.name, "status": "no-meta"}

    pdf_url, kind = resolve_pdf_url(meta.get("url", ""))
    if not pdf_url:
        return {"note": note_path.name, "citekey": meta["citekey"],
                "status": "skipped", "reason": kind}

    if dry_run:
        return {"note": note_path.name, "citekey": meta["citekey"],
                "status": "dry-run", "would-fetch": pdf_url}

    PDF_CACHE.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_CACHE / f"{meta['citekey']}.pdf"
    if not pdf_path.exists():
        ok, msg = download_pdf(pdf_url, pdf_path)
        if not ok:
            return {"note": note_path.name, "citekey": meta["citekey"],
                    "status": "download-failed", "reason": msg}
    body, parse_msg = pdf_to_markdown(pdf_path)
    if body is None:
        return {"note": note_path.name, "citekey": meta["citekey"],
                "status": "parse-failed", "reason": parse_msg}

    out_path = write_fulltext_note(meta, body, kind, pdf_url)
    return {
        "note": note_path.name,
        "citekey": meta["citekey"],
        "status": "ok",
        "source_kind": kind,
        "pdf_bytes": pdf_path.stat().st_size,
        "body_chars": len(body),
        "out": str(out_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=5, help="cap per run (default 5)")
    ap.add_argument("--citekey", default="", help="process specific citekey")
    args = ap.parse_args()

    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)
    FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_CACHE.mkdir(parents=True, exist_ok=True)

    if args.citekey:
        targets = [LITERATURE_DIR / f"@{args.citekey}.md"]
        if not targets[0].exists():
            print(f"ERROR: not found: {targets[0]}")
            return 1
    else:
        targets = find_unread_with_url(args.limit)

    print(f"Targets: {len(targets)} paper(s)")
    print(f"Output:  {FULLTEXT_DIR}")
    print(f"Mode:    pypdf v0 (MinerU swap = v1)")
    print()

    results = []
    for i, n in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {n.name} ...", end=" ", flush=True)
        t0 = time.time()
        try:
            r = process_one(n, dry_run=args.dry_run)
        except Exception as e:
            r = {"note": n.name, "status": "exception", "reason": str(e)[:200]}
        r["elapsed_s"] = round(time.time() - t0, 2)
        results.append(r)
        append_log(r)
        marker = r["status"]
        extra = ""
        if r.get("body_chars"):
            extra = f"  ({r['body_chars']} chars, {r['elapsed_s']}s)"
        elif r.get("reason"):
            extra = f"  [{r['reason']}]"
        print(f"{marker}{extra}")

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results
                       if r["status"] in ("download-failed", "parse-failed", "exception")),
        "fulltext_dir": str(FULLTEXT_DIR),
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
