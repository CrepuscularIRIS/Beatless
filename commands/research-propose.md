---
description: "Research proposal generation + heterogeneous audit — use when user says 'generate research proposal', 'reframe the problem', 'check novelty', 'verify if this is published', 'feasibility audit', 'design 3-step MVE', '出研究方案', '查novelty', '查重'. Stage 3 of 6: Opus reframes (axiom × lesson cross-product), Codex novelty audit, Gemini challenger feasibility, citation verify, Opus convergence to top-3 with 3-step MVE."
argument-hint: "[--top-k 3]"
allowed-tools: Bash, Read, Write, Edit, Agent
---

# /research-propose

**Pipeline position**: Stage 3 of 6 — the meatiest stage; this is where A-tier reframings emerge or fail.

**Engines** (heterogeneous chain enforced):
- **Opus 4.7** — generates cross-product reframings (axiom × lesson) AND final convergence on top-K
- **Codex GPT-5.4** — academic novelty audit per candidate (citation-anchored, conservative; per memory: Codex almost never errs on facts)
- **Gemini 3.1 Pro Preview** — challenger feasibility audit (challenger-framed; per memory: highest academic capability BUT highest hallucination + sycophantic; control via challenger framing + Codex citation-verify pairing + Opus final review)

**Why this exact split**: per `~/.claude/.../memory/feedback_model_routing.md` academic-mode roster — different model families catch different failure modes. Opus generates and converges (lowest hallucination, strongest meta-cognition). Codex verifies citations (conservative, fact-anchored). Gemini probes assumptions (divergent, finds what others miss — but its citations need Codex). Sonnet does NOT appear here on purpose: this is the highest-stakes stage; Sonnet's smoothing-over tendency would dilute it.

**Cronjob-safe**: yes; reads axioms/*, writes proposals/* atomically.

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"

LESSONS_BYTES=$(wc -c < "$SPRINT_DIR/axioms/lessons.md" 2>/dev/null || echo 0)
AXIOMS_BYTES=$(wc -c  < "$SPRINT_DIR/axioms/axioms.md"  2>/dev/null || echo 0)

[ "$LESSONS_BYTES" -ge 1200 ] || { echo "ERROR: axioms/lessons.md missing or <1.2KB — run /research-axiom first"; exit 1; }
[ "$AXIOMS_BYTES"  -ge 2000 ] || { echo "ERROR: axioms/axioms.md missing or <2KB"; exit 1; }

N_AXIOMS=$(grep -c '^## A[0-9]' "$SPRINT_DIR/axioms/axioms.md")
[ "$N_AXIOMS" -ge 6 ] || { echo "ERROR: axioms.md has only $N_AXIOMS axioms; need ≥6"; exit 1; }

mkdir -p "$SPRINT_DIR/proposals"
```

## Anti-gaming gates

| Gate | Check | If failed |
|---|---|---|
| Citation pointers | every reframe cites axioms.md:<line> + lessons.md:<line> | reject reframe |
| Codex citation-verify | every Gemini-cited arxiv-id passes Codex verify | drop hallucinated reframe |
| File artifact | each output file ≥ stated min bytes | halt |
| MVE concrete | each top-K reframe has 3 concrete steps with go/no-go failure conditions | reject reframe |
| Top-K verb-able | each top-K reframe states mechanism in ≤2 sentences with verb-pointing-to-mechanism | reject reframe |
| TODO chain | append after each step | next command refuses |

## Externalization gate

Final `proposals.md` MUST include disclosure block with:
- `top_almost_picked: <ranked reframe N+1 that you almost ranked top — and why you didn't>`
- `most_credible_gemini_objection: <which Gemini infeasibility path was most credible — how does top-1 dodge it>`
- `5min_falsifier: <single-GPU 5-minute experiment that would falsify top-1>`
- standard `priors_used / alternatives_considered / not_checked / confidence / skeptical_PI_questions`

## Permission boundary (per user-directive 2026-04-27)

- File writes ONLY within `${SPRINT_DIR}/proposals/`. Reads from `survey/`, `axioms/` allowed.
- Opus 4.7 + Codex GPT-5.4 + Gemini 3.1 Pro invoked via the `~/.hermes/skills/routing/{codex-academic,gemini-academic}/` wrappers — never raw API.
- Network: HTTPS to arxiv.org / OpenReview only, for citation verify. The Codex/Gemini wrappers gate this.
- Sub-agent permission inheritance: Opus + Codex + Gemini sub-calls inherit this command's scope and MUST self-restrict.

## Multi-round consult policy (per user-directive 2026-04-27)

The current spec calls Codex novelty + Gemini challenger ONCE per reframe. User directive: do MORE rounds when uncertainty exists. Concrete triggers:

- Codex returns `status: cannot-verify` → reword the query (full claim text vs short summary; arxiv-id-only vs full title); up to 2 retry rounds; if still unsure, mark in `disclosure:not_checked:`.
- Codex returns `status: no-match` BUT the reframe sounds "too clean to be unpublished" → MANDATORY second pass with a renaming attempt: "search for [reframe restated using domain-X jargon]". Catches published-but-renamed work.
- Gemini's `hidden_assumptions` returns <3 items → reframe the prompt sharper ("be more adversarial; assume top-conference reviewer skepticism"); second round MUST surface ≥1 NEW assumption distinct from first round.
- During Step 6 Opus convergence: if Opus is uncertain between rank-1 and rank-2 of the candidates, invoke a SECOND Codex novelty pass on rank-2 specifically (cheap insurance). Same for Gemini challenger if rank-2 has strong infeasibility paths.
- Cap: total ≤ 12 sub-consults per /research-propose invocation. Beyond that, surface uncertainty in `disclosure:not_checked:` and continue with best-effort top-K.

## Steps

### Step 1 — Cross-product reframing (Opus 4.7, fresh sub-agent)

Spawn Opus 4.7 with full lessons.md + axioms.md. Generate ALL pairwise (axiom × lesson) reframes.

Agent invocation:
```
subagent_type: general-purpose
model: opus
description: "Cross-product reframing (Opus 4.7)"
prompt: <below>
```

Sub-agent prompt:

```
You are an Opus 4.7 generator. Inputs: $SPRINT_DIR/axioms/axioms.md ($N_AXIOMS axioms) + $SPRINT_DIR/axioms/lessons.md ($N_LESSONS lessons). Generate one REFRAME per (axiom, lesson) pair — total $(N_AXIOMS × N_LESSONS) candidates.

Each reframe is one paragraph stating:
"If we accept lesson L's philosophical move, then axiom A becomes obsolete because <reason>; we should instead model the problem as <new framing>".

Hard constraints per reframe:
1. testable_prediction: something the new framing claims that the old framing predicts differently — must be measurable in a 5-min single-GPU experiment.
2. measurable_contribution: a new metric, mechanism, or operationalization NOT achievable by parameter-tweaking the old framing.
3. evidence_pointers: cite axioms.md:<line> + lessons.md:<line>.

Write to $SPRINT_DIR/proposals/raw_reframes.md. STRICT FORMAT:

# Cross-product reframes — Sprint $SPRINT_TAG

## Reframe (A1 × L1)
- axiom_attacked: <verbatim from axioms.md A1>
- lesson_applied: <philosophical move from lessons.md L1>
- new_framing: <one paragraph>
- testable_prediction: <if we measure X under new framing, expect Y; under old framing, expect Z>
- measurable_contribution: <new metric or new mechanism>
- evidence_pointers: [axioms.md:<line>, lessons.md:<line>]

## Reframe (A1 × L2)
...

(... A_count × L_count entries ...)

EXTERNALIZATION:
disclosure:
  hardest_pairs: <which (A, L) pairs you tried hard to make work but couldn't — list and why>
  unmatched_axioms: <axioms with no fitting lesson — list>
  unmatched_lessons: <lessons with no fitting axiom — list>
  ...
```

**Min reframes: ≥12 (≥ A_count × L_count where A_count ≥ 6 and L_count ≥ 2 → 12 minimum).**

### Step 2 — Codex novelty audit per reframe (parallel where possible)

For EACH reframe in raw_reframes.md, invoke Codex in **academic novelty mode** (per memory rule: this is the academic Codex wrapper, distinct from the github wrapper):

```bash
> "$SPRINT_DIR/proposals/codex_novelty.yaml"

# Iterate reframes — pseudocode; the actual command parses raw_reframes.md and loops:
for each reframe block in raw_reframes.md:
  REFRAME_NEW="<new_framing>"
  REFRAME_PRED="<testable_prediction>"
  REFRAME_CONTRIB="<measurable_contribution>"

  codex exec --model gpt-5.4 --skip-git-repo-check </dev/null "$(cat <<EOF
Academic novelty audit (conservative, citation-anchored, no speculation):

Reframe new framing: $REFRAME_NEW
Testable prediction: $REFRAME_PRED
Measurable contribution: $REFRAME_CONTRIB

Q1 — Has any peer-reviewed paper already published this exact reframe? Answer: published | near-match | no-match.
Q2 — If near-match: list arxiv-id + 1-line distinguishing axis between published work and this reframe.
Q3 — If no-match: list 3 most-related published works with arxiv-id + the axis on which they differ.

Output STRICT YAML, one block per reframe (use the reframe ID like A1xL1):
- reframe_id: A1xL1
  status: published | near-match | no-match
  existing_work:
    - arxiv: <id>
      claim: ...
      distinguishing_axis: ...
  near_matches:
    - arxiv: ...
      distinguishing_axis: ...

DO NOT speculate beyond cited papers. If unsure on citation existence, write status: cannot-verify.
EOF
  )" >> "$SPRINT_DIR/proposals/codex_novelty.yaml"
```

### Step 3 — Filter Codex-published, keep no-match + near-match

Drop reframes with `status: published` (already done). Keep `no-match` + `near-match` for next stage.

### Step 4 — Gemini 3.1 Pro challenger feasibility audit (per surviving reframe)

Per memory rule (Gemini 3.1 Pro: highest academic ability BUT highest hallucination + sycophantic; control via CHALLENGER framing):

```bash
> "$SPRINT_DIR/proposals/gemini_challenge.yaml"

for each surviving reframe:
  gemini --yolo -m gemini-3.1-pro-preview --approval-mode plan -p "$(cat <<EOF
You are an academic adversary. CHALLENGE this reframe — DO NOT support it.

Reframe new framing: $REFRAME_NEW
Testable prediction: $REFRAME_PRED
Measurable contribution: $REFRAME_CONTRIB

Output STRICT YAML, no prose outside this:

reframe_id: <e.g. A1xL1>
hidden_assumptions:
  # 3-5 load-bearing assumptions inside the reframe itself that would invalidate it if wrong
  - <assumption>
  - ...
infeasibility_paths:
  # 3 concrete ways this reframe fails in practice — engineering, theoretical, or empirical
  - <path>
  - ...
ablation_traps:
  # which ablations would distinguish this reframe's mechanism from naive baselines
  - <ablation>
  - ...
required_citations:
  # arxiv-ids that, if they support a CONTRADICTORY claim, would falsify this reframe
  # Every required_citation must be a real arxiv-id. Codex will verify.
  - arxiv: <id>
    contradiction: <one-line>
  - arxiv: ...
    contradiction: ...

Hard rules:
- DO NOT agree-to-please. Your job is to find what is wrong / risky / missing.
- DO NOT generalize ("the literature shows" ← rejected). Cite arxiv-ids only.
- If you cannot find ≥3 hidden_assumptions, you have not tried hard enough — try again.
EOF
  )" </dev/null >> "$SPRINT_DIR/proposals/gemini_challenge.yaml"
```

### Step 5 — Codex citation-verify on Gemini's emitted arxiv-ids

Per memory routing rule: Gemini's citations MUST be Codex-verified to catch fabrication. Extract every arxiv-id from `gemini_challenge.yaml.required_citations[].arxiv` and verify:

```bash
for ARXIV_ID in $(awk '/^\s*-\s*arxiv:/ {print $3}' "$SPRINT_DIR/proposals/gemini_challenge.yaml" | sort -u); do
  codex exec --model gpt-5.4 --skip-git-repo-check </dev/null "$(cat <<EOF
Citation verify (academic mode, conservative):

arxiv:$ARXIV_ID

Q1 — Does this arxiv-id resolve to a real paper? (yes / no)
Q2 — If yes: what is the actual title and 1-line claim?

Output STRICT YAML:
arxiv: $ARXIV_ID
match: yes | no | cannot-verify
title: <if match>
claim: <if match>

DO NOT speculate.
EOF
  )" >> "$SPRINT_DIR/proposals/codex_citverify.yaml"
done
```

Compute hallucination rate. If >30% of Gemini-emitted arxiv-ids fail Codex verify → halt; Gemini is hallucinating, surface to user, do NOT proceed.

For surviving reframes whose Gemini-cited contradictory papers turn out to be hallucinated (i.e. the contradiction was based on a fake citation): the contradiction is invalid → restore that reframe's standing.

### Step 6 — Opus 4.7 convergence to top-K (default K=3)

Spawn a third Opus 4.7 sub-agent (fresh context). Inputs: raw_reframes.md + codex_novelty.yaml + gemini_challenge.yaml + codex_citverify.yaml.

Sub-agent prompt:

```
You are an Opus 4.7 reviewer-of-reviewers. Inputs:
- $SPRINT_DIR/proposals/raw_reframes.md (all candidates)
- $SPRINT_DIR/proposals/codex_novelty.yaml (Codex novelty status per reframe)
- $SPRINT_DIR/proposals/gemini_challenge.yaml (Gemini challenger output)
- $SPRINT_DIR/proposals/codex_citverify.yaml (Gemini's cited arxiv-ids — verified yes/no/cannot-verify)

For each surviving reframe (status ∈ {no-match, near-match} per Codex), score on 4 axes 1-5:
- novelty (Codex result; no-match=5, near-match=3, published=0/dropped)
- feasibility (5 minus the count of credible Gemini infeasibility_paths AFTER citation-verify drops fabricated ones)
- mechanism strength (does testable_prediction depend on a non-trivial mechanism, vs parameter tweaking?)
- compression (R9 from constitution: can it be stated in ≤2 sentences with a verb pointing to a measurable mechanism?)

Pick top K=3 (override via --top-k arg). For each, write to $SPRINT_DIR/proposals/proposals.md:

# Top-K reframes — Sprint $SPRINT_TAG

## Rank 1: <axiom_attacked> via <lesson_applied>

- new_framing: <≤2 sentences, verb-pointing-to-mechanism>
- mechanism: <one paragraph — what is the actual mechanism, not the philosophy>
- 3-step MVE:
  - Step 1 (go/no-go): <action> | failure_condition: <observable that says STOP>
  - Step 2 (go/no-go): <action> | failure_condition: ...
  - Step 3 (go/no-go): <action> | failure_condition: ...
- expected_metric_delta: <on $TARGET_METRIC; quantitative>
- baseline_to_beat: <which existing baseline + arxiv-id>
- evidence_pointers: [axioms.md:<line>, lessons.md:<line>, codex_novelty.yaml:<line>]

## Rank 2: ...

## Rank 3: ...

## 3 axiom-rewrites (sprint-level commitments)
1. <one declarative sentence per rewrite — "<we no longer accept axiom X; instead we accept axiom X'>" form>
2. ...
3. ...

EXTERNALIZATION (mandatory per user-directive 2026-04-27):
disclosure:
  top_almost_picked: |
    Rank-N+1 was: <which reframe>; I almost ranked it top because <reason>; I didn't because <real reason>.
  most_credible_gemini_objection: |
    Gemini's most credible infeasibility path was: <quote>. The top-1 dodges it by <how> OR accepts the risk because <why>.
  5min_falsifier: |
    A single-GPU 5-minute experiment that would falsify top-1 is: <concrete spec>. If we observe <X>, top-1 is dead.
  priors_used: ...
  alternatives_considered: ...
  not_checked: ...
  confidence: per top-K reframe in a small table
  skeptical_PI_questions:
    - q: ...
      a: ...
    - q: ...
      a: ...
    - q: ...
      a: ...
```

**Min byte size 3000. Min ranked reframes: 3.** If <3 survive, halt; the methodology found no A-tier reframe this round.

### Step 7 — Update TODO + decision_trace

```bash
PROP_BYTES=$(wc -c < "$SPRINT_DIR/proposals/proposals.md")
N_TOP=$(grep -cE '^## Rank [0-9]+' "$SPRINT_DIR/proposals/proposals.md")
N_DROPPED_PUB=$(grep -c 'status: published' "$SPRINT_DIR/proposals/codex_novelty.yaml")
GEMINI_HALLUC=$(awk '/^arxiv:/{ids++} /match: no/{bad++} END{if(ids>0) printf "%.0f%%", 100*bad/ids; else print "n/a"}' "$SPRINT_DIR/proposals/codex_citverify.yaml")

cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 3: /research-propose  ($(date -Iseconds))  proposals.md=${PROP_BYTES}B  top_K=${N_TOP}  dropped_published=${N_DROPPED_PUB}  gemini_hallucination_rate=${GEMINI_HALLUC}
EOF

echo '{"ts":"'$(date -Iseconds)'","cycle":0,"niche":null,"event":"propose_complete","proposals_bytes":'$PROP_BYTES',"top_k":'$N_TOP',"dropped_published":'$N_DROPPED_PUB',"gemini_hallucination_rate":"'$GEMINI_HALLUC'"}' >> "$SPRINT_DIR/decision_trace.jsonl"
```

## Output contract
- `proposals/raw_reframes.md` (≥12 candidates)
- `proposals/codex_novelty.yaml` (per-reframe novelty)
- `proposals/gemini_challenge.yaml` (per-reframe challenger output)
- `proposals/codex_citverify.yaml` (Gemini's arxiv-ids verified)
- `proposals/proposals.md` (≥3KB, top-K with 3-step MVE, 3 axiom-rewrites, full disclosure)
- TODO.md appended
- Hands off to: `/research-dispatch`

## Halt conditions
- Codex novelty pass: >50% candidates come back as `published` → topic is too generic, halt + ask user to refine survey
- Gemini citation-verify: >30% Gemini arxiv-ids fail Codex verify → Gemini hallucinating, halt + retry with sharper challenger prompt; if still failing, escalate
- Opus convergence: <3 candidates passing all 4 axes → halt, surface "no A-tier reframe this round"
- Disclosure missing or marketing-speak → reject, retry once, halt
- 5min_falsifier missing → reject (per case-study evidence: this is the load-bearing externalization)
