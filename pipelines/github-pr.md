---
name: github-pr
description: "End-to-end open source contribution engine with AutoPilot orchestration. Discovers fixable issues in agent/LLM repos, evaluates repo quality, sets up dev environment, runs tests to dynamically find/confirm bugs, debugs via GSD2 scientific method, plans fix with Planning-with-Files, implements with Codex (write-mode), researches architecture with Gemini (1M context), triple-reviews against 8-item quality standard, then submits PR per seven-step workflow. All bugs must be dynamically verified — no static-only findings. Use whenever the user mentions contributing to open source, submitting PRs, fixing GitHub issues, building contributor reputation, or wants to help agent/LLM projects."
---

# GitHub PR Pipeline v6 — AutoPilot Contribution Engine

End-to-end: discover → evaluate → setup → **run tests** → **GSD2 debug** → **plan fix** → **Codex implement** → **Gemini architecture check** → triple review → submit PR.

## Philosophy

Every bug must be proven by running code. Every fix must be verified by running tests. Every PR must pass triple review before submission. The pipeline uses each AI tool for what it does best:

- **Claude**: Orchestration, root cause analysis, PR authoring, code reading
- **Codex** (`codex:codex-rescue`): **Write-mode fix generation + debugging** — Codex excels at contained code changes and testing in its sandbox
- **Gemini** (`gemini:gemini-consult`): **Architecture research + contextual review** — Gemini's 1M context is ideal for understanding large codebases and checking design-level correctness

This matches the plugin contracts: Codex gets `--write` tasks, Gemini gets analysis/research tasks.

## AutoPilot Orchestration (GSD2 + Planning with Files)

Use the **3-file pattern** for tracking progress:

Create in `~/workspace/pr-stage/<repo-name>/`:
- `task_plan.md` — phases with checkboxes, updated after each phase
- `findings.md` — test results, stack traces, root cause notes
- `progress.md` — timeline, decisions, blockers

This persists state across tool calls and makes the pipeline resumable if interrupted.

## Context

- Contribution workspace: `~/workspace/contrib/` (fresh clones for PR work — separate from hunt archive)
- Staging: `~/workspace/pr-stage/`
- GitHub: `gh` authenticated as CrepuscularIRIS
- Rubric: `~/workspace/pr-stage/pr-scoring-rubric.md`
- PR standard: `/home/yarizakurahime/claw/github/PR.md` (seven-step workflow)
- Quality standard: `/home/yarizakurahime/claw/github/PullRequest.md` (8-item gate)

---

## Phase 1: DISCOVER FIXABLE ISSUES

Search for issues that maintainers have explicitly welcomed:

```bash
# Priority 1: good first issue
gh search issues --label="good first issue" --state=open --sort=updated --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR langchain OR rag OR mcp OR embedding" -author:CrepuscularIRIS

# Priority 2: help wanted
gh search issues --label="help wanted" --state=open --sort=updated --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR inference OR serving OR tool" -author:CrepuscularIRIS

# Priority 3: confirmed bugs
gh search issues --label="bug" --state=open --sort=comments --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "crash OR panic OR fix OR broken" -author:CrepuscularIRIS
```

Selection criteria — ALL must be true (hard gates, no exceptions):
- **Human maintainer acknowledged** — comment from a repo member/collaborator, NOT a bot (Dosu, copilot, etc.). Check `authorAssociation` field: must be MEMBER, COLLABORATOR, or OWNER
- **Age >7 days** — `createdAt` must be at least 7 days old. Fresh issues may be invalid or duplicates
- **No competing assignees** — read ALL comments; if anyone has asked "assign me" or "I'll work on this", SKIP. Check `assignees` field too
- **No competing PRs** — run `gh pr list --repo <owner/repo> --search "<issue-number>"` to check for existing fix PRs
- **Clear scope** — repro steps, error message, or specific file identified
- **Fixable in <100 lines**
- **Repo has test suite and CI**

---

## Phase 2: EVALUATE REPO (Gemini research)

Use **Gemini** (`gemini:gemini-consult`) for repo evaluation — its 1M context can read CONTRIBUTING.md, recent PRs, and project structure in one pass:

```
Read the repository at ~/workspace/contrib/<repo-name> and evaluate:

1. Read CONTRIBUTING.md — what are the PR requirements?
2. Read .github/PULL_REQUEST_TEMPLATE.md — what format do they expect?
3. Check recent 5 merged PRs — what commit style, description depth, test expectations?
4. Read the module around the bug location — what design patterns are used?
5. Is CI running? Are PRs being reviewed?

Output: repo evaluation summary + PR format requirements for this specific repo.
```

Skip repos that fail 3+ of: CONTRIBUTING.md, PR template, recent commits, maintainer responses, CI active, good-first-issue labels.

---

## Phase 3: SETUP ENVIRONMENT + RUN TESTS

```bash
cd ~/workspace/contrib/<repo-name>

# Fork + upstream
gh repo fork <owner/repo> --clone=false 2>/dev/null || true
git remote add upstream https://github.com/<owner/repo>.git 2>/dev/null || true
git fetch upstream && git checkout main && git pull upstream main

# Install deps
if [ -f pyproject.toml ] || [ -f setup.py ]; then
  uv venv .venv && source .venv/bin/activate
  uv pip install -e ".[dev,test]" 2>&1 || uv pip install -e . 2>&1
fi
if [ -f go.mod ]; then go mod download && go build ./... 2>&1; fi
if [ -f package.json ]; then npm install && npm run build 2>&1 || true; fi
```

### Run full test suite — establish baseline

```bash
pytest --tb=short -q 2>&1 | tee ~/workspace/pr-stage/<repo>/baseline-tests.log
# or: go test -race -v ./... | tee ...
# or: npm test | tee ...
```

Record pass/fail counts. After the fix, tests must be equal or better.

---

## Phase 4: REPRODUCE THE BUG (Dynamic verification required)

Follow the issue's repro steps exactly. If the issue describes a test failure, run that test:

```bash
pytest tests/test_specific.py::test_case -v --tb=long 2>&1
```

**If the bug cannot be reproduced by running code, STOP.** Do not proceed with static-only analysis. Either:
- Ask the maintainer for better repro steps (comment on the issue)
- Pick a different issue

Save reproduction evidence to `findings.md`:
- Exact command run
- Full output/stack trace
- Timestamp

---

## Phase 5: GSD2 DEBUG — Root Cause Analysis

Apply the GSD2 scientific method debugging pattern:

### 5a. Gather symptoms
- What exception/error/panic?
- Which file:line in production code (not test code)?
- What input triggers it?

### 5b. Form hypothesis
- Why does the current code fail?
- What assumption is violated?

### 5c. Test hypothesis
Read the code at the crash site. Trace the execution path. Confirm:
- Is this a logic error, missing null check, wrong type, race condition, or unhandled edge case?

### 5d. For complex bugs — use Codex as debug assistant

Spawn `codex:codex-rescue` in **diagnose mode** (read-only):
```
Debug this test failure in ~/workspace/contrib/<repo-name>.

Failing test: <test name>
Stack trace:
<paste stack trace>

Read the source code at the crash site. What is the root cause?
Do NOT fix it yet — just diagnose. Output a Root Cause Report:
- Root cause (1 sentence)
- Affected file:line
- Why the current code is wrong
- What the fix should be (description, not code)
```

### 5e. Write root cause analysis

Save to `findings.md`:
```
## Root Cause: <issue title>
- File: <file:line>
- Cause: <1-2 sentences>
- Fix approach: <1-2 sentences>
- Confidence: HIGH/MEDIUM
```

---

## Phase 6: PLAN FIX (Planning with Files)

Update `task_plan.md`:
```markdown
# Fix Plan: <repo>#<issue>

## Root Cause
<from Phase 5>

## Changes Required
- [ ] `<file>:<line>` — <what to change>
- [ ] Add/modify test: `<test file>`
- [ ] Verify: `<test command>`

## Risk Assessment
- What could break: <description>
- Edge cases: <list>
- Scope check: <N lines, within 100 limit>
```

Create fix branch:
```bash
git checkout main && git pull upstream main
git checkout -b fix/<issue-slug>
```

---

## Phase 7: IMPLEMENT FIX (Codex write-mode)

Codex excels at contained code changes. Use it in **write mode**:

### Simple fixes (<20 lines)

Spawn `codex:codex-rescue` with `--write`:
```
Fix the bug in ~/workspace/contrib/<repo-name> described in issue #<N>.

Root cause: <from Phase 5>
File to change: <file:line>
What to change: <specific description>

Requirements:
1. Minimal change — fix only the bug
2. Match the repo's existing code style exactly
3. Add or modify a test proving the fix
4. Keep under 20 lines changed total
```

### Complex fixes (20-100 lines)

Use **parallel dispatch** (SuperPowers pattern):

1. **Gemini** (`gemini:gemini-consult`): "Read the full module around `<file>`. What design patterns, invariants, and interfaces must be preserved? What are the edge cases?"

2. **Codex** (`codex:codex-rescue`): "Given this architecture context from Gemini: <paste>. Fix the bug at `<file:line>`. Follow the existing patterns exactly."

### After implementation — verify the diff

```bash
git diff --stat
git diff
```

Check: <100 lines? Only relevant files? No debug prints, no commented-out code, no formatting noise?

---

## Phase 8: VERIFY (Dynamic only)

### 8a. Full test suite
```bash
pytest --tb=short -q 2>&1
# Compare against Phase 3 baseline — MUST be equal or better
```

### 8b. Specific bug reproduction
```bash
# The test/command from Phase 4 must now PASS
pytest tests/test_specific.py::test_case -v 2>&1
```

### 8c. Lint check
```bash
ruff check . 2>/dev/null || go vet ./... 2>/dev/null || npm run lint 2>/dev/null || true
```

If any test regresses → debug and fix before proceeding. Never submit with regressions.

---

## Phase 9: TRIPLE REVIEW (Parallel dispatch)

Spawn all three reviewers in a SINGLE message using the **SuperPowers parallel dispatch** pattern. Each reviews independently.

**Critical rule: NO SELF-REVIEW.** The agent that implemented the fix (Phase 7) must NOT score its own code. Role assignment:
- If **Codex** implemented → Codex reviews architecture/social fit, Gemini reviews correctness/code quality
- If **Claude** implemented → swap accordingly
- The implementer ALWAYS takes the role furthest from their own work

### Scoring discipline

Every score MUST include:
1. **Specific file:line references** — "base.py:250 correctly guards with None check"
2. **Deduction reasons** — if score < 10, state exactly what's missing or wrong
3. **Comparison to alternatives** — "Dosu bot suggested filtering all None values; this fix only guards best_of, which is narrower but sufficient because..."
4. **Anchor at 7** — a score of 7 means "acceptable, meets minimum bar". 8 = good. 9 = excellent with minor nits. 10 = flawless, rare. Scores of 9-10 require exceptional justification.

### Reviewer A (`codex:codex-rescue` or `gemini:gemini-consult` — whichever did NOT implement)
Focus: **correctness + code quality**

```
Review this git diff in ~/workspace/contrib/<repo-name>.
You are an independent reviewer — you did NOT write this code.

MANDATORY: Before scoring, you MUST run the test suite yourself and paste the output summary (pass/fail count).
Also run ONE manual verification: revert the fix, run the new test, confirm it FAILS. Then re-apply and confirm it PASSES. Paste both outputs as proof.

Score each dimension 1-10 (anchor at 7 = acceptable):
1. Correctness — does it fix the root cause? Could it introduce new bugs? Cite specific lines.
2. Minimality — are ALL changed lines necessary? Flag any line that could be removed.
3. Code quality — does it match repo style exactly? Check naming, indentation, patterns.
4. Test coverage — do tests actually exercise the fix? Could the tests pass even WITHOUT the fix (false green)? You MUST verify this by reverting the fix and running the test.
5. No regressions — check edge cases the fix might break. List 2-3 scenarios you verified by running code.

For EACH dimension, output:
| Dimension | Score | Evidence (file:line + specific observation) | Deduction reason (if <10) |

PASS if average >=7. FAIL otherwise.
If any single dimension scores <=5, the overall result is FAIL regardless of average.
```

### Reviewer B (the other agent — whichever did NOT implement)
Focus: **architecture + social fit**

```
Review this PR for ~/workspace/contrib/<repo-name>.
Read the FULL module (not just the diff), the PR description draft, and CONTRIBUTING.md.

Score each dimension 1-10 (anchor at 7 = acceptable):
1. Architecture fit — does the fix respect existing design patterns? Could it be done differently? Compare to how similar changes were made in the repo's git history.
2. Edge cases — list 3 edge cases. For each, state whether the fix handles it and cite evidence.
3. PR description — is root cause explained accurately? Would a maintainer understand the fix in <2 minutes?
4. Social fit — tone appropriate? Follows CONTRIBUTING.md? No overconfident claims?
5. Maintainer perspective — compare to the repo's last 5 merged PRs. Is this PR at the same quality level?

For EACH dimension, output:
| Dimension | Score | Evidence (specific observation) | Deduction reason (if <10) |

PASS if average >=7. FAIL otherwise.
If any single dimension scores <=5, the overall result is FAIL regardless of average.
```

### Claude self-review — focus: 8-item quality gate (from PullRequest.md)

Score against PullRequest.md standard. For each item, provide a YES/NO with specific evidence:

1. **Direction correct** — Is issue >7 days old? Acknowledged by HUMAN maintainer (not bot)? No competing assignees or PRs? (If any NO → score <=6)
2. **Follows repo rules** — Quote specific CONTRIBUTING.md requirements met. List any requirements NOT checked.
3. **Small scope** — Count lines changed. If >50 lines, justify why each file is necessary.
4. **Complete description** — Does PR body explain root cause with technical detail? Not just "fixed the bug".
5. **Verifiable** — Paste the exact test command and its output. If test was written by us, could it pass WITHOUT our fix? (false green check)
6. **Low friction** — Would a non-native English speaker understand the PR? Is tone humble, not lecturing?
7. **Follow-up ready** — What would you do if maintainer asks for a different approach?
8. **Trust building** — Is this an appropriate first contribution to this repo? Or are we overreaching?

Output: 8 rows with Score (1-10) + Evidence. Average must be >=7.
**Hard fail triggers**: item 1 or 2 scores <=5 → overall FAIL (these are non-negotiable).

### Gate decision

- All three reviewers PASS + overall average >=7.0 → proceed to Phase 9b
- Any single reviewer FAIL → fix issues, re-run Phase 8-9
- Any hard fail trigger → STOP, pick a different issue

### Phase 9b: ITERATIVE IMPROVEMENT (max 2 rounds)

After the first review round, collect ALL deduction items into a fix list. Then:

1. **Fix what you can** — missing changeset, missing test, missing comment → implement now
2. **Document what you can't** — "partial-duplicate case is out of scope per issue" → add to PR notes
3. **Re-verify** — run tests again after any code change (`Phase 8` quick re-run)
4. **Re-score ONLY the changed dimensions** — don't re-score everything. Only re-evaluate dimensions where the fix addressed a specific deduction.

Example iteration:
```
Round 1: Codex Social fit = 6 (missing changeset)
→ Action: run `pnpm changeset`, add patch entry
→ Round 2: Codex Social fit = 8 (changeset present, PR not yet submitted)
```

**Rules:**
- Maximum 2 improvement rounds. If still <7.0 after round 2, STOP — the issue may be too complex or the fix approach is wrong
- Never re-score a dimension that had no code change — score inflation through re-asking is not improvement
- Record each round in `findings.md` with before/after scores and what changed
- The FINAL score (after improvements) is what goes in `pr-report.md`

**Final gate**: overall average >=7.5 after improvements → proceed to Phase 10. (Higher bar than round 1 because improvements were applied.)

---

## Phase 10: COMMIT AND PR (Seven-step standard)

### Commit
```bash
git add <changed-files>
git commit -m "fix(<scope>): <concise description>

Fixes <owner/repo>#<issue-number>

<one-line: root cause and how this fixes it>"
```

### Push
```bash
git push origin fix/<issue-slug>
```

### Create PR
```bash
gh pr create \
  --repo <owner/repo> \
  --title "fix(<scope>): <description>" \
  --body "$(cat <<'EOF'
## Summary

Fixes #<issue-number>

<2-3 sentences: what was broken and how this PR fixes it>

## Root Cause

<1-2 sentences: WHY the bug existed — shows you understand the codebase>

## Changes

- `<file>`: <what changed and why>

## Testing

- [x] Full test suite passes (no regressions)
- [x] Specific bug reproduction no longer triggers
- [x] Independently reviewed by automated analysis

```bash
# Verify:
<exact test command>
```

## Notes

Minimal fix — no unrelated changes.
Happy to adjust based on review feedback.
EOF
)"
```

---

## Phase 11: MONITOR AND ITERATE

Check daily:
```bash
gh pr view <N> --repo <owner/repo> --json state,reviews,comments
```

Respond to feedback promptly. Push updates to the same branch.

---

## Phase 12: REPORT

Update `progress.md` and save to `~/workspace/pr-stage/pr-report-<date>.md`:

```markdown
# PR Report — <date>

## Submitted
| Issue | PR | Repo | Fix | Triple Score |
|-------|-----|------|-----|-------------|
| #N | #M | owner/repo | description | Claude X / Codex X / Gemini X |

## Dynamic Verification
- Bug reproduced: YES (command + output)
- Fix verified: YES (tests pass)
- Test baseline: X pass → X pass (no regressions)

## Review Status
- Codex: PASS (X/10)
- Gemini: PASS (X/10)
- Claude: PASS (X/10)
- Maintainer: pending
```

---

## Rules

1. **Dynamic verification only** — every bug must be reproduced by running code
2. **No static-only findings** — if it can't crash when you run it, don't fix it
3. **Codex for fixing/debugging** — write-mode code changes, sandbox testing
4. **Gemini for research/review** — architecture analysis, 1M context codebase reading
5. **Planning with Files** — track state in task_plan.md, findings.md, progress.md
6. **GSD2 scientific method** — hypothesis → test → confirm before fixing
7. **Parallel dispatch** — Codex and Gemini work simultaneously for review
8. **Triple review required** — minimum 7/10 average to submit
9. **8-item quality gate** — from PullRequest.md research standard
10. **Seven-step PR format** — from PR.md workflow standard
11. **One fix per PR** — small, reviewable, easy to merge
12. **Follow up** — PRs are conversations, not fire-and-forget
