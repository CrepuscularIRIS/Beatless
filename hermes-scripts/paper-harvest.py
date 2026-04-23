"""Paper harvester — fills Zotero from arXiv + OpenReview (ICLR/ICML/NeurIPS) + CVF (CVPR).

Scope per user decision 2026-04-23:
  - CCF-A conferences only: ICLR, ICML, NeurIPS, CVPR
  - Papers from 2025 onward, newest first
  - Max 20 new items per cron tick (don't flood library)
  - Dedup against existing Zotero library by arxiv_id / OpenReview id / DOI
  - Push to the pre-created 'Auto-Harvest' collection

Architecture: direct source-API calls (no translation-server needed for these
structured sources). PDFs stay in Zotero via the web API's attachment support.
The Obsidian-side note generation is a separate downstream job — this script
only populates the source layer.
"""
import json
import os
import re
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
AUTO_HARVEST_COLLECTION = "VXXHVU7P"  # pre-created via curl

UA = "paper-harvest/0.1 (https://github.com/CrepuscularIRIS; +research)"
HEADERS = {"User-Agent": UA}

MAX_PER_TICK = 20
ARXIV_CATS = ["cs.LG", "cs.CL", "cs.CV", "cs.AI"]
EARLIEST_YEAR = 2025  # user said post-2025 only

# OpenReview venues — use venueid content field to filter accepted papers
# ICLR 2026 is still in review; ICML 2025 and NeurIPS 2025 are done.
OPENREVIEW_VENUES = [
    ("ICLR.cc/2026/Conference", "iclr-2026"),
    ("ICML.cc/2025/Conference", "icml-2025"),
    ("NeurIPS.cc/2025/Conference", "neurips-2025"),
]

# CVF hosts CVPR open-access; 2026 listings appear June/July 2026
CVF_CVPR_YEARS = [2026, 2025]


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
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
    """Return set of arxiv_ids + DOIs + titles already in the library.

    We paginate the items endpoint, read archiveID + DOI + title, build a
    fast-lookup set for dedup before POSTing.
    """
    ids = set()
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
                ids.add(d["archiveID"].strip().lower())
            if d.get("DOI"):
                ids.add(d["DOI"].strip().lower())
            if d.get("url"):
                ids.add(d["url"].strip().lower())
            if d.get("title"):
                ids.add(("title", d["title"].strip().lower()[:80]))
        start += 100
        if start >= total:
            break
    return ids


def zot_post_items(items):
    """Batch push items (Zotero allows up to 50 per POST)."""
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


# ---------------- arXiv ----------------

def parse_arxiv_entry(entry, ns):
    title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
    abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")[:900]
    published = entry.find("atom:published", ns).text[:10]
    # id looks like http://arxiv.org/abs/2510.26692v1
    raw_id = entry.find("atom:id", ns).text
    m = re.search(r"abs/([0-9]+\.[0-9]+)", raw_id)
    arxiv_id = m.group(1) if m else None
    authors = []
    for a in entry.findall("atom:author", ns):
        nm = a.find("atom:name", ns).text.strip()
        parts = nm.rsplit(" ", 1)
        first = parts[0] if len(parts) > 1 else ""
        last = parts[-1]
        authors.append({"creatorType": "author", "firstName": first, "lastName": last})
    cats = [c.get("term") for c in entry.findall("atom:category", ns)]
    return {
        "arxiv_id": arxiv_id, "title": title, "abstract": abstract,
        "published": published, "authors": authors, "cats": cats,
    }


def fetch_arxiv_new(max_per_cat=15):
    """arXiv listings, newest first per category. Filter to EARLIEST_YEAR+."""
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    collected = []
    for cat in ARXIV_CATS:
        q = urllib.parse.quote(f"cat:{cat}")
        url = (f"https://export.arxiv.org/api/query?search_query={q}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={max_per_cat}")
        try:
            xml_text = http_get(url, timeout=30)
        except Exception as e:
            print(f"arxiv {cat}: fetch failed {e}")
            time.sleep(3)
            continue
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns):
            try:
                p = parse_arxiv_entry(entry, ns)
            except Exception:
                continue
            if not p["arxiv_id"]:
                continue
            year = int(p["published"][:4]) if p["published"] else 0
            if year < EARLIEST_YEAR:
                continue
            collected.append(p)
        time.sleep(3)  # arXiv rate limit courtesy
    # de-dup within one run
    seen = set()
    uniq = []
    for p in collected:
        if p["arxiv_id"] in seen:
            continue
        seen.add(p["arxiv_id"])
        uniq.append(p)
    return uniq


def arxiv_to_zotero_item(p):
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
        "tags": [{"tag": "auto-harvest"}, {"tag": "arxiv"}] +
                [{"tag": c} for c in p["cats"][:3]],
        "collections": [AUTO_HARVEST_COLLECTION],
    }


# ---------------- OpenReview (ICLR / ICML / NeurIPS accepted) ----------------

def fetch_openreview_venue(venueid, limit=25):
    """OpenReview v2 REST API. Pull notes filtered by venueid content field."""
    offset = 0
    pulled = []
    while len(pulled) < limit:
        q = urllib.parse.quote(venueid)
        url = (f"https://api2.openreview.net/notes?content.venueid={q}"
               f"&limit={min(25, limit - len(pulled))}&offset={offset}&sort=cdate:desc")
        try:
            data = json.loads(http_get(url, timeout=30))
        except Exception as e:
            print(f"openreview {venueid}: fetch failed {e}")
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


def openreview_to_zotero_item(note, venue_tag):
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
    # authors: list of full-name strings
    author_names = gv("authors") or []
    authors = []
    for nm in author_names[:20]:
        nm = nm.strip()
        if not nm:
            continue
        parts = nm.rsplit(" ", 1)
        authors.append({"creatorType": "author",
                        "firstName": parts[0] if len(parts) > 1 else "",
                        "lastName": parts[-1]})
    # derive conf name + year
    vid = gv("venueid") or gv("venue") or venue_tag
    year = re.search(r"20\d{2}", vid or "")
    year_str = year.group(0) if year else ""
    # Build URL
    nid = note.get("id", "")
    url = f"https://openreview.net/forum?id={nid}" if nid else ""
    return {
        "itemType": "conferencePaper",
        "title": title,
        "creators": authors,
        "abstractNote": abstract,
        "conferenceName": vid,
        "date": year_str,
        "url": url,
        "libraryCatalog": "OpenReview",
        "extra": f"OpenReview: {nid}",
        "tags": [{"tag": "auto-harvest"}, {"tag": "openreview"}, {"tag": venue_tag}],
        "collections": [AUTO_HARVEST_COLLECTION],
    }


# ---------------- CVF (CVPR open-access) ----------------

def fetch_cvf_cvpr(year, limit=15):
    """Parse the CVPR accepted-papers index from openaccess.thecvf.com."""
    url = f"https://openaccess.thecvf.com/CVPR{year}"
    try:
        html = http_get(url, timeout=30)
    except Exception as e:
        print(f"cvf cvpr-{year}: fetch failed {e}")
        return []
    # Each entry is a <dt class="ptitle"><a href="..."><i>title</i></a></dt>
    # followed by <dd>authors</dd>. Some years use different structure.
    pat = re.compile(
        r'<dt class="ptitle"><a href="([^"]+)">([^<]+)</a></dt>\s*<dd>\s*([^<]+)</dd>',
        re.IGNORECASE | re.DOTALL,
    )
    matches = pat.findall(html)[:limit]
    out = []
    for href, title, authors_str in matches:
        title = re.sub(r"<[^>]+>", "", title).strip()
        authors = []
        for nm in [a.strip() for a in authors_str.split(",")]:
            if not nm:
                continue
            parts = nm.rsplit(" ", 1)
            authors.append({"creatorType": "author",
                            "firstName": parts[0] if len(parts) > 1 else "",
                            "lastName": parts[-1]})
        if href.startswith("/"):
            href = "https://openaccess.thecvf.com" + href
        out.append({"title": title, "url": href, "authors": authors, "year": year})
    return out


def cvf_to_zotero_item(p):
    return {
        "itemType": "conferencePaper",
        "title": p["title"],
        "creators": p["authors"],
        "conferenceName": f"CVPR {p['year']}",
        "date": str(p["year"]),
        "url": p["url"],
        "libraryCatalog": "CVF Open Access",
        "tags": [{"tag": "auto-harvest"}, {"tag": "cvf"}, {"tag": f"cvpr-{p['year']}"}],
        "collections": [AUTO_HARVEST_COLLECTION],
    }


# ---------------- Dedup + main ----------------

def is_duplicate(zot_item, existing):
    a = (zot_item.get("archiveID") or "").strip().lower()
    if a and a in existing:
        return True
    u = (zot_item.get("url") or "").strip().lower()
    if u and u in existing:
        return True
    t = (zot_item.get("title") or "").strip().lower()[:80]
    if t and ("title", t) in existing:
        return True
    return False


def main():
    if not ZOT_KEY or not ZOT_USER:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID not in env")
        return 1

    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "max_per_tick": MAX_PER_TICK,
        "existing_items": 0,
        "arxiv_fetched": 0,
        "openreview_fetched": 0,
        "cvf_fetched": 0,
        "new_items_posted": 0,
        "skipped_duplicates": 0,
        "created_keys": [],
        "errors": [],
    }

    print("== step 1: fetch existing Zotero identifiers ==")
    try:
        existing = fetch_existing_identifiers()
        summary["existing_items"] = len(existing)
        print(f"   {len(existing)} identifiers indexed")
    except Exception as e:
        summary["errors"].append(f"fetch_existing: {e}")
        existing = set()

    candidates = []  # list of (zotero_item_dict, source_tag)

    # --- arXiv ---
    print("== step 2: arXiv ==")
    try:
        ax = fetch_arxiv_new(max_per_cat=10)
        summary["arxiv_fetched"] = len(ax)
        print(f"   {len(ax)} arXiv entries")
        for p in ax:
            it = arxiv_to_zotero_item(p)
            candidates.append((it, "arxiv"))
    except Exception as e:
        summary["errors"].append(f"arxiv: {e}")

    # --- OpenReview venues ---
    print("== step 3: OpenReview (ICLR/ICML/NeurIPS) ==")
    for venueid, tag in OPENREVIEW_VENUES:
        try:
            notes = fetch_openreview_venue(venueid, limit=15)
            print(f"   {tag}: {len(notes)} notes")
            summary["openreview_fetched"] += len(notes)
            for n in notes:
                it = openreview_to_zotero_item(n, tag)
                if it:
                    candidates.append((it, tag))
        except Exception as e:
            summary["errors"].append(f"openreview {venueid}: {e}")
        time.sleep(2)

    # --- CVF CVPR ---
    print("== step 4: CVF (CVPR open-access) ==")
    for y in CVF_CVPR_YEARS:
        try:
            ps = fetch_cvf_cvpr(y, limit=12)
            summary["cvf_fetched"] += len(ps)
            print(f"   cvpr-{y}: {len(ps)} entries")
            for p in ps:
                candidates.append((cvf_to_zotero_item(p), f"cvpr-{y}"))
        except Exception as e:
            summary["errors"].append(f"cvf-{y}: {e}")
        time.sleep(2)

    # --- Dedup ---
    print(f"== step 5: dedup ({len(candidates)} candidates) ==")
    fresh = []
    for it, tag in candidates:
        if is_duplicate(it, existing):
            summary["skipped_duplicates"] += 1
            continue
        fresh.append(it)
        # update existing-set in-memory so same run doesn't double-add
        if it.get("archiveID"):
            existing.add(it["archiveID"].strip().lower())
        if it.get("url"):
            existing.add(it["url"].strip().lower())
        if it.get("title"):
            existing.add(("title", it["title"].strip().lower()[:80]))
        if len(fresh) >= MAX_PER_TICK:
            break
    print(f"   {len(fresh)} fresh (capped at {MAX_PER_TICK})")

    # --- Push ---
    if fresh:
        print(f"== step 6: push to Zotero ({len(fresh)} items) ==")
        created, failed = zot_post_items(fresh)
        summary["new_items_posted"] = len(created)
        summary["created_keys"] = created
        for f in failed:
            summary["errors"].append(f"zot-post: {f}")
        print(f"   created={len(created)}  failed={len(failed)}")
    else:
        print("== step 6: no new items this tick ==")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATUS_FILE, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    Path(MARKER).touch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
