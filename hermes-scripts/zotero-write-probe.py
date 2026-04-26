"""Minimal Zotero write probe.

This script verifies whether the configured Zotero key can write to the
personal library. By default it creates one clearly marked temporary item and
then deletes it immediately.

Usage:
    python3 hermes-scripts/zotero-write-probe.py --expect-denied
    python3 hermes-scripts/zotero-write-probe.py
    python3 hermes-scripts/zotero-write-probe.py --keep
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from beatless_config import CONFIG


UA = f"zotero-write-probe/0.1 ({CONFIG.user_agent_contact})"


def zot_request(method: str, path: str, body=None, extra_headers=None):
    url = f"https://api.zotero.org/users/{CONFIG.zotero_user_id}/{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Zotero-API-Key": CONFIG.zotero_api_key,
        "Content-Type": "application/json",
        "User-Agent": UA,
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return resp.status, json.loads(raw) if raw else {}


def build_probe_item():
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "itemType": "journalArticle",
        "title": f"Beatless Zotero write probe DELETE ME {stamp}",
        "creators": [
            {
                "creatorType": "author",
                "firstName": "Beatless",
                "lastName": "Probe",
            }
        ],
        "abstractNote": "Temporary item created to test Zotero write access.",
        "date": stamp[:10],
        "url": "https://example.invalid/beatless-zotero-write-probe",
        "tags": [
            {"tag": "beatless-test"},
            {"tag": "delete-me"},
        ],
    }


def write_status(summary):
    path = CONFIG.shared_file(".last-zotero-write-probe")
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expect-denied",
        action="store_true",
        help="treat HTTP 403 write denial as success; useful for read-only keys",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the temporary Zotero item instead of deleting it",
    )
    args = parser.parse_args()

    if not CONFIG.zotero_api_key or not CONFIG.zotero_user_id:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID must be set.")
        return 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "expect-denied" if args.expect_denied else "create-delete",
        "created": False,
        "deleted": False,
        "kept": False,
        "http_error": None,
        "zotero_key": None,
        "zotero_version": None,
    }

    try:
        _, response = zot_request("POST", "items", [build_probe_item()])
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:300]
        summary["http_error"] = {"code": exc.code, "body": body}
        write_status(summary)
        invalid_key = "invalid key" in body.lower()
        if args.expect_denied and exc.code == 403 and not invalid_key:
            print("PASS: Zotero write was denied, as expected for a read-only key.")
            return 0
        if invalid_key:
            print("FAIL: Zotero rejected the configured API key as invalid.")
            return 1
        print(f"FAIL: Zotero write failed with HTTP {exc.code}.")
        return 1

    successful = response.get("successful") or {}
    if not successful:
        summary["http_error"] = {"code": "no-successful-items", "body": response}
        write_status(summary)
        print("FAIL: Zotero returned no successful created item.")
        return 1

    created = next(iter(successful.values()))
    zotero_key = created.get("key")
    version = created.get("version")
    summary["created"] = True
    summary["zotero_key"] = zotero_key
    summary["zotero_version"] = version

    if args.keep:
        summary["kept"] = True
        write_status(summary)
        print(f"PASS: created temporary Zotero item {zotero_key}; kept by request.")
        return 0

    if not zotero_key or version is None:
        write_status(summary)
        print("FAIL: created item response did not include key/version for cleanup.")
        return 1

    try:
        zot_request(
            "DELETE",
            f"items/{zotero_key}",
            extra_headers={"If-Unmodified-Since-Version": str(version)},
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:300]
        summary["http_error"] = {"code": exc.code, "body": body}
        write_status(summary)
        print(f"FAIL: created item {zotero_key}, but cleanup delete failed with HTTP {exc.code}.")
        return 1

    summary["deleted"] = True
    write_status(summary)
    print(f"PASS: created and deleted temporary Zotero item {zotero_key}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
