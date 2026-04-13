---
name: github-pr
description: "Find confirmed open issues in agent/LLM repos and submit professional PRs using the full GSD2 workflow. Searches for 'help wanted' / 'good first issue' / maintainer-confirmed bugs, sets up environment, plans fix via GSD2, implements with Codex, verifies with tests + Codex + Gemini review, submits PR per PR.md standard. Also supports batch-fixing 5-10 issues in one repo. Use when the user mentions submitting PRs, fixing open source issues, contributing patches, building contributor reputation, or wants to fix bugs found by github-hunt."
---

# GitHub PR Pipeline v3 — GSD2 Workflow

Find confirmed open issues → set up environment → GSD2 plan → implement fix → verify (tests + dual review) → submit PR per PR.md standard.

## Strategy

The goal is to build a credible contributor profile, not just push code. This means:

1. **Fix OTHER people's issues** — search for issues maintainers want fixed ("help wanted", "good first issue", confirmed bugs with reproduction steps)
2. **Batch-fix option** — pick a repo with many open issues, fix 5-10 in one session
3. **Build reputation** — start with easy fixes, earn trust, then tackle harder bugs
4. **Follow up** — PRs aren't fire-and-forget; respond to reviewer feedback

Do NOT fix our own filed issues unless a maintainer has explicitly confirmed and welcomed a fix.

## Execution Model

- **Claude**: Orchestrator, code analysis, PR authoring
- **Codex** (`codex:codex-rescue` agent): Fix generation (write mode) + code review
- **Gemini** (`gemini:gemini-consult` agent): Architecture understanding + review for complex fixes
- **GSD2 methodology**: Plan before coding, debug systematically, verify before submitting
- **gh CLI**: Issue search, fork, PR creation, status monitoring

## Context

- Archive: `~/workspace/archive/`
- Staging: `~/workspace/pr-stage/`
- GitHub: `gh` authenticated as CrepuscularIRIS
- PR standard: follow PR.md seven-step workflow (Fork → Clone → Branch → Commit → Push → PR → Review)

---

## Phase 1: FIND FIXABLE ISSUES

### Strategy A: Search for labeled issues

```bash
# "good first issue" in agent/LLM repos
gh search issues --label="good first issue" --state=open --sort=created --limit=30 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR langchain OR rag OR embedding"

# "help wanted"
gh search issues --label="help wanted" --state=open --sort=created --limit=30 \
  --json repository,title,number,labels,createdAt,comments \
  -- "agent OR llm OR inference OR serving"

# Confirmed bugs with maintainer responses
gh search issues --label="bug" --state=open --sort=comments --limit=30 \
  --json repository,title,number,labels,createdAt,comments \
  -- "crash OR panic OR error OR fix confirmed"
```

### Strategy B: Batch-fix a single repo

Pick a repo from `~/workspace/archive/` with many open issues:
```bash
for repo in ~/workspace/archive/*/; do
  name=$(basename "$repo")
  remote=$(cd "$repo" && git remote get-url origin 2>/dev/null | sed 's|.*github.com/||;s|\.git||')
  [ -z "$remote" ] && continue
  count=$(gh issue list --repo "$remote" --state open --limit 500 --json number 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
  echo "$count open issues: $remote"
done | sort -rn | head -10
```

### Filter criteria for issue selection

- **Maintainer acknowledged** — at least one comment from a repo member (not just the reporter)
- **Age >7 days** — not a fresh report that might be invalid or duplicate
- **Reproducible** — has steps, test case, or error message
- **Fixable in <100 lines** — estimated scope is manageable
- **Has CI/tests** — so the fix can be verified against the project's own test suite
- **Not already assigned** — respect other contributors' claimed work

Select 1-5 issues to fix. For batch mode, prefer issues in the same repo.

---

## Phase 2: ENVIRONMENT SETUP

For the target repo, create a working development environment:

```bash
cd ~/workspace/archive/<repo-name>

# Fork if not already forked
gh repo fork <owner/repo> --clone=false 2>/dev/null || true

# Set up upstream tracking
git remote add upstream https://github.com/<owner/repo>.git 2>/dev/null || true
git fetch upstream
git checkout main && git pull upstream main

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

### Establish baseline

Run the full test suite BEFORE making any changes:
```bash
# Record how many tests pass/fail before our changes
pytest --tb=short -q 2>&1 | tail -5  # or go test / npm test
```

Save this baseline — after the fix, test count must be equal or better.

---

## Phase 3: GSD2 PLAN (per issue)

For each issue, plan the fix before writing code. Understanding root cause prevents wasted effort.

### 3a. Read the issue thoroughly

```bash
gh issue view <N> --repo <owner/repo> --json title,body,labels,comments
```

Extract: what's broken, reproduction steps, maintainer hints, related files.

### 3b. Understand the code path

Read the relevant source files. Trace from entry point to the bug location:
- What function is involved?
- What input triggers the bug?
- Why does the current code fail?

### 3c. Plan the minimal fix

Answer these questions before writing any code:
- **Root cause**: Why does the bug exist? (one sentence)
- **Fix location**: Which file(s) and line(s) to change?
- **Fix approach**: What's the minimal change? (describe in 1-3 sentences)
- **Test strategy**: How to prove the fix works? (existing test? new test? manual repro?)
- **Risk**: What could this change break?

### 3d. Create fix branch

```bash
git checkout main && git pull upstream main
git checkout -b fix/<issue-slug>
```

---

## Phase 4: IMPLEMENT THE FIX

### Simple fixes (<20 lines): Codex direct

Spawn `codex:codex-rescue` agent with write mode:

```
Fix the bug in ~/workspace/archive/<repo-name> described in issue #<N>:

<paste issue title and key details>

Root cause: <your analysis from Phase 3>
Affected file(s): <file:line>

Requirements:
1. Minimal change — fix only the bug, don't refactor surrounding code
2. Follow the repo's existing code style exactly
3. Add or modify a test that proves this specific bug is fixed
4. Keep total changes under 20 lines
```

### Complex fixes (20-100 lines): Claude + Codex + Gemini

1. **Gemini** (`gemini:gemini-consult`): "Explain the architecture around `<file:line>`. What design patterns does this module use? What are the invariants I need to preserve when modifying this code?"

2. **Claude**: Write the fix based on root cause analysis + Gemini's architecture insight

3. **Codex** (`codex:codex-rescue`): "Review and refine this diff for correctness. Does it fix the bug without breaking invariants?"

### Batch fixes (multiple issues in one repo)

One branch per issue, fix sequentially:
```bash
for issue_num in <list>; do
  git checkout main && git pull upstream main
  git checkout -b fix/issue-$issue_num
  # ... implement fix ... run tests ... commit ...
done
```

---

## Phase 5: VERIFY THE FIX

Every fix must pass all verification gates before submitting a PR.

### 5a. Run full test suite

```bash
source .venv/bin/activate 2>/dev/null
pytest --tb=short -q 2>&1
# Compare against Phase 2 baseline — must be equal or better
```

If the fix breaks existing tests, debug and fix the regression. Never submit a PR with failing tests.

### 5b. Run the specific bug reproduction

```bash
# The specific test that was failing, or the reproduction from the issue
pytest tests/test_specific.py::test_case -v 2>&1
```

This must now PASS (or the vulnerability must no longer be triggerable).

### 5c. Codex review

Spawn `codex:codex-rescue` agent:
```
Review the git diff in ~/workspace/archive/<repo-name>.

Check:
1. Does this fix actually address the reported bug?
2. Does it introduce any regressions or new bugs?
3. Does it follow the repo's existing code style?
4. Is there a simpler approach?
5. Are edge cases handled?

Output: PASS or FAIL with specific reasoning.
```

### 5d. Gemini review (for complex fixes only)

Spawn `gemini:gemini-consult` agent:
```
Review this fix for architectural correctness.
<paste the git diff>

Questions:
1. Does this respect the module's design patterns?
2. Are there edge cases not covered by the fix?
3. Could this change have unintended side effects in other modules?

Output: PASS or FAIL with reasoning.
```

### Gate decision

- Both reviews PASS + tests pass → proceed to Phase 6
- Any review FAIL → fix the issues, re-run Phase 5
- Tests regress → debug and fix before proceeding

---

## Phase 6: COMMIT AND PR

### Commit (conventional commits)

```bash
git add <changed-files>
git commit -m "fix(<scope>): <concise description>

Fixes <owner/repo>#<issue-number>

<one-line: what was wrong and how this fixes it>"
```

### Push

```bash
git push origin fix/<issue-slug>
```

### Create PR (following PR.md seven-step standard)

```bash
gh pr create \
  --repo <owner/repo> \
  --title "fix(<scope>): <description>" \
  --body "$(cat <<'EOF'
## Summary

Fixes #<issue-number>

<2-3 sentences: what was broken and how this PR fixes it>

## Root Cause

<1-2 sentences explaining WHY the bug existed — this shows you understand the codebase>

## Changes

- `<file>`: <what changed and why>

## Testing

- [x] Full test suite passes (no regressions)
- [x] Added/modified test for this specific fix
- [x] Reproduction steps from issue no longer trigger the bug

```bash
# Verify with:
pytest tests/test_specific.py::test_case -v
```

## Notes

Minimal fix — no unrelated changes included.
Happy to adjust based on review feedback.
EOF
)"
```

---

## Phase 7: MONITOR AND ITERATE

PRs are conversations, not fire-and-forget submissions.

### Check for feedback

```bash
gh pr view <N> --repo <owner/repo> --json state,reviews,comments,reviewRequests
```

### Respond to review comments

- **Code style feedback**: Fix immediately, push to same branch
- **Alternative approach suggested**: Evaluate, discuss if needed, implement if better
- **Request for more tests**: Add them
- **Request for scope change**: Discuss — keep the PR minimal

```bash
# After making changes based on review:
git add <files>
git commit -m "refactor: address review feedback — <what changed>"
git push origin fix/<issue-slug>
```

The PR updates automatically when you push to the same branch.

---

## Phase 8: REPORT

Write to `~/workspace/pr-stage/pr-report-<date>.md`:

```markdown
# PR Report — <date>

## Issues Fixed
| Issue | PR | Status | Tests | Codex | Gemini |
|-------|-----|--------|-------|-------|--------|
| owner/repo#N | #M | submitted | PASS | PASS | PASS |

## Environment
- Repo: <name> (<stars>⭐, <lang>)
- Baseline: X pass / Y fail
- After fix: X+N pass / Y-M fail

## Notes
- <any caveats, pending reviews, or follow-up needed>
```

---

## Rules

1. **Fix OTHER people's issues** — don't submit unsolicited fixes for our own reports
2. **Environment setup is mandatory** — build and test before changing anything
3. **Plan before coding** — understand root cause, don't guess-and-check
4. **Tests must pass** — never submit a PR with regressions
5. **Codex + Gemini review** — both must PASS before submitting
6. **PR.md standard** — seven-step workflow, boring professional PRs
7. **One fix per PR** — unless batch-fixing clearly related issues
8. **Follow up on reviews** — respond to feedback, iterate on same branch
9. **Conventional commits** — `fix(<scope>): <description>` + `Fixes #N`
10. **No jargon** — PR reads as if a thoughtful engineer submitted it
