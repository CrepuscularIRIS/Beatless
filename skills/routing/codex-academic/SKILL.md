---
name: codex-academic
description: Delegate ACADEMIC tasks to OpenAI Codex CLI. Distinct from codex-router (engineering/debugging). Three modes — novelty audit, citation verify, claim-vs-code-vs-numbers — all conservative + citation-anchored. Used by /research-* commands and Hermes research-cycle cron.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [routing, codex, academic, novelty, citation-verify]
    related_skills: [codex-router, gemini-academic]
---

# codex-academic

When to use: any task in the academic-research pipeline where Codex's **conservative, citation-anchored, almost-never-wrong** personality is load-bearing. Per memory `feedback_model_routing.md` academic-mode roster: this is the wrapper for /research-survey, /research-propose, /research-review.

**Distinct from `codex-router`** (engineering): codex-router defaults to `gpt-5.3-codex` for terminal-debug loops. codex-academic uses `gpt-5.4` for review-style fact-anchored audit. Both wrappers can coexist.

## Three modes

### Mode 1 — `novelty`
Check whether a proposed reframe / cross-domain transfer is already published.

**Inputs**: `reframe_text`, `target_domain`, `core_move`
**Output contract** (strict YAML):
```yaml
status: published | near-match | no-match | cannot-verify
existing_work:
  - arxiv: <id>
    claim: <one-line>
    distinguishing_axis: <vs-the-reframe>
near_matches:
  - arxiv: <id>
    distinguishing_axis: <axis>
```

### Mode 2 — `citation-verify`
Verify whether an arxiv-id resolves to a real paper with the claimed title/claim. Used to catch Gemini hallucination per `feedback_model_routing.md` § Gemini control discipline.

**Inputs**: `arxiv_id`, optional `expected_title`, optional `expected_claim`
**Output contract**:
```yaml
arxiv: <id>
match: yes | no | cannot-verify
title: <actual title if match>
claim: <actual 1-line claim if match>
```

### Mode 3 — `claim-vs-code-vs-numbers`
Three-column audit: does the diff implement the claim, do the numbers support it.

**Inputs**: `claim_text`, `diff`, `metric_value`, `metric_name`, `failure_condition`, `implicit_block`
**Output contract**:
```yaml
checks:
  R1: pass | flag | block       # mechanism present, not just metric
  R2: pass | flag | block       # ablation present
  R6: pass | flag | block       # baseline failure mode named
  R7: pass | flag | block       # failure_condition concrete + testable
  explicit_vs_implicit: consistent | inconsistent
mismatches:
  claim_vs_code: [...]
  claim_vs_numbers: [...]
verdict: PASS | FLAG | BLOCK
```

## Invocation recipe

Stdin discipline mandatory. Model defaults to `gpt-5.4` (verified working as of 2026-04-27). Use `gpt-5.4-mini` for citation-verify only (fact lookup) to save tokens.

```bash
MODE="${1:?mode required: novelty|citation-verify|claim-vs-code-vs-numbers}"
PAYLOAD_FILE="${2:?payload file required}"
MODEL="${MODEL:-gpt-5.4}"
TIMEOUT="${TIMEOUT_SECONDS:-300}"

# Compose prompt per mode
case "$MODE" in
  novelty)
    PROMPT=$(cat <<'PROMPT_EOF'
Academic novelty audit (conservative, citation-anchored, no speculation).

Given: $(cat "$PAYLOAD_FILE")

Q1 — Has any peer-reviewed paper published this exact reframe? (published / near-match / no-match)
Q2 — If near-match: list arxiv-id + 1-line distinguishing axis between published work and this reframe.
Q3 — If no-match: list 3 most-related published works with arxiv-id + axis on which they differ.

Output STRICT YAML matching the contract in codex-academic § Mode 1. NO speculation; if unsure on citation existence, say "cannot-verify".
PROMPT_EOF
)
    ;;
  citation-verify)
    PROMPT=$(cat <<'PROMPT_EOF'
Citation verify (academic mode, conservative).

Given: $(cat "$PAYLOAD_FILE")

Q1 — Does the arxiv-id resolve to a real paper?
Q2 — If yes: what is the actual title and 1-line claim? Compare with expected_title / expected_claim if provided — flag mismatches.

Output STRICT YAML matching the contract in codex-academic § Mode 2. DO NOT speculate.
PROMPT_EOF
)
    # Use mini for cheaper citation lookup
    MODEL="${MODEL:-gpt-5.4-mini}"
    ;;
  claim-vs-code-vs-numbers)
    PROMPT=$(cat <<'PROMPT_EOF'
Academic correctness review (claim vs code vs numbers, conservative, citation-anchored).

Given: $(cat "$PAYLOAD_FILE")

Check rules from contracts/constitution.v0.1.0.yaml:
- R1 score_is_not_discovery — claim must include transferable mechanism
- R2 complexity_guilty — added components must have ablation
- R6 explain_why_w2s_fails — writeup must name baseline failure mode + correction
- R7 failure_condition_required — failure_condition must be concrete + testable

Also check Principle 3 cross-consistency: does the explicit reasoning contradict any silent_prior in the implicit block?

Output STRICT YAML matching the contract in codex-academic § Mode 3.
PROMPT_EOF
)
    ;;
  *)
    echo "FAILED: unknown mode '$MODE' — use novelty | citation-verify | claim-vs-code-vs-numbers"
    exit 2
    ;;
esac

timeout "$TIMEOUT" codex exec \
  --model "$MODEL" \
  --skip-git-repo-check \
  </dev/null \
  "$PROMPT"
```

## Hard rules (per memory feedback_model_routing.md academic mode)

1. **Stdin discipline**: every invocation MUST `</dev/null` (otherwise codex hangs on "Reading additional input from stdin" — verified 2026-04-26).
2. **No speculation**: if Codex cannot verify a fact, output `cannot-verify` — do NOT fabricate. This is the load-bearing personality of this wrapper; if you ask it to speculate, you've defeated the purpose.
3. **Citation-only mode**: in `citation-verify`, NEVER ask Codex to "improve" or "rewrite" a citation — only verify it resolves.
4. **Pair with gemini-academic**: this wrapper is the verifier; gemini-academic is the diverger. Never use codex-academic for divergence (use codex-router or gemini-academic instead). Never use gemini-academic for citation-verify (always use codex-academic).
5. **No GPT reviews GPT**: per heterogeneous review chain, codex-academic outputs MUST be reviewed by a non-OpenAI model before action (Opus 4.7 or Gemini 3.1 Pro).

## Output contract

Codex output ends with one of:
- The final YAML block per mode contract above
- `RESULT: cannot-complete — <reason>` if the mode cannot be honored

## When to choose this over codex-router

| Need | Pick |
|---|---|
| Code review on a PR | codex-router |
| Run tests + fix iteratively | codex-router |
| Verify whether arxiv:2505.13447 is real | codex-academic (citation-verify) |
| Check if reframe X is already published | codex-academic (novelty) |
| Audit claim-vs-code in research diff | codex-academic (claim-vs-code-vs-numbers) |
| Debug "why does train.py crash" | codex-router |

## Anti-patterns

- ❌ Do NOT use codex-academic on engineering tasks (dilutes the academic personality)
- ❌ Do NOT remove `</dev/null` — same hang issue
- ❌ Do NOT ask Codex to speculate — that's gemini-academic's job
- ❌ Do NOT chain codex-academic → codex-academic for review (no GPT reviews GPT)
