---
name: feed-crawl
description: Crawl Tier 1/2 lab tech-report feeds (RSS/Atom) into ~/obsidian-vault/feeds/<YYYY-MM-DD>/<lab>-<slug>.md. Output is feed-style notes (NOT papers — papers go to Zotero via paper-harvest). 404s logged and skipped. Rate-limit-friendly with 2s sleep between feeds. Dedup by destination path so re-runs are idempotent.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [rss, atom, feeds, labs, obsidian, hermes-native]
---

# feed-crawl — Hermes-native lab feed ingestion

Replaces `~/.hermes/scripts/feed-crawl.py`. Pure ETL — no LLM calls.

## Sources (Tier 1/2 lab whitelist)

Sources live in the script. Tier 1 = top-of-funnel (DeepMind, OpenAI, Anthropic, FAIR, NVIDIA Research, ...). Tier 2 = high-signal (Allen AI, EleutherAI, MosaicML, Cohere, Mistral, ...).

## Procedure

### Step 1 — fetch each feed

```bash
for FEED in "${FEEDS[@]}"; do
  url=$(echo "$FEED" | cut -d'|' -f3)
  lab=$(echo "$FEED" | cut -d'|' -f2)
  tier=$(echo "$FEED" | cut -d'|' -f1)

  RESPONSE=$(timeout 30 curl -sL -A "Mozilla/5.0 hermes-feed-crawl" "$url")
  RC=$?

  if [ $RC -ne 0 ] || [ -z "$RESPONSE" ]; then
    echo "SKIP: $lab feed unreachable"
    continue
  fi

  parse_and_write_feed "$lab" "$tier" "$RESPONSE"

  sleep 2  # rate-limit polite
done
```

### Step 2 — write notes

```bash
DEST_BASE=~/obsidian-vault/feeds/$(date +%Y-%m-%d)
mkdir -p "$DEST_BASE"

# For each feed entry:
DEST="$DEST_BASE/${lab}-$(slug_of_title).md"
[ -f "$DEST" ] && continue   # idempotent: skip duplicates

cat > "$DEST" <<EOF
---
title: "<title>"
source: feed
tier: $tier
lab: $lab
url: <link>
fetched: $(date -Iseconds)
published: <pub_date>
---

<excerpt>
EOF
```

### Step 3 — Hermes memory

```bash
hermes memory write "feed-crawl ts:$(date -Iseconds) feeds_polled:$N entries_written:$WRITTEN"
```

## Why feed != paper

Feeds = signal items from Tier 1/2 labs (technical reports, blog posts, model launches). Some are papers, but most are announcements / system updates / governance posts. They go to `feeds/`, not `papers/literature/`. blog-draft uses them as Signal Post / Flash Signal source material. Zotero stays paper-only.

## Anti-patterns

- ❌ Do NOT push feed entries to Zotero
- ❌ Do NOT block on a single slow feed (timeout 30s per feed, hard)
- ❌ Do NOT crawl ad-hoc URLs not in the lab whitelist
