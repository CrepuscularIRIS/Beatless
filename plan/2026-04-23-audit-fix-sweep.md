# Audit-Fix Sweep — 2026-04-23

**Owner**: CrepuscularIRIS (maintained by Hermes Agent + Claude Code)
**Directive**: execute the 5 "almost-right" fixes consecutively. Audit
before, verify after. One atomic commit at the end.

This doc is the running ledger — each fix gets **Pre-audit → Action → Post-verify**.

---

## Fix order (priority = what unblocks the most downstream work)

1. **Paper quality (CCF-A guarantee)** — unblocks every downstream reading workflow. If the corpus is noisy, every rule extracted is noisy.
2. **Judgment → skill migration** — architectural smell the user explicitly called out. Fixing early prevents more regex rules from being added.
3. **Blog-maintenance audit-only** — kills a cron that's been drifting from its intended spec for two sessions.
4. **Zotero → Obsidian cron** — closes the "papers land in Zotero but never appear in Obsidian" gap that just caused user confusion.
5. **Quality-score enforcement** — raises the floor on what "pr-created" actually means.

---

## Fix 1 — Paper quality: restrict to CCF-A venues

**User directive (verbatim)**: *"paper you grabbed is not high quality, should from all ccfa for guarantee."*

### Pre-audit

- Current `paper-harvest.py` sources: arXiv cat listings (cs.LG/CL/CV/AI) + OpenReview (ICLR 2026, ICML 2025, NeurIPS 2025) + CVF CVPR 2026/2025.
- Current `paper-backfill.py` sources: arXiv keyword queries ONLY (38 queries across cs.LG/CL/CV/AI, year ≥ 2026).
- Current Zotero state: 568 items in `Auto-Harvest` collection; of those, **3 are ICML-2025 accepted, 565 are arXiv preprints** (keyword-harvest output, no CCF-A guarantee).
- Problem: the 565 arXiv items are not guaranteed to be A-tier. User wants a hard CCF-A floor.

### Action plan

1. **Create two sub-collections under `Auto-Harvest`**:
   - `Auto-Harvest/A-Tier` — CCF-A-only (OpenReview accepted + CVF accepted + ACL Anthology accepted)
   - `Auto-Harvest/Scouting` — arXiv preprints, kept separately so they don't contaminate the rule-extraction pipeline
2. **Move the 565 arXiv items into `Scouting`** (bulk update via Zotero API: add to sub-collection, remove from parent).
3. **Extend `paper-harvest.py` with three more CCF-A venues**:
   - OpenReview: COLM 2025 (Conference on Language Modeling — new but CCF-A tracked)
   - CVF: ICCV 2025 (the other vision venue)
   - ACL Anthology: ACL 2025, EMNLP 2024 + 2025, NAACL 2025 (JSON API)
4. **Disable arXiv-keyword backfill by default**. Keep the script; require explicit `--scouting` flag to run it. Its output goes to `Scouting`.
5. **Modify `arxiv_to_zotero_item` + OpenReview/CVF/ACL items** so A-tier items get tag `tier:a` and Scouting gets `tier:scout`.
6. **Re-run Zotero→Obsidian sync scoped to `A-Tier`** so the vault's `literature/` shows only guaranteed A-tier papers.

### Post-verify

- [ ] `A-Tier` collection has ≥100 items (ICML+NeurIPS+ICLR+CVPR+ICCV+ACL Anthology combined backfill).
- [ ] `Scouting` collection holds the 565 arXiv items.
- [ ] `~/obsidian-vault/papers/literature/` contains only A-Tier notes.
- [ ] `paper-harvest.py` cron next run targets the 7 venues, NOT arXiv listings.

---

## Fix 2 — Migrate judgment gates from Python regex to skill prompt

### Pre-audit

Python functions in `github-pr.py` that encode judgment as regex:
- `scan_ai_policy()` — keyword pairs on CONTRIBUTING.md
- `scan_closed_prs_for_ai_rejection()` — same on closed-PR comments
- `has_maintainer_dispute()` — 3 pattern families on maintainer comments
- `has_existing_claim()` — 5 patterns on any comment

Each is a judgment call that a skill prompt will make more accurately.

### Action plan

1. **Create `~/.claude/skills/pr-direction-check/SKILL.md`**. Input: raw data blob (issue body, labels, last N comments with author_association, CONTRIBUTING.md excerpt). Output: structured verdict — `proceed | block:<reason> | yield:<reason> | ambiguous:<need-clarification>`.
2. **Keep in Python (deterministic)**:
   - `has_duplicate_pr()` — exact `Fixes #N` grep, API-backed.
   - `has_block_label()` — exact label string match.
   - `_fetch_issue_comments()`, `fetch_repo_file()` — API plumbing.
3. **Demote to data-gatherers** (remove judgment, just return fetched text):
   - `scan_ai_policy()` → becomes `fetch_contributing()` returning the text.
   - `has_maintainer_dispute()` → already collects comments; just returns them, skill judges.
4. **Wake-gate change**: the Python preflight still rejects on deterministic gates (block-label, duplicate-PR), but for judgment-heavy issues it passes the raw data to `claude -p` with an instruction to invoke `pr-direction-check` FIRST before doing any coding work. The skill's output becomes the next gate.

### Post-verify

- [ ] `~/.claude/skills/pr-direction-check/SKILL.md` exists and is grammatically valid.
- [ ] `github-pr.py` loses ≥80 lines of regex.
- [ ] Running `claude -p "/github-pr aio-libs/aiohttp#12404 …"` manually would invoke the skill and return `block:<reason>`.

---

## Fix 3 — Flip blog-maintenance.py to audit-only

### Pre-audit

- `~/.hermes/scripts/blog-maintenance.py` currently spawns `claude -p` with a 60-line prompt that invokes `/blog-maintenance` and asks it to write/translate posts.
- Per roadmap Phase 2.4: "Retire the autonomous-writing blog cron — detect stale posts, flag to `~/.hermes/shared/.blog-audit.md`, and STOP. Writing stays human-triggered via `/blog-curate`."
- Current behavior contradicts the plan. Drift from spec.

### Action plan

1. Rewrite `blog-maintenance.py` so the main loop:
   - Scans `~/claw/blog/src/content/blogs/` for (a) posts missing `-zh` pair, (b) posts older than 60 days.
   - Writes a markdown audit report to `~/.hermes/shared/.blog-audit.md` with two sections.
   - Writes a status JSON to `~/.hermes/shared/.last-blog-maintenance-status`.
   - **Does NOT invoke `claude -p`**. Returns `wakeAgent: false`.
2. Update the cron prompt text so the scheduler just summarises the audit file instead of writing posts.

### Post-verify

- [ ] Manual dry-run: `python3 blog-maintenance.py` prints `{"wakeAgent": false}` and produces `.blog-audit.md`.
- [ ] No `claude` subprocess spawned.
- [ ] `.blog-audit.md` is human-readable and lists the 104 missing `-zh` pairs.

---

## Fix 4 — Register Zotero→Obsidian as Hermes cron

### Pre-audit

- `~/.hermes/scripts/zotero-to-obsidian.py` exists and works (568 notes generated manually this session).
- Not registered in Hermes cron — no automatic re-sync when new papers land.

### Action plan

1. Make the script default to `--collection <A-Tier-key>` after Fix 1 creates the sub-collection, so autosync only pulls CCF-A-tier notes into the vault.
2. `hermes cron add --script zotero-to-obsidian.py --name "Zotero Sync" --schedule "every 360m" …`
3. Schedule offset from Paper Harvest (same cadence, runs 30 min after each paper harvest) so new papers land in vault within one tick.

### Post-verify

- [ ] `hermes cron list` shows "Zotero Sync" active, schedule every 360m.
- [ ] Manual trigger of the cron job succeeds and writes to `.last-zotero-obsidian-sync`.

---

## Fix 5 — PR quality-score enforcement in wake-gate

### Pre-audit

- `/github-pr.md` spec says: "Aggregation: mean of 3 passes. Min 7.0/10. Hard fail if Direction or Compliance < 5 from any pass."
- `github-pr.py` parses `PIPELINE_RESULT: <status> | <detail>` but NOT a score.
- A rogue LLM session could skip the quality gate and still report `pr-created`. No enforcement.

### Action plan

1. Extend the spec output format: `/github-pr` MUST emit `PIPELINE_QUALITY_SCORE: <float 0-10>` right after `PIPELINE_RESULT:`.
2. `github-pr.py` parses both. On `pr-created` status:
   - If score missing or < 7.0: rewrite status to `quality-blocked` + close the just-submitted PR? (Too aggressive — the PR is already submitted.) **Better**: block the status from being reported as `pr-created`; emit `quality-warn` so Hermes memory captures it for review.
3. Update `github-pr.md` Phase 9 to require the score line in the final output.

### Post-verify

- [ ] `PIPELINE_RESULT: pr-created` without a matching `PIPELINE_QUALITY_SCORE:` line is rewritten to `pr-created-unscored` in the status file.
- [ ] Parsing logic unit-tested with a sample stdout string.

---

## Execution order (strict, sequential)

This doc is the ledger. Each fix's `[ ] Post-verify` items must all be checked before moving to the next fix. The final commit landing in `Beatless/main` includes ALL five fixes plus this plan doc.
