---
description: "Unified open source contribution pipeline. Discovers fixable issues, runs policy preflight (AI content policy, CLA, duplicates), evaluates repos, sets up env, runs tests, debugs via GSD2, implements fix, triple-reviews against 8-item quality standard (pr-quality-gate skill), submits PR per seven-step workflow (pr-workflow skill). Integrates Beatless/standards (PR.md, PullRequest.md, mention.md, Chinese deep-dive) and pua methodology for internal rigor. Works standalone — plugins optional."
---

# GitHub PR Pipeline v8 — Contribution Engine

End-to-end: discover → **policy preflight** → evaluate → setup → reproduce → debug → implement → verify → review → submit → report.

## Source-of-Truth Standards (READ BEFORE EVERY RUN)

This pipeline is bound to the seven documents in `~/claw/Beatless/standards/`. If any of these change, the pipeline behavior changes. Do not invent rules that contradict them; if you think the rules are wrong, surface the conflict rather than working around it.

| File | Use for |
|------|---------|
| `PR.md` | Seven-step fork→clone→branch→commit→push→PR→review workflow. Authoritative cheat-sheet. |
| `PullRequest.md` | 8-item quality gate with hard-fail items (Direction, Compliance), social etiquette, AI disclosure. |
| `PR.source.md` | Original long-form source for PR.md. Use when PR.md is ambiguous. |
| `PullRequest.source.md` | Original long-form source for PullRequest.md. Consult for edge cases. |
| `mention.md` | **Double-layer design**: internal system can be complex, external expression must be plain. Never export internal jargon to external PRs. |
| `GitHub PR 贡献指南.md` | Maintainer psychology, trust capital, PR-size→review-time non-linearity, AI integrity red line, rebase-over-merge rationale. |
| `actions.md` | Reference-quality engineering article (benchmark for what good technical writing looks like). |

Also consult `~/claw/pua/skills/pua-en/SKILL.md` for **internal debugging methodology** only — its 5-step Elevate loop (read failure signals → search → read source → verify assumptions → invert) applies when CI fails, a bug won't reproduce, or a fix doesn't stick. **Do not export pua rhetoric externally.** External tone stays humble per PullRequest.md §Social Etiquette.

## Routing Anchors (must follow)

- **Workspace root**: `~/workspace`
- **Contribution repos**: `~/workspace/contrib/<repo-name>/`
- **Planning-with-Files root**: `~/workspace/pr-stage/<repo-name>/`
- **Required planning files** (create before any implementation):
  - `~/workspace/pr-stage/<repo-name>/task_plan.md`
  - `~/workspace/pr-stage/<repo-name>/findings.md`
  - `~/workspace/pr-stage/<repo-name>/progress.md`
- **Pipeline report**: `~/workspace/pr-stage/<repo-name>/pr-report.md`

## Plugin Policy (optional accelerators, not hard dependencies)

Plugins may be unavailable in `-p` mode or fail to initialize. Every phase MUST work with Claude + Bash alone. Plugins add speed/depth when available.

| Plugin | Best at | Invoke via | Fallback |
|--------|---------|------------|----------|
| Codex (`codex:codex-rescue`) | Contained code fixes, sandbox testing | Agent tool, subagent_type `codex:codex-rescue` | Claude edits files + runs tests via Bash |
| Gemini (`gemini:gemini-consult`) | Large codebase reading (1M context), architecture review | Agent tool, subagent_type `gemini:gemini-consult` | Claude reads key files + grep for patterns |

**Try once, fallback immediately.** Do not retry plugins more than once per phase. If unavailable, proceed with Claude-only and note it in the report.

## Quality Standards (loaded as skills)

Invoke BEFORE Phase 9:
- **`pr-workflow`** — seven-step method (Fork→Clone→Branch→Commit→Push→OpenPR→Review), PR description template
- **`pr-quality-gate`** — 8-item scoring rubric, aggregation rules, social etiquette, AI disclosure

---

## Phase 1: DISCOVER

Find issues maintainers explicitly welcome contributions on.

```bash
gh search issues --label="good first issue" --state=open --sort=updated --limit=10 \
  --json repository,title,number,labels,createdAt,comments
```

Selection criteria (per `GitHub PR 贡献指南.md` §Issue Selection):

- **Goldilocks priority**: avoid trivial (docs typos have limited impact) AND core architectural rewrites (high bar for new contributors). Prefer medium-difficulty `help wanted` / `bug` items with clear repro steps.
- **Maintainer engagement**: issue shows recent maintainer comments acknowledging the problem.
- **Claim etiquette**: before coding, comment "May I try this?" if the repo's CONTRIBUTING asks — otherwise `/assign` or standard claim comment.
- **Not already claimed or with competing PR.**

## Phase 2: POLICY PREFLIGHT (HARD FAIL)

Before any clone or code, verify each candidate repo against `PullRequest.md` hard-fail items (Direction Alignment + Repository Rules Compliance). Skip the issue on any failure — do NOT submit anyway.

### 2a. AI Content Policy Check

Read `CONTRIBUTING.md`, `README.md`, and `.github/CONTRIBUTING.md` end-to-end. Reject if you see language forbidding AI-generated contributions. Typical triggers:

- "AI-generated code of any kind is forbidden"
- "LLM output is not permitted / will be rejected"
- "Contributions produced by AI assistants are prohibited"
- "We do not accept AI-generated content"

Per `GitHub PR 贡献指南.md` §AI Era Integrity Boundary: maintainers currently have extremely high vigilance about AI code. Some repos host their policy on an external site (e.g. `secureblue.dev`) and only reference it in close comments — if you cannot find a policy in-repo, scan the last ~30 closed-unmerged PRs for rejection comments mentioning "AI content policy" / "AI generated" / similar. Treat such evidence as a hard fail.

On fail: `PIPELINE_RESULT: repo-forbids-ai | <owner>/<repo>` and move to the next candidate.

### 2b. CLA / DCO Check

Grep `CONTRIBUTING.md` for: `Contributor License Agreement`, `CLA`, `Developer Certificate of Origin`, `DCO`, `Signed-off-by`, `sign-off`.

- If a CLA is required and a CLA bot is present: you must sign before the PR can merge. If signing requires manual browser action, STOP this candidate and emit `PIPELINE_RESULT: cla-blocked | <owner>/<repo>`. Do not submit in the hope it will "just work".
- If DCO is required: every commit needs a valid `Signed-off-by:` line matching your git author identity. Configure `git commit -s` before committing.

### 2c. Duplicate / Competing Work Check

```bash
gh pr list --repo <owner>/<repo> --state open --search "#<issue-number>" --json number,title,body
gh api repos/<owner>/<repo>/issues/<issue-number>/comments --jq '.[] | {login: .user.login, body: .body}'
```

Reject if:
- An open PR already links `Fixes #<issue>` / `Closes #<issue>` / `Resolves #<issue>`.
- A non-bot, non-author commenter said "I'll work on this", "I'm on it", `/assign`, or similar within the last 14 days.

On fail: `PIPELINE_RESULT: duplicate | <url-of-existing-pr-or-claim>`.

### 2d. Contribution Direction Sanity (JUDGMENT via skill)

**Do NOT try to decide this with grep.** Invoke:

```
Skill("pr-direction-check")
```

Pass the pre-fetched JSON blob (issue body, labels, last 20 comments with
`author_association`, CONTRIBUTING.md excerpt, related open PRs). The skill
returns a single `DIRECTION_VERDICT:` line with one of:

- `proceed` — safe to continue
- `block:ai-forbidden` / `block:maintainer-disputed` / `block:rejected-label` / `block:duplicate-pr` / `block:discussion-not-patch`
- `yield:claimed` / `yield:stale-claim`
- `ambiguous:<reason>` — surface to human, do not proceed autonomously

On any `block:*` verdict, emit matching `PIPELINE_RESULT:` and move to next candidate. On `ambiguous:*`, halt this candidate and log the evidence.

**Why a skill and not Python regex**: dispute detection, AI-policy interpretation, and claim-recency reading all require reading tone + context. Regex gets both false positives ("I don't see any reason to object" flagged as dispute) and false negatives (genuine skepticism phrased unusually). The judgment lives in the skill; Python only supplies the fetched data.

---

## Phase 3: EVALUATE REPO

Before committing to work, verify the repo is contribution-friendly (per `PR.source.md` §Evaluate):

- [ ] `CONTRIBUTING.md` exists and is clear
- [ ] Recent merge activity (PRs merged in last 30 days)
- [ ] CI pipeline visible (GitHub Actions / other)
- [ ] Maintainer responds to issues within ~7 days
- [ ] License is permissive (MIT, Apache, BSD)
- [ ] PR-size expectations match your planned diff (see §Atomicity below)

**Skip if any of**: no contributing guide, no activity in 60 days, hostile issue comments.

### Atomicity Sizing (per GitHub PR 贡献指南 §Size)

| Class | LOC | Expected review time | Signal |
|-------|-----|---------------------|--------|
| Trivial | <50 | Fast | Welcomed sparingly — do not spam |
| **Small (ideal)** | 50–200 | 1–3 days | **Highest acceptance rate** |
| Medium | 200–500 | Needs dedicated review slot | Multiple review rounds likely |
| Large | >500 | Usually stalled or rejected | Consider splitting into stacked PRs |

If your planned diff will exceed 500 LOC, plan to split before you touch code. One logical change per PR, always.

## Phase 4: SETUP

### 4a. Initialize planning files (MANDATORY)

Invoke the Skill:

```
Skill("planning-with-files:plan", args="<repo-name>: <issue-title>")
```

This creates `task_plan.md`, `findings.md`, `progress.md` under `~/workspace/pr-stage/<repo-name>/`. Every subsequent phase writes into these files. Do not skip — the cron-wake-gate protocol depends on these files being present so a later tick can resume.

### 4b. Fork + clone + bootstrap

```bash
gh repo fork <owner>/<repo> --clone --remote
cd <repo>

# Install dependencies + run existing tests
# (language-specific — read README/CONTRIBUTING first)
```

Record baseline test results in `findings.md`. If tests fail before your changes, note which ones and why.

## Phase 5: REPRODUCE (invoke Superpowers)

Dynamically confirm the bug exists by running code, not just reading it.

### 5a. MANDATORY: invoke `superpowers:systematic-debugging`

```
Skill("superpowers:systematic-debugging")
```

This gives you the hypothesis → evidence → verify loop. Follow it rigorously; `findings.md` captures every step.

### 5b. Test-driven contribution

Invoke `superpowers:test-driven-development` and write a **failing test first**:

```
Skill("superpowers:test-driven-development")
```

The failing-test + patch pattern is the strongest evidence a maintainer can see (`GitHub PR 贡献指南.md` §Test-Driven Contribution).

- Record exact error output in `findings.md`.
- If you cannot reproduce after a full pua 5-step elevation + Superpowers debugging loop: post a polite clarification comment on the issue and emit `PIPELINE_RESULT: issue-skipped | cannot-reproduce`. Do not guess.

## Phase 6: ROOT CAUSE + PLAN

Analyze the failure, identify root cause, plan the fix.

- Trace execution path from trigger to failure.
- Identify the minimal set of files to change.
- Update `task_plan.md` with specific files and changes (keep the plan atomic — one logical change per entry).
- Consider: does this fix break anything else? Check callers/dependents (pua "Owner Mindset" — similar bugs elsewhere? upstream/downstream affected?).

### 6a. Gemini for large-codebase reads (when needed)

Two equivalent invocation paths — use whichever is live. Prefer Bash when running in `claude -p` cron context; prefer Agent tool when running interactively.

**Path A — Bash CLI (always available; headless):**
```bash
gemini -p "Trace <function> call chain in <repo-path>. Identify the <n> most likely callers affected by <proposed change>. Output: file:line refs + a one-line risk assessment per caller." --model gemini-2.5-pro
```

**Path B — Agent tool (plugin route; same CLI under the hood):**
```
Agent(subagent_type="gemini:gemini-consult", prompt="Trace <function> call chain in <repo> ... ")
```

Fallback if both unavailable: `grep -rn` + reading key files manually.

### 6b. Stuck > 2 iterations? Escalate to GSD debug

If Phase 5 + 6 haven't produced a root cause after two rounds, invoke:

```
Skill("gsd:gsd-debug")
```

GSD debug persists state across context resets — it's the right tool when the bug survives an `/exp-review` cycle.

## Phase 7: IMPLEMENT

Make the fix. Keep changes minimal and atomic.

- Follow the repo's code style exactly (check recent merged PRs for patterns).
- One logical change only — no drive-by refactors (per `mention.md` §PR 要无聊越无聊越好).
- Add/update tests that cover the fix.
- If DCO was flagged in 2b, use `git commit -s` for every commit.
- **Commit hygiene** per `GitHub PR 贡献指南.md` §Commit Hygiene: each commit compiles, is bisect-friendly, has descriptive message. Squash WIP commits via `git rebase -i` before push.

### 7a. Codex for contained fixes

For self-contained bug fixes (< 100 LOC, single module), delegate to Codex.

**Path A — Bash CLI (always available; headless):**
```bash
codex exec "<exact-repro-steps>
Fix in <file>:<line-range>. Tests live in <test-path>.
Run the specific failing test after edit; paste passing output.
Apply the fix via git apply when done."
```

**Path B — Agent tool (plugin route; same CLI under the hood):**
```
Agent(subagent_type="codex:codex-rescue", prompt="<same prompt as above>")
```

Fallback if both unavailable: Claude edits via Edit tool + verifies via Bash.

## Phase 8: VERIFY (invoke verification gate)

### 8a. MANDATORY: invoke `superpowers:verification-before-completion`

```
Skill("superpowers:verification-before-completion")
```

This skill blocks "it works on my machine" claims — you MUST paste the actual passing test output into `findings.md` before this phase can end.

### 8b. Run the suite

```bash
# Run full test suite — language-specific
pytest -xvs             # Python
go test -race ./...     # Go
npm test                # JS/TS
cargo test --all        # Rust

# Run linters if configured
ruff check / golangci-lint / eslint / clippy
```

All tests must pass locally BEFORE pushing. Paste the exact passing output into `findings.md`. If tests fail, return to Phase 5 (systematic-debugging) — do NOT push.

## Phase 9: CODE REVIEW (invoke review skills)

### 9a. Self-request via `superpowers:requesting-code-review`

```
Skill("superpowers:requesting-code-review")
```

This guides a structured self-review against your own diff before any external review.

### 9b. GSD-style code review of the diff

```
Skill("gsd:gsd-code-review")
```

Reviews the source files changed during this phase for bugs, security issues, and code-quality problems. Writes findings to `findings.md`.

### 9c. `pr-quality-gate` — 8-item scoring

Invoke skill **`pr-quality-gate`** and score all 8 dimensions. In `-p` mode (automated), run three independent review passes:

1. **Pass 1 — Correctness** (Claude): Does the fix address the root cause? Are tests adequate? Any regressions?
2. **Pass 2 — Architecture** (Gemini subagent if available, else Claude second pass): Does the fix fit the codebase patterns? Any design concerns?
3. **Pass 3 — Quality Gate** (Codex subagent if available, else Claude third pass): Score each of the 8 dimensions per the rubric.

**Aggregation**: mean of 3 passes. Min 7.0/10. Hard fail if Direction or Compliance < 5 from any pass.

If score < 7.0: fix issues, re-verify (Phase 8), re-score (max 2 improvement rounds, threshold rises to 7.5).

## Phase 10: SUBMIT PR

Invoke skill **`pr-workflow`** and follow the seven-step method.

### 10a. Final re-check of policy gates

Right before `gh pr create`, repeat 2a/2b/2c. A duplicate PR may have been opened in the last hour. If so, close your branch with a polite note yielding.

### 10b. PR body requirements

PR body MUST include: What, Why, How, Scope, Verification, AI Disclosure sections (see template in `pr-workflow` skill).

**Tone is part of the submission.** The description is read by humans; it should sound like one — this is the `mention.md` double-layer principle:

- **Internal layer** (your thinking): multi-step, rigorous, exhaustive. Keep this private.
- **External layer** (what the maintainer reads): plain, humble, factual. Write as if a stranger with no knowledge of your stack needs to understand and trust the change.

Concrete rules:

- Humility over cleverness. Use "I might be wrong, but...", "If this direction doesn't fit, no problem.", "Happy to adjust."
- No internal tooling references: no agent names, no multi-model pipelines, no orchestration jargon, no "my analysis shows".
- No status tables, no bolded usernames, no emoji-headed sections in external PR bodies.
- Match the project's language — terminology, commit-message format, comment style.
- Keep it short: 2–6 sentences per section beats a 40-line essay.
- Visual evidence for UI changes: screenshot/GIF before and after (per `GitHub PR 贡献指南.md` §Visual Evidence Leverage).

### 10c. AI Disclosure (required by PullRequest.md §AI Disclosure)

Disclose AI assistance factually. Per the Chinese guide's AI integrity red line: maintainers currently treat unverified AI code as spam — proactive, factual disclosure is the only safe posture.

> AI tools assisted with implementation. Every change was manually reviewed, tested locally, and verified against the project's existing conventions.

Do not hide AI use. Do not brag about it. Just state it.

```bash
git fetch upstream && git rebase upstream/main
git push -u origin <branch-name>

gh pr create --repo <owner>/<repo> \
  --title "<type>: <description>" \
  --body "<use template from pr-workflow skill>"
```

## Phase 11: REPORT

Write `~/workspace/pr-stage/<repo-name>/pr-report.md`:

```markdown
## PR Report
- Issue: <owner>/<repo>#<number>
- PR: <owner>/<repo>#<pr-number>
- Preflight: [pass / <reason-if-fail>]
- Review scores: [pass1, pass2, pass3] → average
- Tests: [pass/fail count]
- Diff size: [LOC class]
- Plugins used: [list or "Claude-only"]
- Status: [submitted / needs-work / blocked]
```

End with a two-line status summary so the wake-gate can parse it:

```
PIPELINE_RESULT: <status> | <pr_url_or_reason>
PIPELINE_QUALITY_SCORE: <float 0-10>
```

**The `PIPELINE_QUALITY_SCORE` line is REQUIRED when status is `pr-created`.** It reports the mean of the triple-review (Phase 9). The wake-gate rewrites your "pr-created" status to `pr-created-unscored` (if the line is missing) or `quality-blocked` (if score < 7.0) before logging — you won't get a green mark for shipping unscored work.

Where `<status>` is one of: `pr-created`, `pr-failed`, `issue-skipped`, `needs-human`, `repo-forbids-ai`, `cla-blocked`, `duplicate`, `maintainer-disputed`, `error`.
