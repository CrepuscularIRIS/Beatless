---
description: Heterogeneous 3-pass judge chain. Codex 5.4-mini correctness + Gemini 3.1-pro challenge + Sonnet 4.6 red-team peer branch. No GPT reviews GPT. Reads paradigm §6 and constitution § review_chain.
argument-hint: [--cycle <n>] [--sprint <tag>]
---

# /research-review

**Heterogeneous mandatory.** Generator was Sonnet 4.6; reviewers must cross families.

## Constitutional anchor (MUST READ FIRST)

`/home/lingxufeng/claw/plan/Regulations.md` § "Three Core Research Architecture Principles":
- **Principle 2 (Triple-Heterogeneous Review)** is what this command implements. No model family reviews itself.
- **Principle 3 (Surface Implicit Knowledge)**: each of the 3 reviewers MUST be passed BOTH the explicit reasoning AND the `implicit` block from `decision_trace.jsonl event=surface_implicit`. Reviewers cross-check explicit vs implicit for inconsistency. A finding "explicit claims X but implicit silent_priors contradict X" is a strong BLOCK signal.
- Reviewer prompts MUST include: "the generator's `implicit` block is below; surface inconsistencies between what they wrote and what they admit they assumed/skipped."

## Steps

1. **Read paradigm + constitution first:**
   - `plan/research-paradigm.md` §6 (review protocol), §7 (trace schema)
   - `contracts/constitution.v0.1.0.yaml` § review_chain, § verdict_policy

2. **Identify target cycle** (from `--cycle` arg, or latest `status=keep` row in `results.tsv`).
   - Extract: commit SHA, diff, claimed metric, failure_condition, engaged niche.

3. **Pass 1 — Correctness (Codex gpt-5.4-mini):**
   ```bash
   /codex:review
   ```
   - Pass target diff + claim. Codex checks R1, R2, R6, R7.
   - Output: claim-vs-code-vs-numbers table. Any mismatch = flag.

4. **Pass 2 — Architecture (Gemini 3.1-pro-preview):**
   ```bash
   /gemini:challenge
   ```
   - Pass target diff + decision_trace for this cycle.
   - Gemini checks R5, R9, R10. Probes p-hacking, demands compression, challenges assumptions.
   - Output: unanswered-assumptions list.

5. **Pass 3 — Red-Team peer branch (Sonnet 4.6, fresh Task context):**
   - Single Task tool call, `subagent_type=general-purpose`.
   - Prompt: niche spec `red-team` from paradigm §3 + target artifact + full decision_trace.
   - Branch attempts to prove: shortcut / leakage / seed-cherry-pick / overfit / dataset-reuse.
   - Checks R3, R4, R10. Output: break verdict with evidence or "no break found."

6. **Verdict aggregation** (per constitution § verdict_policy):
   - `BLOCK` if any rule in {R1, R4, R5, R6, R7, R10} fails.
   - `FLAG` if any rule in {R2, R3, R8, R9, R11, R12} fails.
   - `PASS` iff all 12 rules clear across all 3 passes.

7. **Append to `decision_trace.jsonl`:**
   ```json
   {"ts": "...", "cycle": <n>, "niche": "red-team", "event": "review", "verdict": "<PASS|FLAG|BLOCK>", "pass1": {...}, "pass2": {...}, "pass3": {...}}
   ```

8. **On BLOCK:** flip `status=keep` → `discard` retroactively in TSV. `git revert` the commit. Surface to user.

## Hard constraints
- Pass 1 MUST be Codex (not Claude, not Gemini).
- Pass 2 MUST be Gemini (not Codex, not Claude).
- Pass 3 MUST be Sonnet 4.6 in a FRESH Task — never the same context as generation.
