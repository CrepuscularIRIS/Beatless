---
description: "Triple-heterogeneous review — use when user says 'audit this experiment', 'review the kept result', 'red-team this finding', 'check for shortcut/leakage', 'triple review', '审一下', '让Codex+Gemini+Sonnet联审'. Stage 6 of 6: Pass 1 Codex correctness (claim vs code vs numbers), Pass 2 Gemini challenger (R5/R9/R10) + citation-verify, Pass 3 Sonnet red-team peer-branch (FRESH context). Verdict per constitution verdict_policy."
argument-hint: "[--cycle <n>]"
allowed-tools: Bash, Read, Write, Edit, Agent
---

# /research-review

**Pipeline position**: Stage 6 of 6 — only fires after a /research-loop produces `status=keep`.

**Engines** (cross-family enforced; per memory routing rule "no GPT reviews GPT, no Gemini reviews Gemini"):
- **Pass 1** = Codex GPT-5.4 (academic correctness mode, distinct from github wrapper) — checks R1, R2, R6, R7
- **Pass 2** = Gemini 3.1 Pro Preview (challenger-framed, paired with Codex citation-verify per memory hallucination control) — checks R5, R9, R10
- **Pass 3** = Sonnet 4.6 in FRESH Agent context (peer red-team branch, NEVER same context as generation) — checks R3, R4, R10

**Why this exact split**: each model family catches a distinct failure mode. Codex is the only one conservative enough to spot claim-vs-numbers mismatches without speculating. Gemini Pro has the strongest academic database for assumption probing — but its hallucination requires the Codex citation-verify pairing. Sonnet red-team in fresh context catches what same-session Sonnet would smooth over.

**Cronjob-safe**: yes; idempotent per cycle; rerun overwrites the same review files.

## Constitutional anchor

`contracts/constitution.v0.1.0.yaml § review_chain` + `§ verdict_policy`:
- BLOCK if any rule in {R1, R4, R5, R6, R7, R10} fails
- FLAG if any rule in {R2, R3, R8, R9, R11, R12} fails
- PASS iff all 12 rules clear across all 3 passes

Plus Principle 3: each of the 3 reviewers MUST be passed BOTH the explicit reasoning AND the `implicit` block. Reviewers cross-check explicit-vs-implicit for inconsistency. A finding "explicit claims X but implicit silent_priors contradict X" is a strong BLOCK signal.

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"

# Identify target cycle
if [ -n "$ARG_CYCLE" ]; then
  CYCLE="$ARG_CYCLE"
else
  # Latest keep row in results.tsv (skipping header)
  CYCLE=$(awk -F'\t' 'NR>1 && $4=="keep" {n=NR-1} END{print n}' "$SPRINT_DIR/results.tsv")
fi
[ -n "$CYCLE" ] || { echo "ERROR: no keep row found in results.tsv"; exit 1; }

SHA=$(awk -F'\t' -v n=$((CYCLE+1)) 'NR==n {print $1}' "$SPRINT_DIR/results.tsv")
DESC=$(awk -F'\t' -v n=$((CYCLE+1)) 'NR==n {print $5}' "$SPRINT_DIR/results.tsv")
VAL_BPB=$(awk -F'\t' -v n=$((CYCLE+1)) 'NR==n {print $2}' "$SPRINT_DIR/results.tsv")

# Implicit block must exist for this cycle
grep -q "\"event\":\"surface_implicit\".*\"commit\":\"$SHA\"\|\"event\":\"surface_implicit\".*\"cycle\":$CYCLE" "$SPRINT_DIR/decision_trace.jsonl" \
  || { echo "ERROR: no surface_implicit row for cycle $CYCLE / sha $SHA — Principle 3 gate failed; /research-loop did not externalize properly"; exit 1; }

DIFF=$(git -C "$RGMARE_ROOT" show --stat "$SHA")
DIFF_FULL=$(git -C "$RGMARE_ROOT" show "$SHA")
IMPLICIT_BLOCK=$(grep "\"event\":\"surface_implicit\".*\"commit\":\"$SHA\"" "$SPRINT_DIR/decision_trace.jsonl" | tail -1)
NICHE=$(echo "$IMPLICIT_BLOCK" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("niche","unknown"))')
FAILURE_COND=$(grep "\"event\":\"keep\".*\"commit\":\"$SHA\"" "$SPRINT_DIR/decision_trace.jsonl" | tail -1 | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("failure_condition","unknown"))')

mkdir -p "$SPRINT_DIR/reviews"
```

## Anti-gaming gates

| Gate | Check | If failed |
|---|---|---|
| Implicit block present | `event=surface_implicit` row exists for target SHA | exit 1 |
| Cross-family enforced | Pass 1 = Codex, Pass 2 = Gemini, Pass 3 = Sonnet (fresh) | hard error if reordered |
| Citation verify | every Gemini-cited arxiv-id passes Codex verify | drop fabricated objections |
| YAML well-formed | each pass output parses as YAML | retry once, halt on second fail |
| Verdict aggregation | follows constitution verdict_policy exactly | hard error |

> **Schema note (per user-directive 2026-04-27)**: aggregated `cycle-N.md` review file MUST include a `## Reviewer disclosure` block at the bottom with the standard `priors_used / alternatives_considered / not_checked / confidence / skeptical_PI_questions` (the reviewer's own externalization, separate from the generator's). Format unified across all /research-* commands.

## Permission boundary (per user-directive 2026-04-27)

- File writes ONLY within `${SPRINT_DIR}/reviews/`. Reads from `results.tsv`, `decision_trace.jsonl`, git diff/show allowed.
- 3 reviewers via heterogeneous wrappers:
  - Pass 1 = Codex via `~/.hermes/skills/routing/codex-academic/` Mode 3 (claim-vs-code-vs-numbers)
  - Pass 2 = Gemini via `~/.hermes/skills/routing/gemini-academic/` Mode 3 (arxiv-probe)
  - Pass 3 = Sonnet 4.6 via Agent tool (FRESH context, peer red-team niche)
- NO reviewer may invoke another reviewer of its own family (no GPT reviews GPT, no Gemini reviews Gemini).
- Network: HTTPS to arxiv.org / OpenReview ONLY for Codex citation-verify side-calls.

## Multi-round consult policy (per user-directive 2026-04-27)

- If Codex Pass 1 emits any `cannot-verify` on R1/R2/R6/R7 evidence → reword (e.g. paste the relevant code snippet inline rather than referencing diff lines); up to 2 retry rounds.
- If Gemini Pass 2 returns `R10_suspect_score: pass` but the implicit block contains `silent_priors` that look load-bearing → MANDATORY second Gemini round with the silent_priors quoted in the prompt: "challenge assuming these silent priors are wrong".
- If Sonnet Pass 3 returns `NO_BREAK_FOUND` but Gemini found ≥2 plausible shortcut hypotheses → re-spawn Sonnet red-team peer with Gemini's hypotheses as seed prompts; one more round, then accept verdict.
- Cap: 8 sub-consults per /research-review invocation. Beyond that → halt and surface; the verdict is too uncertain to commit.

## Steps

### Step 1 — Pass 1: Codex correctness (academic mode)

```bash
codex exec --model gpt-5.4 --skip-git-repo-check </dev/null "$(cat <<EOF
Academic correctness review (claim vs code vs numbers, conservative, citation-anchored):

Diff stats:
$DIFF

Full diff:
$DIFF_FULL

Claim from results.tsv: $DESC
Metric: val_bpb=$VAL_BPB
Failure condition (R7, from decision_trace.jsonl event=keep): $FAILURE_COND
Implicit block (Principle 3, from decision_trace.jsonl event=surface_implicit): $IMPLICIT_BLOCK

Check these rules from contracts/constitution.v0.1.0.yaml:

R1 — score_is_not_discovery: does the claim include a transferable mechanism, or is it just a metric delta?
R2 — complexity_guilty: was the new component ablated (look for an ablation row in results.tsv near $SHA)?
R6 — explain_why_w2s_fails: does the writeup name the baseline failure mode + the correction mechanism?
R7 — failure_condition_required: is failure_condition concrete + testable (specific regime, observable signal)?

ALSO check Principle 3 cross-consistency:
- explicit_vs_implicit_inconsistency: does the explicit reasoning contradict any silent_prior in the implicit block?

Output STRICT YAML, no prose:
checks:
  R1: pass | flag | block
  R1_evidence: <quote from diff or claim>
  R2: pass | flag | block
  R2_evidence: ...
  R6: pass | flag | block
  R6_evidence: ...
  R7: pass | flag | block
  R7_evidence: ...
  explicit_vs_implicit: consistent | inconsistent
  inconsistency_evidence: <if inconsistent, quote both>
mismatches:
  claim_vs_code: <list any code that does not implement the claim>
  claim_vs_numbers: <list any numerical results that contradict the claim>
verdict: PASS | FLAG | BLOCK
EOF
)" > "$SPRINT_DIR/reviews/cycle-$CYCLE-pass1-codex.yaml"
```

### Step 2 — Pass 2: Gemini 3.1 Pro challenger

Per memory rule: Gemini is challenger-framed only; agreement-seeking prompts are forbidden.

```bash
gemini --yolo -m gemini-3.1-pro-preview --approval-mode plan -p "$(cat <<EOF
You are an academic adversary, not a supporter. CHALLENGE this kept result. DO NOT agree-to-please.

Diff stats:
$DIFF

Claim: $DESC
Metric: val_bpb=$VAL_BPB
Niche: $NICHE
Failure condition: $FAILURE_COND
Implicit block: $IMPLICIT_BLOCK

Probe these rules from constitution.v0.1.0.yaml:

R5 — transfer_mandatory: does the mechanism validate on >1 dataset/task slice? If only one tested, list 3 SPECIFIC cross-dataset transfers that should have been tested + the arxiv-id of a paper providing the cross-dataset.

R9 — compression_over_tricks: is this a metric-trick (stacking complexity) or a true mechanism that compresses prior phenomena? Cite ≥1 prior published work whose explanation this either subsumes or fails to subsume — give arxiv-id.

R10 — suspect_score_before_explanation: list 5 specific shortcut/leakage/seed-hack/format-shortcut hypotheses, each with the empirical signature that would prove it.

Required: every claim cites arxiv-id (Codex will verify; hallucinated IDs will be dropped).

Output STRICT YAML:
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
EOF
)" </dev/null > "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-gemini.yaml"
```

### Step 3 — Codex citation-verify on Gemini's emitted arxiv-ids

```bash
> "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-citverify.yaml"

for ARXIV_ID in $(awk '/arxiv:/ {gsub(/[",]/,""); print $NF}' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-gemini.yaml" | sort -u); do
  codex exec --model gpt-5.4 --skip-git-repo-check </dev/null "$(cat <<EOF
Citation verify (academic mode, conservative):

arxiv:$ARXIV_ID

Q1 — Does this arxiv-id resolve to a real paper? (yes / no / cannot-verify)
Q2 — If yes: what is the actual title and 1-line claim?

Output STRICT YAML:
arxiv: $ARXIV_ID
match: yes | no | cannot-verify
title: <if match>
claim: <if match>

DO NOT speculate.
EOF
)" >> "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-citverify.yaml"
done

# Compute Gemini hallucination rate
N_TOTAL=$(grep -c '^arxiv:' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-citverify.yaml")
N_BAD=$(grep -c 'match: no' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-citverify.yaml")
HALLUC=$([ "$N_TOTAL" -gt 0 ] && echo "scale=2; 100 * $N_BAD / $N_TOTAL" | bc || echo "0")

[ "$(echo "$HALLUC > 30" | bc)" = "1" ] && { echo "ERROR: Gemini hallucination rate ${HALLUC}% > 30% — halting; rerun with sharper challenger prompt"; exit 1; }
```

Drop Gemini objections whose supporting arxiv-id failed verify (those objections were based on fabricated citations).

### Step 4 — Pass 3: Sonnet 4.6 red-team peer-branch (FRESH Agent context)

CRITICAL: this MUST be a fresh Agent invocation. Same-session Sonnet would smooth over what red-team should attack.

```
Agent invocation:
  subagent_type: general-purpose
  description: "Red-team peer review (Sonnet 4.6, fresh context)"
  prompt: <below>

(NO model override → defaults to Sonnet 4.6, fresh context per Agent tool semantics.)
```

Sub-agent prompt:

```
You are a peer red-team subagent. niche_id = red-team. DO NOT propose methods. DO NOT spawn other subagents.

Inputs:
- diff: $DIFF
- decision_trace cycle $CYCLE (paste relevant rows)
- implicit block: $IMPLICIT_BLOCK
- constitution rules to engage: R3 (seed distribution), R4 (test-feedback poison), R10 (suspect score)

YOUR JOB: prove the result is shortcut / leakage / seed-cherry-pick / overfit / dataset-reuse / format-hack.

Probe specifically:
1. R3: are the 3 seeds genuinely independent, or did the second/third seed inherit state? Check decision_trace for seed values.
2. R4: did any test-set signal leak into the training loop? Inspect the diff for `test_loader`, `eval_*`, score-thresholding code.
3. R10: list 5 shortcut hypotheses with empirical signatures. For each, state whether the available evidence (run.log + results.tsv + diff) supports it.

Output STRICT YAML:
break_attempts:
  - hypothesis: <e.g. "test set leaked via dataset shuffling without proper split">
    evidence: <quote from diff or run.log line N or decision_trace row>
    likelihood: high | medium | low
  - ...
verdict: BREAK_FOUND | NO_BREAK_FOUND
break_summary: <if BREAK_FOUND, one paragraph with the strongest evidence>

DO NOT propose methods. DO NOT smooth over weaknesses; your job is to find them.
```

Write to `$SPRINT_DIR/reviews/cycle-$CYCLE-pass3-redteam.yaml`.

### Step 5 — Verdict aggregation per constitution verdict_policy

```bash
P1_VERDICT=$(grep '^verdict:' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass1-codex.yaml" | awk '{print $2}')
P2_VERDICT=$(grep '^verdict:' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-gemini.yaml" | awk '{print $2}')
P3_VERDICT=$(grep '^verdict:' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass3-redteam.yaml" | awk '{print $2}')

# Aggregate per constitution.v0.1.0.yaml:
# BLOCK if any rule in {R1, R4, R5, R6, R7, R10} fails (= status: block from any pass for these rules)
# FLAG if any rule in {R2, R3, R8, R9, R11, R12} fails
# PASS iff all 12 rules clear

# Hard rule: P3 BREAK_FOUND ⇒ BLOCK regardless of P1/P2.
if [ "$P3_VERDICT" = "BREAK_FOUND" ]; then
  FINAL_VERDICT="BLOCK"
elif grep -qE 'R(1|4|5|6|7|10): block' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass"*.yaml; then
  FINAL_VERDICT="BLOCK"
elif grep -qE 'R(2|3|8|9|11|12): flag' "$SPRINT_DIR/reviews/cycle-$CYCLE-pass"*.yaml; then
  FINAL_VERDICT="FLAG"
elif [ "$P1_VERDICT" = "PASS" ] && [ "$P2_VERDICT" = "PASS" ] && [ "$P3_VERDICT" = "NO_BREAK_FOUND" ]; then
  FINAL_VERDICT="PASS"
else
  FINAL_VERDICT="FLAG"  # safe default
fi
```

### Step 6 — Write aggregated review + decision_trace

```bash
cat > "$SPRINT_DIR/reviews/cycle-$CYCLE.md" <<EOF
# Triple-heterogeneous review — Cycle $CYCLE / sha $SHA

## Pass 1 — Codex GPT-5.4 (correctness, R1/R2/R6/R7)
verdict: $P1_VERDICT
$(cat "$SPRINT_DIR/reviews/cycle-$CYCLE-pass1-codex.yaml")

## Pass 2 — Gemini 3.1 Pro Preview (challenger, R5/R9/R10)
verdict: $P2_VERDICT
gemini_hallucination_rate: ${HALLUC}%
$(cat "$SPRINT_DIR/reviews/cycle-$CYCLE-pass2-gemini.yaml")

## Pass 3 — Sonnet 4.6 red-team peer (fresh context, R3/R4/R10)
verdict: $P3_VERDICT
$(cat "$SPRINT_DIR/reviews/cycle-$CYCLE-pass3-redteam.yaml")

## Final verdict: $FINAL_VERDICT
EOF

echo '{"ts":"'$(date -Iseconds)'","cycle":'$CYCLE',"niche":"red-team","event":"review","verdict":"'$FINAL_VERDICT'","commit":"'$SHA'","gemini_hallucination_rate":"'${HALLUC}'%"}' >> "$SPRINT_DIR/decision_trace.jsonl"
```

### Step 7 — On BLOCK: revert kept result

```bash
if [ "$FINAL_VERDICT" = "BLOCK" ]; then
  # Flip results.tsv keep → discard for this row (with audit comment in decision_trace, not in TSV)
  awk -F'\t' -v sha="$SHA" 'BEGIN{OFS="\t"} $1==sha && $4=="keep" {$4="discard"} {print}' "$SPRINT_DIR/results.tsv" > "$SPRINT_DIR/results.tsv.tmp"
  mv "$SPRINT_DIR/results.tsv.tmp" "$SPRINT_DIR/results.tsv"

  git -C "$RGMARE_ROOT" revert --no-edit "$SHA"

  echo '{"ts":"'$(date -Iseconds)'","cycle":'$CYCLE',"event":"red_team_break","commit":"'$SHA'","reverted":true}' >> "$SPRINT_DIR/decision_trace.jsonl"

  echo "[review] BLOCK — kept result $SHA reverted; results.tsv flipped keep → discard"
fi
```

### Step 8 — Update TODO

```bash
cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 6 cycle $CYCLE: /research-review  ($(date -Iseconds))  sha=$SHA  verdict=$FINAL_VERDICT  P1=$P1_VERDICT  P2=$P2_VERDICT  P3=$P3_VERDICT  gemini_hallucination=${HALLUC}%
EOF
```

## Output contract
- `reviews/cycle-N-pass1-codex.yaml`
- `reviews/cycle-N-pass2-gemini.yaml`
- `reviews/cycle-N-pass2-citverify.yaml`
- `reviews/cycle-N-pass3-redteam.yaml`
- `reviews/cycle-N.md` (aggregated, with FINAL_VERDICT)
- `decision_trace.jsonl` row event=review (and event=red_team_break if BLOCK)
- TODO.md appended
- Hands off back to `/research-dispatch` for next cycle (or halt if SOTA / budget / unrecoverable BLOCK)

## Halt conditions
- Pass 1 returns malformed YAML twice → halt
- Gemini hallucination rate >30% → halt; rerun challenger with sharper prompt
- Sonnet red-team Agent crashes → halt; do NOT auto-PASS (silent fall-through to PASS would defeat the entire heterogeneous-review premise)
- Implicit block missing for target cycle → exit 1 (caller's /research-loop did not externalize)
