---
name: paper-harvest
description: Harvest new papers from arXiv (lab+keyword filter), OpenReview (CCF-A venues), CVF, ACL Anthology, and HuggingFace Papers. Dedup against Zotero (arxiv_id → DOI → URL → title-similarity 0.85). Push fresh items into Zotero collections, capped per tick. Hermes memory tracks per-source last-fetched markers so we don't re-poll empty windows.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [zotero, arxiv, openreview, cvf, acl, harvest, hermes-native]
---

# paper-harvest — Hermes-native paper ingestion

Replaces `~/.hermes/scripts/paper-harvest.py`. The script's logic (HTTP polling + dedup + Zotero push) is preserved, but invocation flows through this skill so memory + observability + dedup-by-content (not just slug) become first-class.

## Inputs

- `MAX_PER_TICK` — env, default 20 (pushed up to 40 by Repos convergence work)
- `ZOTERO_API_KEY`, `ZOTERO_USER_ID`, `ZOTERO_COLLECTION` — required, in `~/.hermes/.env`

## Procedure

### Step 1 — Hermes memory check (per-source last-fetched markers)

```bash
LAST_ARXIV=$(hermes memory query "paper-harvest arxiv last_id" 2>/dev/null | tail -1)
LAST_OPENREVIEW=$(hermes memory query "paper-harvest openreview last_id" 2>/dev/null | tail -1)
# ... per source
```

If a source's marker indicates we polled it < 30 min ago, skip. Avoids hammering rate-limited endpoints.

### Step 2 — fetch sources (parallel where possible)

| Source | Tool | Filter |
|---|---|---|
| arXiv | atom feed `cat:cs.LG/cs.CL/cs.AI/...` | lab whitelist (DeepMind, OpenAI, Anthropic, ...) ∪ keyword whitelist (RLHF, agents, eval, ...) |
| OpenReview | API `notes` by venueid | venueids: iclr-2026, iclr-2025, icml-2025, neurips-2025, colm-2025 |
| CVF | scrape `openaccess.thecvf.com/<conf>_<year>/papers` | top-N most recent |
| ACL Anthology | site mirror | acl-2025, emnlp-2025 |
| HF Papers | `/api/daily_papers?limit=100` | known-failing SSL → graceful degrade |

All HTTP via Hermes `web_tools`; no raw `requests.get()` allowed (so retries/backoff are uniform).

### Step 3 — dedup vs Zotero

```python
# Pseudocode — actual impl uses hermes file_tools to read/write index
existing = load_zotero_index()
fresh = []
for p in candidates:
    if is_duplicate(p, existing, title_sim_threshold=0.85):
        continue
    fresh.append(p)
fresh = fresh[:MAX_PER_TICK]
```

Title similarity at 0.85 catches the `luo2025beyond` ↔ `luo2025beyondb` case (which the slug-only dedup missed).

### Step 4 — push to Zotero + Hermes memory

```bash
# Push items via Zotero API
push_to_zotero(fresh)

# Update markers
hermes memory write "paper-harvest arxiv last_id $latest_arxiv_id"
hermes memory write "paper-harvest openreview last_id $latest_openreview_id"

# Status receipt
cat > ~/.hermes/shared/.last-paper-harvest-status <<EOF
{
  "ts": "$(date -Iseconds)",
  "fresh_pushed": $count,
  "skipped_duplicates": $skipped,
  "errors": $errors,
  "sources_polled": ["arxiv", "openreview", "cvf", "acl"]
}
EOF
```

## Anti-patterns

- ❌ Do NOT bypass dedup — duplicate paper-spotlight posts (Finding F1) are caused by exactly this
- ❌ Do NOT push more than `MAX_PER_TICK` — preserves human review bandwidth
- ❌ Do NOT mix authentication; secrets only via `~/.hermes/.env`
