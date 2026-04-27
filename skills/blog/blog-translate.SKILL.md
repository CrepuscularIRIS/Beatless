---
name: blog-translate
description: Translate English blog posts at ~/claw/blog/src/content/blogs/<slug>/ into Chinese pairs at ~/claw/blog/src/content/blogs/<slug>-zh/index.mdx with `draft: true`. Hermes-native flow with codex+gemini review chain (no self-review). Default writer = MiniMax M2.7 per Hermes config Blog/Media role.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [blog, translation, hermes-native, heterogeneous-review]
    related_skills: [codex-router, gemini-router]
---

# Blog Translation v2 — English → Chinese (canonical path + heterogeneous review)

This is the v2 rewrite that closes the audit findings F1 / F2 / F5:

- **F2 path mismatch fixed**: drafts now write to the SAME path the audit reads (`~/claw/blog/src/content/blogs/<slug>-zh/`) with `draft: true` so they're invisible in production builds but visible to `blog-maintenance` audit, breaking the 43-times re-translation loop.
- **F5 self-review fixed**: after the writer drafts, this skill calls `codex-router` for faithfulness review + `gemini-router` for fluency review. Only after both pass does the draft get committed.
- **F1 redundant work fixed**: skill checks Hermes memory for "already translated <slug>" before scheduling new work.

## Path conventions (canonical, post-F2 fix)

| Path | Role |
|---|---|
| `~/claw/blog/src/content/blogs/<slug>/index.mdx` | English source (live, draft: false) |
| `~/claw/blog/src/content/blogs/<slug>-zh/index.mdx` | **Chinese pair, output target**. `draft: true` until human review. Astro skips drafts in prod build. |

The legacy `~/obsidian-vault/blog-drafts/` is **deprecated**; do not write there. Existing 111 drafts in that location should be migrated by a one-shot `migrate-drafts.py` (separate task).

## When to invoke

- Cron prompt asks "translate any untranslated posts"
- Audit at `~/.hermes/shared/.blog-audit.md` lists English posts missing `-zh` pairs
- User says "translate the latest post" / "翻译最新博客"

## Procedure (Hermes Agent runs this end-to-end)

### Step 0 — memory check (skip if already translated)

```bash
# Hermes-side: check memory for prior translation
hermes memory query "blog-translate $SLUG" 2>/dev/null | grep -q DONE && {
  echo "SKIP: $SLUG already translated (per Hermes memory)"
  exit 0
}
```

### Step 1 — discover targets

```bash
BLOG=~/claw/blog/src/content/blogs

# Posts missing their -zh pair AND not draft themselves
for d in "$BLOG"/*/; do
  slug=$(basename "$d")
  case "$slug" in *-zh) continue;; esac
  [ -f "$BLOG/$slug/index.mdx" ] || continue
  grep -q "^draft: true" "$BLOG/$slug/index.mdx" 2>/dev/null && continue
  [ -d "$BLOG/${slug}-zh" ] && continue
  echo "$slug"
done
```

### Step 2 — generate translation

The Hermes-routed model (MiniMax M2.7) reads the English source, applies the FIVE COMMANDMENTS (below), and writes to `~/claw/blog/src/content/blogs/<slug>-zh/index.mdx` with frontmatter:

```yaml
---
title: "<Chinese title>"
description: "<Chinese description>"
publishDate: "<unchanged>"
updatedDate: "<unchanged>"
category: "<unchanged>"
tags: [<unchanged>]
language: zh
draft: true               # ← always true; human flips to false
---
```

### Step 3 — codex faithfulness review (异源审查 1/2)

Invoke `codex-router` skill with prompt:

```
Compare these two files for translation faithfulness:
  EN: ~/claw/blog/src/content/blogs/<slug>/index.mdx
  ZH: ~/claw/blog/src/content/blogs/<slug>-zh/index.mdx

Score 0-10 on:
  - All key claims preserved
  - All numbers / dates / names unchanged
  - All code blocks identical
  - All link URLs preserved (only display text translated)
  - No facts added or dropped

Output a single line: SCORE: <0-10>  REASON: <one sentence>
Pass threshold: 7.0
```

### Step 4 — gemini fluency review (异源审查 2/2)

Invoke `gemini-router` skill with prompt:

```
Read this Chinese translation and score Chinese fluency 0-10:
  ~/claw/blog/src/content/blogs/<slug>-zh/index.mdx

Specifically check:
  - No banned phrases (近日 / 引发广泛关注 / 意义重大 / 赋能 / etc.)
  - Paragraphs ≤4 lines
  - Reads natural in Chinese (not literal-translation feel)
  - Technical terms either preserved as English (LLM, RLHF) or have natural Chinese rendering

Output: VERDICT: pass|fail|flag  SCORE: <0-10>  REASON: <one sentence>
Pass threshold: 7.0
```

### Step 5 — verdict

- Both pass (≥ 7.0): keep draft, log `DONE: <slug>` to Hermes memory
- Either fail: rewrite the failing section, retry once. After second fail, mark `BLOCKED: <slug>` in memory and skip
- Either flag: keep draft but mark `NEEDS-HUMAN: <slug>` in memory; do NOT auto-promote

## Five Commandments (style constitution, unchanged)

1. **第一句话定生死** — first sentence must hook. Never start with "近日", "最近", "随着AI的发展".
2. **判断先于罗列** — preserve curatorial judgment.
3. **技术准确但不炫技** — explain or assume, don't pad with jargon.
4. **视觉呼吸感** — paragraphs ≤4 lines, bold key numbers, occasional blockquote/separator.
5. **诚实标注不确定性** — preserve hedging.

## Banned phrases (DO NOT use)

`近日` `日前` `近期` `引发了广泛关注` `引发广泛关注` `意义重大` `具有里程碑意义` `赋能` `降本增效` `数智化` `业界普遍认为` `不禁让人思考`

## Frontmatter rules (machine-checked)

- `title`, `description` translated to Chinese
- `publishDate`, `updatedDate`, `category`, `tags` unchanged
- `language: zh`
- `draft: true` (always — until human flips)

## NEVER

- Never write to `~/obsidian-vault/blog-drafts/` (deprecated post-F2)
- Never set `draft: false` automatically — only humans publish
- Never use the same model family to write AND review (per Regulations § Three Core Principles, R2)
- Never skip Step 3 / Step 4 — heterogeneous review is non-negotiable
