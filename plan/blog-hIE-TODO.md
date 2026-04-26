# Blog hIE Taxonomy — TODO List

**Created**: 2026-04-25
**Owner**: CrepuscularIRIS
**Source**: `~/claw/plan/blog-taxonomy-hIE.md` §9 + post-patch follow-ups

Tracks open work after the 2026-04-25 hIE taxonomy patch (blog-draft + blog-translate + audit-evolution all updated to emit/preserve `hIE` + `hero_image` frontmatter fields).

---

## ✅ Done 2026-04-25

- [x] 5-hIE asset library bootstrapped at `~/claw/blog/src/assets/hIE/` (15 images, 14 MB)
- [x] Canonical taxonomy doc at `~/claw/plan/blog-taxonomy-hIE.md`
- [x] Asset README at `~/claw/blog/src/assets/hIE/README.md`
- [x] `blog-draft.py` Stage 2 prompt emits `hIE` field
- [x] `blog-draft.py` Stage 3 prompt embeds `hIE` + `hero_image` in frontmatter
- [x] `blog-draft.py` Python `pick_hero_image()` (deterministic, no LLM tokens)
- [x] `blog-translate.py` reads source frontmatter for `hIE`/`hero_image`, preserves or defaults
- [x] `audit-evolution.md` frontmatter spec: `hIE: saturnus` + group-shot fallback hero

---

## 🔧 Manual one-time tasks

### TODO-1: Crop Saturnus from group shot

`~/claw/blog/src/assets/hIE/saturnus/` is empty because Saturnus has no public single-character imagery. The 5-hIE same-frame group shot at `~/claw/blog/src/assets/hIE/_shared/group-5hIE-arato-alphacoders-896444.jpg` (1920×1080) contains all 5 hIEs including Saturnus.

**Action**: Crop Saturnus's region from the group shot, save as `~/claw/blog/src/assets/hIE/saturnus/saturnus-cropped-from-group-896444.jpg`.

**Tools**:
- Manual: any image editor (GIMP, Photoshop, Krita, even Preview crop on macOS)
- Scripted: `pillow`-based Python script (~15 lines) — happy to write it on request
- Online: e.g. `croppola.com`

**Why deferred**: needs visual judgment (which region of the group is Saturnus). Auto-cropping by grid would produce 5 generic slices, not character-bounded crops.

**Acceptance**: file exists at the path above, ≥800px on the short edge, clearly shows Saturnus.

---

### TODO-2: Fill the Saturnus mood-substitute fallback

While TODO-1 is the canonical fix, an interim improvement is to also drop 1-2 mood-imagery files (gold-tone abstract, archival, structured-pattern — CC-BY from Unsplash) into `saturnus/` so meta-audit posts get something thematic even before the crop is done.

**Tag** these images with `mood-substitute: true` in their filename (e.g. `mood-substitute-gold-archive-unsplash-XXXX.jpg`) so they're flagged for replacement when canon imagery becomes available.

**Acceptance**: `saturnus/` has 1-2 mood-substitute images OR the crop from TODO-1 is in place.

---

### TODO-3: Backfill `hIE` + `hero_image` on existing 67 drafts

The 67+ drafts in `~/obsidian-vault/blog-drafts/` were produced before the taxonomy existed. They lack `hIE` and `hero_image` frontmatter fields.

**Options** (in order of effort):

1. **Don't backfill** — accept legacy. New drafts (post-patch) will have the fields. Old drafts get reviewed manually when committed to the live blog and the hIE/hero added at commit time. **Lowest effort, recommended.**

2. **Bulk default** — write a one-shot Python script that:
   - Walks `~/obsidian-vault/blog-drafts/*/index.mdx`
   - For each, infers hIE from the post's existing `category` field (if any) or defaults to `snowdrop`
   - Adds `hIE:` and `hero_image:` lines to frontmatter via `pick_hero_image()`
   - ~30 lines, idempotent, dry-run mode first
   
3. **LLM-assisted retag** — invoke Step on each draft to pick the best-fit hIE based on content. More accurate but expensive (67 LLM calls).

**Recommended**: **Option 1** (don't backfill) until the taxonomy proves useful in practice. Switch to option 2 if/when you start linking from the live blog's category index pages and need hIE present everywhere.

---

### TODO-4: Wallhaven assets (when network access is available)

Codex's image research surfaced 2 high-value Wallhaven URLs that were unreachable from this machine due to SSL block:

- `https://wallhaven.cc/w/p8kwjj` — Lacia 4K minimalism (3840×2160) → `lacia/`
- `https://wallhaven.cc/w/kw3xk6` — Methode + Lacia 1920×1080 → `methode/` and `_shared/`

**Direct CDN URLs** (work when you have network access):
```
https://w.wallhaven.cc/full/p8/wallhaven-p8kwjj.jpg
https://w.wallhaven.cc/full/kw/wallhaven-kw3xk6.jpg
```

**Action**: from a machine with Wallhaven access, run:
```bash
ASSETS=~/claw/blog/src/assets/hIE
curl -sSL -A 'Mozilla/5.0' -o "$ASSETS/lacia/wallhaven-p8kwjj-lacia-4k-minimalism.jpg"  https://w.wallhaven.cc/full/p8/wallhaven-p8kwjj.jpg
curl -sSL -A 'Mozilla/5.0' -o "$ASSETS/methode/wallhaven-kw3xk6-methode-lacia.jpg"  https://w.wallhaven.cc/full/kw/wallhaven-kw3xk6.jpg
```

---

### TODO-5: Source attribution table per file

`~/claw/blog/src/assets/hIE/README.md` summarizes attribution at the directory level. For long-term traceability, consider a per-file attribution sidecar:

```
src/assets/hIE/snowdrop/
├── 291936-beatless-lacia-monochrome-redjuice-snowdrop.jpg
├── 291936-beatless-lacia-monochrome-redjuice-snowdrop.json   ← sidecar
```

Sidecar JSON:
```json
{
  "source_url": "https://files.yande.re/image/.../yande.re%20291936%20...",
  "original_artist": "redjuice",
  "license": "fan-art / fair-use / non-commercial",
  "downloaded_at": "2026-04-25",
  "downloaded_by": "blog-translate.py / blog-draft.py first-run"
}
```

**Why deferred**: the README captures enough for now. Sidecar files are nice-to-have, not blocking.

---

## 🧠 Architectural follow-ups

### TODO-6: Shared Python module for `pick_hero_image()`

`pick_hero_image()` is duplicated in both `blog-draft.py` and `blog-translate.py` (~15 lines each, identical logic). Extract to `~/.hermes/scripts/_blog_taxonomy.py` and import.

**Why deferred**: duplication is currently <30 lines, low maintenance burden. Refactor when a third script needs the function.

---

### TODO-7: hIE coverage check in `audit-evolution`

The Daily Evolution audit currently checks 8 regulation dimensions (R1–R8). Consider adding **R9: hIE Frontmatter Compliance** — checks every new draft has `hIE` + `hero_image` fields, flags drafts that drift from the 5-way taxonomy.

**When to add**: after running 1-2 weeks of audit reports under the current 8-dim setup. If hIE drift is a real issue in the wild, promote it to R9. If not, skip.

---

### TODO-8: Live blog sidebar / tag pages per hIE

Astro lets you build per-tag index pages. Once the live blog has 5+ posts per hIE, build:

```
/blog/snowdrop/   ← all paper-spotlight posts
/blog/kouka/      ← all signal posts
/blog/saturnus/   ← all meta/audit posts
/blog/methode/    ← all engineering posts
/blog/lacia/      ← all bundle/digest posts
```

Each index page uses the hIE's hero from `_shared/` group shot or a representative single-character image. Visual coherence emerges from this.

**Status**: deferred until live blog has the volume to justify dedicated pages.

---

### TODO-9: Local PDF → Markdown pipeline (MinerU)

**Created**: 2026-04-26
**Goal**: build a local paper-text database to drop token cost on paper-spotlight drafting.

**Current state**: `paper-harvest.py` posts metadata + URL into Zotero; `zotero-to-obsidian.py` mirrors a stub note (`@<citekey>.md`) into `~/obsidian-vault/papers/literature/`. The stub carries the abstract, but `blog-draft.py` has no body text to work with — so when the LLM writes a paper spotlight, it depends on whatever it can re-derive from the abstract + hook.

**Direction**: insert a third stage between Zotero and the blog drafter:

```
paper-harvest.py        → Zotero (metadata + PDF URL, optionally PDF attachment)
zotero-to-obsidian.py   → ~/obsidian-vault/papers/literature/@<citekey>.md  (stub)
NEW: paper-fulltext.py  → MinerU on PDF → ~/obsidian-vault/papers/full-text/<citekey>.md
                                          (sectioned Markdown, equations preserved)
blog-draft.py           → reads stub + full-text, drafts spotlight without re-fetching
```

**Why MinerU**: SciPDF / GROBID / nougat all have PDF-to-Markdown angles, but MinerU is the
current SOTA for academic-paper structure preservation (figures, equations, tables). It
runs locally — no per-page LLM cost.

**Open design questions** (revisit when this gets prioritized):
- Disk footprint: ~9000 papers × ~2-5 MB Markdown each ≈ 20-45 GB
- PDF storage: Zotero already manages PDFs; do we duplicate locally or stream from Zotero?
- Trigger model: extract on Zotero-sync (eager) vs on blog-draft demand (lazy)
- Quality gate: MinerU output has known issues with multi-column rendering — need a
  validator before the body text is trusted by `blog-draft.py`

**Why deferred**: token cost on the current pipeline is acceptable (the writer model
is MMX, not Claude). MinerU adds value when the pipeline has to scale to thousands of
papers and we want spotlight drafts that go beyond what the abstract can reveal.
Revisit when the paper backlog crosses the threshold where re-fetching is the bottleneck.

---

## 📋 Status snapshot (auto-updateable)

```
Asset library:    ~/claw/blog/src/assets/hIE/   (15 files, 14 MB)
  _shared/  4 files     ✓
  snowdrop/ 3 files     ✓
  kouka/    3 files     ✓
  saturnus/ 0 files     ⚠ TODO-1, TODO-2
  methode/  3 files     ✓
  lacia/    2 files     ✓ (could add TODO-4)

Pipeline integration:
  blog-draft.py     ✓ Stage 2 emits hIE, Stage 3 embeds in frontmatter
  blog-translate.py ✓ preserves source hIE, defaults to snowdrop
  audit-evolution   ✓ frontmatter has hIE: saturnus + fallback hero

Backfill:
  67 existing drafts:  legacy (option 1: don't backfill, recommended)
```

---

## How to amend this TODO

Add new items as `### TODO-N: <title>` blocks. Mark done with `~~strikethrough~~` or move under "Done 2026-MM-DD". Keep the status snapshot at the bottom updated when asset counts change.
