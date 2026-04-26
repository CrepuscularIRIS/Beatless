---
description: "Generate research hypotheses using two-path methodology. Path 1 (idea-first): domain exploration, bottleneck analysis, method selection based on problem+dataset characteristics. Path 2 (application-first): cross-domain transfer, shared first principles, hidden assumption mining. Multi-agent parallel analysis, 2025+ literature focus."
argument-hint: "[topic or focus area] [--path idea|application] [--dimensions N]"
allowed-tools: Read, Write, Grep, Glob, Bash, Agent, Skill, mcp__plugin_gsd_gsd__*
---

# Experiment Discover: Two-Path Hypothesis Generator

Analyze and generate hypotheses for: **$ARGUMENTS**

## Your Role: Research Lead

You lead a structured research process that produces ranked, feasible, falsifiable hypotheses. You coordinate plugins for parallel thinking, literature search, and feasibility assessment.

---

## Step 0: Read Context

Read all available project files:
- `Task.md` or `program.md` (project spec, constraints, target metric)
- `results.tsv` (past experiments — what worked, what failed, what crashed)
- `findings.md` (accumulated knowledge from prior rounds)
- `progress.md` (current state, round counter)
- Modifiable source code (train.py, model files, etc.)

Summarize current state in ≤5 bullets before proceeding.

### Smoke / Halt Guard

If this is a smoke workspace or the current state is already halted, do not run brainstorming,
literature search, Codex feasibility, GSD writes, or planning updates.

Treat the workspace as halted when any of these are true:
- `program.md` describes a smoke/dispatch-verification workspace.
- `progress.md` says `HALT`, `halted`, or `smoke rule satisfied`.
- `results.tsv` has a completed smoke baseline and `program.md` says to run at most once.

In that case, return this explicit no-op output and stop:

```
Experiment Discover — <project-name>

Verdict: HALT
Reason: smoke workspace already satisfied; no research target exists.

No hypotheses generated.
No files changed.

Next: create or switch to a real experiment workspace with a substantive program.md or Task.md.
```

---

## Step 1: Research Path Selection

All research comes from two fundamental sources. Select based on context:

### Path 1: Idea-First (Exploration + Innovation)

**Use when**: exploring a new domain, seeking extensions or innovations on existing approaches, optimizing within a known problem space.

**Methodology (follow in order)**:

1. **Domain Understanding**: What is the core problem? What makes this dataset or task hard? Form your own understanding — even small extensions or incremental innovations can be very valuable if they address the real difficulty.

2. **Bottleneck Identification** (CRITICAL for difficult problems):
   - Where exactly does performance plateau? Which samples/classes/cases are hardest?
   - Is the bottleneck data quality? Model capacity? Loss signal? Optimization landscape? Evaluation protocol?
   - For difficult datasets: the difficulty must be clearly located before any method is proposed. A method that doesn't address the actual bottleneck is wasted compute.

3. **Method + Paradigm Selection**:
   - Must be based on the target problem, its background, and the dataset's characteristics.
   - The paradigm must fit the problem — not just be "latest SOTA from another task."
   - Consider: does this problem need more data? Better architecture? Different loss? Different training paradigm entirely?

4. **Model + Training Strategy**:
   - Select based on computational constraints AND bottleneck analysis.
   - Model size and architecture should match the information structure of the data.
   - Training strategy should match the optimization landscape (curriculum? multi-stage? self-training?).

5. **Literature Grounding**:
   - Papers from **2025 onward preferred**. Earlier papers are references and historical context, not blueprints.
   - Look for methods that address the specific bottleneck you identified, not just highest-scoring methods on related benchmarks.

### Path 2: Application-First (Transfer + First Principles)

**Use when**: a concrete real-world problem exists, or the current approach has hit a ceiling that suggests a paradigm limitation rather than a tuning problem.

**Methodology (follow in order)**:

1. **Scenario Analysis**: What is the concrete problem? What domain constraints exist? What does "solved" look like for a practitioner, not just a leaderboard?

2. **Cross-Domain Transfer** (NOT surface-level):
   - Look for algorithms solving **structurally similar** problems in other fields.
   - This is NOT "apply transformer from NLP to vision." That's surface transfer.
   - Real transfer: find the shared mathematical structure, optimization geometry, or information-theoretic property. Example: "attention sparsity in speech recognition addresses the same long-range dependency bottleneck as our spatial attention collapse."

3. **Shared First Principles**:
   - What fundamental principles (information theory, optimization theory, statistical learning theory) govern both domains?
   - New theories are time-sensitive (quickly absorbed by the community). First principles are durable.
   - Look for structural analogies: if two problems share the same loss landscape geometry, methods from one may transfer even if the domains look nothing alike.

4. **Hidden Assumption Mining** (highest-value targets):
   - What does the target field assume that might be wrong?
   - Widely accepted assumptions that are actually flawed = highest impact research.
   - Examples: "everyone uses cross-entropy because it's standard, but the label noise structure in this dataset makes it degenerate." "Everyone trains end-to-end, but the gradient flow through this bottleneck layer is provably vanishing."
   - Challenge: "Why does everyone do X? Is the original justification still valid with modern architectures/data scales?"

5. **Literature Grounding**:
   - 2025+ papers for the target domain.
   - Also foundational works that established the assumptions you are challenging.
   - Cross-domain papers that solved the structural analogue.

### Path Selection Heuristic

| Signal | Path |
|--------|------|
| Metric improving but slowly → more of the same direction | Idea-first |
| Metric plateaued, all obvious variations tried | Application-first |
| New domain, first time working on this problem | Idea-first |
| Known problem, existing methods seem fundamentally limited | Application-first |
| User specified `--path idea` or `--path application` | As specified |

If unclear, run both paths in parallel (spawn separate brainstorming rounds).

---

## Step 2: Problem Value Gate

Before investing plugin compute, answer 4 questions:

| # | Question | YES = proceed | NO = reconsider |
|---|----------|---------------|-----------------|
| 1 | Recognized pain point in target community? | Papers cite this gap | Only you think it matters |
| 2 | Structural (not just metric optimization)? | Architectural/representational failure | "SOTA 85%, I want 87%" |
| 3 | Fits A-tier venue narrative? | "Changes how I think about X" | "Nice improvement" |
| 4 | Solving it rewrites understanding? | Framework/paradigm shift | +1 component |

**Score**: 4/4 → strong. 3/4 → proceed with caution. ≤2/4 → reframe.

**For benchmark optimization runs** (pure score focus): questions 2-4 are scored differently. Structural model/training improvements that generalize count as YES even without venue narrative. A 0.02 val_bpb improvement from a cleaner architecture is structurally valuable.

Write the gate result to `findings.md`.

---

## Step 3: Multi-Agent Parallel Brainstorming

Use Skill tool to invoke `superpowers:brainstorming` for structured parallel thinking.

Generate **8+ candidate hypotheses**, drawing from multiple cognitive entry points:

**From decomposition stack** (2-3 of these):
- Dataset / augmentation (data-centric leverage)
- Architecture (block type, scale, topology, attention pattern)
- Loss function (reweighting, boundary, consistency, contrastive)
- Training paradigm (curriculum, self-training, multi-stage, distillation)

**From abstract axioms** (1 of these):
- Information bottleneck / orthogonality / duality / equivariance / causality / minimum description length

**From cross-domain analogy** (1 of these):
- What works for structurally similar problems in speech, NLP, point clouds, video, RL, physics simulation?

**From concrete phenomena** (1 of these):
- Gradient pathology, shortcut learning, distribution shift, label noise, calibration failure

Each hypothesis must state:
- One falsifiable sentence
- Which bottleneck or assumption it addresses
- Which path (idea-first or application-first) it comes from

---

## Step 4: Literature Grounding (Gemini)

Invoke Gemini for 2025+ literature search:

```
Agent tool:
  subagent_type: "gemini-cli"
  prompt: "Search academic literature (2025 papers strongly preferred, 2024 acceptable) for: [top 3-4 hypotheses from Step 3].

For each hypothesis:
1. 3-5 closest published papers (title, venue, year, one-line takeaway)
2. Which paper is closest to our approach? What remains unfilled?
3. Strongest counter-argument or simpler alternative
4. Any hidden assumption in the field that this hypothesis challenges?

Focus on: [target domain from Task.md/program.md]. Return structured, with citations."
```

**Fallback** if Gemini unavailable: Use WebSearch for arxiv queries. Mark results `[UNVERIFIED — WebSearch fallback]`.

Also invoke Gemini as devil's advocate:
```
Agent tool:
  subagent_type: "gemini-cli"
  prompt: "Play devil's advocate against the top hypothesis: [describe it].
Attack with: (1) simpler explanation that achieves similar results, (2) prior work that already solved this, (3) fundamental flaw that prevents generalization."
```

Paste Gemini results verbatim into `findings.md` under `## Literature — <date>`. Do not paraphrase — paraphrasing drops uncertainty markers.

---

## Step 5: Feasibility Assessment (Codex)

Invoke Codex for implementation feasibility:

```
Agent tool:
  subagent_type: "codex-cli"
  prompt: "Assess feasibility of these hypotheses against the current codebase at [project root]:

[top 3 hypotheses with one-line descriptions]

For each, check:
1. Files to change (list exact paths)
2. Implementation complexity (1-5 scale, with justification)
3. VRAM / compute risk (will it fit in [GPU spec from Task.md]?)
4. Rollback safety (can we git reset cleanly?)
5. Expected gain magnitude vs implementation cost
6. Any dependency or API changes needed (should be NONE)

Be brutally honest. A beautiful idea that needs 500 lines of new code and a new library is worse than an ugly idea that needs 5 lines."
```

**Fallback** if Codex unavailable: Claude reads the codebase directly and estimates. Mark `[UNVERIFIED — Claude-only assessment]`.

---

## Step 6: Rank and Select

Build ranked shortlist (top 3):

| Rank | Hypothesis | Path | Bottleneck Addressed | Expected Gain | Complexity | VRAM Risk | Prior Art Threat | Rollback? |
|------|-----------|------|---------------------|---------------|------------|-----------|-----------------|-----------|

**Selection criteria** (ordered by priority):
1. Addresses the identified bottleneck (not just "might help")
2. Expected gain on target metric
3. Low prior-art threat (genuine novelty or new angle)
4. Low complexity (fewer lines changed = better)
5. Safe rollback

**Tie-breaker**: simpler wins. A 0.001 improvement from deleting code beats a 0.002 improvement from adding 50 lines.

---

## Step 7: Write Planning Artifacts

Update planning files. Try Skill `planning-with-files:plan` first, fallback to direct writes:

- **task_plan.md**: Selected hypothesis, execution steps, files to modify, success criterion, kill trigger
- **findings.md**: Full analysis — rejected alternatives with reasons, literature notes, devil's advocate responses, bottleneck analysis
- **progress.md**: Timestamped decision record, path used (idea-first / application-first), value gate score

Use GSD to record the decision:
- MCP tool `mcp__plugin_gsd_gsd__gsd_add_decision` with hypothesis selection rationale
- Fallback: write directly to findings.md

---

## Step 8: Output

```
Hypothesis selected:
  [One falsifiable sentence]

Research path: [Idea-first / Application-first]
Bottleneck addressed: [specific bottleneck]
Key insight: [what assumption is challenged or what structural analogy is exploited]
Prior art gap: [what the closest paper doesn't do]
Complexity: [1-5] — [N files, ~M lines]
Value gate: [score]/4

Next: /exp-run "<hypothesis sentence>"
```
