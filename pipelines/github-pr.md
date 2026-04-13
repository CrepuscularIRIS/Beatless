---
name: github-pr
description: "End-to-end open source contribution pipeline. Discovers fixable issues in agent/LLM repos (good first issue, help wanted, confirmed bugs), evaluates repo quality, sets up dev environment, runs tests to find/confirm bugs, plans fix via GSD2, implements with Codex, triple-reviews with Claude+Codex+Gemini against 8-item quality standard, then submits PR per seven-step workflow. Use whenever the user mentions contributing to open source, submitting PRs, fixing GitHub issues, building contributor reputation, finding good first issues, or wants to help agent/LLM projects."
---

# GitHub PR Pipeline v5 — Unified Contribution Engine

End-to-end: discover fixable issues → evaluate repo → setup env → run tests → plan fix → implement → triple review → submit PR.

## Philosophy

The goal is building a credible contributor profile, not spamming issues. Every PR must pass an 8-item quality gate before submission. The pipeline merges discovery (formerly github-hunt) with delivery (PR submission) into one flow: find something worth fixing, fix it properly, get it merged.

Key principles from research:
- PR acceptance depends more on contributor reputation, communication quality, and scope control than on code cleverness
- Maintainers value "low friction to review" above all — small scope, clear description, tests included
- Start with docs/small bugs/test gaps, not architecture rewrites
- One PR per issue, follow repo conventions exactly

## Execution Model

- **Claude**: Orchestrator, code analysis, PR authoring, root cause analysis
- **Codex** (`codex:codex-rescue` agent): Fix implementation (write mode) + independent code review
- **Gemini** (`gemini:gemini-consult` agent): Architecture analysis + independent code review
- **GSD2 methodology**: Plan before coding, debug systematically, verify before claiming done
- **gh CLI**: Issue/repo search, fork, PR creation, status monitoring
- **uv / npm / go**: Environment setup and test execution

## Context

- Archive: `~/workspace/archive/`
- Staging: `~/workspace/pr-stage/`
- GitHub: `gh` authenticated as CrepuscularIRIS
- Scoring rubric: `~/workspace/pr-stage/pr-scoring-rubric.md`

---

## Phase 1: DISCOVER FIXABLE ISSUES

The best issues to fix are ones where the maintainer has already said "yes, this needs fixing."

### Search strategy

```bash
# Priority 1: good first issue in agent/LLM repos
gh search issues --label="good first issue" --state=open --sort=updated --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR langchain OR rag OR mcp OR embedding"

# Priority 2: help wanted
gh search issues --label="help wanted" --state=open --sort=updated --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR inference OR serving OR tool"

# Priority 3: confirmed bugs with maintainer response
gh search issues --label="bug" --state=open --sort=comments --limit=20 \
  --json repository,title,number,labels,createdAt,comments \
  -- "crash OR panic OR fix OR broken"
```

### Issue selection criteria

Pick issues that meet ALL of these:
- **Maintainer acknowledged** — at least one comment from a repo member, not just the reporter
- **Age >7 days** — not a fresh report that might be duplicate or invalid
- **Clear scope** — reproduction steps, error message, or specific file mentioned
- **Fixable in <100 lines** — manageable scope for building trust
- **Not assigned** — respect other contributors' claimed work
- **Repo has tests/CI** — so the fix can be verified

Skip issues that are: feature requests disguised as bugs, design discussions, performance optimization debates, or "everything is broken" reports with no specifics.

---

## Phase 2: EVALUATE REPO QUALITY

Before investing time, check if the repo is contributor-friendly. Read these files:

```bash
cd ~/workspace/archive/<repo-name>
# Check contributor infrastructure
cat CONTRIBUTING.md 2>/dev/null | head -50
cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null
cat .github/CODEOWNERS 2>/dev/null | head -10
```

### Repo scorecard (all should be YES)

- Has CONTRIBUTING.md or contributor guidelines?
- Has PR template?
- Recent commits in last 30 days?
- PRs are being reviewed and merged (not ignored)?
- CI is running on PRs?
- Issues have maintainer responses?
- Has `good first issue` / `help wanted` labels?

If a repo fails 3+ of these, pick a different one. Investing in an unresponsive repo wastes time.

### Read recent merged PRs

```bash
gh pr list --repo <owner/repo> --state merged --limit=5 --json title,body,files,reviews
```

Study how the maintainers like PRs formatted. What commit style? How detailed are descriptions? Do they expect tests? This tells you what "good" looks like for THIS specific repo.

---

## Phase 3: SETUP ENVIRONMENT

Build a working dev environment. If this fails, try to fix dep issues. If still broken, skip this repo.

```bash
cd ~/workspace/archive/<repo-name>

# Fork + upstream tracking
gh repo fork <owner/repo> --clone=false 2>/dev/null || true
git remote add upstream https://github.com/<owner/repo>.git 2>/dev/null || true
git fetch upstream && git checkout main && git pull upstream main

# Python
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ]; then
  uv venv .venv && source .venv/bin/activate
  uv pip install -e ".[dev,test]" 2>&1 || uv pip install -e ".[dev]" 2>&1 || uv pip install -e . 2>&1
  [ -f requirements-dev.txt ] && uv pip install -r requirements-dev.txt 2>&1
fi

# Go
if [ -f go.mod ]; then go mod download && go build ./... 2>&1; fi

# Node.js
if [ -f package.json ]; then npm install && npm run build 2>&1 || true; fi
```

### Establish test baseline

Run the full test suite BEFORE making any changes:
```bash
pytest --tb=short -q 2>&1 | tail -10  # or go test / npm test
```

Record pass/fail counts. After the fix, this must be equal or better.

---

## Phase 4: REPRODUCE AND UNDERSTAND THE BUG

Before writing any code, prove you understand the problem.

### Read the issue thoroughly
```bash
gh issue view <N> --repo <owner/repo> --json title,body,labels,comments
```

### Reproduce the bug

If the issue includes repro steps, follow them exactly:
```bash
# Run the specific failing test or repro command from the issue
pytest tests/test_specific.py::test_case -v --tb=long 2>&1
```

If there's no repro in the issue, construct one from the description. If you can't reproduce it, leave a polite comment asking for more details — don't guess.

### Trace root cause

Read the stack trace or error output bottom-up:
1. Which file:line in production code fails?
2. What input/condition triggers it?
3. Why does the current code handle it incorrectly?
4. What's the minimal change to fix it?

Write down your understanding as a 3-sentence root cause analysis. This goes in the PR description later.

---

## Phase 5: PLAN THE FIX (GSD2 style)

Answer these before writing any code:

- **Root cause** (1 sentence): Why does the bug exist?
- **Fix location**: Which file(s) and line(s)?
- **Fix approach** (1-3 sentences): What's the minimal change?
- **Test strategy**: How to prove the fix works? Existing test? New test?
- **Risk**: What could this change break? Any edge cases?
- **Scope check**: Is this still <100 lines? If not, narrow it.

Create fix branch:
```bash
git checkout main && git pull upstream main
git checkout -b fix/<issue-slug>
```

---

## Phase 6: IMPLEMENT THE FIX

### Simple fixes (<20 lines): Codex direct

Spawn `codex:codex-rescue` agent:
```
Fix the bug in ~/workspace/archive/<repo-name> described in issue #<N>:
<paste issue title + key details>

Root cause: <your analysis from Phase 4>
Affected file(s): <file:line>

Requirements:
1. Minimal change — fix only the bug
2. Follow the repo's existing code style exactly
3. Add or modify a test that proves this specific bug is fixed
4. Keep under 20 lines changed
```

### Complex fixes (20-100 lines): Claude + Codex + Gemini

1. **Gemini** (`gemini:gemini-consult`): "Explain the architecture around `<file:line>`. What design patterns and invariants must I preserve?"
2. **Claude**: Write the fix based on root cause + Gemini's architecture insight
3. **Codex** (`codex:codex-rescue`): "Review and refine this diff. Does it fix the bug without breaking invariants?"

### After implementation

Verify the diff is clean:
```bash
git diff --stat
git diff
```

Check: Is the diff <100 lines? Does it touch only relevant files? No debug prints, no commented-out code, no unrelated formatting changes?

---

## Phase 7: VERIFY THE FIX

Every fix must pass ALL verification gates.

### 7a. Full test suite
```bash
pytest --tb=short -q 2>&1
# Compare against Phase 3 baseline — must be equal or better
```

If the fix breaks existing tests, debug and fix. Never submit with regressions.

### 7b. Specific bug reproduction
```bash
# The test/command that was failing must now pass
pytest tests/test_specific.py::test_case -v 2>&1
```

### 7c. Lint/format check
```bash
# Follow whatever the repo uses
ruff check . 2>/dev/null || true
go vet ./... 2>/dev/null || true
npm run lint 2>/dev/null || true
```

---

## Phase 8: TRIPLE REVIEW (Claude + Codex + Gemini)

Spawn all three reviewers in PARALLEL. Each scores independently against the 8-item quality standard.

### Codex review (`codex:codex-rescue`)
```
Review this PR diff in ~/workspace/archive/<repo-name> against these 8 criteria.
Score each 1-10:

1. Direction correct — does this fix address a real, welcomed issue?
2. Follows repo rules — matches CONTRIBUTING.md, code style, commit format?
3. Small scope — only changes needed for the fix, nothing extra?
4. Complete description — root cause explained, verification included?
5. Verifiable — tests pass, reproduction command works?
6. Code quality — clean diff, no debug artifacts, lint-clean?
7. Correctness — actually fixes the bug? edge cases handled?
8. No regressions — existing tests still pass?

Output: score table + PASS/FAIL verdict. FAIL if any dimension <5 or average <7.
```

### Gemini review (`gemini:gemini-consult`)
```
Review this PR diff for architectural correctness and social fit:

1. Does the fix respect the module's design patterns?
2. Are edge cases covered?
3. Would a maintainer find this easy to review?
4. Is the PR description clear and complete?
5. Is the tone humble and professional?
6. Would you merge this if you were the maintainer?

Output: score table + PASS/FAIL verdict. Be strict.
```

### Claude self-review

Score the diff yourself using the rubric at `~/workspace/pr-stage/pr-scoring-rubric.md`.

### Gate decision

- All three PASS + average >=7/10 → proceed to Phase 9
- Any FAIL → fix the issues, re-run Phase 7-8
- Average <7/10 → the fix needs more work before submitting

---

## Phase 9: COMMIT AND PR

### Commit (conventional format)
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

### Create PR (seven-step standard from PR.md)
```bash
gh pr create \
  --repo <owner/repo> \
  --title "fix(<scope>): <description>" \
  --body "$(cat <<'EOF'
## Summary

Fixes #<issue-number>

<2-3 sentences: what was broken and how this PR fixes it>

## Root Cause

<1-2 sentences: WHY the bug existed — this shows you understand the codebase>

## Changes

- `<file>`: <what changed and why>

## Testing

- [x] Full test suite passes (no regressions)
- [x] Specific reproduction no longer triggers the bug
- [x] Reviewed by independent code analysis

```bash
# Verify with:
<exact test command>
```

## Notes

Minimal fix — no unrelated changes included.
Happy to adjust based on review feedback.
EOF
)"
```

---

## Phase 10: MONITOR AND ITERATE

PRs are conversations. Check daily and respond promptly.

```bash
gh pr view <N> --repo <owner/repo> --json state,reviews,comments,reviewRequests
```

- **Code style feedback**: Fix immediately, push to same branch
- **Alternative approach suggested**: Evaluate honestly, implement if better
- **More tests requested**: Add them
- **Scope concerns**: Discuss, keep minimal

```bash
git add <files>
git commit -m "refactor: address review feedback — <what changed>"
git push origin fix/<issue-slug>
```

---

## Phase 11: REPORT

Save to `~/workspace/pr-stage/pr-report-<date>.md`:

```markdown
# PR Report — <date>

## Submitted
| Issue | PR | Repo | Fix | Score |
|-------|-----|------|-----|-------|
| #N | #M | owner/repo | description | 8.5/10 |

## Triple Review Scores
| Dimension | Claude | Codex | Gemini | Avg |
|-----------|--------|-------|--------|-----|
| Direction | N | N | N | N |
| Repo rules | N | N | N | N |
| Scope | N | N | N | N |
| Description | N | N | N | N |
| Verifiable | N | N | N | N |
| Code quality | N | N | N | N |
| Correctness | N | N | N | N |
| No regressions | N | N | N | N |
| **Average** | | | | **N** |

## Test Baseline
- Before: X pass / Y fail
- After: X+N pass / Y-M fail

## Reviewer Status
- Pending / Approved / Changes Requested
```

---

## Rules

1. **Only fix welcomed issues** — `good first issue`, `help wanted`, or maintainer-confirmed
2. **Evaluate repo first** — don't invest in unresponsive repos
3. **Reproduce before fixing** — prove you understand the bug
4. **Plan before coding** — root cause analysis, not guess-and-check
5. **Tests must pass** — never submit with regressions
6. **Triple review required** — Claude + Codex + Gemini all must PASS
7. **Minimum 7/10 average** — below this, improve the fix before submitting
8. **Seven-step PR format** — title, description, root cause, changes, testing, notes
9. **One fix per PR** — small scope, easy to review
10. **Follow up on reviews** — respond promptly, iterate on same branch
11. **No static-only findings** — every fix must be verified by running code
12. **Build trust gradually** — start with docs/small bugs, earn bigger fixes later
