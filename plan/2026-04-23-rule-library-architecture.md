# Rule Library Architecture — Zotero → Obsidian → Experiments

**Created**: 2026-04-23
**Owner**: <your-github-user> (maintained by Hermes Agent + Claude Code)
**Status**: first draft — describes the user's stated philosophy and
translates it into a concrete schema the pipeline can implement.
Supersedes the vague "Phase 2 curation" description in the roadmap.

---

## 0. The user's thesis (quoted)

> What we are building inside Obsidian is a **rule-based knowledge system**, grounded in top-conf papers / technical reports / OpenReview / arXiv. A key question: **how do we identify a new field, or a new problem within a field?**
>
> My current understanding:
> - **No new concepts → no new rules**
> - During implementation, we continuously establish new standards
> - These standards collectively form a **rule library**
> - This rule library is the true starting point for producing high-quality experiments
>
> I plan to reference the training strategy and paradigm from **Constitutional AI**: the system should allow AI to operate in a multi-threaded, autonomous manner, especially when exploring research entry points and problem formulations.
>
> Core goal: **extract a potential underlying rule from each paper**.

This doc turns that philosophy into a schema, a workflow, and a set of
concrete files to produce.

---

## 1. Source grounding (already captured in AI-alignment digest)

The AAR (automated-w2s-research) framework and its analysis give us
a ready answer to "what counts as a new problem":

- **Falsification-based novelty**: an idea is "new" iff it **recovers PGR on an OOD validation set**. Surface-level change without OOD transfer = eval-overfit (虚假策略).
- **Implicit schema per artifact**: `(hypothesis, code diff, PGR delta, OOD-PGR delta)`.
- **Multi-threaded exploration**: 9 parallel Opus agents, each seeded with a differentiated prior (data reweighting, loss modification, unsupervised elicitation, etc.) to prevent entropy collapse.
- **Auditor agent**: separate semantic-monitoring layer watches peer methodology.

This is the template. The rule library is the generalization of AAR's
leaderboard-driven, falsifiable-novelty protocol to the broader 2026+
agents-and-training-paradigms corpus.

---

## 2. What is a "rule"?

A **rule** is a falsifiable, reusable claim extracted from a paper,
expressed in a form that can feed experiment design.

### 2.1 The RULE schema (per-paper)

Each paper in the Zotero `Auto-Harvest` collection gets an Obsidian
note at `~/obsidian-vault/papers/literature/@<citekey>.md`. Inside the
note body, one or more RULE blocks, each using this YAML subheader:

```yaml
rule:
  id: R-<yyyy>-<nnn>            # auto-assigned, globally unique
  claim: "<one-line falsifiable claim, present tense>"
  bottleneck: "<the real problem the rule addresses>"
  preconditions:                 # when does this rule apply?
    - "<e.g. student ≫ teacher capacity>"
    - "<e.g. pretraining covers target distribution>"
  proposed_mechanism: "<1-2 sentences on WHY>"
  evidence:
    pgr_delta: "<number or N/A>"
    ood_pgr_delta: "<number or N/A>"
    benchmarks: ["<bench-1>", "<bench-2>"]
    code: "<link or citekey>"
  counterexamples:               # rules that lose here
    - "<link to other rule id or N/A>"
  tier: candidate | promoted | retired
  direction: agents | training | evaluation | safety | infra
  linked_papers: ["@<other-citekey>", ...]
```

Plain English: each rule answers six questions — what, when, why,
with-what-evidence, what-breaks-it, where-in-the-landscape.

### 2.2 Tiers

- **candidate**: extracted from a single paper. Not yet cross-checked against other work.
- **promoted**: survived at least one experiment (pass/fail on the user's own `/exp-run`) OR replicated across ≥ 2 papers with different data.
- **retired**: a counterexample knocked it out. Kept in library with `retired: <why>` for the falsification history.

### 2.3 What counts as a NEW rule (the user's question)

Adapting the AAR falsification test to the extraction stage:

1. **Claim is not already in the rule library.** (Literal match or semantic match via `qmd` search.)
2. **Claim references a bottleneck or mechanism that currently has no rule.**
3. **OR** it contradicts an existing rule and provides evidence — triggering a split: existing rule → retired or scoped with new preconditions.

If none of the above: the paper gets a note but no new rule — it's a
data point for an existing rule (appended under `evidence:`).

This directly answers "no new concepts → no new rules."

---

## 3. Pipeline (Zotero → Obsidian → Rules → Experiments)

```
┌──────────────────────────────────────────────────────────────┐
│ Zotero: Auto-Harvest collection                              │
│   - paper-harvest cron (arXiv cats, 2025+, every 360m)       │
│   - paper-backfill one-shot (topical, 2026+, on demand)      │
│   - manual Chrome Connector drops                            │
└──────────────────────────┬───────────────────────────────────┘
                           │ (sync script, future)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Obsidian: ~/obsidian-vault/papers/literature/                │
│   @<citekey>.md  ← one per paper, references Zotero PDF      │
│   Frontmatter: title, source, direction, status, hook        │
│   Body: your own notes + zero-to-many RULE blocks            │
└──────────────────────────┬───────────────────────────────────┘
                           │ (rule extractor, future)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Obsidian: ~/obsidian-vault/rules/                            │
│   R-2026-001.md  ← one file per rule, with full schema       │
│   Cross-linked to @<citekey>.md evidence via wiki-links      │
│   Tag index: direction/, tier/, status/                      │
└──────────────────────────┬───────────────────────────────────┘
                           │ (exp-discover consumes this)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ /exp-init → /exp-discover → /exp-run                         │
│   Hypothesis seeds drawn from candidate-tier rules           │
│   PGR + OOD-PGR measured                                     │
│   Result feeds back to rule file:                            │
│     - positive → tier: candidate → promoted                  │
│     - negative → tier: retired; counterexample link         │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Constitutional-AI-style multi-threaded exploration

The user wants multi-threaded autonomous operation for "exploring
research entry points and problem formulations." Mapping CAI + AAR
onto our pipeline:

### 4.1 Three agent classes (future Hermes cron jobs)

| Agent | Runs every | Reads | Produces |
|---|---|---|---|
| **Extractor** | 12h | recent Zotero notes where `hook:` is populated | draft RULE blocks, tier=candidate |
| **Auditor** | daily | newly-drafted candidate rules | flags rules where claim∥mechanism is inconsistent, duplicates existing rule, or has no falsifiable evidence. Writes ADJUDICATION block into the rule file. |
| **Proposer** | weekly | promoted rules + open-problems list | suggests 3 `/exp-init` seed hypotheses that would test an untested precondition or counterexample boundary |

All three use differentiated priors (per AAR anti-entropy-collapse):
Extractor is generous in drafting, Auditor is skeptical, Proposer is
divergent.

### 4.2 Open-problems list

`~/obsidian-vault/rules/_open-problems.md` — plaintext list of bottlenecks
that no rule addresses yet. The Proposer agent mines this, `/exp-discover`
consults it, and the user eyeballs it weekly to see what's uncovered.

---

## 5. Concrete first deliverables (when the user is ready to start)

Not yet — flagged here so the order is explicit:

1. **Template files** in `~/obsidian-vault/.obsidian/templates/`:
   - `Literature Note.md` — the `@<citekey>.md` template (frontmatter + RULE block placeholder)
   - `Rule.md` — the `R-<yyyy>-<nnn>.md` template
   - `Open Problem.md` — item in `_open-problems.md`
2. **Zotero → Obsidian sync** (Better BibTeX + mdnotes or equivalent). Writes `@<citekey>.md` skeletons for every Auto-Harvest item. PDFs stay in Zotero.
3. **Extractor prompt** — Skill or command that the user can run against a new batch of literature notes. Reads paper abstract + the user's `hook:`, drafts candidate rules.
4. **Auditor prompt** — Separate command that reviews the extractor's output before promotion to the rule library.
5. **Rule → `/exp-init` bridge** — a `/exp-from-rule R-2026-xxx` helper that seeds Task.md from a promoted rule.

None of these require code yet. What they require is the user to define
the exact 3-section template for literature notes and the exact shape
of `hook:` — both of which they said they'd specify later. This doc
waits.

---

## 6. Where the rule library differs from "surface Obsidian features"

User wrote: "*surface-level features like highlighting methods and citation relationships are useful, but they are not sufficient*."

The three things this doc adds beyond surface features:

| Surface feature | Not enough because | Rule-library addition |
|---|---|---|
| Highlight quote + citekey | Doesn't force the reader to state the falsifiable claim | RULE block requires `claim:` + `evidence:` + `preconditions:` fields |
| Wiki-link between papers | Doesn't distinguish "cited by" from "contradicts" | Rule file has explicit `counterexamples:` and `linked_papers:` separated |
| Tag `#attention` | Flat tag can't capture status of a claim | `tier: candidate | promoted | retired` is a first-class field |
| Dataview query | Pulls papers by metadata but not by testability | Rules are **filterable by `evidence.pgr_delta ≥ 0.5`**, which is the AAR-style signal |

The rule library turns Obsidian from "a tidier reading-note folder"
into "a queryable falsifiable-claim database the experiment runner can
consume."

---

## 7. What this plan does NOT do (yet)

- Does not implement the Extractor / Auditor / Proposer agents — flagged for a later phase; user will define the methodology first.
- Does not wire the `R-*` → `/exp-init` bridge — needs the rule library to exist first.
- Does not replace the user's own curation judgment — these agents are drafting tools, not decision makers.
- Does not touch the blog workflow — a separate path; rules may inform blog posts but this doc is about the KB side only.

---

## 8. Review cadence

- When the first 100-200 papers from the backfill settle in Zotero and sync to Obsidian, **revise §2 schema** against real examples — the user said "I will research in detail later" and this gives concrete data to ground that research.
- When the first `/exp-run` completes and produces a PGR delta, revise §4.1 Auditor to use real metrics as its check rather than the abstract description.
- Monthly: `rules/_open-problems.md` triage — retire stale bottlenecks, promote frequent ones.
