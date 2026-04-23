---
description: "Triage GitHub notifications for open PRs and claimed issues. Address maintainer review comments, fix failing CI, push requested changes, yield to prior claimers, report status. Internal rigor per ~/claw/pua methodology (exhaust solutions, verify with evidence). External tone stays humble per Beatless/standards/PullRequest.md §6. Never opens new PRs or claims new issues. Works standalone — plugins optional."
---

# PR Follow-up v3

Handles existing PR/issue follow-up only. Zero new work creation.

## Source-of-Truth Standards (READ BEFORE EVERY RUN)

This command is bound to the double-layer model from `~/claw/Beatless/standards/mention.md`:

| Layer | Binding | What it controls |
|-------|---------|------------------|
| **Internal — rigor** | `~/claw/pua/skills/pua-en/SKILL.md` | How hard you push yourself when CI fails, a bug won't reproduce, or a maintainer is asking something you can't answer yet. |
| **Internal — standard** | `~/claw/Beatless/standards/PullRequest.md` §5 (Verifiability), §7 (Continuous Follow-Through) | What "done" means — evidence-based, tests pass, no trailing CI failures. |
| **External — tone** | `~/claw/Beatless/standards/PullRequest.md` §6 + §Social Etiquette, `mention.md` §5–7 | What reaches the maintainer. Humble, concise, no internal jargon. |
| **External — workflow** | `~/claw/Beatless/standards/PR.md` Step 7 | Fixes go to the same branch, not a new PR. `git push --force-with-lease` after rebase. |
| **External — meta** | `~/claw/Beatless/standards/GitHub PR 贡献指南.md` §社交互动的微妙平衡 | Polite, code-not-person framing, bump only once after 14 days. |

**Rule**: internal debugging can be as exhausting and rigorous as pua demands; the external reply must never leak any of that rhetoric, methodology name, or step-count.

## Routing Anchors (must follow)

- **Workspace root**: `~/workspace`
- **Follow-up summary**: `~/workspace/pr-stage/_followup/<timestamp>.md`
- **Per-repo planning files** (create if edits needed):
  - `~/workspace/pr-stage/<repo-name>/task_plan.md`
  - `~/workspace/pr-stage/<repo-name>/findings.md`
  - `~/workspace/pr-stage/<repo-name>/progress.md`

## Hard Constraints

1. **Never** open a new PR from this command
2. **Never** claim new issues from this command
3. Ignore bot-only noise (dependabot, renovate, github-actions[bot], codacy, mergify, cla-assistant)
4. If nothing actionable exists, write a one-line no-action summary and exit
5. **Fix CI before replying**. Never reply "working on it" while CI is red — push the fix, then one short reply.
6. **Evidence before assertions** (pua Non-Negotiable One). Never claim "fixed" without having pasted the passing test output into `findings.md` first.
7. **Exhaust the 5-step Elevate before giving up** (pua methodology). See §Internal Debugging Loop below.

## Plugin Policy

Same as github-pr: plugins are optional. Every step must work with Claude + Bash alone.

| Plugin | Use for | Fallback |
|--------|---------|----------|
| Codex | Implementing requested code changes | Claude Edit + Bash test |
| Gemini | Understanding large review context | Claude reads key files |

**Try once, fallback immediately.** No retries.

---

## Internal Debugging Loop (per pua methodology)

When CI fails, a bug won't reproduce, or a maintainer asks a question you can't confidently answer, run this loop before asking the user for help. Keep all of it in `findings.md` — it never goes into the external reply.

1. **Read failure signals word by word.** The CI log, the reviewer's exact sentences, the error message — do not skim. 90% of answers are sitting in plain sight.
2. **Search.** The full error string + the project name, upstream issue tracker, Stack Overflow. Do not rely on memory.
3. **Read raw source.** Not summaries. Open the 50 lines around the failing line. Read the maintainer's referenced file directly.
4. **Verify assumptions.** Every "this should work" you assumed — confirm with a tool (grep, `python -c`, `curl`, repo history).
5. **Invert.** If you assumed the bug is in A, assume it is NOT in A. Look elsewhere.

Only after all 5 are done may you say "I need help" or "I can't do this without clarification". Partial attempts do not count. Keep a short log of which steps you completed in `findings.md`.

## Reply Tone (EXTERNAL — non-negotiable)

Per `PullRequest.md` §6 (Low-Friction Communication), §Social Etiquette, and `mention.md` §5–7.

### Preferred phrasing

- "Thanks, fixed in `<sha>`."
- "I might be wrong, but the issue seems to be..."
- "Pushed a fix. Happy to adjust if the direction isn't right."
- "If this approach doesn't fit, no problem — glad to take another pass."
- "Good point, reverted that part."

### Forbidden phrasing and formatting

- "My analysis shows..." / "The optimal approach is..." / "Here is a comprehensive breakdown of..."
- Bolded `@username` in reply bodies (plain `@username` is fine).
- Status tables in replies (`| Step | Status |`).
- Emoji-headed section titles (`### 📊 Summary`).
- Multi-level bulleted headings for a 2-sentence answer.
- Any mention of internal tooling: agents, orchestration, multi-model pipelines, skill names, "pua", methodology step counts.
- "As an AI..." / "I will now..." / "Let me proceed to..."
- Apologies that aren't specific ("Sorry for the delay" without a reason is empty).

### Length

- Default: 2–4 sentences.
- Max: 8 lines unless the maintainer asked a specific multi-part technical question.
- If the answer needs a long explanation, link to a commit or a diff range and summarise in one line.

### Example diffs

Bad:

```
**@mikebonnet** done — commit 6cba0ab **implements exactly what you described**:

| Step | Status |
|------|--------|
| Fix unit tests | ✅ Complete |
| Push to branch | ✅ Complete |
| CI green       | ✅ Verified |

Let me know if you need any further changes!
```

Good:

```
Pushed 6cba0ab — unit tests are green now. Let me know if you want the
helper factored differently.
```

---

## Workflow

### Step 1: Gather Notifications

The wake-gate (`github-response.py`) already classified each PR as one of:
`new-comments`, `unreplied`, `ci-failing` (or a combination). Trust the signal and act on ALL flagged PRs — do not re-filter.

If invoked manually without a wake payload:

```bash
gh api notifications --jq '.[] | select(.subject.type == "PullRequest") | {repo: .repository.full_name, title: .subject.title, reason: .reason, url: .subject.url}'

gh search prs --author=CrepuscularIRIS --state=open \
  --json repository,title,number,reviewDecision,statusCheckRollup --limit=20
```

### Step 2: Priority Order

Handle in this order (do NOT move to the next tier while earlier items remain):

1. **ci-failing** — reproduce locally, fix, push, then reply (≤ 2 sentences) acknowledging the fix.
2. **unreplied** — every maintainer comment with no subsequent author reply needs a response. Even if the answer is "good point, will do" — silence is the worst signal.
3. **new-comments** — acknowledge or answer any comment posted since our last visit.

### Step 3: Classify each comment

| Type | Action |
|------|--------|
| **Changes requested** | Read all comments → implement → push → one short reply per comment or one summary |
| **Comment / question** | Answer with evidence (commit SHA, file:line, log snippet). No code changes unless asked. |
| **CI failure** | Investigate locally (never trust "works on my machine") → fix → push → reply |
| **Merge conflict** | Rebase onto upstream/main → `git push --force-with-lease` → one-line note |
| **Approved + mergeable** | Thank the reviewer in one sentence. Do not nudge for merge. |
| **Stale (>14 days idle)** | One polite bump comment. Never a second. |
| **Competing PR / yielded** | Close ours: "Closing in favor of #<N> — thanks for the quicker work." |

### Step 4: Implement Changes (if needed)

For requested code changes, invoke the skills at the right moment:

#### 4a. MANDATORY before any code edit: `superpowers:receiving-code-review`

```
Skill("superpowers:receiving-code-review")
```

This enforces technical rigor on feedback — you check each comment against evidence before agreeing. Blocks "performative agreement" and "blind implementation" when a reviewer's suggestion is actually wrong.

#### 4b. If the feedback is a CI failure or a bug, also invoke `superpowers:systematic-debugging`

```
Skill("superpowers:systematic-debugging")
```

Use this before the Internal Debugging Loop (§Internal Debugging Loop above). Layer them: systematic-debugging gives structure, the 5-step loop gives rigor, `findings.md` records the evidence.

#### 4c. Stuck? Escalate to GSD-debug

After 2 failed rounds on the same issue:

```
Skill("gsd:gsd-debug")
```

Persists state across context resets. Right tool when a CI regression survives multiple fixes.

#### 4d. Implement + push

1. `cd ~/workspace/contrib/<repo-name>/`
2. Read ALL review comments before making any changes (per §4a).
3. For self-contained fixes, delegate to Codex. Two equivalent paths — prefer Bash in headless/cron context:

   **Path A — Bash CLI:**
   ```bash
   codex exec "<exact-failure>
   Fix in <file>:<line>. Run <specific-test> after edit; paste passing output."
   ```

   **Path B — Agent tool:**
   ```
   Agent(subagent_type="codex:codex-rescue", prompt="<same prompt>")
   ```

   For understanding large review contexts (many comments across many files), use Gemini:
   ```bash
   gemini -p "Summarize the review threads on PR <url> into a flat action list: each item = {file:line, reviewer, ask, required-change}. Group by file." --model gemini-2.5-pro
   ```
4. Address each comment in a separate commit when practical (bisect-friendly, per `PR.md` Step 4 + Chinese guide §Commit 卫生).
5. Run full test suite after changes.
6. Run the lint/format tools the repo actually uses — check `.pre-commit-config.yaml`, `package.json` scripts, `Makefile`.

#### 4e. MANDATORY before push: `superpowers:verification-before-completion`

```
Skill("superpowers:verification-before-completion")
```

Evidence over assertions. You cannot reply "fix pushed, CI should be green now" without having already observed the passing output.

#### 4f. Quality gate

Invoke **`pr-quality-gate`** skill items 2–7 (skip Direction and Trust — already established on this PR) before pushing.

Push to existing branch (PR updates automatically).

### Step 5: Reply

- Post one reply per thread (not per comment) unless threads are independent.
- Include a commit SHA the maintainer can click.
- Ask a follow-up question ONLY if you genuinely need it to proceed, AND you completed the Internal Debugging Loop first.
- Do not append "thank you for your thorough review" unless you mean it specifically.
- **Draft, then self-reject once.** Before posting, read the draft and check it against §Forbidden phrasing. If it trips any, rewrite.

### Step 6: Write Summary

Write to `~/workspace/pr-stage/_followup/<YYYYMMDD-HHMMSS>.md`:

```markdown
## Follow-up Summary — <date>

### Actions Taken
- <repo>#<pr>: pushed <sha>, replied to @<user>

### Still Pending
- <repo>#<pr>: waiting on maintainer (last ball in their court)

### CI Fixed
- <repo>#<pr>: <which check> now green

### Skipped (and why)
- <repo>#<pr>: CLA unsigned (manual), noted
- <repo>#<pr>: competing PR #N merged — closed ours

### Internal Loops Run
- <repo>#<pr>: exhausted pua 5-step for CI failure — root cause was <summary>

### Plugins Used
- [list or "Claude-only"]
```
