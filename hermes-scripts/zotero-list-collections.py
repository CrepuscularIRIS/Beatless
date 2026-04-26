"""List Zotero personal-library collections and their keys."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from beatless_config import CONFIG


UA = f"zotero-list-collections/0.1 ({CONFIG.user_agent_contact})"


def fetch_collections():
    start = 0
    while True:
        query = urllib.parse.urlencode({
            "limit": 100,
            "start": start,
            "format": "json",
            "sort": "title",
            "direction": "asc",
        })
        url = f"https://api.zotero.org/users/{CONFIG.zotero_user_id}/collections?{query}"
        req = urllib.request.Request(
            url,
            headers={"Zotero-API-Key": CONFIG.zotero_api_key, "User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Total-Results", "0"))
            batch = json.loads(resp.read().decode("utf-8", errors="ignore"))
        for item in batch:
            yield item
        start += 100
        if start >= total or not batch:
            break


def main():
    if not CONFIG.zotero_api_key or not CONFIG.zotero_user_id:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID must be set.")
        return 1

    rows = []
    for item in fetch_collections():
        data = item.get("data", {})
        rows.append((data.get("name", "<unnamed>"), item.get("key", "")))

    if not rows:
        print("No Zotero collections found.")
        return 0

    width = max(len(name) for name, _key in rows)
    for name, key in rows:
        print(f"{name.ljust(width)}  {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
