# OpenClaw Pipeline V2 — Findings, Wiring, and Next Steps

**Date**: 2026-04-09  
**Context**: Follow-up to PIPELINE_FINDINGS.md after user feedback.

---

## 1. Gemini plugin — verified to exist and mirror Codex

User question: *"Does Gemini have plugins in ClaudeCode like Codex does?"*

**Answer: YES.** Both plugins are installed and provide equivalent commands:

| Codex plugin | Gemini plugin |
|--------------|---------------|
| `/codex:setup` | `/gemini:setup` |
| `/codex:status` | `/gemini:status` |
| `/codex:review` | `/gemini:review` |
| `/codex:rescue` | *(no equivalent — but `/gemini:consult` covers investigation)* |
| `/codex:result` | `/gemini:result` |
| `/codex:cancel` | `/gemini:cancel` |
| *(no equivalent)* | `/gemini:analyze`, `/gemini:challenge`, `/gemini:guide` |

Install paths:
- `~/.claude/plugins/cache/openai-codex/codex/1.0.2/commands/`
- `~/.claude/plugins/cache/arescope-plugins/gemini/1.0.0/commands/`

### What this means for the routing chain

When the router spawns `claude --print`, the Sonnet 4.6 instance inside that process can use **both** `/codex:review` and `/gemini:review` via its built-in plugin runtime — each one spawns the real `codex` / `gemini` CLI binary underneath.

**So the full chain is:**

```
Beatless Agent (step-3.5-flash / MiniMax-M2.7)
  └─ claude_code_cli tool (rawcli-router plugin)
       └─ spawn("claude", "--print", prompt)
            └─ Claude Sonnet 4.6 (ClaudeCode CLI)
                 ├─ /codex:review  → spawn("codex", ...)
                 └─ /gemini:review → spawn("gemini", ...)
```

**Conclusion**: the user's existing stack already bridges to Codex AND Gemini CLIs. The `codex-bridge.js` I proposed earlier is **not strictly needed** — it would just make the delegation explicit and skip the Sonnet middleman. Given Codex quota concerns, we will **not** write it for now. Sonnet will delegate via `/codex:review` when prompted with the right keywords.

### How to trigger each backend from a Beatless agent

| Want Sonnet only | Say: `rc "/gsd-do <task>"` or plain `rc "<task>"` |
| Want Gemini | Say: `rc "deep research: <topic>"` or `rc "外部大脑 <topic>"` (keyword-gated in router) |
| Want Codex | Say: `rc "codex review /path/to/file"` or `rc "审查 <diff>"` (Sonnet delegates via `/codex:review`) |

---

## 2. Mailbox CLI — BUILT and verified

**File**: `.openclaw/scripts/mail.mjs` (~170 lines, zero deps, Node built-ins only).

### Smoke tests run

```bash
node mail.mjs list                                                           # 5 empty mailboxes
node mail.mjs send --from methode --to lacia --type idle_report ...           # ok
node mail.mjs read --agent lacia --unread                                     # 2 letters returned
node mail.mjs mark --agent lacia --id <id>                                    # ok
# Concurrent stress: 6 parallel sends → count=6 ✓
for i in 1..6; do node mail.mjs send ... & done; wait                         # all 6 succeeded
```

### Key properties

- **Agent-to-agent direct** — does NOT invoke ClaudeCode. Called via the `exec` tool.
- **Flock-free** — uses atomic `open(O_EXCL)` lockfile with 5s timeout and 30s stale-lock stealing. Verified under 6-way concurrent load.
- **JSONL per recipient** at `.openclaw/mailbox/<agent>.jsonl`.
- **Types**: `message`, `idle_report`, `task_request`, `task_result`, `review_verdict`, `alert`, `ack`.
- **Usage documented** in all 5 workspace `TOOLS.md` files (synced to `Beatless/agents/*/`).

### Commands

```
mail send   --from <a> --to <b> --type <t> --subject "<s>" --body "<text>"
mail read   --agent <name> [--unread] [--limit N]
mail mark   --agent <name> --id <id>
mail count  --agent <name> [--unread]
mail sweep  --agent <name> --keep-days N
mail list
```

### Workspace skill disparity (separate issue)

The old skill-based mailbox was uneven:
- lacia: 27 skills including `agent-mailbox`
- methode: 3 skills, **no mailbox**
- satonus: 8 skills including `agent-mailbox`
- snowdrop: 6 skills including `agent-mailbox`
- kouka: 6 skills, **no mailbox**

**This is now moot** — `mail.mjs` lives outside the per-workspace skill tree, so all 5 agents can use it equally via `exec`. The old per-workspace `agent-mailbox` skills can be left in place or removed later; they are not required for the new channel.

---

## 3. Blog maintenance pipeline (design, NOT yet wired)

User requirement: rewrite outdated posts in `~/blog/posts/`, expand under-detailed explanations, reorganize. **Must go through OpenClaw → GSD commands → Codex/Gemini plugins.** Store output locally, no auto-commit, user will review multiple times.

### Current blog state

```
~/blog/
  posts/           (production Astro posts)
  drafts/          (Kouka scratch — already writes here via test-output)
  Research/        (Snowdrop research exports)
  assets/, audio/, public/, src/   (Astro site plumbing)
```

### Proposed pipeline (no auto-submit)

**Scope**: one cron — `Blog-Maintenance-Kouka` (already exists at Tue/Fri 10:00). Add a second phase to it.

```
HEARTBEAT-CRON (Kouka, existing Blog-Maintenance-Kouka):

Phase A — AUDIT (existing, keep as-is):
  1. Read shared memory for delivered artifacts
  2. Decide: new post vs. maintenance pass

Phase B — MAINTENANCE (NEW):
  3. exec: ls -lt ~/blog/posts/*.md | head -20
     → pick oldest 3 candidates (or posts with known TODOs)

  4. For each candidate:
     a. rc "/gsd-do audit the markdown file ~/blog/posts/<slug>.md for:
            - broken links (curl -I each URL)
            - outdated facts (dates before 2026, deprecated libs)
            - under-explained sections (flag < 200 words per H2)
            Return findings as YAML with {link_issues, stale_facts, thin_sections}"
        → Sonnet reads the file, runs curls, returns structured audit
        → save to ~/blog/Research/audit/<slug>.yaml

     b. If thin_sections found:
        rc "deep research: expand section '<heading>' of <slug> with
            2026 sources, maintain tone, 300-500 words"
        → triggers Gemini bridge → expansion draft

     c. rc "apply audit findings + expansion to ~/blog/posts/<slug>.md
            as a PATCH — write the updated file to ~/blog/drafts/<slug>.rewrite.md
            DO NOT overwrite the original. DO NOT commit."
        → Sonnet writes patched version to drafts/

  5. mail send --from kouka --to satonus --type review_verdict --subject
     "blog rewrite: <slug>" --body "drafts/<slug>.rewrite.md ready for review"

Phase C — SATONUS REVIEW (next tick):
  Satonus reads mailbox, runs:
  rc "审查 diff between ~/blog/posts/<slug>.md and ~/blog/drafts/<slug>.rewrite.md —
      codex review for factual regressions, tone drift, link quality"
  → Sonnet delegates to /codex:review (or falls back to its own review)
  → verdict PASS/HOLD/REJECT written to ~/blog/Research/review/<slug>.yaml
  → mail send --from satonus --to lacia --type review_verdict

Phase D — USER GATE (no autonomous action):
  Lacia reads review mailbox. Does NOT auto-apply.
  Lacia writes Queue.md entry:
    "[BLOG-REWRITE] 3 candidates ready for your review:
       - drafts/a.rewrite.md  (PASS)
       - drafts/b.rewrite.md  (HOLD — stale citation)
       - drafts/c.rewrite.md  (REJECT — tone drift)
     Run: diff ~/blog/posts/<slug>.md ~/blog/drafts/<slug>.rewrite.md"
  User reviews, manually applies via their own editor and git.
```

### Why this hits all three backends

- **Sonnet** — default for file read/write, audit logic, patch generation (phase B-a, B-c, C)
- **Gemini** — phase B-b triggered by "deep research" keyword in rc prompt
- **Codex** — phase C triggered by "审查 / codex review" keyword (Sonnet delegates via `/codex:review`)

### What is NOT done (user explicit)

- No auto-commit
- No auto-push
- No overwrite of original posts — everything lands in `~/blog/drafts/` first
- Deletion requires manual user action on Queue.md entry

---

## 4. GitHub discovery + local PR pipeline (design, NOT yet wired)

User requirement: find real good-first-issues on 5k–30k star repos (non-mainstream), simulate the codebase via AgentTeam, find bugs (real ones, not made up), prepare a local PR. **DO NOT submit issues. DO prepare PRs. Store locally for user review.**

### Proposed pipeline (manual trigger first, cron later)

```
Daily trigger — ./openclaw-local cron run Lacia-GH-Discovery (new)

Stage 1 — Lacia dispatches parallel fan-out via mailbox

Stage 2 — Snowdrop: repo discovery (Gemini-backed)
  rc "deep research: find 5 active open source repos on GitHub
      with 5000-30000 stars, non-mainstream (NOT vscode/react/kubernetes),
      strong contributor activity in last 30 days,
      clear CONTRIBUTING.md, and open good-first-issues with 'bug' label.
      Return repo URLs + 1-line rationale for each."
  → Gemini bridge → ranked candidates
  → mail send --from snowdrop --to methode --type task_request
              --subject "simulate repos" --body "<5 URLs>"

Stage 3 — Methode (wave of 3–5 subagents): clone + simulate
  For each candidate repo (parallel):
    rc "/gsd-quick clone https://github.com/<repo> to /tmp/ghsim/<slug>
        run its test suite, read the top 5 open issues,
        identify ONE real bug with:
          - a failing repro
          - a root-cause analysis
          - a minimal fix as a unified diff
        DO NOT push. DO NOT open a PR. Store output to
        ~/blog/Research/ghsim/<slug>/{repro.md, rca.md, patch.diff}"
    → Sonnet runs the plan inside ClaudeCode's agent runtime
    → AgentTeam effect: each repo gets its own subagent session
  → mail send --from methode --to satonus --type review_verdict
              --subject "ghsim ready" --body "<5 slugs>"

Stage 4 — Satonus: codex review of each proposed patch
  rc "审查 each file in ~/blog/Research/ghsim/<slug>/patch.diff
      for correctness, test coverage, style conformance, PR-readiness.
      Codex literal-genie mode. Return PASS/HOLD/REJECT per slug."
  → Sonnet delegates via /codex:review (or falls back if Codex quota out)
  → write verdicts to ~/blog/Research/ghsim/<slug>/verdict.yaml
  → mail send --from satonus --to kouka --type task_request
              --subject "package PRs" --body "<PASS slugs>"

Stage 5 — Kouka: local PR preparation (NO submission)
  For each PASS slug:
    rc "from ~/blog/Research/ghsim/<slug>/, produce a PR package:
         - pr-title.txt
         - pr-body.md (with repro, rca, patch summary, test plan)
         - pr-checklist.md
         Save all to ~/blog/Research/ghsim/<slug>/pr/
         DO NOT run gh pr create. DO NOT push."
  → mail send --from kouka --to lacia --type task_result
              --subject "PRs staged for review" --body "<N> packages at ~/blog/Research/ghsim/*/pr/"

Stage 6 — Lacia: user-facing summary
  Lacia writes Queue.md entry:
    "[GH-PR-BATCH <date>] N packages ready:
       - <repo1> — PASS — pr at ~/blog/Research/ghsim/<slug1>/pr/
       - <repo2> — HOLD — reviewer flagged test coverage gap
       - <repo3> — REJECT — patch did not fix root cause
     Run: cat ~/blog/Research/ghsim/<slug>/pr/pr-body.md
     Apply: cd /tmp/ghsim/<slug> && git apply ~/blog/Research/ghsim/<slug>/patch.diff"
```

### Hard safety rules baked into the prompts

1. `gh pr create` / `gh issue create` / `git push` — **forbidden at every stage**. Agent prompts explicitly deny these.
2. All artifacts under `~/blog/Research/ghsim/` — user-reviewable, grep-able, git-ignored until user decides to commit.
3. AgentTeam pattern — each repo gets its own isolated subagent session so failures don't contaminate others.
4. Codex is best-effort — if `/codex:review` returns quota error, Satonus falls back to Sonnet-native review and flags it in the verdict YAML as `reviewer: sonnet-fallback`.

### What is NOT done yet

- No cron job created (`openclaw cron add ...`)
- No HEARTBEAT.md updates to reference the new pipeline
- No prompts templated into reusable scripts
- No sample run executed

Waiting on user's explicit "go" before wiring any of it. The design above is the **contract** the agent prompts will enforce.

---

## 5. Things explicitly deferred per user feedback

| Item | Status | Reason |
|------|--------|--------|
| `codex-bridge.js` | ❌ skipped | Codex quota concerns; Sonnet's `/codex:review` delegation is sufficient for now |
| StepFun push on idle | ❌ deferred | User has a specific goal first (blog maintenance) — push comes later |
| Issue submission on GitHub | ❌ forbidden | User said "do NOT submit issues, do PRs instead, local only first" |
| Auto-commit of blog rewrites | ❌ forbidden | User wants to review multiple times |
| Heartbeat/cron wiring of new pipelines | ⏸️ held | Waiting on user sign-off on §3 and §4 designs |

---

## 6. What IS actually done in this turn

1. ✅ Verified Gemini has the same plugin structure as Codex (§1).
2. ✅ Built `.openclaw/scripts/mail.mjs` — zero-dep, concurrent-safe mailbox CLI (§2).
3. ✅ Smoke-tested mail CLI: send / read / mark / count / list / 6-way concurrent send all pass.
4. ✅ Appended "Inter-Agent Mailbox" usage block to all 5 workspace `TOOLS.md` + synced to `Beatless/agents/*/TOOLS.md`.
5. ✅ Created `.openclaw/mailbox/` storage directory.
6. ✅ Drafted the blog maintenance pipeline (§3) and GitHub discovery pipeline (§4) — **not wired**.
7. ✅ This document.

Nothing destructive. No commits. No pushes. No cron changes. No overwrites of existing posts.

---

## 7. Decision points — please confirm before I proceed

1. **Blog pipeline (§3)** — approve the design? Any wording changes? Which 3 posts to start with (or let Kouka pick "oldest 3")?
2. **GitHub pipeline (§4)** — approve? Any avoid-list of repos? Rate limit (how many candidates/day)?
3. **Wire the crons** — `openclaw cron add ...` for both, once you approve the designs? Or do you want me to make them runnable manually only (`./openclaw-local cron run <name>`) until proven stable?
4. **Skill cleanup** — want me to remove the old `agent-mailbox*` skills from workspace-*/ since they're superseded? Or leave them dormant?

I'll wait for your go on each before changing any more files.
