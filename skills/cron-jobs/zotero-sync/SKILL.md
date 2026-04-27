---
name: zotero-sync
description: Mirror a Zotero collection into the Obsidian vault as `@<citekey>.md` notes, one per item. Skips items already mirrored (by Zotero key); writes new notes with extracted metadata + abstract. Records sync receipts so blog-draft can detect newly available paper notes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [zotero, obsidian, sync, hermes-native]
---

# zotero-sync — Hermes-native vault mirror

Replaces `~/.hermes/scripts/zotero-to-obsidian.py`. Pure ETL: pulls Zotero items, writes Obsidian notes, no LLM calls.

## Inputs (env)

- `ZOTERO_API_KEY`, `ZOTERO_USER_ID`
- `ZOTERO_COLLECTION` — target collection key (e.g. `5CD5RDNA`)
- `OBSIDIAN_VAULT` — defaults to `~/obsidian-vault`

## Procedure

### Step 1 — fetch Zotero items (paginated)

```bash
# /users/{user}/items?limit=100&start=N
ITEMS=$(zotero_fetch_collection "$ZOTERO_COLLECTION")
```

### Step 2 — write notes

For each item:
- Compute citekey (e.g. `luo2025beyond`)
- Target: `$OBSIDIAN_VAULT/papers/literature/@<citekey>.md`
- Skip if file exists AND content hash matches Zotero item
- Otherwise write/update with frontmatter (title, authors, year, venue, doi, url, abstract, tags) + body (abstract + Zotero attachment links)

### Step 3 — receipt

```bash
cat > ~/.hermes/shared/.last-zotero-obsidian-sync <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "vault": "$OBSIDIAN_VAULT",
  "literature_dir": "$OBSIDIAN_VAULT/papers/literature",
  "collection": "$ZOTERO_COLLECTION",
  "written": $written,
  "skipped_existing": $skipped,
  "errors": [],
  "error_count": 0
}
EOF
```

### Step 4 — Hermes memory

```bash
true  # AGENT-ACTION: record to memory tool: "zotero-sync ts:$(date -Iseconds) written:$written skipped:$skipped"
```

## Anti-patterns

- ❌ Do NOT push Zotero items here (that's `paper-harvest`)
- ❌ Do NOT touch the Obsidian vault outside `papers/literature/` from this skill
- ❌ Do NOT call any LLM — this skill is deliberately pure ETL
