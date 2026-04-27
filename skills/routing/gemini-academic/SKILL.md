---
name: gemini-academic
description: Delegate ACADEMIC tasks to Gemini CLI. Distinct from gemini-router (engineering/long-context). Three modes — cross-domain mining (Flash), challenger feasibility audit (Pro), arxiv probe (Pro). All challenger-framed; never agreement-seeking. Always paired with codex-academic citation-verify.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [routing, gemini, academic, challenger, cross-domain]
    related_skills: [gemini-router, codex-academic]
---

# gemini-academic

When to use: tasks that need Gemini's **strongest academic database + divergent thinking** — but with hallucination + sycophancy controls. Per memory `feedback_model_routing.md` academic-mode roster: Gemini 3.1 Pro has the highest academic ability AND the highest hallucination rate AND tends to please. This wrapper bakes in the controls.

**Distinct from `gemini-router`** (engineering): gemini-router is for long-context code / translation review. gemini-academic is for cross-domain mining + challenger feasibility — every prompt is challenger-framed, every emitted citation gets Codex-verified.

## Hard control discipline (per memory § Gemini control discipline)

These are not optional — every mode below applies them:

1. **Always challenger-framed, never supporter-framed**. Prompt must contain "challenge", "find what is wrong/risky/missing", "DO NOT agree-to-please". Never "do you agree", "is this right", "support this".
2. **Demand machine-checkable evidence**. Every claim cites arxiv-id (or DOI). Soft references like "the literature shows" → reject the output.
3. **Always pair with codex-academic citation-verify**. Caller MUST run codex-academic Mode 2 on every arxiv-id Gemini emits. Hallucination rate >30% → halt.
4. **Never the terminal artifact**. Gemini's output is intermediate; an Opus 4.7 review must follow before any decision is made.
5. **Stdin discipline**: every `gemini -p` call MUST `</dev/null`.

## Three modes

### Mode 1 — `cross-domain-mining`
Find K breakthrough papers from non-adjacent fields whose CORE METHODOLOGICAL MOVE could plausibly transfer to a target domain. Used by `/research-survey` Stage 1.

Engine: `gemini-3-flash-preview` (bulk academic search). Flash is enough — Pro's depth isn't worth the hallucination risk on bulk paper discovery.

**Inputs**: `target_domain`, `K` (default 3)
**Output contract** (strict YAML):
```yaml
candidates:
  - arxiv: <id>
    title: <verbatim>
    field: <not target_domain>
    core_move: <one sentence, philosophical not technical>
    axiom_attacked: <which default axiom of target_domain>
  - arxiv: ...
    ...
```

### Mode 2 — `challenger-feasibility`
Probe a proposed reframe for hidden assumptions, infeasibility paths, ablation traps, and contradicting prior work. Used by `/research-propose` Stage 3.

Engine: `gemini-3.1-pro-preview` with `--approval-mode plan` (read-only). Pro's depth is needed to find non-trivial assumption holes; the hallucination is controlled by codex-academic citation-verify on the output.

**Inputs**: `reframe_text`, `testable_prediction`, `measurable_contribution`
**Output contract**:
```yaml
hidden_assumptions:
  - <load-bearing assumption inside the reframe — 3-5 items>
infeasibility_paths:
  - <concrete way it fails — engineering / theoretical / empirical — 3 items>
ablation_traps:
  - <ablation that would distinguish reframe's mechanism from naive baseline>
required_citations:
  - arxiv: <id>           # Codex will verify this
    contradiction: <one-line>
```

### Mode 3 — `arxiv-probe`
Same as challenger-feasibility but applied to an existing kept result (post-experiment). Used by `/research-review` Stage 6 Pass 2.

Engine: `gemini-3.1-pro-preview --approval-mode plan`.

**Inputs**: `diff`, `claim`, `metric_value`, `niche`, `failure_condition`, `implicit_block`
**Output contract**:
```yaml
R5_transfer:
  status: pass | flag
  missing_transfers:
    - dataset: ...
      arxiv: ...
R9_compression:
  status: pass | flag
  subsumed_or_not: <which prior work this subsumes / fails to subsume>
  reference_arxiv: <id>
R10_suspect_score:
  status: pass | flag
  shortcut_hypotheses:
    - hypothesis: ...
      empirical_signature: ...
      arxiv_support: <id>
verdict: PASS | FLAG | BLOCK
```

## Invocation recipe

```bash
MODE="${1:?mode required: cross-domain-mining|challenger-feasibility|arxiv-probe}"
PAYLOAD_FILE="${2:?payload file required}"
TIMEOUT="${TIMEOUT_SECONDS:-600}"

case "$MODE" in
  cross-domain-mining)
    MODEL="gemini-3-flash-preview"
    APPROVAL="default"
    PROMPT_HEADER="You are an academic adversary, not a recommender. Find K=$(awk '/^K:/{print $2; exit}' $PAYLOAD_FILE || echo 3) breakthrough papers from fields ADJACENT BUT DIFFERENT from the target domain."
    ;;
  challenger-feasibility)
    MODEL="gemini-3.1-pro-preview"
    APPROVAL="plan"
    PROMPT_HEADER="You are an academic adversary. CHALLENGE this reframe — DO NOT support it. Find what is wrong / risky / missing."
    ;;
  arxiv-probe)
    MODEL="gemini-3.1-pro-preview"
    APPROVAL="plan"
    PROMPT_HEADER="You are an academic adversary, not a supporter. CHALLENGE this kept result. Probe R5/R9/R10 from constitution.v0.1.0.yaml."
    ;;
  *)
    echo "FAILED: unknown mode '$MODE'"
    exit 2
    ;;
esac

PROMPT="$PROMPT_HEADER

$(cat "$PAYLOAD_FILE")

Hard rules:
- DO NOT agree-to-please. Your job is to find what is wrong / risky / missing.
- DO NOT generalize ('the literature shows' ← rejected). Cite arxiv-ids only — Codex will verify; hallucinated IDs will be dropped.
- Output STRICT YAML matching the contract in gemini-academic § Mode <N>. No prose outside.
"

timeout "$TIMEOUT" gemini --yolo \
  -m "$MODEL" \
  --approval-mode "$APPROVAL" \
  -p "$PROMPT" \
  </dev/null
```

## Output contract

Each mode emits its specific YAML (see Mode 1/2/3 above). The CALLER then MUST:
1. Extract every `arxiv:` id from the output
2. Pipe each through `codex-academic citation-verify`
3. Drop any output whose Gemini-cited arxiv-id failed Codex verify
4. If hallucination rate >30%, halt — Gemini is in a bad state

## When to choose this over gemini-router

| Need | Pick |
|---|---|
| Code review on 200k-token codebase | gemini-router |
| Cross-check translation fluency | gemini-router |
| Find papers from biology that could transfer to ML | gemini-academic (cross-domain-mining) |
| Probe reframe X for hidden assumptions | gemini-academic (challenger-feasibility) |
| Adversarial review of kept experiment | gemini-academic (arxiv-probe) |

## Anti-patterns

- ❌ DO NOT use gemini-academic without paired codex-academic citation-verify (hallucination escapes)
- ❌ DO NOT use agreement-framed prompts ("do you agree", "support this") — defeats the wrapper purpose
- ❌ DO NOT use gemini-academic output as the final decision artifact — Opus 4.7 must review
- ❌ DO NOT remove `</dev/null` (cron stdin hang)
- ❌ DO NOT use `gemini-3.1-pro` without `-preview` suffix (returns 404 per gemini-router note)
