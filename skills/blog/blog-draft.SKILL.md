---
name: blog-draft
description: "Draft new bilingual (en + zh) blog posts from Obsidian vault sources (papers and feeds). v2 writes drafts directly to ~/claw/blog/src/content/blogs/<slug>/ and <slug>-zh/ with draft:true frontmatter (canonical path; old ~/obsidian-vault/blog-drafts/ deprecated). Picks Signal Post / Paper Spotlight / Milestone Post per the AI blog writing template guide."
version: 2.0.0
author: Hermes Agent + CrepuscularIRIS
platforms: [linux, macos]
prerequisites:
  env: [MMX_API_KEY, MMX_BASE_URL]
metadata:
  hermes:
    tags: [blog, drafting, bilingual, curation, hermes-native]
    template_guide: /home/lingxufeng/claw/plan/AI博客写作模板指南.md
    style_version: v1.0
    related_skills: [blog-translate, codex-router, gemini-router]
---

# Blog Drafting — New Bilingual Posts (T2)

Drafts NEW posts (not translations) from curated source material. Output is **bilingual** — every post produces both `<slug>/` (English) and `<slug>-zh/` (Chinese) under `~/obsidian-vault/blog-drafts/`. Human reviews + commits.

## Source material

| Path | Content type | How to use |
|---|---|---|
| `~/obsidian-vault/papers/literature/@*.md` | Zotero-synced paper notes (24 papers as of 2026-04-25) | Source for **Paper Spotlight** template |
| `~/obsidian-vault/feeds/<YYYY-MM-DD>/` | Daily feed snapshots from feed-crawl.py (43 days as of 2026-04-25) | Source for **Signal Post** / **Flash Signal** templates |
| `~/.hermes/shared/.blog-audit.md` | Latest blog audit (rewrite candidates) | Identify stale posts to refresh |

## Three templates (choose one per draft)

From `/home/lingxufeng/claw/plan/AI博客写作模板指南.md` § 二/三/四.

### A. Signal Post (news curation)

Standard sections: TL;DR → 发生了什么 → 为什么这件事值得关注 → 我的保留意见 → 来源.

Use when: A feed item is a single newsworthy event you want to commentary-curate. ~500-1000 字.

### B. Paper Spotlight (paper curation)

Standard sections: 一句话摘要 → 为什么选这篇 → 核心方法（3 分钟版） → 关键结果（表格） → 局限与未回答的问题 → 延伸线索.

Use when: A paper from `papers/literature/` deserves a deep recommend. ~800-1500 字.

### C. Milestone Post (major events)

Standard sections: 事件概述 → 技术解读 → 历史坐标（之前/本次/之后） → 多方视角 → 关键来源.

Use when: A confirmed major industry event deserves a full chronicle. ~1500-3000 字. Use sparingly.

## Bilingual requirement (v2 canonical paths)

Every draft produces **two files**, both with `draft: true` frontmatter:
- `~/claw/blog/src/content/blogs/<slug>/index.mdx` — English version
- `~/claw/blog/src/content/blogs/<slug>-zh/index.mdx` — Chinese version

Astro production builds skip `draft: true` entries, so writes are safe. Human flips `draft: false` to publish.

Same content, both written from scratch (not translated). The agent writes them as a pair, not English-then-translate. Both versions independently obey the five commandments.

**Memory check first** (avoids duplicate `luo2025beyond` / `luo2025beyondb`-style collisions):

```bash
SLUG_HINT="<author><year><word>"   # e.g. luo2025beyond
hermes memory query "blog-draft $SLUG_HINT" 2>/dev/null | grep -q DONE && {
  echo "SKIP: $SLUG_HINT already drafted"; exit 0
}
```

After successful write, log: `hermes memory write "blog-draft $SLUG DONE"`.

## Heterogeneous review (v2, before declaring done)

Before final write, invoke at least one external pass via `codex-router` or `gemini-router`:
- For Paper Spotlight → `codex-router` checks correctness vs paper PDF
- For Signal Post → `gemini-router` checks tone + factual claims vs sources
- Milestone Post → both

## Slug convention

`<YYYY-MM-DD>-<topic-slug>` for time-anchored posts (signal/milestone), or `<topic-slug>` for evergreen papers.

## Frontmatter (mandatory, both en and zh)

```yaml
---
title: "..."
description: "..."
publishDate: "YYYY-MM-DD"
updatedDate: "YYYY-MM-DD"
category: signal | paper | milestone | bundle
tags: [tag1, tag2]
language: en  # or "zh" in the -zh pair
draft: true
sources: [url1, url2]
confidence: high | medium | low
status: complete | draft | needs-update
---
```

## Style constitution — same five commandments as `blog-translate`

1. 第一句话定生死 (no "近日"/"最近"/"随着AI的发展")
2. 判断先于罗列 (curatorial judgment, not aggregation)
3. 技术准确但不炫技 (explain or assume, don't pad)
4. 视觉呼吸感 (≤4-line paragraphs, bold key numbers)
5. 诚实标注不确定性 (preserve hedges)

## Banned phrases — same list as `blog-translate`

`近日 / 日前 / 近期 / 引发了广泛关注 / 意义重大 / 赋能 / 降本增效 / 数智化 / 业界普遍认为 / 不禁让人思考`

## Workflow

1. **Pick a source.** Either:
   - Most recent `~/obsidian-vault/feeds/<date>/` for Signal Post.
   - A `papers/literature/@*.md` not yet covered by any blog post for Paper Spotlight.
   - Audit-flagged stale post for refresh.

2. **Decide template.** Single news event → Signal. Single paper → Paper Spotlight. Confirmed industry shift → Milestone.

3. **Decide slug.** `<YYYY-MM-DD>-<topic>` or `<topic>` (evergreen).

4. **Write English version** at `~/obsidian-vault/blog-drafts/<slug>/index.mdx`. Apply the five commandments. Use the section template literally (don't merge sections).

5. **Write Chinese version** at `~/obsidian-vault/blog-drafts/<slug>-zh/index.mdx`. Same content, native Chinese (not translated). Apply the same five commandments. Banned phrases forbidden.

6. **Self-audit.** Run the checklist below. If anything fails, fix before declaring done.

## Self-audit checklist (must run before declaring done)

For BOTH the en and zh files:

- [ ] Output starts with `---` frontmatter (no `<think>` blocks leaked).
- [ ] `language` field correct (`en` or `zh`).
- [ ] `draft: true` set.
- [ ] Title hooks (no banned-phrase opener).
- [ ] Body contains the agent's own curatorial judgment (delete-test: if you remove the agent's commentary, does the post still have unique value? If no, fail.).
- [ ] All technical terms explained or known to the audience.
- [ ] Paragraphs ≤4 lines.
- [ ] No banned phrases (grep the output).
- [ ] Links resolve (sources field populated).
- [ ] Confidence field honestly set (high only if multiple primary sources confirm).
- [ ] If image references included, the images themselves are accessible.

## NEVER

- Never write directly to `~/claw/blog/src/content/blogs/`. Always to `~/obsidian-vault/blog-drafts/`.
- Never write English-only or Chinese-only — both are mandatory.
- Never use Claude/Codex/Gemini in the writing path. Hermes-routed models only.
- Never auto-commit. Human reviews → manual commit.
- Never hallucinate sources. Every `sources:` URL must come from the actual feed/paper note.

## Output report

After drafting, output a one-line summary:
```
Draft: <slug> (template=<signal|paper|milestone>, en=<wc> words, zh=<chars> 字)  →  ~/obsidian-vault/blog-drafts/
```
