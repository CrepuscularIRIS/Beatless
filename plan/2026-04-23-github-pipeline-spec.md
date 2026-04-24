# GitHub Pipeline — Step & TODO Spec (Robust)

**Created**: 2026-04-23
**Owner**: CrepuscularIRIS (maintained by Hermes Agent + Claude Code)
**Status**: live operational spec — this is the source of truth for what
runs in cron right now. If the Python script or command .md drifts from
this doc, the doc wins — fix the code to match.

---

## 0. Scope

Two complementary cron jobs form the GitHub pipeline:

1. **GitHub PR Pipeline** (`github-pr.py` → `/github-pr`) — every 150m.
   Discovers claimable issues, runs a strict preflight, submits PRs.
2. **GitHub Response** (`github-response.py` → `/pr-followup`) — every 60m.
   Triages open PRs (CI failures, maintainer comments, merge conflicts)
   and pushes fixes / replies.

Both are driven by the same three-layer philosophy:

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1 — Python wake-gate (DETERMINISTIC)               │
│   • API calls (gh, Zotero, arXiv-none-here)              │
│   • Label matching, duplicate-id detection               │
│   • Comment fetching, score parsing                      │
│   • Status-file writes                                   │
└───────────────────────┬──────────────────────────────────┘
                        │ spawns `claude -p --model sonnet`
                        ▼
┌──────────────────────────────────────────────────────────┐
│ Layer 2 — Claude Code session (JUDGMENT via skills)      │
│   • pr-direction-check            (dispute/AI-policy)    │
│   • planning-with-files:plan      (task_plan/findings)   │
│   • superpowers:*                 (debug/TDD/verify)     │
│   • gsd:gsd-debug, gsd-code-review                       │
│   • pr-quality-gate, pr-workflow                         │
└───────────────────────┬──────────────────────────────────┘
                        │ delegates to
                        ▼
┌──────────────────────────────────────────────────────────┐
│ Layer 3 — External model CLIs (HEAVY LIFTING)            │
│   • codex exec / Agent(codex-rescue)   — fixes           │
│   • gemini -p / Agent(gemini-consult)  — 1M-ctx reads    │
└──────────────────────────────────────────────────────────┘
```

**Rule**: each layer owns its strengths. Python doesn't try to interpret
maintainer tone. The LLM doesn't try to do deterministic ID lookups.
External models don't try to own the control flow.

---

## 1. `/github-pr` — full 12-phase flow

### Phase 1 — DISCOVER (Python)

**Script**: `github-pr.py::get_claimable_issues()`

- `gh search issues --label="good first issue" / "help wanted" / "bug"`
- 5 languages: python, rust, go, javascript, typescript
- Top 5 deduped candidates → preflight

✅ **Already implemented**. Confirmed in code.

### Phase 2 — POLICY PREFLIGHT (Python — deterministic only)

**Script**: `github-pr.py::preflight_filter()`

| Gate | Function | What it catches |
|---|---|---|
| 2.1 block-label | `has_block_label()` | issue carries `wontfix` / `invalid` / `needs-design` / `on-hold` / `question` / `stale` etc. |
| 2.2 duplicate-PR | `has_duplicate_pr()` | open PR links `Fixes #N` / `Closes #N` / `Resolves #N` |
| 2.3 data-fetch | `_fetch_issue_comments()` + `check_repo_policy()` | fetches comments + CONTRIBUTING.md text — passed to Phase 2.5, NO JUDGMENT |

✅ **Already implemented**. Judgment-based regex (AI-policy, dispute, claim) explicitly removed in commit `451067b`.

### Phase 2.5 — DIRECTION CHECK (Skill — judgment)

**Skill**: `pr-direction-check` (lives in `~/.claude/skills/pr-direction-check/SKILL.md`)

- Input: JSON blob (issue + labels + last 20 comments with `author_association` + CONTRIBUTING.md)
- Output: `DIRECTION_VERDICT: <status> | <evidence>` with `<status>` = `proceed` / `block:*` / `yield:*` / `ambiguous:*`
- On `block:*`: emit matching `PIPELINE_RESULT`, skip candidate
- On `yield:*`: emit `PIPELINE_RESULT: duplicate | <reason>`, skip
- On `ambiguous:*`: emit `PIPELINE_RESULT: needs-human | <reason>`, STOP

✅ **Skill created + wired into prompt**. aiohttp#12404 would now be caught here.

### Phase 3 — EVALUATE REPO (judgment)

Read CONTRIBUTING / recent merges / CI pipeline / PR-size expectation. Defer to the Claude Code session's reasoning — no script-side enforcement.

### Phase 4 — SETUP

- **Phase 4a — Planning files (MANDATORY)**:
  ```
  Skill("planning-with-files:plan", args="<repo-name>: <issue-title>")
  ```
  Creates `~/workspace/pr-stage/<repo>/{task_plan,findings,progress}.md`.
  **This is the durability layer** — if the session is interrupted, the
  next cron tick can resume from these files.

- **Phase 4b — Fork + clone + baseline tests**: Bash.

✅ **Spec wired in `/github-pr.md`**. Python wake-gate passes the routing anchors.

### Phase 5 — REPRODUCE (Superpowers)

- `Skill("superpowers:systematic-debugging")` — hypothesis/evidence/verify loop
- `Skill("superpowers:test-driven-development")` — failing test first, then fix

✅ **Both wired**. Mandatory, not optional.

### Phase 6 — ROOT CAUSE + PLAN

- `Agent(subagent_type="gemini:gemini-consult", ...)` — for repos > 50k LOC
  — OR equivalent Bash: `gemini -p "trace <function> ..." --model gemini-2.5-pro`
- Escalation if stuck: `Skill("gsd:gsd-debug")` — persistent debug state

✅ **Wired with both Agent + bash paths**.

### Phase 7 — IMPLEMENT

- `Agent(subagent_type="codex:codex-rescue", ...)` — self-contained fixes
  — OR Bash: `codex exec "<prompt>"` + `codex apply`
- Follow repo code style (verified at Phase 3)
- DCO sign-off if flagged: `git commit -s`

✅ **Both paths documented**.

### Phase 8 — VERIFY (HARD GATE)

- `Skill("superpowers:verification-before-completion")` — blocks "works on my machine" claims
- Run full test suite; paste passing output into `findings.md`
- If failing → return to Phase 5

✅ **Wired**. The skill enforces evidence-over-assertions.

### Phase 9 — CODE REVIEW (HARD GATE)

Three sub-gates:

- `Skill("superpowers:requesting-code-review")` — structured self-review of the diff
- `Skill("gsd:gsd-code-review")` — bugs/security/quality scan of changed files
- `Skill("pr-quality-gate")` — **8-item scoring rubric**, triple-review:
  - Pass 1 (Claude): Correctness
  - Pass 2 (Gemini via Agent or `gemini -p`): Architecture
  - Pass 3 (Codex via Agent or `codex exec`): Quality gate scoring

**Aggregation**: mean of 3 passes. **Threshold: 7.0/10 minimum.**
Hard fail if Direction or Compliance < 5 from any pass.

✅ **All three sub-gates wired in spec**. Enforcement happens in Phase 11.

### Phase 10 — SUBMIT PR

- `Skill("pr-workflow")` — the Fork→Clone→Branch→Commit→Push→PR→Review seven-step
- Final pre-submission re-check of duplicate-PR / CLA status
- PR body must include: What / Why / How / Scope / Verification / AI Disclosure
- Humility tone per `Beatless/standards/PullRequest.md` §Social Etiquette

✅ **Wired**.

### Phase 11 — REPORT (quality-score enforcement)

Emit **both lines**:

```
PIPELINE_RESULT: <status> | <pr_url_or_reason>
PIPELINE_QUALITY_SCORE: <float 0-10>
```

Python wake-gate parses both. If `status=pr-created`:
- missing score → rewrite to `pr-created-unscored`
- score < 7.0  → rewrite to `quality-blocked`
- score ≥ 7.0  → keep `pr-created`, record score in status JSON

Status values: `pr-created`, `pr-failed`, `issue-skipped`, `needs-human`, `repo-forbids-ai`, `cla-blocked`, `duplicate`, `maintainer-disputed`, `error`, and the derived `pr-created-unscored`, `quality-blocked`.

✅ **Parser unit-tested; spec updated in `/github-pr.md` Phase 11**.

---

## 2. `/pr-followup` — full flow

### Wake-gate (github-response.py — deterministic)

For each open PR by `CrepuscularIRIS`:

| Signal | How detected | Action |
|---|---|---|
| `ci-failing` | `statusCheckRollup` in `gh pr view` has any FAILURE | priority 1 — fix first |
| `unreplied` | maintainer comment with no subsequent author reply | priority 2 |
| `new-comments` | maintainer comment after last marker timestamp | priority 3 |

✅ **Wired**.

### Step 4 — Implement (skill-gated)

| Skill | When |
|---|---|
| `Skill("superpowers:receiving-code-review")` | BEFORE any code edit — block performative agreement |
| `Skill("superpowers:systematic-debugging")` | When feedback is a CI / repro failure |
| `Skill("gsd:gsd-debug")` | After 2 failed rounds on the same issue |
| `Agent("codex:codex-rescue")` / `codex exec` | For self-contained fixes |
| `gemini -p` / `Agent("gemini:gemini-consult")` | For review-context summarization |
| `Skill("superpowers:verification-before-completion")` | MANDATORY before `git push` |
| `Skill("pr-quality-gate")` items 2–7 | Before push; Direction+Trust already established |

✅ **All 7 wired**.

### Reply tone (non-negotiable)

Enforced by prompt language at every step:

| Forbidden | Why |
|---|---|
| "You're absolutely right" | performative agreement — fails `receiving-code-review` |
| "Thanks for..." | gratitude without specificity |
| "Great point" / "Excellent" | same pattern |
| Bolded `@username` | robotic |
| Status tables | AI artifact |
| Emoji-headed sections | AI artifact |
| "My analysis shows..." | authority-posturing |
| "As an AI..." / "Let me proceed..." | AI-revealing |

**Draft → self-reject pass → post** is required per the command spec.

---

## 3. Script ↔ Spec consistency matrix

| Spec phase | Python script has | Verified |
|---|---|---|
| Phase 1 discover | `get_claimable_issues()` | ✅ |
| Phase 2.1 block-label | `has_block_label()` | ✅ |
| Phase 2.2 duplicate-PR | `has_duplicate_pr()` | ✅ |
| Phase 2.3 data-fetch | `_fetch_issue_comments()`, `check_repo_policy()` | ✅ |
| Phase 2.5 direction-check | Prompt passes JSON blob; mandates `Skill("pr-direction-check")` | ✅ |
| Phase 4a planning-with-files | Prompt mandates `Skill("planning-with-files:plan")` | ✅ |
| Phase 5 superpowers TDD+debug | Prompt mandates both skills | ✅ |
| Phase 7 codex | Both Agent + bash CLI paths documented | ✅ |
| Phase 8 verification gate | Prompt mandates `Skill("superpowers:verification-before-completion")` | ✅ |
| Phase 9 triple review | All 3 skills (`superpowers:requesting-code-review`, `gsd:gsd-code-review`, `pr-quality-gate`) | ✅ |
| Phase 10 workflow | `Skill("pr-workflow")` | ✅ |
| Phase 11 score parse | `re.search(r'PIPELINE_QUALITY_SCORE:\s*([0-9.]+)')` in `main()` | ✅ |
| Response: superpowers:* | All 3 skills wired in `/pr-followup.md` Step 4 | ✅ |

Every spec item has a script-side enforcement or prompt-side mandate.

---

## 4. Fallback policy — when a plugin is unavailable

Plugins may not load in `-p` mode. Every phase must continue without them:

| Plugin unavailable | Fallback |
|---|---|
| `gemini:gemini-consult` | `gemini -p "<prompt>" --model gemini-2.5-pro` (bash CLI) |
| `codex:codex-rescue` | `codex exec "<prompt>"` + `codex apply` (bash CLI) |
| `gsd:gsd-debug` | `Skill("superpowers:systematic-debugging")` alone |
| `planning-with-files:plan` | Write `task_plan.md` / `findings.md` / `progress.md` manually with `Write` tool |
| All Skills fail to load | Log `Skill unavailable: <name>` to `findings.md` and continue with Claude-only reasoning |

**Rule**: no single dependency can halt the pipeline. The fallback ladder runs in this order: Skill → Agent → Bash CLI → Claude-only.

---

## 5. TODO — concrete open items

Ordered by dependency. Items further down depend on items above.

### Immediate (block the pipeline from being fully robust)

- [ ] **Add `allowed-tools` allowlist audit** — the user explicitly said "do not restrict tools," so nothing to do here. Keeping the default (all-tools) is correct. ✅ no-op.
- [ ] **Unit-test the direction-check skill** with 5 known cases: `aiohttp#12404` (block:disputed), `containers/ramalama#2646` (proceed), a `wontfix`-labeled issue (block:rejected-label), a user-claimed issue (yield:claimed), an AI-banned repo (block:ai-forbidden). Run via `claude -p` and inspect `DIRECTION_VERDICT:` output.
- [ ] **Verify the PIPELINE_QUALITY_SCORE is emitted by a real run** — next cron tick at 11:20 local. Inspect status JSON for the new `quality_score` field.

### Short-term (improve robustness)

- [ ] **Add `superpowers:using-superpowers` as the session-start skill** — the user-rule says "establishes how to find and use skills, requiring Skill tool invocation before ANY response including clarifying questions." Currently the session doesn't formally kick-off with this skill. Wire as Phase 0.
- [ ] **Add a `needs-human` status lane to Hermes cron summary** — when `ambiguous:*` is returned by direction-check, the status file needs human review. Hermes should surface this.
- [ ] **Rate-limit tracking** — if the `claude -p` session runs out of tokens mid-pipeline, capture the state in `progress.md` so the next cron tick resumes from there.

### Medium-term (architectural polish)

- [ ] **Register `pr-direction-check` as a proper plugin skill** — currently it's a loose SKILL.md under `~/.claude/skills/`. Convert to a plugin so it's versioned + distributable.
- [ ] **Add MCP metrics via `gsd_record_metric`** — each phase completion (with duration + status) recorded. Enables per-phase duration tracking over time.
- [ ] **Promote `pr-direction-check` to handle PR-review judgment too** (currently only issue-discovery). The `/pr-followup` receiving-code-review flow could benefit from the same skill structure for "should I accept this reviewer comment or push back?"

### Blocked / deferred (per user)

- [ ] Obsidian methodology + memory workflow — waiting on user spec
- [ ] Rule extraction agent (Extractor / Auditor / Proposer) — waiting on user methodology
- [ ] Blog 3-section template — waiting on user spec
- [ ] Stock / Polymarket — waiting on user methodology
- [ ] Daily Opus-4.7 evolution loop — planned for after KB + blog + exp are all green

---

## 6. Invariants to maintain

If any of these become false, the pipeline is broken — regardless of
whether the cron reports "ok":

1. **Every `PIPELINE_RESULT: pr-created` must have a `PIPELINE_QUALITY_SCORE: ≥ 7.0`**. Enforced in `write_status()`.
2. **Every phase that edits code must have invoked `planning-with-files:plan` first**. Enforced in the prompt — no hard check, but `findings.md` absence is a smell.
3. **No regex judgment gates in Python for the PR pipeline**. Grep `github-pr.py` for pattern-based matchers — only `has_block_label` (exact string match) and `has_duplicate_pr` (`Fixes #N` grep) should exist.
4. **Every cron summary includes the skill trace**: the session transcript must show which skills were actually invoked. Recorded in `~/.hermes/sessions/session_<id>.json` automatically.
5. **Idempotent**: running `github-pr.py` twice in a row on the same issue must not double-submit. Enforced by `has_duplicate_pr` on the re-check in Phase 10.
6. **Reply tone audit**: every comment posted by the pipeline passes the forbidden-phrasing list. Currently relies on LLM self-discipline — a post-compose check in `github-response.py` is on the TODO.

---

## 7. Daily verification checklist

To confirm the pipeline is alive and correct:

```bash
# 1. Cron status
hermes cron list | grep -E "(GitHub|Paper|Zotero)"

# 2. Last-run status
ls -la ~/.hermes/shared/.last-github-*

# 3. Latest PR + response summaries
cat ~/.hermes/shared/.last-github-pr
cat ~/.hermes/shared/.last-github-response-status | python3 -m json.tool | head -30

# 4. Zotero A-Tier count trend
curl -sS -H "Zotero-API-Key: $ZOTERO_API_KEY" -D - \
  "https://api.zotero.org/users/$ZOTERO_USER_ID/collections/5CD5RDNA/items?limit=1" \
  2>&1 | grep -i total-results

# 5. Obsidian vault literature count
ls ~/obsidian-vault/papers/literature/ | wc -l

# 6. Recent errors
tail -30 ~/.hermes/logs/errors.log
```
