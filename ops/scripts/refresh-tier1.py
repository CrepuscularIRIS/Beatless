"""Refresh Tier 1 — network-derived candidate repos from followed-users events.

Per Beatless/standards/Repos.md §Tier 1. Runs daily (registered as a Hermes
cron job). Pulls events for each user we follow, scores repos by activity
weight, applies Tier 2 BIG_ORGS exclusion, and writes the ranked top-8 to
~/.hermes/state/repos.tier1.json. github-pr.py reads this file each tick.

Event weights (from Repos.md):
    CreateEvent (refType=repository)   5
    PullRequestEvent (action=opened)   4
    ForkEvent                          3
    WatchEvent (i.e. star)             2

Hard filters applied after scoring:
  - org not in BIG_ORGS
  - repo stars >= MIN_REPO_STARS (default 20, env-overridable)
  - repo not archived, not disabled
  - repo language in our language whitelist (we only contribute to these)
  - repo has at least one open issue with one of:
      'good first issue' | 'help wanted' | 'bug'

Output JSON shape:
    {
      "ts": "<iso>",
      "followee_count": <int>,
      "events_seen": <int>,
      "repos": [
        {"repo": "org/name", "score": <int>, "stars": <int>, "lang": "...", "signals": ["WatchEvent","ForkEvent"]},
        ...
      ]
    }
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Any

STATE_FILE = Path.home() / ".hermes" / "state" / "repos.tier1.json"
SHARED_STATUS = Path.home() / ".hermes" / "shared" / ".last-refresh-tier1-status"

EVENT_WEIGHTS = {
    "CreateEvent":      5,   # only count repository CreateEvents below
    "PullRequestEvent": 4,
    "ForkEvent":        3,
    "WatchEvent":       2,
}

LANGUAGE_WHITELIST = {"Python", "Rust", "Go", "JavaScript", "TypeScript", "C++", "Shell"}

BIG_ORGS = {
    "anthropics", "anthropic-ai",
    "google", "google-deepmind", "google-gemini", "googleapis", "googlecloudplatform",
    "openai", "microsoft", "meta", "facebookresearch",
    "nvidia", "huggingface", "tensorflow", "pytorch",
    "minimax-ai", "alibaba-nlp", "deepseek-ai",
}

MIN_REPO_STARS = int(os.environ.get("GITHUB_PR_MIN_STARS", "20"))
MAX_FOLLOWEES = int(os.environ.get("TIER1_MAX_FOLLOWEES", "120"))
TIER1_CAP = int(os.environ.get("TIER1_CAP", "8"))


def _gh_api(path: str, paginate: bool = False) -> list[dict] | dict:
    """Call gh api. Returns parsed JSON or [] on error. paginate=True follows
    Link headers via gh's --paginate flag."""
    cmd = ["gh", "api", path]
    if paginate:
        cmd.append("--paginate")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return []
    if r.returncode != 0:
        return []
    txt = (r.stdout or "").strip()
    if not txt:
        return []
    try:
        # --paginate concatenates JSON arrays as one stream — handle multi-array case
        if paginate and txt.lstrip().startswith("[") and txt.count("][") >= 1:
            merged: list[Any] = []
            for piece in txt.replace("][", "]\n[").split("\n"):
                merged.extend(json.loads(piece))
            return merged
        return json.loads(txt)
    except json.JSONDecodeError:
        return []


def fetch_following() -> list[str]:
    """Return list of login names this user follows."""
    me = _gh_api("user")
    if not isinstance(me, dict) or not me.get("login"):
        return []
    raw = _gh_api(f"users/{me['login']}/following?per_page=100", paginate=True)
    if not isinstance(raw, list):
        return []
    return [u.get("login") for u in raw if isinstance(u, dict) and u.get("login")][:MAX_FOLLOWEES]


def fetch_user_events(login: str) -> list[dict]:
    """Last 30 public events for a user."""
    raw = _gh_api(f"users/{login}/events/public?per_page=30")
    return raw if isinstance(raw, list) else []


def score_events(events_by_user: dict[str, list[dict]]) -> dict[str, dict]:
    """Aggregate per-repo score from all followees' events."""
    by_repo: dict[str, dict] = {}
    for login, events in events_by_user.items():
        for ev in events:
            etype = ev.get("type", "")
            if etype not in EVENT_WEIGHTS:
                continue
            repo_obj = ev.get("repo") or {}
            slug = repo_obj.get("name") or ""  # already org/repo
            if not slug or "/" not in slug:
                continue
            # CreateEvent of repository (not branch/tag) only
            if etype == "CreateEvent":
                payload = ev.get("payload") or {}
                if payload.get("ref_type") != "repository":
                    continue
            # PullRequestEvent only when action=opened
            if etype == "PullRequestEvent":
                payload = ev.get("payload") or {}
                if payload.get("action") != "opened":
                    continue
            entry = by_repo.setdefault(slug, {"score": 0, "signals": [], "followees": set()})
            entry["score"] += EVENT_WEIGHTS[etype]
            entry["signals"].append(f"{login}:{etype}")
            entry["followees"].add(login)
    return by_repo


def fetch_repo_meta(slug: str) -> dict | None:
    """Get stars / lang / archived / disabled / has-help-wanted."""
    repo = _gh_api(f"repos/{slug}")
    if not isinstance(repo, dict) or not repo.get("full_name"):
        return None
    if repo.get("archived") or repo.get("disabled") or repo.get("private"):
        return None
    return {
        "full_name": repo["full_name"],
        "stars": int(repo.get("stargazers_count") or 0),
        "lang": repo.get("language") or "",
        "license": (repo.get("license") or {}).get("spdx_id") or "",
        "open_issues": int(repo.get("open_issues_count") or 0),
    }


def has_claimable_issue(slug: str) -> bool:
    """Cheap probe: does the repo have at least one open issue tagged
    good-first-issue / help-wanted / bug?"""
    for label in ("good first issue", "help wanted", "bug"):
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", slug,
             "--label", label,
             "--state", "open",
             "--limit", "1",
             "--json", "number"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip().startswith("["):
            try:
                items = json.loads(result.stdout)
                if items:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    print(f"[refresh-tier1] start {started}")
    followees = fetch_following()
    print(f"[refresh-tier1] following {len(followees)} users")
    if not followees:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({
            "ts": started, "followee_count": 0, "events_seen": 0, "repos": [],
            "note": "no followees fetched; auth or empty graph",
        }, indent=2))
        return 1

    events_by_user: dict[str, list[dict]] = {}
    total_events = 0
    for login in followees:
        evts = fetch_user_events(login)
        if evts:
            events_by_user[login] = evts
            total_events += len(evts)
    print(f"[refresh-tier1] {total_events} events from {len(events_by_user)} active users")

    scored = score_events(events_by_user)
    print(f"[refresh-tier1] {len(scored)} candidate repos pre-filter")

    # Apply Tier 2 (BIG_ORGS) and metadata gates.
    survivors: list[dict] = []
    for slug, entry in sorted(scored.items(), key=lambda kv: -kv[1]["score"]):
        org = slug.split("/", 1)[0].lower()
        if org in BIG_ORGS:
            continue
        meta = fetch_repo_meta(slug)
        if not meta:
            continue
        if meta["stars"] < MIN_REPO_STARS:
            continue
        if LANGUAGE_WHITELIST and meta["lang"] and meta["lang"] not in LANGUAGE_WHITELIST:
            continue
        if not has_claimable_issue(slug):
            continue
        survivors.append({
            "repo": slug,
            "score": entry["score"],
            "stars": meta["stars"],
            "lang": meta["lang"],
            "license": meta["license"],
            "signals": entry["signals"][:6],   # cap signals trail
            "followee_count": len(entry["followees"]),
        })
        if len(survivors) >= TIER1_CAP:
            break

    print(f"[refresh-tier1] {len(survivors)} repos after Tier-2/3 gates")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "ts": started,
        "followee_count": len(followees),
        "events_seen": total_events,
        "repos": survivors,
    }, indent=2))

    SHARED_STATUS.parent.mkdir(parents=True, exist_ok=True)
    SHARED_STATUS.write_text(json.dumps({
        "ts": started,
        "tier1_size": len(survivors),
        "events_seen": total_events,
        "followee_count": len(followees),
    }, indent=2))

    print(f"[refresh-tier1] wrote {STATE_FILE}")
    for r in survivors:
        print(f"  [{r['score']:>3}] {r['repo']:40} {r['stars']}★  {r['lang']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
