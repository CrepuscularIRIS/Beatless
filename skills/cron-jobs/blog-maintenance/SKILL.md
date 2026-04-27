---
name: blog-maintenance
description: "Audit the Astro blog at ~/claw/blog/ for missing zh translations, broken links, stale posts, and one-off content fixes. v2 reads from canonical path ~/claw/blog/src/content/blogs/ and treats draft:true entries as 'translated, awaiting human flip' so the audit no longer false-positives on translated drafts (closes Finding F2)."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [blog, audit, maintenance, hermes-native]
    related_skills: [blog-translate, claude-code-router]
---

# blog-maintenance — Hermes-native blog audit

Replaces `~/.hermes/scripts/blog-maintenance.py`. Runs every 12h. Now correctly recognizes `draft: true` Chinese pairs as already-translated, breaking the 43x re-translation loop (Finding F2 from daily-evolution audit).

## Procedure

### Step 1 — audit canonical path (post-F2 fix)

```bash
BLOG=~/claw/blog/src/content/blogs

# A post is "missing zh" iff:
#   - English source exists at $BLOG/<slug>/index.mdx with draft:false
#   - $BLOG/<slug>-zh/ does NOT exist OR exists but has no index.mdx
# Note: a draft:true zh pair COUNTS as translated (waiting for human review).

MISSING_ZH=()
for d in "$BLOG"/*/; do
  slug=$(basename "$d")
  case "$slug" in *-zh) continue;; esac
  src="$BLOG/$slug/index.mdx"
  [ -f "$src" ] || continue
  grep -q "^draft: true" "$src" 2>/dev/null && continue
  if [ ! -f "$BLOG/${slug}-zh/index.mdx" ]; then
    MISSING_ZH+=("$slug")
  fi
done
```

### Step 2 — staleness check (≥ 60 days, no update)

```bash
STALE=()
for d in "$BLOG"/*/; do
  src="$d/index.mdx"
  [ -f "$src" ] || continue
  age_days=$(( ($(date +%s) - $(stat -c %Y "$src")) / 86400 ))
  if [ "$age_days" -ge 60 ]; then
    STALE+=("$(basename "$d")")
  fi
done
```

### Step 3 — broken link audit (sample, not exhaustive)

For each post modified in last 7d, extract external URLs and HEAD-check the top-10 most-recent. Mark dead. Don't auto-fix — only report.

### Step 4 — write audit receipt

```bash
cat > ~/.hermes/shared/.blog-audit.md <<EOF
# Blog Audit — $(date -Iseconds)

missing-zh: ${#MISSING_ZH[@]}
stale: ${#STALE[@]}

## Missing Chinese pairs (canonical path scan)
$(printf '- %s\n' "${MISSING_ZH[@]}")

## Stale (>= 60 days)
$(printf '- %s\n' "${STALE[@]}")
EOF
```

### Step 5 — Hermes memory + optional remediation

```bash
true  # AGENT-ACTION: record to memory tool: "blog-maintenance ts:$(date -Iseconds) missing_zh:${#MISSING_ZH[@]} stale:${#STALE[@]}"

# Optional: if missing_zh > threshold, can chain into blog-translate skill
# (kept manual for now — skip auto-promote per Regulations).
```

## Anti-patterns

- ❌ Do NOT scan `~/obsidian-vault/blog-drafts/` for missing-zh — that's the legacy path that caused F2
- ❌ Do NOT auto-publish (flip `draft:true` → `false`) — only humans publish
- ❌ Do NOT count a post with `draft:true` zh pair as "missing" — it's awaiting review, not missing
