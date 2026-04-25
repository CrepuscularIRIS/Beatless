# Blog Taxonomy — 5 hIE Categories (Beatless mapping)

**Created**: 2026-04-25
**Owner**: CrepuscularIRIS
**Source archive**: `/home/lingxufeng/claw/Beatless/archive/v2-deprecated/agents/{kouka,snowdrop,saturnus,methode,lacia}/IDENTITY.md`
**Asset library**: `/home/lingxufeng/blog/src/assets/hIE/`

---

## 1. The 5 hIEs (recovered canonical from Beatless v2 archive)

| hIE | Type | Vibe (verbatim from IDENTITY.md) | Marker |
|---|---|---|---|
| **Kouka** | hIE-001 | high pressure stop loss, fast decision, deadline first | red |
| **Snowdrop** | hIE-002 | counterfactual exploration, assumption challenge, breakthrough | snow |
| **Saturnus** | hIE-003 | governance, auditability, risk gate | gold |
| **Methode** | hIE-004 | engineering execution, artifact closure, automation | tool |
| **Lacia** | hIE-005 | symbiotic guidance, narrative convergence, human friendly | black |

These map to characters from the Beatless light novel (長谷敏司) and the OpenClaw v2 agent constellation. Each is a Beatless humanoid AI ("hIE"). The taxonomy reuses these as blog category markers.

---

## 2. Blog category ↔ hIE mapping (canonical)

| hIE | `category` field | Post types |
|---|---|---|
| **Snowdrop** ❄️ hIE-002 | `paper-spotlight` | High-quality papers, paradigm-challenging research, novel methods, breakthrough findings |
| **Kouka** 🔴 hIE-001 | `signal` | News curation, product launches, breaking events, time-sensitive announcements |
| **Saturnus** 🟡 hIE-003 | `meta` | Daily Evolution audits, regulation reports, security reviews, system health checks |
| **Methode** 🛠 hIE-004 | `engineering` | Tool builds, infrastructure, framework dives, code-heavy implementations |
| **Lacia** ⚫ hIE-005 | `bundle` / `digest` | Paper Bundles, Weekly Digests, longform synthesis connecting multiple sources |

When a post fits multiple categories, choose the hIE whose vibe is the dominant intent. `_shared/` imagery is for taxonomy index / multi-hIE posts.

---

## 3. Frontmatter contract

Every post mdx must declare:

```yaml
---
title: "..."
description: "..."
publishDate: "YYYY-MM-DD"
category: paper | signal | meta | engineering | bundle | digest    # one of the 5
hIE: snowdrop | kouka | saturnus | methode | lacia                  # canonical taxonomy
hero_image: /assets/hIE/<hIE>/<filename>.jpg                        # absolute Astro path
tags: [...]
language: en | zh
draft: true | false
sources: ["url1", "url2"]                                          # for image attribution
confidence: high | medium | low
---
```

`category` and `hIE` MUST be consistent per the table in §2.

---

## 4. Asset path convention

```
~/blog/src/assets/hIE/
├── _shared/        # 5-hIE same-frame, multi-character, generic Beatless
├── snowdrop/       # paper-spotlight imagery
├── kouka/          # signal/news imagery
├── saturnus/       # meta/audit imagery (currently EMPTY — see §6)
├── methode/        # engineering imagery
├── lacia/          # bundle/digest imagery
└── README.md       # source attribution + license stance
```

In post mdx, reference as: `/assets/hIE/<hIE>/<filename>` (Astro resolves from `src/assets/`).

---

## 5. Hero-image selection rules

For a new draft:

1. Decide hIE based on §2 category mapping.
2. Pick from `assets/hIE/<hIE>/` — round-robin to avoid repeating same hero across consecutive posts of the same category.
3. If `<hIE>/` is empty (currently only Saturnus), fall back to `_shared/group-5hIE-arato-alphacoders-896444.jpg` (the 5-hIE same-frame includes all characters).
4. Add the original source URL to `sources:` frontmatter for attribution.
5. NEVER hot-link to external CDNs; always use the local asset.

---

## 6. The Saturnus gap

Saturnus has very limited public single-character imagery (Codex's research confirmed yande.re returns 0 hits for `saturnus` tag; AlphaCoders Beatless category is Lacia-dominated).

**Default fallback**: meta-audit posts use `_shared/group-5hIE-arato-alphacoders-896444.jpg` (Saturnus is in frame).

**Resolution paths** (in order of preference):
1. Crop Saturnus's region from the group shot, save as `saturnus/saturnus-cropped-from-group-896444.jpg`. Manual one-time crop.
2. Pixiv / Twitter `#セラタス` `#Saturnus_Beatless` search (requires login, can't be cron-driven).
3. Mood-substitute (gold-tone abstract, archival, structured-pattern). Tag with `mood-substitute: true` in frontmatter so it's flagged for future replacement.

Until saturnus/ is filled with proper imagery, do NOT auto-generate fake Beatless-style art via MMX — per Codex's reasoning, AI-substituted character art looks worse than honest mood-imagery.

---

## 7. Where this plugs into the cron pipeline

| Script | Change | Status |
|---|---|---|
| `~/.hermes/scripts/blog-draft.py` Stage 2 (Step extraction) | Add `hIE` field to extracted JSON struct (Step picks 1 of 5 based on paper nature) | TODO |
| `~/.hermes/scripts/blog-draft.py` Stage 3 (MMX writing) | Receives `hIE` → adds to frontmatter + selects hero from `assets/hIE/<hIE>/` round-robin | TODO |
| `~/.hermes/scripts/blog-translate.py` | Mirror source post's `category` → `hIE` field (translation preserves original taxonomy) | TODO |
| `~/.claude/commands/audit-evolution.md` | Add `hIE: saturnus` to its frontmatter (auditor → governance) | TODO |
| New: `~/.hermes/scripts/blog-source-image.py` | Round-robin selector for hero images per hIE; called by both draft scripts | TODO |

---

## 8. Sources & attribution stance

All images currently in the library are derived from public anime image boards (yande.re, AlphaCoders) where original artists are tagged in the URL/metadata. Most prominent original artist: **redjuice / Kuwashima Rei** (Beatless original character designer).

**Per-post obligation**: every post embedding one of these images MUST cite the original source URL in the `sources:` frontmatter list. The `~/blog/src/assets/hIE/README.md` keeps the canonical artist-attribution table for cross-referencing.

**Use stance**: personal blog, non-commercial, transformative curation (using as taxonomy markers, not standalone reproduction). When in doubt, use `_shared/` group shots rather than single-character keyvis.

---

## 9. Open work (post-2026-04-25)

- [ ] Crop Saturnus from group shot (1-time manual)
- [ ] Patch `blog-draft.py` Stage 2 to emit `hIE` field
- [ ] Patch `blog-draft.py` Stage 3 to use hero image
- [ ] Write `blog-source-image.py` round-robin selector
- [ ] Update `audit-evolution.md` frontmatter to include `hIE: saturnus`
- [ ] Backfill `category` + `hIE` + `hero_image` on the 67+ existing drafts in `~/obsidian-vault/blog-drafts/`
