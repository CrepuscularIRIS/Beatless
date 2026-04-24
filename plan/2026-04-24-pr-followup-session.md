# PR Follow-up Session — 2026-04-24

**Trigger**: User observation that someone is asking for help in the GitHub mailbox.
**Scope**: `/pr-followup` only — fix CI / respond to maintainer comments on existing PRs. No new PRs, no new issue claims.
**Standards bound**: `pua` (internal rigor) + `PullRequest.md` §5/§6/§7 + `mention.md` §5–7 (external tone).

---

## 1. Mailbox Triage (2026-04-24 07:45 UTC snapshot)

| Priority | Repo / PR | State | Signal | Action |
|----------|-----------|-------|--------|--------|
| **P0** | `flavio-fernandes/mqtt2kasa#24` | OPEN, CI fail | **Owner explicitly asked** ("Sorry, but the test is failing... If you can, please take a look") | Fix `basic_test.sh:27` on `aiomqtt>=2.0` API, push, reply once. Owner even gave a starting hypothesis: `timeout` param changed in v2. |
| **P1** | `containers/ramalama#2646` | OPEN, CI fail | Maintainer @rhatdan (MEMBER) assigned issue #2526 to me, PR #2646 is my response; CI failing | Investigate CI rollup → fix → push → brief reply |
| P2 | `codecov/codecov-action#1940` | Bug thread (mentioned) | CI flake mention; my PR #1941 already open | Read thread, no action unless a specific ask surfaces |
| P3 | `conda/conda-index#286` | OPEN, all green | Maintainer said "running CI" on 2026-04-22, all checks green now | Wait — ball in their court. No reply needed. |
| P3 | `tjcsl/ion#1890` | OPEN, all checks ✅ | REVIEW_REQUIRED; no maintainer ask | Wait. |
| Noise | `pytorch/torchtitan` fix/hf-dataset-shuffle | CI fail (old attempts) | No maintainer comment since last push | Monitor only |
| Noise | `bemanproject/exemplar` fix/beman-tidy | CI fail | No maintainer ask, generated-content PR | Leave; don't escalate |
| Skip | `aio-libs/aiohttp` fix/body-part-reader | CLOSED (#12413) | We closed yesterday per Direction-Alignment fail | Ignore CI noise on dead branch |

## 2. TODO (Ordered)

### Immediate (this session)
- [ ] **T1**: `mqtt2kasa#24` — reproduce `basic_test.sh:27` locally, fix aiomqtt v2 API usage, push, reply to @flavio-fernandes with commit SHA
- [ ] **T2**: `ramalama#2646` — inspect CI rollup, identify failing job, fix, push, brief reply
- [ ] **T3**: Write `/home/lingxufeng/workspace/pr-stage/_followup/20260424-*.md` summary

### Short-term (after session)
- [ ] Wire Task #61 (superpowers:using-superpowers as Phase 0 of /github-pr) — deferred; not blocking
- [ ] Unit-test `pr-direction-check` skill with 5 known cases
- [ ] Verify next cron emits `PIPELINE_QUALITY_SCORE`

### Blocked / deferred
- [ ] Obsidian methodology notes (user said medium-term)
- [ ] Rule extraction agent (user said medium-term)
- [ ] Blog 3-section template (deferred)

## 3. Tools Plan

| Step | Tool | Fallback |
|------|------|----------|
| Gather mailbox | `gh api notifications` | — |
| Per-PR rollup | `gh pr view --json statusCheckRollup` | gh api |
| Read failing CI log | `gh run view <id> --log-failed` | gh api artifact |
| Reproduce locally | `cd ~/workspace/contrib/<repo>` + `pytest` or `bash basic_test.sh` | Codex exec |
| Understand large review context | `gemini -p "..." --model gemini-2.5-pro` | Read comments directly |
| Implement fix (self-contained) | Claude Edit | `codex exec` (Path B) |
| Verify before push | Run tests + invoke `superpowers:verification-before-completion` | — |
| Push | `git push --force-with-lease` if rebased; plain push if additive | — |

## 4. Skills Gated on Ingress

- `superpowers:receiving-code-review` — before ANY code edit responding to review feedback
- `superpowers:systematic-debugging` — on each CI failure (paired with pua 5-step internal loop)
- `superpowers:verification-before-completion` — before every reply claiming "fix pushed"
- `gsd:gsd-debug` — ONLY if 2 rounds fail on the same issue
- `pr-quality-gate` items 2–7 — before push (skip Direction + Trust which are already established on follow-up)

## 5. External Reply Budget

- Per thread: 2–4 sentences max
- Never bold `@user`
- Never status table
- Never mention agents, skills, methodology, step counts
- Draft → self-reject once → post

## 6. Exit Criteria

- [ ] T1 done: mqtt2kasa CI green, reply posted
- [ ] T2 done: ramalama CI green, reply posted
- [ ] T3 done: summary written
- [ ] No new PRs opened; no new issues claimed
- [ ] All internal pua reasoning stays in `findings.md`; nothing leaks into reply
