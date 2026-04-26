---
description: Run one experiment cycle. Edit → commit → run → grep metric → keep-or-reset → append TSV. 5-min budget, single mutable file, NEVER STOP once loop has begun. Reads paradigm doc §5 and §7.
argument-hint: "<short idea description>"
---

# /research-loop

**Engine:** Sonnet 4.6. Autonomous loop discipline per `autoresearch/program.md`.

## Constitutional anchor (MUST READ FIRST — non-negotiable)

`/home/lingxufeng/claw/plan/Regulations.md` § "Three Core Research Architecture Principles":
- **Principle 1 — Parallel + Orthogonal Coverage** (this command runs single-cycle, but the cycle's idea must come from `/research-parallel` orthogonal selection — never freelance)
- **Principle 2 — Triple-Heterogeneous Review** (any `keep` requires `/research-review` with Codex + Gemini + Sonnet-fresh — no Claude self-judging)
- **Principle 3 — Surface Implicit Knowledge** (the cycle is incomplete without the `implicit` block defined below; this is the CAI foundation)

Violating any principle → cycle is `incomplete`, not eligible for ledger, not eligible for `keep`.

## Steps

1. **Read paradigm first:**
   - `plan/research-paradigm.md` §5 (experiment cycle), §7 (decision-trace schema), §12 (escalation)
   - `contracts/constitution.v0.1.0.yaml` R2, R3, R7 (gate checks)

2. **Single-file edit** (NOT `prepare.py` or any evaluation harness):
   - Default mutable: `train.py` (autoresearch-style).
   - For automated-w2s-research arms: the niche-designated file under `w2s_research/ideas/<niche>/`.
   - Change must match `$ARGUMENTS` description.

3. **Commit BEFORE running:** `git commit -am "<arg description>"`. Every experiment = one commit.

4. **Run:** `uv run train.py > run.log 2>&1`. Redirect ALL output. Never `tee`. Kill at 10 min hard cap.

5. **Read metric:** `grep "^val_bpb:\|^peak_vram_mb:" run.log`.
   - Empty output → crash. `tail -n 50 run.log` for stack. Brief fix attempt. If still broken, status=`crash`.

6. **Append TSV** (`ledgers/<sprint>/results.tsv`, tab-separated — NOT comma):
   ```
   <short-commit>\t<val_bpb>\t<memory_gb>\t<keep|discard|crash>\t<description>
   ```
   - crashes: `val_bpb=0.000000`, `memory_gb=0.0`.

7. **Keep-or-reset:**
   - Metric improved → keep commit (branch advances).
   - Equal or worse → `git reset --hard HEAD~1`.

8. **R3 seed check** (if status=keep):
   - Re-run with 2 additional seeds.
   - Compute mean ± std across 3 seeds.
   - If `best - mean > 2*std`, R3 fails → flip keep → discard, `git revert`.

9. **R7 failure condition** (if status=keep):
   - Append to `decision_trace.jsonl` with `event=keep`, `metric`, `failure_condition`.
   - No unconditional claims allowed.

10. **R2 complexity gate** (if status=keep AND added new component):
    - Ablation required: remove the component, re-run 1 seed.
    - If ablated metric ≥ kept metric, R2 fails → flip keep → discard.

11. **Surface Implicit Knowledge** (Principle 3 — MANDATORY before declaring cycle done):

    Append a structured `implicit` block to `decision_trace.jsonl` with `event=surface_implicit`
    using THIS schema (every field non-empty, every implicit claim cites an evidence_pointer):

    ```yaml
    explicit:
      reasoning_trace: "<what you did this cycle, in 3-6 lines>"
      result: "<metric delta, commit SHA, status>"

    implicit:
      silent_priors: |
        <assumptions you made that the prompt did NOT ask you to state.
         e.g. "I assumed batch_size doesn't change this comparison because ...",
              "I treated the evaluator as untrustworthy on edge case X because ...">
      unspoken_alternatives: |
        <approaches you considered but didn't try, AND the real reason you skipped them
         (NOT 'token budget' — technical judgment, intuition, prior bias).
         e.g. "I skipped LoRA rank=64 because my intuition is rank=16 saturates here;
              that intuition rests on ...">
      failure_dna: |
        <a level deeper than the commit message. Surface reason vs likely real cause.
         e.g. "Surface: lr too high. Likely real: my warmup schedule masks the actual
              gradient pathology, which I'd see if I plotted grad_norm vs step.">
      hidden_dependencies: |
        <env priors this conclusion silently rests on: seed, CUDA version, dataset
         column ordering, race conditions, undocumented upstream behavior.>
      what_a_skeptical_PI_would_ask: |
        <The 3 questions you'd LEAST want to answer if a skeptical PI showed up now.
         Write them, then take a first honest crack at each.>

    evidence_pointers:
      - "<file:line | run.log line | commit SHA | dataset key — every implicit claim cited>"
    ```

    **Hard rule:** missing or marketing-speak `implicit` block ⇒ cycle = `incomplete`,
    NOT eligible for `keep` regardless of metric. Re-run; cycle does not consume budget.

12. **Hand off to `/research-review`** for Triple-Heterogeneous audit BEFORE the cycle
    is considered closed (Principle 2). Pass the `implicit` block to all three reviewers —
    they must check for inconsistencies between explicit and implicit claims.

## NEVER STOP discipline
Once invoked (especially when chained in a session), do NOT ask the user "should I continue." The human may be asleep. Loop until manually interrupted. If stuck on ideas, reread `Idea.md`, combine near-misses, try more radical changes.

## Escalation
- 2 consecutive crashes on same idea → `/codex:rescue --model gpt-5.3-codex` with `findings.md`.
- Constitution violation detected → halt loop, emit `event=halt`, surface to user.
