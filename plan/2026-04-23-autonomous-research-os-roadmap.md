# Autonomous Research OS — Roadmap

**Created**: 2026-04-23
**Owner**: CrepuscularIRIS (maintained by Hermes Agent + Claude Code)
**Supersedes / extends**: `2026-04-23-personal-research-automation-system.md`
**Status**: decisions locked 2026-04-23 — ready to execute

---

## 0. The direct question: what first?

> *"Should we first focus on building and organizing the local knowledge base?"*

**Yes. That's the right call.** Everything downstream is blocked on it.

| Downstream capability | Blocked by |
|---|---|
| Blog = curated, high-quality outputs | Needs a body of source material to curate FROM |
| `/exp-*` autonomous research | Needs reference papers to ground hypotheses and avoid reinventing |
| Daily evolution loop | Needs historical artifacts (notes, exp runs, papers read) to reflect on |
| Long-horizon research-direction tracking | Needs continuous timestamped inputs |

If we try to run the blog or exp pipeline on today's empty vault, we'll get the exact "messy, outdated, redundant" failure mode you just flagged. The KB is the foundation dependency.

---

## 1. Architecture (what gets written where)

```
┌──────────────────────────────────────────────────────────────┐
│ RAW / CONTINUOUS                                             │
│  ~/obsidian-vault/papers/          — arXiv + top-conf PDFs   │
│  ~/obsidian-vault/papers/notes/    — one .md per paper       │
│  ~/obsidian-vault/feeds/           — blog/report snapshots   │
│  ~/obsidian-vault/experiments/     — every exp run, raw       │
│  ~/obsidian-vault/daily/           — daily reflection outputs │
└──────────────────────────────────────────────────────────────┘
                 │           │            │
                 ▼           ▼            ▼
         ┌─────────────┬──────────┬────────────────┐
         │ CURATION LAYER (weekly, human-in-loop)  │
         └─────────────┬──────────┬────────────────┘
                       ▼          ▼
        ┌──────────────────┐   ┌──────────────────────┐
        │ BLOG (curated)   │   │ EXP (validated)      │
        │ ~/claw/blog      │   │ experiments/ results │
        │ — Engineering    │   │   + findings that    │
        │ — Research       │   │   survived scrutiny  │
        │ — Interpretation │   │                      │
        └──────────────────┘   └──────────────────────┘
```

**Rule of thumb**: raw things accumulate automatically; curated things need a deliberate pass. Never write raw harvest output directly to the blog.

---

## 2. Component inventory (what we already have vs. what we need)

| Component | Status | Notes |
|---|---|---|
| Obsidian vault scaffold | ✅ installed | `~/obsidian-vault/` with `papers/`, `methodology/`, `experiments/`, `blog-drafts/` |
| Hermes Agent + cron | ✅ running | 4 jobs (GitHub response/PR, auto-research, blog-maintenance) |
| Claude Code commands | ✅ ready | `/exp-*`, `/blog-maintenance`, `/pr-followup`, `/github-pr` |
| MiniMax skill pack + `mmx` CLI | ✅ working | Verified image-gen end-to-end |
| GWS (gmail/drive/docs/calendar) skills + `gws` CLI | ✅ installed | Auth not yet run — needed for Drive-based paper sync |
| Model routing (Kimi/Step/MiniMax) | ✅ verified | Env hygiene fixed this session |
| Zotero library | ✅ in use (source-of-truth) | **Kept** — PDFs, metadata, annotations, cross-device sync |
| Zotero → Obsidian sync (Better BibTeX + mdnotes) | ❌ not wired | **Phase 1.1** |
| Multi-source paper harvester (arXiv + top-conf + PapersWithCode + HF Papers + GitHub Trending → Zotero) | ❌ missing | **Phase 1.2 primary** |
| Blog/report feed crawler (direct to Obsidian) | ❌ missing | **Phase 1.3 secondary** |
| Paper-note generation loop | ❌ missing | **Phase 2** |
| KB → blog curation workflow | ❌ missing | **Phase 2** |
| `/exp-discover` using KB as ground | ⚠ exists, not wired to KB | **Phase 3** |
| Daily evolution loop (Opus 4.7 reflection) | ❌ missing | **Phase 4** |
| Multi-direction progress dashboard | ❌ missing | **Phase 5** |

---

## 3. Phased plan

Each phase ends with a visible, testable artifact. Don't start phase N+1 until phase N's artifact exists.

### Phase 1 — Knowledge Base Foundation (week 1)

**Goal**: Zotero remains the source-of-truth library. Obsidian becomes the thinking layer. Papers land in Zotero, structured notes (not PDFs) sync into Obsidian, where the graph lives. Feeds and exp logs live natively in Obsidian.

#### 1.0 Architecture — Zotero as source layer, Obsidian as thinking layer

| Layer | Tool | Holds | Does NOT hold |
|---|---|---|---|
| Source | Zotero | PDFs, bibliographic metadata, DOI / arXiv ids, highlights, citekeys, cross-device sync | Interpretive notes, wiki-links, methodology |
| Thinking | Obsidian | Literature notes (per paper), methodology notes, exp logs, cross-paper synthesis, direction tracking, blog drafts | PDFs (referenced via citekey only), full metadata (referenced via citekey) |

**Rule**: a paper's PDF never enters the Obsidian vault. The vault stores the note; the note references the paper by Zotero citekey. This keeps the vault under 1 GB even at 100 GB+ paper corpus.

#### 1.1 Zotero → Obsidian sync

1. **Zotero Better BibTeX plugin** — canonical citekey format per entry.
2. **Mdnotes / zotero-obsidian-import** — auto-export each new Zotero entry's highlights + metadata to `~/obsidian-vault/papers/literature/@<citekey>.md`.
3. The generated note has a `Source PDF:` link that opens the PDF in Zotero (not the vault).
4. Hermes cron job `zotero-sync.py` (every 180m) triggers the export when new entries arrive.

#### 1.2 Multi-source paper harvester

Papers flow **into Zotero first** (source layer), not directly into Obsidian. Hybrid ingestion per your directive — no single source covers everything at scale.

| Source | Entry point | Priority |
|---|---|---|
| arXiv | API listings for cs.LG / cs.CL / cs.CV / cs.AI (2025+) | primary |
| Top-conf (NeurIPS / ICML / ICLR / ACL / COLM / AAAI / KDD / CVPR) | OpenReview API + conference-hosted indexes | primary |
| **Papers with Code** | `paperswithcode.com/api/v1/papers/` — gives paper + code link + SOTA tracking | **new** |
| **Hugging Face Papers** | `huggingface.co/api/papers` — daily curated top picks | **new** |
| **GitHub Trending** | scrape `github.com/trending/python?since=daily` — surface repos citing arXiv ids in README | **new** |

`paper-harvest.py` (every 360m) queries each source, dedupes by arXiv id / DOI / GitHub repo URL, and **adds to Zotero via `zotero-api-client`** (NOT directly to Obsidian). The Zotero→Obsidian sync in §1.1 carries the note into the thinking layer.

#### 1.3 Feed crawler (native Obsidian — not via Zotero)

Blog posts, company announcements, and technical reports are ephemeral content that shouldn't clutter Zotero. These live directly in `~/obsidian-vault/feeds/<yyyy-mm-dd>/<slug>.md` via `feed-crawl.py` (every 720m) using the installed `blogwatcher` skill.

Sources: Anthropic / OpenAI / Google DeepMind / Moonshot / Zhipu / MiniMax / ByteDance Seed / Meta FAIR blogs; selected researcher Substacks; OpenReview activity feed.

#### 1.4 KB frontmatter schema

Every note in the vault has:

```yaml
title: ...
source: zotero | feed | report | exp
citekey: <zotero-citekey>        # only if source == zotero
url: ...
date: 2026-04-23
status: unread | read | summarized | cited | blogged
direction: attention | reasoning | agent-infra | training | data | ...
tags: [...]
related: [[@other-citekey]]
hook: ""  # filled during curation — "why this matters to me"
```

Obsidian templates in `~/obsidian-vault/.obsidian/templates/` so new-note creation is one keystroke.

#### 1.5 `/kb-status` command

`hermes chat -q "/kb-status"` returns: unread count per direction, stale summarized-but-not-blogged entries, papers cited in your own drafts, last harvester run time.

**Exit criterion**: after 3 days of cron runs, ≥50 Zotero entries with matching Obsidian notes, ≥30 feed snapshots in `~/obsidian-vault/feeds/`, `/kb-status` returns clean output.

---

### Phase 2 — KB → Blog Curation (week 2)

**Goal**: the blog stops generating content from scratch and starts shipping curated interpretations of what's already in the KB.

1. **Weekly curation session** (human-in-loop, Friday)
   - You (the user) open the Obsidian vault, walk through `status: unread` papers, mark the keepers with `status: summarized`.
   - For keepers, add a one-line `hook:` — the "why is this interesting to me" note.

2. **`/blog-curate` command** (new Claude Code command)
   - Reads the vault's `status: summarized` entries with populated `hook:` that aren't yet `status: blogged`.
   - For each, proposes a blog post outline (3-section template — Problem / How It Works / Why It Matters).
   - Waits for user ACK per post.
   - On ACK, writes the bilingual EN + ZH pair into `~/claw/blog/src/content/blogs/<slug>/` and its `-zh` partner.
   - Sets the KB note's `status: blogged` and adds `blog_url: ...` pointing at the eventual post.

3. **Image sourcing** — per your direction, **web-sourced images are fine; no need to always generate via MiniMax**. Priority order:
   - Web-sourced CC0 / CC-BY / fair-use anime/manga key-visual imagery via a `/blog-source-image <keyword>` helper that grabs a few candidates for you to pick from.
   - Existing anime/manga reference libraries you already own (Beatless, Fate, etc.) in `~/claw/blog/src/assets/reference/` once curated.
   - MiniMax `mmx` generation as fallback when nothing suitable is found.
   - The 3-section template (Problem / How It Works / Why It Matters) is the **baseline but not rigid** — the blog stays flexible as long as it's engaging, visually appealing, and attention-grabbing. Deviate when the topic demands.

4. **Retire the autonomous-writing blog cron** — current `blog-maintenance.py` writes new posts on its own schedule, which is exactly how you get "messy, outdated, redundant." Change its role to **audit-only**: detect stale posts (by date + tag), flag them to `~/.hermes/shared/.blog-audit.md`, and STOP. Writing stays human-triggered via `/blog-curate`.

**Exit criterion**: one full week of Friday-curated blog posts shipped end-to-end (KB entry → `/blog-curate` → committed to blog repo). Zero new blog posts created outside this flow.

---

### Phase 3 — AutoResearch (exp) wired to the KB (weeks 3–4)

**Goal**: `/exp-*` uses the KB as its literature substrate; findings flow back into the KB.

1. **`/exp-discover` extension** — first tool call is now `kb_search <topic>` against the local vault. Replaces unreliable WebSearch as the primary grounding step. WebSearch remains a fallback for 2026 material not yet in KB.

2. **Experiment log writeback** — `/exp-run` writes each round's plan + findings to `~/obsidian-vault/experiments/<project>/<date>-round-N.md`. Links back to papers cited via wikilinks.

3. **Exp → blog promotion** — only experiments that pass a gate ("the finding generalizes / reproduces / makes it into a paper draft") get surfaced on the blog via `/blog-curate`. No raw experiment runs in the blog.

4. **Batch paper download priority** — before kicking off any exp, run a targeted arXiv/conf harvest scoped to the experiment's topic. This ensures the exp has recent literature grounding.

**Exit criterion**: one full exp cycle from KB-grounded hypothesis → dual-GPU run → findings note in KB → (optional) curated blog post. Running loop autonomous for ≥48h without intervention.

---

### Phase 4 — Daily Evolution Loop (week 3, in parallel with Phase 3)

This is the self-improvement mechanism you described. Design follows.

#### 4.1 What "a day's work" means

The system's observable surface every 24h:

- Git commits in `~/claw/*`
- Hermes cron run results + status JSONs in `~/.hermes/shared/`
- New files in `~/obsidian-vault/`
- Claude Code session transcripts
- GitHub PRs opened/merged/closed
- Hermes memory entries created/updated

The evolution job consumes all of these.

#### 4.2 The job

**Trigger**: Hermes cron, daily 03:30 ET (after all cron jobs have had their first-of-day runs).

**Script**: `~/.hermes/scripts/daily-reflect.py`.

**Model**: Claude Opus 4.7 via `claude -p --model opus-4-7`. Depth over speed; one run per day. **No budget cap for now** per user direction — cost optimization deferred until the rest of the system pipeline is fully built out.

**Input**: structured digest (see 4.3) written by the script BEFORE invoking claude.

**Prompt skeleton** (`/daily-reflect` command):

```
You are the evolution layer of the Autonomous Research OS.
Today's digest is at /tmp/daily-reflect-<date>.md. Read it.

Produce 4 artifacts in ~/obsidian-vault/daily/<date>/:
  SUMMARY.md     — what happened today, 8 bullets max
  ISSUES.md      — problems observed, ranked by severity (low/med/high), with evidence pointers
  IMPROVEMENTS.md — proposals to address each issue, each with effort estimate (S/M/L)
  NEXT_STEPS.md  — the 3 things we should DO tomorrow, ranked, with concrete file paths

Rules:
- Every claim references a file or a commit sha. No unsupported assertions.
- "Problem" means something that will bite us later if not fixed. Skip cosmetic.
- "Improvement" must name a specific file to change or a specific command to run.
- If the system had a quiet day (<5 commits, no cron failures, no new PRs), write
  minimal artifacts and end with "QUIET_DAY: YES". Don't invent work.
```

#### 4.3 What goes into the digest

`daily-reflect.py` builds the digest by running, in order:

1. `git -C ~/claw/<each-repo> log --since=24h --stat` — raw commit history.
2. `cat ~/.hermes/shared/.last-*-status` — cron job results from the day.
3. `find ~/obsidian-vault -mtime -1 -name "*.md"` — new/changed KB notes.
4. `gh search prs --author=CrepuscularIRIS --state=all --sort=updated --limit=20` — PR activity.
5. `hermes sessions list --since 24h` — session history.
6. `journalctl --user -u hermes-gateway --since "24 hours ago"` — gateway log tail, filtered.

Each section capped at ~1000 tokens; truncated with a "…truncated, see <file>" pointer so Opus can pull the full source if needed.

#### 4.4 What happens after reflection

- **Read-only default**: artifacts land in the vault. No auto-commit, no auto-PR.
- **Weekly review** (Sunday): you read 7 days of `NEXT_STEPS.md`, pick what to act on, and open issues or run `/exp-init` as appropriate.
- **Opt-in auto-fix** (scope per user direction):
  - **Primary target: Hermes** — `~/.hermes/scripts/*.py`, `~/.hermes/config.yaml`. The Opus agent may apply `[auto:safe]` to trivial reversible changes here; a follow-up cron at 04:00 commits and pushes.
  - **Optional target: Blog** — `~/claw/blog/` for content fixes, typo corrections, stale-link cleanup, frontmatter repairs. Opens PR against `main` (doesn't merge).
  - **Never auto-touched**: `~/claw/Beatless/`, `~/claw/pua/`, anything under `~/.claude/`, experiment workspaces under `~/research/`, and the Zotero library. Human review required.

#### 4.5 Evolution of the evolution loop

Meta-reflection runs **weekly** on Sunday, Opus again, consuming the 7 daily files. Output: `~/obsidian-vault/daily/<week>/WEEKLY-SYNTHESIS.md`. This is the signal that decides whether the framework itself needs restructuring (e.g., if the same issue shows up 5 days in a row, it's a structural problem, not a daily fix).

---

### Phase 5 — Multi-direction progress tracking (week 4+)

Once Phases 1–4 are ticking, the blog grows a **Directions** section: one page per research lane (attention, reasoning, agent-infra, etc.). Each direction page is auto-regenerated weekly from:

- KB notes tagged with that `direction:`
- Blog posts in that lane
- Exp runs touching that lane

Rendered as: recent paper list → posts published → open questions → current hypothesis → status timeline. This is how the blog graduates from a personal writeup site into a visible research dashboard.

---

## 4. What this means for the agent stack

| Layer | Role |
|---|---|
| You | Set priorities, curate, approve. Primary orchestration via Hermes chat. |
| Hermes Agent | Scheduling, memory, routing, simple synthesis. Kimi K2.6 as backbone. |
| Claude Code (Sonnet) | Day-to-day execution — commands, edits, PR pipelines, blog curation. |
| Claude Code (Opus 4.7) | Daily + weekly reflection only. High-signal, low-volume. |
| Step 3.5 Flash | Hermes subagents for routine work. |
| MiniMax M2.7 | Blog writing when delegated. Image-gen when needed. |

The user's lever is **Hermes chat**. Hermes knows the whole system state (via memory + status files) and is the single interface you address in natural language. Claude Code is called by Hermes (or by you directly) for execution.

---

## 5. Immediate next actions (ordered execution queue)

Order matters. Manual-guided first, automation later.

1. **[Phase 1.0] Decide Zotero → Obsidian sync tool** — evaluate Better BibTeX + mdnotes vs zotero-obsidian-import. Pick one, document the citekey format we lock to. ~30min.

2. **[Phase 1.1] Wire existing Zotero library → Obsidian** — before any new harvest. Sync whatever already lives in Zotero so the vault isn't empty when the harvester kicks in. Verifies the pipeline works on real data. ~1h depending on library size.

3. **[Phase 1.4] Write vault frontmatter schema + Obsidian templates** — the `@<citekey>.md` template for literature notes, feed note template, exp-log template. ~45min.

4. **[Phase 1.2] Write `paper-harvest.py`** — arXiv + top-conf first (simplest APIs), then PapersWithCode, HuggingFace Papers, and GitHub Trending. Dedupe, push into Zotero via `zotero-api-client`. Manual run first, inspect output. ~3h.

5. **[Phase 1.2 cont.] Register harvester as Hermes cron** once output is clean. `hermes cron add ... every 360m`.

6. **[Phase 1.3] Wire `blogwatcher` feed crawler** — 8–10 source URLs, direct-to-Obsidian output. Manual run, verify, then register. ~45min.

7. **[Phase 2.4] Retire autonomous blog-writing cron** — flip `blog-maintenance.py` to audit-only mode. Stop the stream of AI-written posts before they pile further. ~20min.

8. **[Phase 4.1–4.3] Scaffold `daily-reflect.py`** — digest builder first (pure Python, deterministic). NO-OP LLM call initially. Verify digest is correct before plugging in Opus. ~1.5h.

9. **[Phase 4.2] Wire daily-reflect Opus call** — `claude -p --model opus-4-7` on the digest, no budget cap. Artifacts land in `~/obsidian-vault/daily/<date>/`. ~45min.

10. **[Phase 2.2] `/blog-curate` command** — the human-in-loop curation flow from KB → blog. Only after the KB has real content. ~1.5h.

**User-guided cadence**: items 1–3 first (KB foundation on existing data). Then pause, inspect. Then items 4–7 (new intake + blog cron cleanup). Then items 8–10 (evolution loop). Stock / Polymarket still deferred per earlier sessions.

---

## 6. Decisions locked 2026-04-23

| # | Question | Decision |
|---|---|---|
| 1 | **Zotero bridge** | **Keep Zotero** as source-of-truth (PDFs, metadata, annotations, cross-device sync). Obsidian is the thinking layer (structured notes, citekeys, source links only). No PDF duplication into the vault. Vault stays <1GB even at 100GB+ paper corpus. |
| 2 | **Paper sources** | Hybrid multi-source: arXiv + top-conf (OpenReview) + **PapersWithCode** + **Hugging Face Papers** + **GitHub Trending**. No single source covers everything at scale. |
| 3 | **Auto-fix blast radius** | **Hermes (primary)** — scripts and config. **Blog (optional)** — content fixes via PR, never auto-merge. **Never**: Beatless, pua, `~/.claude/`, research workspaces, Zotero library. |
| 4 | **Opus daily budget** | **No cap for now.** Defer cost optimization until the full system pipeline is built. User will guide manually at this stage. |
| 5 | **3-section blog template** | Keep **Problem / How It Works / Why It Matters** as the baseline — but **not rigid**. Blog stays flexible: engaging, visually appealing, attention-driven. Will iterate on advanced formats later. |

---

## 7. Success criteria (how we know the OS is alive)

- [ ] KB has ≥200 papers with notes after 1 month.
- [ ] Blog ships ≥4 curated interpretive posts per month, all traceable back to KB notes.
- [ ] At least one `/exp-run` completes to convergence per fortnight, with findings in `experiments/`.
- [ ] Daily-reflect runs 7 days in a row without human intervention.
- [ ] Weekly synthesis surfaces ≥1 structural issue per week that wouldn't have been obvious otherwise.
- [ ] Messaging with Hermes feels like talking to a second brain, not a tool — you ask, it knows.

---

## 8. What this plan does NOT do

- Does not touch the Stock / Polymarket workflow — still waiting on your methodology handoff.
- Does not reimplement the exp pipeline — reuses `/exp-*` as-is, only adds KB grounding (Phase 3).
- Does not replace Zotero — Zotero stays as the source-of-truth library. Obsidian is an additive thinking layer, not a replacement.
- Does not duplicate PDFs into the vault — the `@<citekey>.md` note links back to Zotero; PDFs never leave Zotero.
- Does not impose a cost cap on Opus reflection — user is manually guiding at this stage.
- Does not create a UI — Obsidian is the UI for the KB, the Astro blog is the UI for curated output, Hermes chat is the UI for everything else.

---

## 9. Next-stage architecture (user is designing)

Roadmap above is Phase 1–5 of the near-term Research OS. User flagged that they are working on the **next-stage architecture** beyond this — likely the shape of the full Autonomous Research OS once the KB + blog + exp + daily-reflect loops are all green.

Placeholder: this section will be filled when the user shares the next-stage design. For now, every decision in Phase 1–5 should be reversible and composable so the next stage can graft on without forcing a rewrite.

---

## 10. Status update — 2026-04-25

Two days into this roadmap. What actually shipped vs. what §2 inventory still claims:

### Now done (was ❌ in §2 inventory)

- **Zotero → Obsidian sync** — `~/.hermes/scripts/zotero-to-obsidian.py` is live, manual run only (not yet a cron job per §1.1's `every 180m` plan). 24 papers synced into `~/obsidian-vault/papers/literature/@*.md` from the A-Tier Zotero collection.
- **Multi-source paper harvester** — `~/.hermes/scripts/paper-harvest.py` + `paper-backfill.py` exist and run.
- **Blog/report feed crawler** — `~/.hermes/scripts/feed-crawl.py` is producing daily snapshots; 43 days in `~/obsidian-vault/feeds/`.

### Newly built 2026-04-25 (NOT in §2)

- **Blog translation pipeline (T1)** — `~/.hermes/scripts/blog-translate.py` + Hermes cron job `Blog Translate` (every 10m). Produced 7 bilingual drafts in `~/obsidian-vault/blog-drafts/` during this session. Uses MiniMax M2.7 directly (no Claude in writing path) per user directive.
- **Blog drafting pipeline (T2)** — `~/.hermes/scripts/blog-draft.py` + Hermes cron job `Blog Draft` (every 30m). Reads Zotero notes, generates bilingual Paper Spotlight per the 2026-04-25 `AI 博客写作模板指南.md` template. Same Hermes-only writing path.
- **3-section template arrived** — `/home/lingxufeng/claw/plan/AI博客写作模板指南.md` (the spec §6.1 was blocking on). Three templates: Signal Post / Paper Spotlight / Milestone Post. Five style commandments. 12 banned phrases. Quality checklist.

### Still missing (§2 inventory)

- **Paper-note generation loop** (Phase 2) — currently the Zotero notes are basic frontmatter + abstract; no per-paper "what / why-surprising / how-useful-to-me" curation step.
- **`/exp-discover` wired to KB** (Phase 3) — `/exp-*` commands moved to `deprecated/` during the 2026-04-24 paradigm pivot to the new `/research-*` family.
- **Daily evolution loop** (Phase 4) — not built.
- **Multi-direction progress dashboard** (Phase 5) — not built.

### Architecture re-confirmed (was confused 2026-04-25)

- **`github-pr.py` and `github-response.py` shelling out to `claude -p` is BY DESIGN** per §2 of `2026-04-23-personal-research-automation-system.md`: "Hermes cron wake-gates call `claude -p --model sonnet` with a specific `/command`."
- **Blog scripts using MMX directly is a content-vs-code SPECIAL CASE** — content (translation, drafting) wants Hermes-routed models; code (PR review, refactor) wants Claude. Both run through Hermes cron — Hermes owns the schedule, the script picks the right writer per task type.

### Diff between 2026-04-24 paradigm pivot and this roadmap

The 2026-04-24 pivot to `Research Constitution + Automated Research Ecology` (see `~/claw/Beatless/plan/2026-04-24-research-constitution-paradigm-phase-1.md`) supersedes Phase 3's `/exp-*` design with the new `/research-*` family. The KB foundation (Phase 1) and blog curation (Phase 2) of THIS roadmap are still load-bearing.

Phase 4 (Daily Evolution Loop with Opus 4.7) and Phase 5 (Dashboard) are unchanged by the pivot.
