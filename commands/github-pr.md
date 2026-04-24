---
description: "Open-source contribution pipeline. Session-start → discover → policy preflight → evaluate → setup → reproduce → implement → verify → triple-review → submit → report. Bound to Beatless/standards + pua. Plugins optional."
---

# /github-pr — Contribution Engine v9

## Bound references

- `~/claw/Beatless/standards/` — `PR.md` (7-step), `PullRequest.md` (8-item gate, hard-fails), `mention.md` (internal vs external layer), `GitHub PR 贡献指南.md` (maintainer psychology, AI integrity).
- `~/claw/pua/skills/` — 5-step Elevate loop for internal debugging. **Never export pua rhetoric externally.**
- Routing: `feedback_plugin_routing.md` (Gemini=research, Codex=review, native=debug, escalate to `gpt-5.3-codex` only after 2 failed native rounds).

## Anchors

- Repos: `~/workspace/contrib/<repo-name>/`
- Planning files (required): `~/workspace/pr-stage/<repo-name>/{task_plan,findings,progress}.md`
- Report: `~/workspace/pr-stage/<repo-name>/pr-report.md`

## Required skills (invoke at marked phases)

| Phase | Skill | Purpose |
|---|---|---|
| 0 | `superpowers:using-superpowers` | Skill-first rigor for the whole pipeline |
| 2d | `pr-direction-check` | Judgment gate (AI-policy / dispute / claim / duplicate) |
| 4a | `planning-with-files:plan` | Create task_plan / findings / progress |
| 5a | `superpowers:systematic-debugging` | Hypothesis → evidence loop |
| 5b | `superpowers:test-driven-development` | Failing test first |
| 6b | `gsd:gsd-debug` | Stuck 2+ rounds (persists across resets) |
| 8a | `superpowers:verification-before-completion` | Evidence before claims |
| 9a | `superpowers:requesting-code-review` | Structured self-review |
| 9b | `gsd:gsd-code-review` | File-level review |
| 9c | `pr-quality-gate` | 8-item scoring + triple-pass |
| 10 | `pr-workflow` | PR body template |

Plugins optional — every phase must work with Claude + Bash alone. Try once, fallback immediately.

---

## Phase 0: SESSION START

Before Phase 1, establish skill-first rigor for the entire pipeline:

```
Skill("superpowers:using-superpowers")
```

This binds: (a) mandatory skill-invocation discipline across all later phases, (b) TDD-enforcement on any code edit, (c) verification-before-completion gating, (d) no performative agreement when receiving feedback. If this skill is unavailable, note it in `findings.md` and proceed with manual rigor — do NOT skip the commitments silently.

---

## Phase 1: DISCOVER

```bash
gh search issues --label="good first issue" --state=open --sort=updated --limit=10 \
  --json repository,title,number,labels,createdAt,comments
```

Goldilocks: medium-difficulty `help wanted`/`bug` with clear repro + recent maintainer engagement + not claimed.

## Phase 2: POLICY PREFLIGHT (HARD FAIL)

**2a. AI policy** — read CONTRIBUTING / README end-to-end + scan last 30 closed-unmerged PRs for "AI content" rejections. Fail → `PIPELINE_RESULT: repo-forbids-ai | <owner>/<repo>`.

**2b. CLA/DCO** — grep CONTRIBUTING for `CLA|DCO|Signed-off-by`. Manual-action CLA → STOP + `PIPELINE_RESULT: cla-blocked`. DCO → `git commit -s` everywhere.

**2c. Duplicate** — `gh pr list --search "#<N>"` + last 14d of issue comments for prior claim. Fail → `PIPELINE_RESULT: duplicate | <url>`.

**2d. Direction (judgment, NOT regex)**

```
Skill("pr-direction-check")
```

Pass issue JSON (title/body/labels/last 20 comments with `author_association`/CONTRIBUTING excerpt/related PRs). Returns one `DIRECTION_VERDICT:` line — map `block:*` to matching PIPELINE_RESULT, `ambiguous:*` to halt + log.

## Phase 3: EVALUATE REPO

Required: clear CONTRIBUTING, merges in last 30d, visible CI, permissive license, maintainer response ≤7d. Target diff ≤200 LOC (200-500 = multiple rounds; >500 = split before coding).

## Phase 4: SETUP

```
Skill("planning-with-files:plan", args="<repo>: <issue-title>")
```

```bash
gh repo fork <owner>/<repo> --clone --remote
cd <repo>
# Install deps + run existing tests. Record baseline in findings.md.
```

## Phase 5: REPRODUCE

```
Skill("superpowers:systematic-debugging")
Skill("superpowers:test-driven-development")
```

Write the failing test first; record exact error in findings.md. Cannot reproduce after a full pua 5-step + Superpowers debug loop → polite clarification comment on the issue + `PIPELINE_RESULT: issue-skipped | cannot-reproduce`. Do not guess.

## Phase 6: ROOT CAUSE + PLAN

Trace execution, identify minimal files, update task_plan.md, check callers for similar bugs (pua Owner Mindset).

**6a. Gemini for call-chain reading (when needed):**
```bash
# Light trace: --model gemini-3-flash-preview
# Deep architectural risk analysis: --model gemini-3.1-pro-preview
gemini -p "Trace <function> in <repo>. Callers affected by <change>. Output: file:line + risk per caller." --model gemini-3.1-pro-preview
```

Or `Agent(subagent_type="gemini:gemini-consult", prompt="...")`.

**6b. Stuck 2+ rounds:**
```
Skill("gsd:gsd-debug")
```

## Phase 7: IMPLEMENT

Minimal, atomic, repo-style-matching. One logical change per commit. Add/update tests. DCO → `git commit -s`.

**7a. Codex for contained fix (<100 LOC, single module):**
```bash
codex exec --model gpt-5.4-mini "<repro-steps>
Fix in <file>:<lines>. Tests at <path>.
Run failing test after edit; paste passing output.
Apply via git apply when done."
```

Agent alternative: `Agent(subagent_type="codex:codex-rescue", prompt="Use --model gpt-5.4-mini. <same prompt>")`.

Switch to `gpt-5.3-codex` ONLY for pure terminal-debug escalation (repro + log inspection, no code edit) — normally never reached, reserve for when Claude + gpt-5.4-mini both stalled.

## Phase 8: VERIFY

```
Skill("superpowers:verification-before-completion")
```

Paste actual passing test output into findings.md before this phase ends. Then run full suite + linters (`pytest -xvs` / `go test -race ./...` / `npm test` / `cargo test --all`). Any fail → back to Phase 5.

## Phase 9: REVIEW (triple-pass — ALL THREE ARE MANDATORY)

```
Skill("superpowers:requesting-code-review")
Skill("gsd:gsd-code-review")
Skill("pr-quality-gate")
```

Three independent passes. **Each must run its assigned model** — no silent fallback to Claude. If a subagent is unavailable, emit `PIPELINE_RESULT: review-unavailable | <which-subagent>` and STOP (do not ship).

### Pass 1 — Correctness (Claude, native)

Direct review by the running Claude instance. Scores the 8 `pr-quality-gate` dimensions against: root cause addressed, test adequacy, regression risk, diff atomicity.

Output line (must appear in the PR cron log verbatim):
```
PASS_1_CORRECTNESS: <score 0-10> | notes: <≤200 chars>
```

### Pass 2 — Architecture (Gemini MANDATORY — `gemini-3.1-pro-preview`)

```bash
gemini -p "Review PR diff at <branch> against <repo-path>. Assess: does the fix fit the codebase patterns? Are there hidden coupling risks? Any undocumented assumptions? Score each of the 8 pr-quality-gate dimensions (Direction, Compliance, Atomicity, Description, Verifiability, Communication, Follow-through, Credibility) 0-10 and aggregate. Output format: '8-dim scores: d1=X d2=X ... d8=X | aggregate=X | top-risk=<one sentence>'" --model gemini-3.1-pro-preview
```

Or Agent route:
```
Agent(subagent_type="gemini:gemini-consult", prompt="Use --model gemini-3.1-pro-preview. <same prompt>")
```

Output line (must appear in the PR cron log verbatim):
```
PASS_2_ARCHITECTURE: <aggregate 0-10> | risk: <≤200 chars>
```

If the gemini call returns an error or empty output: emit `PIPELINE_RESULT: review-unavailable | gemini` and stop.

### Pass 3 — Quality Gate (Codex MANDATORY — `gpt-5.4-mini` via `/codex:adversarial-review`)

Prefer the dedicated adversarial-review command, which challenges design choices rather than just flagging defects:

```
Skill("codex:adversarial-review", args="--wait --base <upstream-default-branch> --scope working-tree")
```

Bash fallback if skill unavailable:
```bash
codex exec --skip-git-repo-check --model gpt-5.4-mini "Adversarial code review of the current working-tree diff in <repo-path>. Challenge: (a) is this actually the right fix, or a band-aid? (b) does the test actually prove the bug is gone on the general case? (c) what's the smallest production-breaking input we haven't covered? Score 0-10 per pr-quality-gate 8 dimensions. Output: '8-dim scores: ... | aggregate=X | challenge=<one sentence>'"
```

Output line (must appear in the PR cron log verbatim):
```
PASS_3_ADVERSARIAL: <aggregate 0-10> | challenge: <≤200 chars>
```

If the codex call returns an error or empty output: emit `PIPELINE_RESULT: review-unavailable | codex` and stop.

### Aggregation + promotion gate

```
REVIEW_AGGREGATE: pass1=<X> pass2=<Y> pass3=<Z> | mean=<M>
```

- **Mean < 7.0** → fix + re-verify (Phase 8) + re-score (max 2 rounds; threshold rises to 7.5 on retry).
- **Any pass has Direction or Compliance < 5** → hard fail, emit `PIPELINE_RESULT: quality-blocked` regardless of mean.
- **Mean ≥ 7.0 AND no hard-fail dimensions** → proceed to Phase 10.

**Wake-gate parsing**: it accepts EITHER the explicit `PASS_N_*:` prefix line OR the `pass<N>=<X>` value from `REVIEW_AGGREGATE`. Prefix lines are preferred (they carry notes/risk/challenge text). Aggregate-only still counts a pass as present; the status JSON records `pass_evidence` as `prefix` vs `aggregate` for debugging.

If NONE of the three passes can be recovered (neither prefix nor aggregate) → status is rewritten to `pr-created-unreviewed` with `missing_passes=pass1,pass2,pass3`. This is the backstop against the silent-collapse failure mode the 2026-04-24 audit exposed.

## Phase 10: SUBMIT

**10a.** Re-check 2a/2b/2c right before `gh pr create` (a duplicate may have appeared).

**10b.**
```
Skill("pr-workflow")
```

PR body sections: What / Why / How / Scope / Verification / AI Disclosure.

**10c. AI Disclosure (required):**
> AI tools assisted with implementation. Every change was manually reviewed, tested locally, and verified against the project's existing conventions.

Do not hide. Do not brag. State it.

**10d. Push + create:**
```bash
git fetch upstream && git rebase upstream/main
git push -u origin <branch>
gh pr create --repo <owner>/<repo> --title "<type>: <desc>" --body "<template>"
```

External tone (`mention.md`): humble, no internal jargon, no status tables, no bolded @user, no emoji-headed sections. 2–6 sentences per section.

## Phase 11: REPORT

Write `~/workspace/pr-stage/<repo>/pr-report.md`:

```markdown
- Issue: <owner>/<repo>#<N>
- PR: <owner>/<repo>#<PR>
- Preflight: pass | <reason>
- Review scores: [p1, p2, p3] → mean
- Tests: pass/fail count
- Diff: <LOC class>
- Plugins: [list or "Claude-only"]
- Status: submitted | needs-work | blocked
```

End with EXACTLY two machine-parsed lines:

```
PIPELINE_RESULT: <status> | <url-or-reason>
PIPELINE_QUALITY_SCORE: <0-10>
```

`<status>`: `pr-created` | `pr-failed` | `issue-skipped` | `needs-human` | `repo-forbids-ai` | `cla-blocked` | `duplicate` | `maintainer-disputed` | `error`.

`PIPELINE_QUALITY_SCORE` is REQUIRED when status is `pr-created`. Missing → wake-gate rewrites to `pr-created-unscored`; score < 7.0 → `quality-blocked`.
