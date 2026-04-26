---
description: "Multi-plugin review of experiment state. Codex reviews code correctness, Gemini reviews research direction, GSD verifies goal alignment. Produces continue/pivot/rollback/halt recommendation with evidence."
argument-hint: "[--base <ref>] [--deep]"
allowed-tools: Bash, Read, Write, Grep, Glob, Agent, Skill, mcp__plugin_gsd_gsd__*
---

# Experiment Review

Comprehensive review of current experiment state before continuing.

## Step 1: Determine Scope

```bash
git branch --show-current
git log --oneline -10
git diff --stat HEAD~5..HEAD 2>/dev/null || git diff --stat
```

- Default: working tree + current branch diff from baseline
- If `--base <ref>` specified: diff against that ref
- Read `results.tsv` for full experiment history
- Read `findings.md` and `progress.md` for context

Summarize: rounds completed, current best metric, recent trajectory (improving / flat / declining).

## Step 2: Code Review (Codex)

```
Agent tool:
  subagent_type: "codex-cli"
  prompt: "Review the current experiment diff in [project root].

Check:
1. Correctness — any bugs, off-by-one, dtype mismatches, gradient flow breaks?
2. Unintended side effects — does the change affect parts of the pipeline it shouldn't?
3. Simplification — can the same result be achieved with less code?
4. Constraint compliance — no edits to read-only files? No new dependencies?
5. Reproducibility — is the change deterministic? Any uncontrolled randomness?

Be specific: cite file, line, and what's wrong."
```

**Fallback**: Claude reads the diff directly. Mark `[Claude-only review]`.

## Step 3: Direction Review (Gemini)

```
Agent tool:
  subagent_type: "gemini-cli"
  prompt: "Research direction review for [project description].

Current state:
- Target metric: [from Task.md/program.md]
- Best achieved: [from results.tsv]
- Recent trajectory: [last 5 experiments from results.tsv]
- Current hypothesis: [from task_plan.md]

Questions:
1. Are we on a productive path toward the target, or showing signs of local minimum?
2. What's the strongest reason to pivot to a different approach?
3. Any 2025+ papers that change the landscape for this problem?
4. Is there a hidden assumption in our current approach that might be wrong?
5. If we're stuck: what would a researcher with a different background try?

Be direct. 'Keep going' is only right if the evidence supports it."
```

**Fallback**: Claude analyzes results history for trend. Mark `[UNVERIFIED]`.

## Step 4: Goal Verification (GSD)

Try GSD verification:
- Skill tool → `gsd:gsd-verify-work`

If unavailable, manual checklist:
- [ ] Only permitted files changed
- [ ] No dependency additions
- [ ] No edits to read-only files (prepare.py etc.)
- [ ] Metrics trending toward target
- [ ] No regressions in non-target metrics (memory, training time)
- [ ] Results.tsv consistent with actual runs
- [ ] Planning files up to date

## Step 5: Methodology Check

Evaluate against the two-path framework:

**If currently on Idea-first path:**
- Is the identified bottleneck still the right one? (results may have shifted it)
- Are we still matching method to problem characteristics?
- Have we checked 2025+ literature for the specific bottleneck?

**If currently on Application-first path:**
- Is the cross-domain analogy holding up in practice?
- Are we testing the shared first principle, or just surface-level transfer?
- Has the hidden assumption we challenged actually been disproven by our experiments?

**Path switch signal:**
- If idea-first has plateaued after 3+ rounds → consider switching to application-first
- If application-first transfer isn't showing gains → the structural analogy may not hold; switch to idea-first with deeper bottleneck analysis

## Step 6: Decision Table

| Dimension | Score (1-5) | Evidence |
|-----------|-------------|----------|
| Code correctness | | Codex findings |
| Direction (toward target) | | Metric trajectory |
| Complexity budget | | Lines changed vs gain |
| Reproducibility | | Variance across runs |
| Rollback safety | | Clean git state? |
| Methodology alignment | | Path check result |

**Aggregate recommendation**:
- All ≥ 3 → **Continue** with current direction
- Any 1-2 in direction or methodology → **Pivot** (invoke `/exp-discover`)
- Code correctness ≤ 2 → **Rollback** to last known good, fix, then continue
- Direction + methodology both ≤ 2 → **Halt** and wait for human input

## Step 7: Update Planning Files

- `findings.md`: append review summary with scores and evidence
- `progress.md`: append go/no-go decision with timestamp

If `--deep` was specified, also:
- Run `superpowers:brainstorming` for alternative approach suggestions
- Write expanded analysis to `findings.md`

## Step 8: Output

```
Review — Round [N], [date]

Verdict:  [CONTINUE / PIVOT / ROLLBACK / HALT]
Evidence: [one-line summary of key finding]

Scores:
  Correctness:    [N]/5
  Direction:      [N]/5
  Complexity:     [N]/5
  Reproducibility:[N]/5
  Methodology:    [N]/5

Next: [exact command — /exp-run, /exp-discover, or halt reason]
```
