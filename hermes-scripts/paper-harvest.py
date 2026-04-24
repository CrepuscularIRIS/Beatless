"""Paper harvester v2 — Zotero ingestion from arXiv + OpenReview + CVF + HF + ACL.

Scope per user spec 2026-04-24:
  - Sources: arXiv, OpenReview (ICLR/ICML/NeurIPS/COLM), CVF (CVPR/ICCV), HF Papers, ACL Anthology (ACL/EMNLP/NAACL)
  - CCF-A venues: NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV (+ optional ACL/EMNLP/NAACL if LLM-relevant)
  - Tier 1 labs: Anthropic, OpenAI, DeepMind
  - Tier 2 labs: Moonshot, Qwen, DeepSeek, ByteDance
  - Time filter: 2026 → A-Tier; 2025-09+ → A-Tier; 2025 pre-Sept → Scouting
  - Dedup: arxiv_id → DOI → title similarity
  - arXiv filter: known lab OR keywords (alignment, agents, reasoning)
  - HF Papers: promote to A-Tier only if CCF-A venue OR Tier 1/2 lab matches
  - Technical reports (lab blogs) go to feed-crawler, NOT Zotero
  - No rule extraction, no summarization: ingestion + filtering + routing only

Architecture: direct source-API calls. PDFs stay in Zotero via the web API.
The Obsidian note layer is downstream (zotero-to-obsidian.py).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

MARKER = os.path.expanduser("~/.hermes/shared/.last-paper-harvest")
STATUS_FILE = os.path.expanduser("~/.hermes/shared/.last-paper-harvest-status")

ZOT_KEY = os.environ.get("ZOTERO_API_KEY", "")
ZOT_USER = os.environ.get("ZOTERO_USER_ID", "")
HF_TOKEN = os.environ.get("Huggingface_Token") or os.environ.get("HUGGINGFACE_TOKEN") or ""
AUTO_HARVEST_COLLECTION = "VXXHVU7P"

UA = "paper-harvest/0.2 (https://github.com/CrepuscularIRIS; +research)"
HEADERS = {"User-Agent": UA}

MAX_PER_TICK = 20
ARXIV_CATS = ["cs.LG", "cs.CL", "cs.CV", "cs.AI"]
EARLIEST_YEAR = 2025

A_TIER_COLLECTION = "5CD5RDNA"
SCOUTING_COLLECTION = "SIDPSB39"

# ---- Tier definitions (spec 2026-04-24) ----

TIER_1_LABS = {
    "anthropic",
    "openai",
    "deepmind", "google deepmind",
}

TIER_2_LABS = {
    "moonshot", "kimi",
    "qwen", "alibaba qwen", "tongyi", "tongyi qianwen",
    "deepseek",
    "bytedance", "bytedance seed", "seed team",
}

# Non-tiered labs kept as affiliation-only signal (go to Scouting, not A-Tier).
OTHER_LAB_SIGNALS = {
    "meta ai", "meta fair", "fair labs",
    "microsoft research", "msr",
    "apple machine learning", "apple ai",
    "nvidia research", "nvidia",
    "allen institute", "ai2", "allenai",
    "mistral",
    "zhipu", "glm",
    "minimax", "hailuo",
    "tencent", "hunyuan",
    "baidu", "ernie",
    "01.ai", "yi-lightning",
    "xiaomi",
    "stepfun",
}

ALL_LAB_SIGNALS = TIER_1_LABS | TIER_2_LABS | OTHER_LAB_SIGNALS

# ---- CCF-A venues (spec) ----

CCF_A_VENUES = {"NeurIPS", "ICML", "ICLR", "CVPR", "ICCV", "ECCV", "COLM"}
CCF_A_OPTIONAL = {"ACL", "EMNLP", "NAACL"}  # LLM-relevant; user enabled

# ---- arXiv keyword filter ----

ARXIV_KEYWORDS = ["alignment", "agent", "reasoning"]

# ---- OpenReview venue list ----
# (venueid, slug_tag, year, venue_label)
# OpenReview venues. Tuple: (venueid, slug_tag, year, venue_label, [venue_display]).
# venue_display is the fallback `content.venue` string for venues that don't
# publish under a structured venueid (e.g. COLM uses display-name filter only).
OPENREVIEW_VENUES = [
    ("ICLR.cc/2026/Conference",    "iclr-2026",    2026, "ICLR",    None),
    ("ICLR.cc/2025/Conference",    "iclr-2025",    2025, "ICLR",    None),
    ("ICML.cc/2025/Conference",    "icml-2025",    2025, "ICML",    None),
    ("NeurIPS.cc/2025/Conference", "neurips-2025", 2025, "NeurIPS", None),
    ("COLM/2025/Conference",       "colm-2025",    2025, "COLM",    "COLM 2025"),
]

# CVF venue list: (conf_url_name, slug_tag, year, venue_label)
CVF_VENUES = [
    ("CVPR", "cvpr-2026", 2026, "CVPR"),
    ("CVPR", "cvpr-2025", 2025, "CVPR"),
    ("ICCV", "iccv-2025", 2025, "ICCV"),
]

# ACL Anthology venue list: (anthology_event_prefix, slug_tag, year, venue_label)
# Gracefully handles missing events (404) — e.g. NAACL 2025 didn't run.
ACL_VENUES = [
    ("acl",   "acl-2025",   2025, "ACL"),
    ("emnlp", "emnlp-2025", 2025, "EMNLP"),
    ("naacl", "naacl-2026", 2026, "NAACL"),
]


# =================================================================
# HTTP + Zotero helpers (unchanged from v1)
# =================================================================

def http_get(url, timeout=25, extra_headers=None):
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def zot_request(method, path, body=None):
    url = f"https://api.zotero.org/users/{ZOT_USER}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Zotero-API-Key": ZOT_KEY, "Content-Type": "application/json",
                 "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return json.loads(raw) if raw else {}


def fetch_existing_identifiers():
    """Return dict with sets: arxiv_ids/dois/urls + list of lowercased titles.

    title list is used for similarity-based dedup (see title_similarity).
    """
    index = {"ids": set(), "titles": []}
    start = 0
    while True:
        url = f"https://api.zotero.org/users/{ZOT_USER}/items?limit=100&start={start}&format=json"
        req = urllib.request.Request(url, headers={"Zotero-API-Key": ZOT_KEY, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            total = int(r.headers.get("Total-Results", "0"))
            data = json.loads(r.read().decode("utf-8"))
        for it in data:
            d = it.get("data", {})
            if d.get("archiveID"):
                index["ids"].add(d["archiveID"].strip().lower())
            if d.get("DOI"):
                index["ids"].add(d["DOI"].strip().lower())
            if d.get("url"):
                index["ids"].add(d["url"].strip().lower())
            if d.get("title"):
                t = d["title"].strip().lower()
                index["ids"].add(("title", t[:80]))
                index["titles"].append(t)
        start += 100
        if start >= total:
            break
    return index


def zot_post_items(items):
    created = []
    failed = []
    for i in range(0, len(items), 50):
        batch = items[i:i + 50]
        try:
            resp = zot_request("POST", "items", batch)
            for k, v in (resp.get("successful") or {}).items():
                created.append({"key": v["key"],
                                "title": v.get("data", {}).get("title", "<no title>")[:80]})
            for k, v in (resp.get("failed") or {}).items():
                failed.append({"i": k, "msg": v.get("message", "?")[:200]})
        except urllib.error.HTTPError as e:
            failed.append({"batch_start": i, "http": e.code, "body": e.read().decode()[:200]})
        time.sleep(1)
    return created, failed


# =================================================================
# Tier classifier + time filter + title similarity (new in v2)
# =================================================================

def is_recent_enough(year, month=None):
    """True iff year >= 2026, OR (year == 2025 and month is not None and month >= 9).

    month may be None (e.g. from venue-year-only records); in that case 2025
    is treated as too-old for A-Tier (falls to Scouting at classifier level)
    but still recent enough to process.
    """
    if year is None or year < 2025:
        return False
    if year >= 2026:
        return True
    # year == 2025
    if month is not None and month >= 9:
        return True
    # 2025 with unknown month or pre-September → eligible for processing but
    # not auto-A-Tier. Classifier handles tier separately.
    return True


def detect_tier_lab(text):
    """Return (tier_label, lab_name) where tier_label is 'tier1' | 'tier2' | 'other' | None."""
    lower = (text or "").lower()
    for lab in TIER_1_LABS:
        if lab in lower:
            return ("tier1", lab)
    for lab in TIER_2_LABS:
        if lab in lower:
            return ("tier2", lab)
    for lab in OTHER_LAB_SIGNALS:
        if lab in lower:
            return ("other", lab)
    return (None, None)


def classify_tier(venue_label=None, authors_text="", year=None, month=None):
    """Central routing decision.

    Returns 'A-Tier' | 'Scouting'.

    Rules (in order):
      1. If venue ∈ CCF_A_VENUES ∪ CCF_A_OPTIONAL → A-Tier (conference papers always qualify by venue).
      2. Elif year is 2026 OR (year == 2025 AND month >= 9):
         - If lab ∈ Tier 1/2 → A-Tier
         - Else → Scouting
      3. Else (2025 pre-Sept, or unknown year): Scouting
    """
    v = (venue_label or "").strip()
    if v in CCF_A_VENUES or v in CCF_A_OPTIONAL:
        return "A-Tier"

    tier_label, _lab = detect_tier_lab(authors_text)
    is_promotion_window = (year is not None and year >= 2026) or \
                          (year == 2025 and month is not None and month >= 9)

    if is_promotion_window and tier_label in ("tier1", "tier2"):
        return "A-Tier"
    return "Scouting"


def _normalize_title(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return set(w for w in s.split() if len(w) > 2)


def title_similarity(a, b):
    """Jaccard similarity on token sets (words > 2 chars, alphanumeric)."""
    ta, tb = _normalize_title(a), _normalize_title(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_duplicate(zot_item, existing_index, title_sim_threshold=0.85):
    """Check arxiv_id → DOI → url → title similarity against existing Zotero index."""
    ids = existing_index["ids"]
    a = (zot_item.get("archiveID") or "").strip().lower()
    if a and a in ids:
        return True
    u = (zot_item.get("url") or "").strip().lower()
    if u and u in ids:
        return True
    t = (zot_item.get("title") or "").strip().lower()
    if t:
        if ("title", t[:80]) in ids:
            return True
        for prior in existing_index["titles"]:
            if title_similarity(t, prior) >= title_sim_threshold:
                return True
    return False


def index_ingest(index, zot_item):
    """Update the in-memory index after posting a new item (prevents same-run dupes)."""
    if zot_item.get("archiveID"):
        index["ids"].add(zot_item["archiveID"].strip().lower())
    if zot_item.get("url"):
        index["ids"].add(zot_item["url"].strip().lower())
    if zot_item.get("title"):
        t = zot_item["title"].strip().lower()
        index["ids"].add(("title", t[:80]))
        index["titles"].append(t)


# =================================================================
# arXiv
# =================================================================

def parse_arxiv_entry(entry, ns):
    title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
    abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")[:900]
    published = entry.find("atom:published", ns).text[:10]
    raw_id = entry.find("atom:id", ns).text
    m = re.search(r"abs/([0-9]+\.[0-9]+)", raw_id)
    arxiv_id = m.group(1) if m else None
    authors = []
    author_names = []
    for a in entry.findall("atom:author", ns):
        nm = a.find("atom:name", ns).text.strip()
        author_names.append(nm)
        parts = nm.rsplit(" ", 1)
        first = parts[0] if len(parts) > 1 else ""
        last = parts[-1]
        authors.append({"creatorType": "author", "firstName": first, "lastName": last})
    cats = [c.get("term") for c in entry.findall("atom:category", ns)]
    year = int(published[:4]) if len(published) >= 4 else None
    month = int(published[5:7]) if len(published) >= 7 else None
    return {
        "arxiv_id": arxiv_id, "title": title, "abstract": abstract,
        "published": published, "year": year, "month": month,
        "authors": authors, "author_names": author_names, "cats": cats,
    }


def _collect_arxiv_search(search_url, ns):
    try:
        xml_text = http_get(search_url, timeout=30)
    except Exception as e:
        print(f"arxiv query failed: {e}")
        return []
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.findall("atom:entry", ns):
        try:
            p = parse_arxiv_entry(entry, ns)
        except Exception:
            continue
        if not p["arxiv_id"]:
            continue
        entry_text = ET.tostring(entry, encoding="unicode")
        tier_label, lab = detect_tier_lab(entry_text)
        if tier_label:
            p["_lab_tier"] = tier_label
            p["_lab_name"] = lab
        out.append(p)
    return out


def fetch_arxiv_by_labs_or_keywords(limit_per_cat=25):
    """arXiv path: fetch recent per-category, keep only papers that have a
    Tier 1/2 lab signal OR contain an arXiv keyword in title/abstract.

    Everything else is dropped (noise control).
    """
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    collected = []
    for cat in ARXIV_CATS:
        q = urllib.parse.quote(f"cat:{cat}")
        url = (f"https://export.arxiv.org/api/query?search_query={q}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={limit_per_cat}")
        entries = _collect_arxiv_search(url, ns)
        for p in entries:
            if not is_recent_enough(p.get("year"), p.get("month")):
                continue
            haystack = (p["title"] + " " + p["abstract"]).lower()
            has_keyword = any(kw in haystack for kw in ARXIV_KEYWORDS)
            has_tier_lab = p.get("_lab_tier") in ("tier1", "tier2")
            if has_keyword or has_tier_lab:
                p["_topic"] = cat
                collected.append(p)
        time.sleep(4)
    # dedup by arxiv_id within this run
    seen = set()
    uniq = []
    for p in collected:
        if p["arxiv_id"] in seen:
            continue
        seen.add(p["arxiv_id"])
        uniq.append(p)
    return uniq


def arxiv_to_zotero_item(p, tier, extra_tags=None):
    target = A_TIER_COLLECTION if tier == "A-Tier" else SCOUTING_COLLECTION
    tags = [{"tag": "auto-harvest"}, {"tag": "arxiv"}, {"tag": f"tier:{tier}"}]
    tags += [{"tag": c} for c in p.get("cats", [])[:3]]
    if p.get("_topic"):
        tags.append({"tag": f"topic:{p['_topic']}"})
    if p.get("_lab_tier"):
        tags.append({"tag": f"lab-tier:{p['_lab_tier']}"})
    if p.get("_lab_name"):
        tags.append({"tag": f"lab:{p['_lab_name']}"})
    for t in (extra_tags or []):
        tags.append({"tag": t})
    extra = f"source: arxiv\narxiv_id: {p['arxiv_id']}\nyear: {p.get('year','')}"
    if p.get("_lab_name"):
        extra += f"\nlab: {p['_lab_name']}"
    return {
        "itemType": "preprint",
        "title": p["title"],
        "creators": p["authors"],
        "abstractNote": p["abstract"],
        "repository": "arXiv",
        "archiveID": f"arXiv:{p['arxiv_id']}",
        "url": f"https://arxiv.org/abs/{p['arxiv_id']}",
        "date": p["published"],
        "libraryCatalog": "arXiv.org",
        "extra": extra,
        "tags": tags,
        "collections": [target],
    }


# =================================================================
# OpenReview
# =================================================================

def _openreview_query(field, value, limit):
    """Single OpenReview query by content.{field}=<value>."""
    offset = 0
    pulled = []
    while len(pulled) < limit:
        q = urllib.parse.quote(value)
        url = (f"https://api2.openreview.net/notes?content.{field}={q}"
               f"&limit={min(25, limit - len(pulled))}&offset={offset}&sort=cdate:desc")
        try:
            data = json.loads(http_get(url, timeout=30))
        except Exception as e:
            print(f"openreview content.{field}={value}: fetch failed {e}")
            break
        notes = data.get("notes", [])
        if not notes:
            break
        pulled.extend(notes)
        if len(notes) < 25:
            break
        offset += 25
        time.sleep(2)
    return pulled


def fetch_openreview_venue(venueid, limit=25, venue_display=None):
    """Try content.venueid first. If empty, retry content.venue (display name).

    COLM uses the venue display field ("COLM 2025") rather than the structured
    venueid ("COLM/2025/Conference"). Passing venue_display enables the fallback.
    """
    notes = _openreview_query("venueid", venueid, limit)
    if not notes and venue_display:
        notes = _openreview_query("venue", venue_display, limit)
    return notes


def openreview_to_zotero_item(note, venue_tag, venue_label, year):
    content = note.get("content", {})
    def gv(k):
        v = content.get(k)
        if isinstance(v, dict):
            return v.get("value")
        return v

    title = (gv("title") or "").strip()
    if not title:
        return None
    abstract = (gv("abstract") or "").strip()[:900]
    author_names = gv("authors") or []
    authors = []
    for nm in author_names[:20]:
        nm = (nm or "").strip()
        if not nm:
            continue
        parts = nm.rsplit(" ", 1)
        authors.append({"creatorType": "author",
                        "firstName": parts[0] if len(parts) > 1 else "",
                        "lastName": parts[-1]})
    nid = note.get("id", "")
    url = f"https://openreview.net/forum?id={nid}" if nid else ""

    # Detect lab for metadata (doesn't change tier — venue-based A-Tier).
    authors_concat = " ".join(author_names)
    tier_label, lab_name = detect_tier_lab(authors_concat)

    tags = [{"tag": "auto-harvest"}, {"tag": "openreview"},
            {"tag": venue_tag}, {"tag": "tier:A-Tier"}]
    if lab_name:
        tags.append({"tag": f"lab:{lab_name}"})
    if tier_label:
        tags.append({"tag": f"lab-tier:{tier_label}"})
    extra = f"source: openreview\nvenue: {venue_label}\nyear: {year}"
    if lab_name:
        extra += f"\nlab: {lab_name}"
    return {
        "itemType": "conferencePaper",
        "title": title,
        "creators": authors,
        "abstractNote": abstract,
        "conferenceName": f"{venue_label} {year}",
        "date": str(year),
        "url": url,
        "libraryCatalog": "OpenReview",
        "extra": extra,
        "tags": tags,
        "collections": [A_TIER_COLLECTION],
    }


# =================================================================
# CVF
# =================================================================

CVF_TITLE_PAT = re.compile(
    r'<dt class="ptitle"><br><a href="(/content/[^"]+\.html)">([^<]+)</a></dt>\s*<dd>(.*?)</dd>',
    re.IGNORECASE | re.DOTALL,
)
CVF_AUTHOR_PAT = re.compile(r'name="query_author"\s+value="([^"]+)"')


def fetch_cvf_conference(conf_name, year, limit=15):
    # Use ?day=all so the listing contains all accepted papers (not just the
    # day-one subset on the plain landing page).
    url = f"https://openaccess.thecvf.com/{conf_name}{year}?day=all"
    try:
        html = http_get(url, timeout=30)
    except Exception as e:
        print(f"cvf {conf_name}-{year}: fetch failed {e}")
        return []
    matches = CVF_TITLE_PAT.findall(html)[:limit]
    out = []
    for href, title, dd_block in matches:
        title = re.sub(r"<[^>]+>", "", title).strip()
        author_names = CVF_AUTHOR_PAT.findall(dd_block)
        authors = []
        for nm in author_names[:20]:
            nm = nm.strip()
            if not nm:
                continue
            parts = nm.rsplit(" ", 1)
            authors.append({"creatorType": "author",
                            "firstName": parts[0] if len(parts) > 1 else "",
                            "lastName": parts[-1]})
        if href.startswith("/"):
            href = "https://openaccess.thecvf.com" + href
        out.append({"title": title, "url": href, "authors": authors,
                    "author_names": author_names, "year": year, "conf": conf_name})
    return out


def cvf_to_zotero_item(p, venue_tag, venue_label):
    authors_concat = " ".join(p.get("author_names", []))
    tier_label, lab_name = detect_tier_lab(authors_concat)
    tags = [{"tag": "auto-harvest"}, {"tag": "cvf"},
            {"tag": venue_tag}, {"tag": "tier:A-Tier"}]
    if lab_name:
        tags.append({"tag": f"lab:{lab_name}"})
    if tier_label:
        tags.append({"tag": f"lab-tier:{tier_label}"})
    extra = f"source: cvf\nvenue: {venue_label}\nyear: {p['year']}"
    if lab_name:
        extra += f"\nlab: {lab_name}"
    return {
        "itemType": "conferencePaper",
        "title": p["title"],
        "creators": p["authors"],
        "conferenceName": f"{venue_label} {p['year']}",
        "date": str(p["year"]),
        "url": p["url"],
        "libraryCatalog": "CVF Open Access",
        "extra": extra,
        "tags": tags,
        "collections": [A_TIER_COLLECTION],
    }


# =================================================================
# HuggingFace Papers (new in v2)
# =================================================================

def fetch_huggingface_papers(limit=100):
    """Hit HF daily-papers API. Returns normalized dicts.

    API caps at limit=100 (HTTP 400 for 101+, verified 2026-04-24). Caller
    may pass higher values but the server will reject them — we clamp here
    as a safety net.
    """
    limit = min(limit, 100)
    url = f"https://huggingface.co/api/daily_papers?limit={limit}"
    extra = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else None
    try:
        raw = http_get(url, timeout=25, extra_headers=extra)
        data = json.loads(raw)
    except Exception as e:
        print(f"hf papers fetch failed: {e}")
        return []
    out = []
    for entry in data:
        paper = entry.get("paper", entry) or {}
        title = (paper.get("title") or "").strip()
        if not title:
            continue
        arxiv_id = paper.get("id") or paper.get("arxiv_id") or ""
        abstract = (paper.get("summary") or paper.get("abstract") or "").strip()[:900]
        published = (paper.get("publishedAt") or entry.get("publishedAt") or "")[:10]
        year = int(published[:4]) if len(published) >= 4 else None
        month = int(published[5:7]) if len(published) >= 7 else None
        author_names = []
        authors = []
        for a in paper.get("authors", []) or []:
            nm = (a.get("name") if isinstance(a, dict) else str(a)).strip()
            if not nm:
                continue
            author_names.append(nm)
            parts = nm.rsplit(" ", 1)
            authors.append({"creatorType": "author",
                            "firstName": parts[0] if len(parts) > 1 else "",
                            "lastName": parts[-1]})
        authors_concat = " ".join(author_names)
        tier_label, lab_name = detect_tier_lab(authors_concat + " " + abstract)
        out.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "published": published,
            "year": year,
            "month": month,
            "authors": authors,
            "author_names": author_names,
            "_lab_tier": tier_label,
            "_lab_name": lab_name,
        })
    return out


def huggingface_to_zotero_item(p, tier):
    target = A_TIER_COLLECTION if tier == "A-Tier" else SCOUTING_COLLECTION
    tags = [{"tag": "auto-harvest"}, {"tag": "huggingface"}, {"tag": f"tier:{tier}"}]
    if p.get("_lab_tier"):
        tags.append({"tag": f"lab-tier:{p['_lab_tier']}"})
    if p.get("_lab_name"):
        tags.append({"tag": f"lab:{p['_lab_name']}"})
    extra = f"source: huggingface\nyear: {p.get('year','')}"
    if p.get("arxiv_id"):
        extra += f"\narxiv_id: {p['arxiv_id']}"
    if p.get("_lab_name"):
        extra += f"\nlab: {p['_lab_name']}"
    if p.get("arxiv_id"):
        archive_id = f"arXiv:{p['arxiv_id']}"
        url = f"https://arxiv.org/abs/{p['arxiv_id']}"
    else:
        archive_id = ""
        url = f"https://huggingface.co/papers/{p.get('arxiv_id','')}" if p.get("arxiv_id") else ""
    return {
        "itemType": "preprint",
        "title": p["title"],
        "creators": p["authors"],
        "abstractNote": p["abstract"],
        "repository": "arXiv" if p.get("arxiv_id") else "HuggingFace Papers",
        "archiveID": archive_id,
        "url": url,
        "date": p.get("published", ""),
        "libraryCatalog": "HuggingFace Papers",
        "extra": extra,
        "tags": tags,
        "collections": [target],
    }


# =================================================================
# ACL Anthology (new in v2)
# =================================================================

ACL_TITLE_PAT = re.compile(
    r'<a\s+class=align-middle\s+href=(/\d{4}\.[a-z-]+\.\d+)/>(.+?)</a>',
    re.IGNORECASE | re.DOTALL,
)
ACL_PEOPLE_PAT = re.compile(r'<a[^>]+href=/people/[^>]+>([^<]+)</a>', re.IGNORECASE)


def fetch_acl_event(event_prefix, year, limit=20):
    """Scrape ACL Anthology event page for accepted papers.

    URL pattern: https://aclanthology.org/events/<prefix>-<year>/
    Graceful on 404 (e.g. NAACL year that didn't run).

    ACL markup note: attributes are unquoted and the page is a single flat
    document, not block-structured. We split on <strong> (each paper entry
    starts with <strong><a ...>title</a></strong>) and skip the first entry
    per volume (it's the "Proceedings of ..." container).
    """
    url = f"https://aclanthology.org/events/{event_prefix}-{year}/"
    try:
        html = http_get(url, timeout=25)
    except Exception as e:
        print(f"acl-anthology {event_prefix}-{year}: fetch failed {e}")
        return []
    blocks = html.split("<strong>")
    out = []
    for blk in blocks[1:]:
        title_m = ACL_TITLE_PAT.search(blk)
        if not title_m:
            continue
        href = title_m.group(1)
        title_raw = title_m.group(2)
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        if not title or title.lower().startswith("proceedings"):
            continue  # skip volume headers
        # Authors are /people/<name>/ anchors within the block.
        author_names = ACL_PEOPLE_PAT.findall(blk)
        author_names = [a.strip() for a in author_names if a.strip()]
        authors = []
        for nm in author_names[:20]:
            parts = nm.rsplit(" ", 1)
            authors.append({"creatorType": "author",
                            "firstName": parts[0] if len(parts) > 1 else "",
                            "lastName": parts[-1]})
        out.append({
            "title": title,
            "url": f"https://aclanthology.org{href}/",
            "authors": authors,
            "author_names": author_names,
            "year": year,
            "event": event_prefix,
        })
        if len(out) >= limit:
            break
    return out


def acl_to_zotero_item(p, venue_tag, venue_label):
    authors_concat = " ".join(p.get("author_names", []))
    tier_label, lab_name = detect_tier_lab(authors_concat)
    tags = [{"tag": "auto-harvest"}, {"tag": "acl-anthology"},
            {"tag": venue_tag}, {"tag": "tier:A-Tier"}]
    if lab_name:
        tags.append({"tag": f"lab:{lab_name}"})
    if tier_label:
        tags.append({"tag": f"lab-tier:{tier_label}"})
    extra = f"source: acl-anthology\nvenue: {venue_label}\nyear: {p['year']}"
    if lab_name:
        extra += f"\nlab: {lab_name}"
    return {
        "itemType": "conferencePaper",
        "title": p["title"],
        "creators": p["authors"],
        "conferenceName": f"{venue_label} {p['year']}",
        "date": str(p["year"]),
        "url": p["url"],
        "libraryCatalog": "ACL Anthology",
        "extra": extra,
        "tags": tags,
        "collections": [A_TIER_COLLECTION],
    }


# =================================================================
# Main
# =================================================================

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + classify + dedup but DO NOT write to Zotero.")
    parser.add_argument("--max", type=int, default=MAX_PER_TICK,
                        help=f"Max items posted this tick (default {MAX_PER_TICK}).")
    parser.add_argument("--per-venue", type=int, default=15,
                        help="OpenReview notes per venue (default 15).")
    parser.add_argument("--per-cvf", type=int, default=12,
                        help="CVF papers per conference (default 12).")
    parser.add_argument("--per-acl", type=int, default=12,
                        help="ACL Anthology papers per event (default 12).")
    parser.add_argument("--per-cat", type=int, default=25,
                        help="arXiv results per category (default 25).")
    parser.add_argument("--hf-limit", type=int, default=100,
                        help="HuggingFace daily-papers count (default 100, API cap observed 2026-04-24).")
    args = parser.parse_args(argv)

    if not ZOT_KEY or not ZOT_USER:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID not in env")
        return 1

    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "max_per_tick": args.max,
        "dry_run": args.dry_run,
        "existing_items": 0,
        "per_source_fetched": {"arxiv": 0, "openreview": 0, "cvf": 0, "huggingface": 0, "acl": 0},
        "per_tier_candidates": {"A-Tier": 0, "Scouting": 0},
        "new_items_posted": 0,
        "skipped_duplicates": 0,
        "created_keys": [],
        "errors": [],
    }

    print("== step 1: fetch existing Zotero identifiers ==")
    try:
        index = fetch_existing_identifiers()
        summary["existing_items"] = len(index["ids"])
        print(f"   {len(index['ids'])} identifiers indexed, {len(index['titles'])} titles")
    except Exception as e:
        summary["errors"].append(f"fetch_existing: {e}")
        index = {"ids": set(), "titles": []}

    candidates = []  # list of (zotero_item_dict, source_tag)

    # --- OpenReview (venue-based A-Tier) ---
    print("== step 2: OpenReview CCF-A venues ==")
    for venueid, tag, year, venue_label, venue_display in OPENREVIEW_VENUES:
        try:
            notes = fetch_openreview_venue(venueid, limit=args.per_venue, venue_display=venue_display)
            print(f"   {tag}: {len(notes)} notes")
            summary["per_source_fetched"]["openreview"] += len(notes)
            for n in notes:
                it = openreview_to_zotero_item(n, tag, venue_label, year)
                if it:
                    candidates.append((it, tag))
        except Exception as e:
            summary["errors"].append(f"openreview {venueid}: {e}")
        time.sleep(2)

    # --- CVF (venue-based A-Tier) ---
    print("== step 3: CVF CCF-A venues ==")
    for conf, tag, year, venue_label in CVF_VENUES:
        try:
            ps = fetch_cvf_conference(conf, year, limit=args.per_cvf)
            summary["per_source_fetched"]["cvf"] += len(ps)
            print(f"   {tag}: {len(ps)} entries")
            for p in ps:
                candidates.append((cvf_to_zotero_item(p, tag, venue_label), tag))
        except Exception as e:
            summary["errors"].append(f"cvf-{tag}: {e}")
        time.sleep(2)

    # --- ACL Anthology (venue-based A-Tier, optional CCF-A) ---
    print("== step 4: ACL Anthology venues ==")
    for prefix, tag, year, venue_label in ACL_VENUES:
        try:
            ps = fetch_acl_event(prefix, year, limit=args.per_acl)
            summary["per_source_fetched"]["acl"] += len(ps)
            print(f"   {tag}: {len(ps)} entries")
            for p in ps:
                candidates.append((acl_to_zotero_item(p, tag, venue_label), tag))
        except Exception as e:
            summary["errors"].append(f"acl-{tag}: {e}")
        time.sleep(2)

    # --- arXiv (lab OR keyword filter; tier decided per-item) ---
    print("== step 5: arXiv (lab/keyword filter) ==")
    try:
        ax = fetch_arxiv_by_labs_or_keywords(limit_per_cat=args.per_cat)
        summary["per_source_fetched"]["arxiv"] = len(ax)
        print(f"   {len(ax)} arXiv entries passed filter")
        for p in ax:
            tier = classify_tier(
                venue_label=None,
                authors_text=" ".join(p.get("author_names", [])) + " " + p.get("abstract", ""),
                year=p.get("year"),
                month=p.get("month"),
            )
            candidates.append((arxiv_to_zotero_item(p, tier=tier),
                               f"arxiv-{p.get('_lab_name','kw')}"))
    except Exception as e:
        summary["errors"].append(f"arxiv: {e}")

    # --- HuggingFace Papers (promote to A-Tier only on venue/lab match) ---
    print("== step 6: HuggingFace Papers ==")
    try:
        hps = fetch_huggingface_papers(limit=args.hf_limit)
        summary["per_source_fetched"]["huggingface"] = len(hps)
        print(f"   {len(hps)} HF paper entries")
        for p in hps:
            # HF has no venue metadata → classifier falls back to lab+time check.
            tier = classify_tier(
                venue_label=None,
                authors_text=" ".join(p.get("author_names", [])) + " " + p.get("abstract", ""),
                year=p.get("year"),
                month=p.get("month"),
            )
            candidates.append((huggingface_to_zotero_item(p, tier=tier),
                               f"hf-{p.get('_lab_name','none')}"))
    except Exception as e:
        summary["errors"].append(f"huggingface: {e}")

    # --- Dedup + tier accounting ---
    print(f"== step 7: dedup ({len(candidates)} candidates) ==")
    fresh = []
    for it, tag in candidates:
        if is_duplicate(it, index):
            summary["skipped_duplicates"] += 1
            continue
        tier_tag = next((t["tag"].split(":", 1)[1] for t in it.get("tags", [])
                         if t.get("tag", "").startswith("tier:")), None)
        if tier_tag in summary["per_tier_candidates"]:
            summary["per_tier_candidates"][tier_tag] += 1
        fresh.append(it)
        index_ingest(index, it)
        if len(fresh) >= args.max:
            break
    print(f"   {len(fresh)} fresh (capped at {args.max})")

    # --- Push (or skip if dry run) ---
    if args.dry_run:
        print("== step 8: DRY RUN — no Zotero writes ==")
        for it in fresh[:10]:
            tier_tag = next((t["tag"] for t in it.get("tags", [])
                             if t.get("tag", "").startswith("tier:")), "tier:?")
            print(f"   [{tier_tag}] {it['title'][:90]}")
    elif fresh:
        print(f"== step 8: push to Zotero ({len(fresh)} items) ==")
        created, failed = zot_post_items(fresh)
        summary["new_items_posted"] = len(created)
        summary["created_keys"] = created
        for f in failed:
            summary["errors"].append(f"zot-post: {f}")
        print(f"   created={len(created)}  failed={len(failed)}")
    else:
        print("== step 8: no new items this tick ==")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATUS_FILE, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    if not args.dry_run:
        Path(MARKER).touch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
