---
description: Stage 4 of 6 — Pick top reframe from proposals.md, dispatch parallel niche subagents (peer Sonnet 4.6, single-message, no nesting), collect ranked proposals filtered for implicit-block presence. Replaces /research-parallel.
argument-hint: "[--reframe rank-N] [--niches paper-filter,prior-elicitor,...]"
allowed-tools: Bash, Read, Write, Edit, Agent
---

# /research-dispatch

**Pipeline position**: Stage 4 of 6 (per cycle).

**Engines**:
- Sonnet 4.6 — orchestrator (this command's body)
- Sonnet 4.6 × N — parallel peer subagents (Agent tool, `subagent_type=general-purpose`, no model override = Sonnet)

**Architecture rules** (per user-directive 2026-04-27):
- NO AgentTeams; just peer subagents
- ONE message → N parallel Agent tool calls (concurrent, NOT sequential)
- NO nested spawning (a peer cannot spawn another peer)
- Each peer gets ONE niche; cosine-overlap matrix < 0.6 enforced

**Cronjob-safe**: yes; idempotent per cycle (each run creates a new `dispatch/cycle-N/` dir).

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"

PROP_BYTES=$(wc -c < "$SPRINT_DIR/proposals/proposals.md" 2>/dev/null || echo 0)
[ "$PROP_BYTES" -ge 3000 ] || { echo "ERROR: proposals/proposals.md missing or <3KB — run /research-propose first"; exit 1; }

N_TOP=$(grep -cE '^## Rank [0-9]+' "$SPRINT_DIR/proposals/proposals.md")
[ "$N_TOP" -ge 1 ] || { echo "ERROR: proposals.md has no ranked reframes"; exit 1; }
```

## Anti-gaming gates

| Gate | Check | If failed |
|---|---|---|
| Single-message dispatch | all N Agent calls in ONE assistant turn | if dispatched sequentially: command halts, this isn't parallel |
| Implicit block presence | every subagent return contains `implicit:` block | drop that proposal, count as `incomplete_branch` |
| Orthogonality | cosine-overlap matrix between niche core_questions ≤ 0.6 | reassign one niche, log `event=orthogonality_check` |
| Min surviving | ≥3 niches return complete proposals | halt; externalization is failing |
| TODO chain | append entry | next command refuses |

## Externalization gate

Each peer subagent's return MUST contain a structured `implicit:` block (per Pratical.md Principle 3 + case-study calibration). Format mandated below in Step 4. Missing → that proposal is dropped pre-ranking.

> **Schema note (per user-directive 2026-04-27)**: subagent `implicit:` block IS the unified `disclosure:` per anti-gaming/externalization contract. Tooling matches `^disclosure:|^implicit:|event":"surface_implicit"`.

## Permission boundary (per user-directive 2026-04-27)

- File writes ONLY within `${SPRINT_DIR}/dispatch/cycle-N/`. Reads from `proposals/`, `sprint.yaml`, `decision_trace.jsonl` allowed.
- Peer Sonnet 4.6 subagents spawned via Agent tool (`subagent_type=general-purpose`, no model override). They inherit this command's permission scope and MUST self-restrict to per-niche YAML output only.
- NO peer subagent may spawn further subagents (Pratical §4 hard rule).
- NO peer subagent may invoke Codex/Gemini directly — they're proposal generators, not auditors. Audit happens in /research-review.
- Network: peer subagents are read-only on the local filesystem; no network calls during dispatch.

## Multi-round consult policy (per user-directive 2026-04-27)

Dispatch is fast (parallel peer subagents). But if the orchestrator's R11 entropy-collapse check shows ≥2 niches converging, do up to 2 reassignment rounds before continuing — cheaper than running a wasted cycle.

- After Step 7 entropy check: if collapse detected, call `gemini-academic challenger-feasibility` on the converging proposals to identify what makes them duplicate; then re-dispatch ONLY the affected niches with sharpened niche prompts.
- Cap: 2 reassignment rounds; if still converging, surface to user (the niche set may be too narrow for this reframe).

## Steps

### Step 1 — Determine cycle number + create dirs

```bash
CYCLE=$(ls -d "$SPRINT_DIR/dispatch/cycle-"* 2>/dev/null | wc -l)
CYCLE=$((CYCLE + 1))
CYCLE_DIR="$SPRINT_DIR/dispatch/cycle-$CYCLE"
mkdir -p "$CYCLE_DIR"
echo "[dispatch] cycle: $CYCLE"
```

### Step 2 — Pick reframe + niches

```bash
# Default: rank-1 from proposals.md
RANK="${ARG_REFRAME:-1}"
REFRAME_BLOCK=$(awk -v r="^## Rank $RANK:" '$0 ~ r {flag=1} flag {print} flag && /^## Rank/ && $0 !~ r {exit}' "$SPRINT_DIR/proposals/proposals.md")

# Default: from sprint.yaml active_niches; override via --niches
ACTIVE_NICHES="${ARG_NICHES:-$(awk '/^active_niches:/{flag=1; next} /^[a-z_]+:/{flag=0} flag{gsub(/^\s*-\s*/,""); print}' "$SPRINT_DIR/sprint.yaml")}"

# Min 3, max 9
N_NICHES=$(echo "$ACTIVE_NICHES" | wc -l)
[ "$N_NICHES" -lt 3 ] && { echo "ERROR: need ≥3 niches; got $N_NICHES"; exit 1; }
[ "$N_NICHES" -gt 9 ] && ACTIVE_NICHES=$(echo "$ACTIVE_NICHES" | head -9)
```

### Step 3 — Orthogonality precheck (R11)

For each niche, write a one-sentence "core question" (what does this niche specifically test?). Compute cosine-overlap matrix using Sonnet 4.6 inline (LLM-judge style; no separate Agent — this is a quick semantic distance call).

Any pair with cosine > 0.6 → swap one niche for an inactive one from sprint.yaml. Log matrix to `$SPRINT_DIR/decision_trace.jsonl` with `event=orthogonality_check`.

```bash
echo '{"ts":"'$(date -Iseconds)'","cycle":'$CYCLE',"event":"orthogonality_check","matrix":<json>,"reassigned":[<niches>]}' >> "$SPRINT_DIR/decision_trace.jsonl"
```

### Step 4 — SINGLE-MESSAGE PARALLEL DISPATCH

This is the load-bearing step. Emit N `Agent` tool calls in ONE assistant message (concurrent dispatch, NOT sequential). Per memory + Pratical §4: peer-level only, no nesting.

For each niche, the peer prompt is:

```
You are a peer NICHE SUBAGENT. niche_id = <niche>. DO NOT spawn other subagents. DO NOT nest.

Inputs (read these files; do NOT call out for more):
- The chosen reframe (pasted below):
  <REFRAME_BLOCK>

- Your niche spec (paste from constitution.v0.1.0.yaml § niches[<niche>]):
  direction: <fuzzy>
  goal: <sharp>
  forbidden: [...]

- Last 10 rows of $SPRINT_DIR/results.tsv (current ledger state)
- Last 5 entries of $SPRINT_DIR/decision_trace.jsonl filtered niche=<niche>

TASK: propose ONE concrete next experiment that:
1. Operationalizes the reframe within YOUR niche's direction (do not stray to another niche)
2. Obeys the 12-rule constitution — especially R7: register a concrete failure_condition
3. Fits autoresearch loop discipline: 5-min single-GPU budget; mutates ONE file (specify which)
4. Engages at least one of the constitution rules explicitly (cite which)

Output STRICT YAML, no prose:

niche: <niche-id>
proposal_summary: <one sentence>
file_to_mutate: <exact path; e.g. train.py or w2s_research/ideas/<niche>/run.py>
specific_change: <2-3 sentences — what code mutation operationalizes the reframe>
expected_metric_delta: <on the sprint's target_metric>
failure_condition: <regime in which this breaks — concrete, observable; R7>
constitution_rules_engaged: [R<n>, R<n>, ...]

implicit:                                            # MANDATORY — Principle 3
  silent_priors: |
    <assumptions you made the prompt did NOT ask you to state — e.g. "I assumed batch_size doesn't change this comparison because ...">
  unspoken_alternatives: |
    <approaches you considered but didn't try, AND the real reason you skipped — technical judgment / intuition / prior bias, NOT "token budget">
  failure_dna: |
    <a level deeper than the commit message; surface reason vs likely real cause>
  hidden_dependencies: |
    <env priors this conclusion silently rests on: seed, CUDA version, dataset column ordering, race conditions, undocumented upstream behavior>
  what_a_skeptical_PI_would_ask: |
    <The top-3 questions you'd LEAST want to answer; first-pass honest answers below each>

evidence_pointers: [proposals.md:<line>, sprint.yaml:<line>, decision_trace.jsonl:<line>]

HARD CONSTRAINT: missing or marketing-speak `implicit:` block ⇒ your proposal is INCOMPLETE and dropped from ranking. The orchestrator filters before ranking.

DO NOT add prose outside this YAML.
```

Each Agent call writes its return to `$CYCLE_DIR/<niche>.yaml`.

### Step 5 — Collect, filter incomplete, rank

```bash
> "$CYCLE_DIR/proposals.jsonl"
> "$CYCLE_DIR/incomplete.jsonl"

for f in $CYCLE_DIR/*.yaml; do
  niche=$(basename "$f" .yaml)
  has_implicit=$(grep -c '^implicit:' "$f")
  has_silent_priors=$(grep -c '^\s*silent_priors:' "$f")

  if [ "$has_implicit" -ge 1 ] && [ "$has_silent_priors" -ge 1 ]; then
    # Convert YAML → JSONL row, append
    yq -o=json "$f" >> "$CYCLE_DIR/proposals.jsonl"
  else
    echo '{"niche":"'$niche'","reason":"missing or thin implicit block","raw_path":"'$f'"}' >> "$CYCLE_DIR/incomplete.jsonl"
    echo '{"ts":"'$(date -Iseconds)'","cycle":'$CYCLE',"niche":"'$niche'","event":"incomplete_branch","reason":"missing_implicit"}' >> "$SPRINT_DIR/decision_trace.jsonl"
  fi
done

# Need ≥3 surviving
N_SURVIVING=$(wc -l < "$CYCLE_DIR/proposals.jsonl")
[ "$N_SURVIVING" -ge 3 ] || { echo "ERROR: only $N_SURVIVING surviving niches; externalization is failing"; exit 1; }
```

### Step 6 — Rank surviving proposals

Rank by (in order):
1. Constitution-rule alignment count (more engaged rules = higher)
2. Failure-condition specificity (concrete observable beats hand-wave)
3. Niche-distinctness from prior cycles (R11 entropy collapse: penalize repetition)

Sonnet 4.6 inline scoring; output ranked JSONL to `$CYCLE_DIR/ranked.jsonl`.

### Step 7 — R11 entropy-collapse check

If ≥2 niches converge on same direction (cosine > 0.6 between their `proposal_summary` values), mark both for temperature-raise / reassignment in next cycle. Append `decision_trace.jsonl` with `event=entropy_collapse_alert`.

### Step 8 — Append to decision_trace, write surface_implicit pairs

For each surviving proposal:
```bash
echo '{"ts":"...","cycle":'$CYCLE',"niche":"<n>","event":"propose","proposal_summary":"...","constitution_rules_engaged":[...]}' >> $SPRINT_DIR/decision_trace.jsonl
echo '{"ts":"...","cycle":'$CYCLE',"niche":"<n>","event":"surface_implicit","silent_priors":"...","unspoken_alternatives":"...","failure_dna":"...","hidden_dependencies":"...","what_a_skeptical_PI_would_ask":"..."}' >> $SPRINT_DIR/decision_trace.jsonl
```

### Step 9 — Surface ranked list to user; do NOT auto-pick

Per Pratical Principle 2: generator-as-judge is forbidden. Print the ranked list to user; user picks one with `/research-loop "<idea>"`.

```
Cycle <N> dispatch summary:
  Reframe target: Rank <R> ("<axiom_attacked>")
  Niches dispatched: <N_DISPATCHED>
  Complete proposals: <N_SURVIVING>
  Incomplete (missing implicit): <N_INCOMPLETE>
  Entropy alert: <yes|no>

Top-3 ranked:
  1. [<niche>] <proposal_summary>
  2. [<niche>] <proposal_summary>
  3. [<niche>] <proposal_summary>

Next: /research-loop "<chosen idea>"  (autoresearch single-cycle execution)
```

### Step 10 — Update TODO

```bash
cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 4 cycle $CYCLE: /research-dispatch  ($(date -Iseconds))  surviving=${N_SURVIVING}  incomplete=${N_INCOMPLETE}  entropy_alert=<yes|no>
EOF
```

## Output contract
- `dispatch/cycle-N/<niche>.yaml` (one per niche dispatched)
- `dispatch/cycle-N/proposals.jsonl` (surviving)
- `dispatch/cycle-N/incomplete.jsonl` (audit trail of dropped)
- `dispatch/cycle-N/ranked.jsonl` (ordered)
- updates to `decision_trace.jsonl` (orthogonality_check, propose×N, surface_implicit×N, possibly entropy_collapse_alert)
- TODO.md appended
- Hands off to: `/research-loop "<chosen idea>"`

## Halt conditions
- <3 niches with complete implicit block → halt; the implicit-block prompt isn't strong enough or models are gaming it
- Orthogonality cannot be achieved (>3 reassignments) → halt; sprint topic too narrow for 9 niches
- Any peer subagent times out or returns malformed YAML twice → halt that niche, log; if >2 niches halt, halt whole cycle
