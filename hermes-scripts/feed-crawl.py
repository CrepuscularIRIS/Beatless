"""Feed crawler — top-lab tech reports into Obsidian feeds/.

Per roadmap Phase 1.3 and user directive (2026-04-24): technical reports from
Tier 1/2 labs go to Obsidian feeds/ — NOT to Zotero. Zotero stays paper-only.

Sources are RSS/Atom feeds (robust across sites); 404s are logged and skipped.
Output: ~/obsidian-vault/feeds/<YYYY-MM-DD>/<lab>-<slug>.md with frontmatter
compatible with the Zotero→Obsidian schema (source=feed, tier=tierN, lab=...).

Rate-limit friendly: 2s sleep between feeds. Dedup by destination path.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser

VAULT_FEEDS = Path(os.path.expanduser("~/obsidian-vault/feeds"))
STATUS_FILE = Path(os.path.expanduser("~/.hermes/shared/.last-feed-crawl-status"))
MARKER = Path(os.path.expanduser("~/.hermes/shared/.last-feed-crawl"))

# Tier-ranked feed sources.
# Tier 1 = Anthropic / OpenAI / DeepMind (user directive)
# Tier 2 = Moonshot / Qwen / DeepSeek / ByteDance
# Tier 3 = useful-but-not-top-priority ML/LLM blogs
FEEDS = [
    # --- Tier 1 — working RSS ---
    {"lab": "openai",               "tier": "tier1", "url": "https://openai.com/news/rss.xml"},
    {"lab": "deepmind",             "tier": "tier1", "url": "https://deepmind.google/blog/rss.xml"},
    # --- Tier 2 — working RSS ---
    {"lab": "qwen",                 "tier": "tier2", "url": "https://qwenlm.github.io/blog/index.xml"},
    # --- Tier 3 — aggregator; captures many labs' community posts ---
    {"lab": "huggingface",          "tier": "tier3", "url": "https://huggingface.co/blog/feed.xml"},
    # --- Extra published-RSS sources (low-cost to probe) ---
    {"lab": "google-research",      "tier": "tier1", "url": "https://research.google/blog/rss/"},
    {"lab": "microsoft-research",   "tier": "tier3", "url": "https://www.microsoft.com/en-us/research/feed/"},
]

# HTML scrapers for RSS-less labs. Each entry: (lab, tier, index_url, article_url_pattern).
# Static HTML only — sites requiring JS rendering (Meta AI blog, DeepSeek) are
# deferred until we decide whether to ship Playwright (~400 MB chromium cost).
HTML_SCRAPERS = [
    {"lab": "anthropic", "tier": "tier1",
     "index_url": "https://www.anthropic.com/news",
     "slug_pattern": r'href="(/news/[^"]+)"',
     "url_prefix": "https://www.anthropic.com"},
]

# DEFERRED (heavy JS rendering or no public blog as of 2026-04):
#   Meta AI (ai.meta.com/blog) — heavy SPA, needs Playwright
#   DeepSeek (deepseek.com/news) — returns 404
#   ByteDance Seed (team.doubao.com) — SPA, needs Playwright
#   Moonshot (moonshot.cn) — needs Playwright
#   Anthropic Alignment (alignment.anthropic.com) — HTML but no article markup
# TODO: ship Playwright variant only if these sources prove high-value.

UA = "hermes-feed-crawl/0.1 (+research)"


def slugify(s):
    """Turn a title into a filesystem-safe slug."""
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s or "").lower().strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:60].strip("-") or "untitled"


def is_recent(entry, days):
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return False
    try:
        dt = datetime(*published[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    age = datetime.now(timezone.utc) - dt
    return 0 <= age.days <= days


def write_feed_note(entry, lab, tier, feeds_dir):
    title = (entry.get("title") or "(untitled)").strip()
    url = entry.get("link") or ""
    summary = (entry.get("summary") or "").replace("\n", " ")[:800]
    # Strip inline HTML from summary for readability in Obsidian
    summary = re.sub(r"<[^>]+>", "", summary)
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return None, "no-date"
    try:
        date = f"{published[0]:04d}-{published[1]:02d}-{published[2]:02d}"
    except (TypeError, ValueError):
        return None, "bad-date"
    slug = slugify(title)
    if slug == "untitled" and url:
        slug = hashlib.sha256(url.encode()).hexdigest()[:16]
    date_dir = feeds_dir / date
    date_dir.mkdir(parents=True, exist_ok=True)
    path = date_dir / f"{lab}-{slug}.md"
    if path.exists():
        return None, "exists"
    safe_title = title.replace('"', "'")[:200]
    content = f"""---
title: "{safe_title}"
source: feed
url: {url}
date: {date}
lab: {lab}
tier: {tier}
status: unread
tags: [feed, {lab}, {tier}]
---

**Source:** [{url}]({url})

## Summary

{summary}
"""
    path.write_text(content)
    return str(path), "written"


def fetch_feed(url):
    """Wrap feedparser.parse with a timeout + UA header."""
    # feedparser supports request_headers since 6.x
    return feedparser.parse(url, request_headers={"User-Agent": UA})


def http_get(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


META_TAG_PATS = {
    "og:title": re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"'),
    "og:description": re.compile(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"'),
    "article:published_time": re.compile(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"'),
}


def scrape_article(url):
    """Fetch one article URL, extract title + description + date from meta tags.

    Returns dict or None on failure. Date falls back to crawl time if not
    present in meta (Anthropic doesn't publish article:published_time).
    """
    try:
        html = http_get(url)
    except Exception:
        return None
    out = {"url": url}
    for key, pat in META_TAG_PATS.items():
        m = pat.search(html)
        if m:
            out[key] = m.group(1)
    return out


def scrape_html_source(scraper_cfg, days, feeds_dir, summary_ref, dry_run):
    """Generic static-HTML scraper. Fetch index, extract article slugs, fetch
    each article for title/description/date, emit notes same as RSS path.
    """
    lab, tier = scraper_cfg["lab"], scraper_cfg["tier"]
    try:
        index_html = http_get(scraper_cfg["index_url"])
    except Exception as e:
        summary_ref["errors"].append(f"{lab}: index-fetch-failed {e}")
        summary_ref["per_feed"][lab] = {"error": f"index: {e}"[:120]}
        print(f"  {lab} (html): INDEX FAILED — {e}")
        return

    slug_pat = re.compile(scraper_cfg["slug_pattern"])
    slugs = list(dict.fromkeys(slug_pat.findall(index_html)))  # preserve order, dedup
    print(f"  {lab} (html): {len(slugs)} article slugs found")
    prefix = scraper_cfg.get("url_prefix", "")

    fetched, written, skipped, too_old = 0, 0, 0, 0
    for slug in slugs[:25]:  # cap index-page crawl to avoid flood
        article_url = prefix + slug if slug.startswith("/") else slug
        art = scrape_article(article_url)
        if not art or not art.get("og:title"):
            continue
        fetched += 1

        # Date: use article:published_time if present, else today's date.
        if art.get("article:published_time"):
            date_str = art["article:published_time"][:10]
            try:
                pub_dt = datetime.fromisoformat(date_str)
                year, month, day = pub_dt.year, pub_dt.month, pub_dt.day
            except ValueError:
                year = month = day = None
        else:
            # No date metadata — treat as today (captured via index order,
            # so older articles fall off the index and won't re-appear).
            now = datetime.now(timezone.utc)
            year, month, day = now.year, now.month, now.day

        if year and month and day:
            if not is_recent_enough_ymd(year, month, day, days):
                too_old += 1
                continue
            date = f"{year:04d}-{month:02d}-{day:02d}"
        else:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if dry_run:
            written += 1
            time.sleep(1)
            continue

        slug_part = slugify(art["og:title"]) or slug.rsplit("/", 1)[-1].strip("/")
        date_dir = feeds_dir / date
        date_dir.mkdir(parents=True, exist_ok=True)
        path = date_dir / f"{lab}-{slug_part}.md"
        if path.exists():
            skipped += 1
            continue
        safe_title = art["og:title"].replace('"', "'")[:200]
        desc = art.get("og:description", "")[:800].replace("\n", " ")
        content = f"""---
title: "{safe_title}"
source: feed
url: {article_url}
date: {date}
lab: {lab}
tier: {tier}
status: unread
tags: [feed, {lab}, {tier}]
---

**Source:** [{article_url}]({article_url})

## Summary

{desc}
"""
        path.write_text(content)
        written += 1
        time.sleep(1)  # polite rate-limit between article fetches

    summary_ref["per_feed"][lab] = {
        "tier": tier, "source": "html", "fetched": fetched, "eligible": written + skipped,
        "too_old": too_old, "written": written, "skipped_existing": skipped,
    }
    summary_ref["new_notes"] += written
    summary_ref["skipped_existing"] += skipped
    summary_ref["per_tier"][tier] = summary_ref["per_tier"].get(tier, 0) + written
    print(f"  {lab} (html, {tier}): articles={fetched} written={written} skipped={skipped} too_old={too_old}")


def is_recent_enough_ymd(year, month, day, days):
    try:
        dt = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return False
    age = datetime.now(timezone.utc) - dt
    return 0 <= age.days <= days


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse feeds + count new entries, but don't write notes.")
    parser.add_argument("--days", type=int, default=60,
                        help="Only ingest entries published in last N days (default 60).")
    args = parser.parse_args(argv)

    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "days_filter": args.days,
        "per_feed": {},
        "per_tier": {"tier1": 0, "tier2": 0, "tier3": 0},
        "new_notes": 0,
        "skipped_existing": 0,
        "errors": [],
    }

    VAULT_FEEDS.mkdir(parents=True, exist_ok=True)
    print(f"== feed-crawl started ({'DRY RUN' if args.dry_run else 'LIVE'}) ==")

    for feed_cfg in FEEDS:
        lab, tier, url = feed_cfg["lab"], feed_cfg["tier"], feed_cfg["url"]
        try:
            parsed = fetch_feed(url)
        except Exception as e:
            summary["errors"].append(f"{lab}: fetch-failed {e}")
            summary["per_feed"][lab] = {"error": f"fetch: {e}"[:120]}
            print(f"  {lab}: FETCH FAILED — {e}")
            continue

        if parsed.bozo and not parsed.entries:
            msg = str(parsed.bozo_exception)[:120]
            summary["errors"].append(f"{lab}: bozo {msg}")
            summary["per_feed"][lab] = {"error": f"bozo: {msg}"}
            print(f"  {lab}: BOZO — {msg}")
            continue

        fetched = len(parsed.entries)
        written = 0
        skipped = 0
        too_old = 0
        for entry in parsed.entries:
            if not is_recent(entry, args.days):
                too_old += 1
                continue
            if args.dry_run:
                written += 1
                continue
            path, reason = write_feed_note(entry, lab, tier, VAULT_FEEDS)
            if reason == "written":
                written += 1
            elif reason == "exists":
                skipped += 1

        summary["per_feed"][lab] = {
            "tier": tier,
            "fetched": fetched,
            "eligible": written + skipped,
            "too_old": too_old,
            "written": written,
            "skipped_existing": skipped,
        }
        summary["new_notes"] += written
        summary["skipped_existing"] += skipped
        summary["per_tier"][tier] = summary["per_tier"].get(tier, 0) + written
        print(f"  {lab} ({tier}): fetched={fetched} recent={written + skipped} written={written} skipped={skipped}")
        time.sleep(2)

    # HTML scrapers (non-RSS labs)
    for scraper_cfg in HTML_SCRAPERS:
        scrape_html_source(scraper_cfg, args.days, VAULT_FEEDS, summary, args.dry_run)
        time.sleep(2)

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(summary, indent=2, default=str))
    if not args.dry_run:
        MARKER.touch()
    print(f"\nTotal new notes: {summary['new_notes']}  per-tier: {summary['per_tier']}  errors: {len(summary['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
