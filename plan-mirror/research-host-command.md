---
description: End-to-end hosted autonomous research pipeline. Discover hypotheses → bootstrap sprint → parallel niches → run loops → triple-review → reflect → repeat. Runs UNTIL SOTA / budget exhausted / unrecoverable BLOCK / human halt. Embeds the 3 Core Research Principles (P1 Parallel-Orthogonal, P2 Triple-Heterogeneous Review, P3 Surface Implicit Knowledge). NEVER asks "should I continue" — human may be asleep.
argument-hint: "[<plan-doc> | resume] [--sprint <tag>]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent, Skill, mcp__plugin_gsd_gsd__*
---

# /research-host — Hosted Autonomous Research Pipeline

This is the **single-command** alternative to running `/research-bootstrap → /research-parallel → /research-loop → /research-review` by hand. It hosts the full pipeline: discover → plan → run → judge → reflect → repeat. Once invoked, it runs autonomously until a halt condition fires.

> **Why this exists**: the granular `/research-*` commands are correct individually but require constant manual orchestration. This command absorbs the orchestration and hands off only on terminal conditions.

## Constitutional anchor (READ FIRST — every iteration)

`/home/lingxufeng/claw/plan/Regulations.md` § "Three Core Research Architecture Principles":
- **P1 Parallel + Orthogonal Coverage** → Phase 2 below (niche selection + cosine check)
- **P2 Triple-Heterogeneous Review** → Phase 4 below (Codex / Gemini / Sonnet-fresh)
- **P3 Surface Implicit Knowledge** → enforced in EVERY phase. Generator outputs without `implicit` block are dropped, not retried with budget.

Violating any principle on any cycle = halt the loop, log `event=principle_violation`, surface to user.

## Paradigm anchor — rule-guided self-evolving ecosystem (NOT instruction-execution)

Per `/home/lingxufeng/research/Report/AI 科研系统演化新范式.md`:

- **Rules = selection pressure**, not execution steps. The constitution defines "what's NOT allowed" + "how value is judged"; agents explore freely within those bounds.
- **Agents = mutation sources**, not stepwise executors. Each peer Sonnet branch is a variation on the parent state.
- **Eval / anti-cheat / falsification / reproduction = natural selection**. Triple-review (P2) is the selection mechanism.
- **Quality-Diversity over single-objective**: a `keep` is not just "metric improved." It's "metric improved AND niche diversity preserved." We maintain a MAP-Elites-style archive (`ledgers/<sprint>/archive.jsonl`) — one row per (niche × behavior-bucket) cell, keeping the best occupant. Diverse-but-average proposals are STEPPING STONES, retained even if they don't improve the headline metric.
- **Mutation operators (Phase 3 generator MUST pick one explicitly)**:
  1. **Semantic mutation** — lock all components except one; replace that component orthogonally (cross-domain or in-domain). Document which component was held vs varied.
  2. **Non-uniform mutation** — early sprint: large perturbations (architecture-level). Late sprint: small perturbations (hyperparam-level). The generator picks magnitude based on `ledger.cycle_count / sprint.budget`.
  3. **Trajectory-grounded targeted mutation** — read `decision_trace.jsonl` for the lineage's failure attribution; mutate the implicated module specifically, not the whole train.py.
- **Anti specification-gaming**: meta-evaluative audits (constitution layer 4) — the triple-review chain is the implementation. Anything that hill-climbs the metric without addressing the bottleneck is BLOCK regardless of metric.

## Plugin readiness (test ONCE at startup, record in `progress.md`)

| Plugin | Use | Test invocation | If unavailable |
|---|---|---|---|
| Codex (`codex:codex-rescue`) | code edits + correctness review (P2 Pass 1) | `codex exec --skip-git-repo-check </dev/null "Reply OK"` | halt — Pass 1 cannot be skipped |
| Gemini (`gemini:gemini-consult`) | literature search + assumption-challenge (P2 Pass 2) | `gemini --yolo -p "Reply OK" </dev/null` | halt — Pass 2 cannot be skipped |
| Sonnet 4.6 (peer Task) | parallel niche generators + red-team (P2 Pass 3) | always available in this session | n/a |

**Stdin discipline (critical for Codex):** every `codex exec` and `gemini -p` call from this command MUST close stdin (`</dev/null` or `<<< ""`). Without it, Codex hangs on "Reading additional input from stdin..." (verified 2026-04-26). Document this in `progress.md` plugin row.

## Halt conditions (enumerated — only these halt the loop)

1. **SOTA achieved**: target metric in `Plan.md` reached, or `results.tsv` has a `keep` row meeting threshold
2. **Budget exhausted**: `--budget` arg or `Plan.md` budget consumed
3. **Unrecoverable BLOCK**: triple-review BLOCK that cannot be reverted (e.g. constitution violation traced to wider system)
4. **Stagnation**: 4 consecutive cycles after a `/research-host` discover-refresh produce no `keep`. Trigger another discover first; if THAT also yields no progress in next 4 cycles, halt.
5. **Human interrupt**: explicit `/research-halt` or kill signal
6. **Hardware fault**: GPU unreachable mid-run

Anything else (single-cycle crash, single FLAG, slow progress) → keep going.

---

## Phase 0 — Status check + resume

```bash
# Where are we?
cd <workspace>   # arg path or pwd if running in research workspace
git rev-parse --is-inside-work-tree
git branch --show-current
git status --short

# What's pinned?
test -f contracts/constitution.v0.1.0.yaml && echo "constitution present"
test -f ledgers/<sprint>/sprint.yaml      && echo "sprint pinned"
test -f traces/decision_trace.jsonl       && echo "trace exists"
test -f progress.md                       && echo "progress exists — RESUMING"
```

If `progress.md` exists with prior rounds:
- Read last completed round N + any running PIDs
- `ps -p <PID>` — if alive, enter monitor-idle mode
- If round N is mid-cycle (e.g. proposal logged but no review): jump to that subphase
- **NEVER restart from round 1 if higher rounds recorded.**

If `progress.md` absent: continue to Phase 1.

## Phase 1 — Discover (idea-first OR application-first)

**Triggers**: fresh sprint OR stagnation refresh (4 consecutive no-improvement).

Use the two-path methodology (per deprecated `exp-discover`, kept):

### Path 1 — Idea-First (exploration)
1. Domain understanding (≤5 lines)
2. **Bottleneck identification** (CRITICAL): where exactly does performance plateau? Locate the difficulty before any method is proposed.
3. Method + paradigm selection (must fit the bottleneck, not just be "latest SOTA")
4. Model + training strategy (match optimization landscape)
5. Literature grounding (delegate to Gemini — see below)

### Path 2 — Application-First (transfer)
1. Scenario analysis (concrete problem, domain constraints)
2. **Cross-domain transfer** at structural level (NOT "transformer from NLP to vision" — that's surface). Find shared mathematical / optimization geometry.
3. Shared first principles (info theory, optimization theory)
4. **Hidden assumption mining** (highest-value targets): what does the target field assume that might be wrong?

### Literature delegation (real tool use, not Q&A)

```
Agent tool:
  subagent_type: gemini:gemini-consult
  prompt: |
    Use web_search + web_fetch (real tools, not memory). For the topic <bottleneck>:
    1. List 5-8 papers from 2025+ closest to this exact bottleneck (title, venue, arXiv id, 1-line takeaway).
    2. For each, name the strongest counter-argument.
    3. Surface 3 hidden assumptions the field is making that might be wrong.

    SURFACE IMPLICIT KNOWLEDGE — your output is incomplete without:
      silent_priors, unspoken_alternatives, failure_dna,
      hidden_dependencies, what_a_skeptical_PI_would_ask
    Each implicit claim cites an evidence_pointer (URL or arXiv id).
```

Output: ≥5 hypotheses, ranked by feasibility × novelty × bottleneck-relevance, each with falsifiable failure-condition. Write to `task_plan.md`.

Stagnation halt-cycle: if Phase 1 has been run twice without producing any keep → halt (see condition 4).

## Phase 2 — Bootstrap + Niche selection (P1)

If `sprint.yaml` doesn't exist, create it. Choose niches:

1. Read top-N hypotheses from `task_plan.md` (N = sprint.yaml `max_niches`, default 5).
2. **Orthogonality enforcement (P1)**:
   - Write a one-sentence "core question" per niche.
   - Pairwise compare via embedding cosine OR LLM judge.
   - Any pair > 0.6 → reassign one of them (pull next hypothesis from `task_plan.md`).
   - Log the matrix to `decision_trace.jsonl` with `event=orthogonality_check`.
3. **R11 entropy-collapse**: if the previous cycle had ≥2 niches converge, force-reassign now.

## Phase 3 — Dispatch + Loop (P1 + P3)

### 3a. Same-message parallel dispatch (P1) — **explicit mutation operator per branch**

Single assistant turn, N `Agent` Task calls (subagent_type=`general-purpose`, peer Sonnet branches, NEVER nested). Each prompt MUST require the branch to declare its mutation operator (one of: semantic / non-uniform / trajectory-grounded), so the QD archive can attribute lineage and the orchestrator can detect operator drift:

```
You are a peer Sonnet 4.6 branch in sprint <sprint>. Niche: <niche-id>.
Direction: <one-line>
Forbidden: <list>
Read: Plan.md, sprint.yaml, contracts/constitution.v0.1.0.yaml, last 10 ledger rows, last 5 implicit blocks for this niche.

Propose ONE next experiment:
  - Mutation operator (one of: semantic | non-uniform | trajectory-grounded). State which component is HELD vs VARIED.
  - Behavior bucket (categorical — e.g. {arch_change, opt_change, loss_change, data_change, regularizer_change}). The QD archive keeps best occupant per (niche × bucket).
  - Hypothesis (falsifiable, one sentence)
  - Change scope (files + functions)
  - Success metric + numeric threshold
  - Failure condition (R7 — when would this NOT work?)
  - Expected metric delta + cost

SURFACE IMPLICIT KNOWLEDGE (P3 — non-negotiable):
  silent_priors:                   <assumptions you make I didn't ask you to state>
  unspoken_alternatives:           <directions you considered but skipped + REAL reason>
  failure_dna:                     <root cause one level deeper than commit msg>
  hidden_dependencies:             <env priors: seed, version, undocumented behavior>
  what_a_skeptical_PI_would_ask:   <top 3 questions you'd LEAST want to answer; answer them>
Each implicit claim cites an evidence_pointer (file:line / log line / commit SHA / dataset key).

DO NOT spawn further Task calls. DO NOT nest. Return proposal + implicit block as your final message.
```

### 3b. Filter + rank
- Drop branches whose return lacks `implicit` block (Principle 3 enforcement). Log `event=incomplete_branch`.
- Rank surviving proposals against constitution (R-rules).
- Append each to `decision_trace.jsonl` with `event=propose` AND a paired `event=surface_implicit`.
- Pick the top proposal. Generator-as-judge is forbidden — use a separate ranker prompt or a deterministic score (cost/expected-delta).

### 3c. Run the cycle (autonomous /research-loop core)

```bash
START_COMMIT=$(git rev-parse --short HEAD)
```

Delegate the code change to Codex (so the generator doesn't fix its own diff):
```
Agent tool:
  subagent_type: codex:codex-rescue
  prompt: |
    Apply this single experiment to <mutable file>: <one-line description>.
    Keep changes minimal. Don't add new dependencies. Don't modify prepare.py / evaluator.
    Verify build succeeds. Return diff summary.
```

(If Codex exec from this command path: append `</dev/null` to close stdin.)

```bash
git commit -am "exp: <description>"
timeout <budget+120> uv run train.py > run.log 2>&1
grep "^val_metric:\|^peak_vram_mb:" run.log    # parse
```

Append `results.tsv` row. Decide using QD logic:
- **improved on headline metric** → keep, write to `archive.jsonl` cell `(niche, behavior_bucket)` if better than current occupant.
- **NOT improved on headline BUT this (niche, bucket) cell was empty / had a worse occupant** → KEEP as **stepping stone**. Annotate `status=stepping_stone`. The QD archive grows; the working branch may still `git reset --hard` to the headline-best commit, but the stepping-stone commit is preserved on a stub branch `archive/<niche>/<bucket>` for future trajectory-grounded mutations to reference.
- **equal/worse on metric AND no QD diversity gain** → `git reset --hard $START_COMMIT`, status=discard.
- **crash** → fix once, else discard.

**This is the key behavioral change vs single-objective optimization**: a single-axis "did the metric go up?" gate causes diversity collapse. The QD gate keeps stepping stones that are average-now but might unlock a future phase.

R3 seed check on keep: re-run 2 more seeds, mean ± std; if `best - mean > 2*std` → discard.

R2 ablation gate on keep with new component: remove component, re-run; if ≥ keep metric → discard.

## Phase 4 — Triple-Heterogeneous Review (P2)

For every `keep` row, BEFORE it's considered final:

```
# Pass 1 — Codex correctness (R1, R2, R6, R7)
Agent: codex:codex-rescue
prompt: |
  Review commit <SHA>. Check claim-vs-code-vs-numbers.
  Compare run.log metrics to the commit message claims.
  Flag any mismatch. Return: claim-vs-code-vs-numbers table.
```

```
# Pass 2 — Gemini assumption-challenge (R5, R9, R10)
Agent: gemini:gemini-consult
prompt: |
  Use real web_search if needed. Review commit <SHA> + decision_trace for cycle.
  Probe p-hacking, demand compression, challenge silent_priors from the implicit block.
  Return: unanswered-assumptions list, alternative root causes the generator missed.
```

```
# Pass 3 — Sonnet 4.6 red-team in FRESH context (R3, R4, R10)
Agent tool, subagent_type=general-purpose:
  prompt: |
    You are a red-team peer branch. Cold context — you have NOT seen the generator's reasoning.
    Read commit <SHA>, run.log, decision_trace.jsonl events for this cycle.
    Try to PROVE: shortcut / leakage / seed cherry-pick / overfit / dataset reuse.
    Cross-check the generator's `implicit` block against the diff:
      - Does any silent_prior contradict the diff?
      - Does any unspoken_alternative actually invalidate the kept change?
    Return: BREAK with evidence, or "no break found".
```

Aggregate per `verdict_policy`:
- BLOCK rules {R1,R4,R5,R6,R7,R10,R12} fail → `git revert`, flip ledger keep→discard, log halt OR retry
- FLAG rules {R2,R3,R8,R9,R11} fail → log + limit-time response window
- PASS only if 12 rules clear AND all 3 reviewers PASS

Append `event=review` with `verdict`, `pass1`, `pass2`, `pass3` to `decision_trace.jsonl`.

## Phase 5 — Reflect (every K cycles, default K=5)

1. Compile `findings.md` summary: best metric trajectory, niche productivity, recurring failure DNA.
2. Promote patterns from accumulated `implicit` blocks into proposed new R-rules:
   - If 3+ cycles share the same `silent_prior` → propose as new constitution clause via `/research-constitution --amend`.
   - If 3+ cycles share the same `failure_dna` → propose new kill-switch trigger.
3. Update `task_plan.md` with the next K experiments.
4. Decide: continue / stagnation-discover / halt.

## Phase 6 — Loop back

Unless a halt condition fires, return to Phase 3 (or Phase 1 on stagnation refresh). **NEVER ask the user "continue?"** — human may be asleep, the discipline is autonomous loop until terminal condition.

---

## Hard Constraints (apply across all phases)

1. **Same-message parallel dispatch** — Phase 3a is ONE assistant turn with N Agent calls. No serial dispatch.
2. **No nested Tasks** — peer-level only. A spawned Task cannot spawn its own Tasks.
3. **No model-family self-judging** — Sonnet generated, Codex+Gemini+Sonnet-fresh review.
4. **Stdin closed on every Codex / Gemini exec** — `</dev/null` always.
5. **State on disk** — every ledger row, decision_trace event, progress entry persisted before next phase. `/research-host resume` must reconstruct from disk alone.
6. **NEVER ask the user to confirm continuation** — only halt on the 6 enumerated conditions.
7. **Implicit block enforcement** — missing block = branch dropped, not retried at budget cost.
8. **No destructive ops** beyond `git reset --hard` of the current cycle's commit on discard. No force-push, no checkpoint deletion, no `rm -rf` of historical artifacts.

## Resume contract

`/research-host resume` must:
- Read `progress.md` for last round + plugin availability + sprint tag
- Read `traces/decision_trace.jsonl` tail for the most recent `event` per cycle
- Read `results.tsv` tail for the latest ledger state
- Pick up at the next subphase (e.g. if last event=`propose` with no paired `review`, jump to Phase 4)

## Reporting

At every halt, output:
- Final state (round N, best metric, ledger summary)
- Halt reason (one of the 6 enumerated)
- Top 3 implicit-knowledge patterns surfaced this run (P3 yield)
- Proposed constitution amendments (if any)
- Suggested next sprint focus (if continuing later)

End with `=== HOST HALTED: <reason> ===` so the parent process can detect.
