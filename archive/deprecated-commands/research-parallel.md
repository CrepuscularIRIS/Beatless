---
description: Dispatch peer-branch niche exploration in parallel. Sonnet 4.6 orchestrator + up to 9 concurrent peer Sonnet 4.6 subagents. No hierarchy, no nesting. Reads paradigm doc §3, §4, §7.
argument-hint: [--niches n1,n2,...] [--sprint <tag>]
---

# /research-parallel

**Engine:** Sonnet 4.6 throughout (per paradigm §1). Peer branches, not AgentTeam.

## Constitutional anchor (MUST READ FIRST)

`/home/lingxufeng/claw/plan/Regulations.md` § "Three Core Research Architecture Principles":
- **Principle 1 — Parallel + Orthogonal Coverage**: this command IS the Principle-1 implementation. Niche selection must enforce orthogonality (cosine-overlap between any two niche direction-statements ≤ 0.6, sampled by orchestrator). R11 entropy-collapse check is mandatory.
- **Principle 2 — Triple-Heterogeneous Review**: each Task's proposal must be ranked but never auto-selected; final keep requires `/research-review` chain after `/research-loop`.
- **Principle 3 — Surface Implicit Knowledge**: every spawned Task MUST include the prompt fragment below.

Failure on any principle → orchestrator MUST halt and surface to user, not silently proceed.

## Mandatory prompt fragment for every spawned Task

Inject this verbatim into each peer-Task prompt (after niche spec, before "do not nest"):

```
SURFACE IMPLICIT KNOWLEDGE (Principle 3 — non-negotiable):
Your output is incomplete unless it contains an `implicit` block with:
  silent_priors            — assumptions you make that I did not ask you to state
  unspoken_alternatives    — directions you considered but skipped, AND the real reason
                             (technical judgment / intuition / prior bias, NOT token budget)
  failure_dna              — root cause one level deeper than the surface explanation
  hidden_dependencies      — env priors this rests on (seed, version, undocumented behavior)
  what_a_skeptical_PI_would_ask — top-3 questions you'd least want to answer; answer them honestly

Each implicit claim cites an evidence_pointer (file:line / log line / commit SHA / dataset key).
No `implicit` block ⇒ your proposal is incomplete and excluded from ranking.
```

## Steps

1. **Read paradigm first:**
   - `plan/research-paradigm.md` §3 (niche specs), §4 (parallel protocol), §7 (decision-trace schema)
   - `contracts/constitution.v0.1.0.yaml` (full 12 rules + niche forbidden-behaviors)
   - `~/claw/plan/Regulations.md` § Three Core Principles (the anchor above)
   - Active sprint tag: from `$ARGUMENTS` `--sprint` or latest `ledgers/*/sprint.yaml`.

2. **Pick niches this cycle (Principle 1 — orthogonality enforcement):**
   - Default: all niches in sprint.yaml `active_niches` (up to 9).
   - Override: if `--niches` passed, use that subset.
   - Min 3, max 9. Skip `paper-filter` / `theory-compressor` in tight-budget mode.
   - Check R11 (entropy collapse): if last cycle had ≥2 niches converge on same direction, force-reassign them.
   - **Orthogonality precheck**: for the chosen niche set, write a one-sentence "core question" per niche, then run a quick semantic similarity pass between every pair (LLM-judge or embedding cosine). Any pair > 0.6 = reassign. Log the matrix to `decision_trace.jsonl` with `event=orthogonality_check`.

3. **Dispatch in ONE message** (critical — concurrent, not sequential):
   - Emit N `Task` tool calls in a single assistant turn.
   - Each Task: `subagent_type=general-purpose`, prompt built from:
     - niche spec (direction + goal + forbidden from §3)
     - 12 rules (summary form)
     - current ledger tail (last 10 rows of `results.tsv`)
     - last 5 entries of `decision_trace.jsonl` for THIS niche
     - explicit "do not spawn further Task calls; do not nest"
   - Each Task returns: proposed next experiment (what to change, failure condition per R7, expected metric delta, which rules engaged).

4. **Merge (append-only):**
   - **Filter incomplete first**: any Task whose return lacks an `implicit` block is dropped from ranking and counted as an incomplete branch (Principle 3 enforcement). Log `event=incomplete_branch` with niche + reason.
   - Rank surviving proposals against constitution.
   - Append each surviving proposal to `decision_trace.jsonl` with `event=propose` PLUS its `implicit` block in a paired `event=surface_implicit` row.
   - Flag convergence (≥2 niches same direction) for R11 next-cycle reassignment.
   - Do NOT pick a winner automatically — surface ranked list to user. Generator-as-judge is forbidden (Principle 2).

5. **Output:** ranked proposal list. User picks one → `/research-loop "<idea>"`.

## Hard constraints
- One Task per niche. Never spawn a Task from inside a Task.
- Peer-level only. No orchestrator-above-orchestrator.
- Token cap: if dispatching >9 branches, REFUSE (paradigm §4).
