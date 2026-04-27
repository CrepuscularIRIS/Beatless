---
description: Stage 2 of 6 — Opus 4.7 distills cross-domain lessons one level up + enumerates target-domain hidden axioms. Outputs lessons.md + axioms.md with load-bearing flags. Engine choice = Opus per low-hallucination + meta-cognition.
argument-hint: "[--focus <subset>]"
allowed-tools: Bash, Read, Write, Edit, Agent
---

# /research-axiom

**Pipeline position**: Stage 2 of 6.

**Engine**: Opus 4.7 — invoked via `Agent(subagent_type=general-purpose, model=opus, ...)`.

**Why Opus, not Sonnet**: per `~/.claude/.../memory/feedback_model_routing.md` academic-mode roster:
- Lowest hallucination rate → axiom enumeration must be honest, not aspirational
- Strongest meta-cognition → seeing what the literature DOESN'T say is the core skill here
- Sonnet would smooth over the "uncomfortable" axioms (the ones whose questioning would invalidate metric-driven SOTA work)

This is the only stage where Opus's premium cost is justified — it's load-bearing for everything downstream.

**Cronjob-safe**: yes; reads survey/*, writes axioms/* atomically.

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"

LIT_BYTES=$(wc -c < "$SPRINT_DIR/survey/literature.md" 2>/dev/null || echo 0)
XD_BYTES=$(wc -c < "$SPRINT_DIR/survey/cross-domain.md" 2>/dev/null || echo 0)

[ "$LIT_BYTES" -ge 2000 ] || { echo "ERROR: survey/literature.md missing or <2KB — run /research-survey first"; exit 1; }
[ "$XD_BYTES" -ge 1500 ]  || { echo "ERROR: survey/cross-domain.md missing or <1.5KB — run /research-survey first"; exit 1; }

# Each survey file must have disclosure block
grep -q '^## Disclosure\|^disclosure:' "$SPRINT_DIR/survey/literature.md"   || { echo "ERROR: literature.md missing disclosure block"; exit 1; }
grep -q '^## Disclosure\|^disclosure:' "$SPRINT_DIR/survey/cross-domain.md" || { echo "ERROR: cross-domain.md missing disclosure block"; exit 1; }
```

## Anti-gaming gates

| Gate | Check | If failed |
|---|---|---|
| Evidence pointers | every axiom cites which papers in literature.md accept it | reject step |
| Load-bearing flag | every axiom marked yes/no with one-sentence justification | reject step |
| File artifact | output files ≥ stated min bytes | halt |
| Min count | ≥6 axioms (per case-study calibration) | retry once, then halt |
| TODO chain | append entry after each step | next command refuses to run |

## Externalization gate

Per user-directive 2026-04-27: Opus is the strongest model at this, so it gets the strictest gate. Output disclosure block must include:

- `priors_used:` — assumptions Opus applied
- `alternatives_considered:` — alternative axiom enumerations Opus rejected, with real reason
- `axioms_uncomfortable_to_question:` (axiom-specific addendum) — list ≥2 axioms whose questioning would invalidate metric-driven SOTA work in this domain. The temptation to skip them is real; surface them anyway.
- `not_checked:` — load-bearing inferences NOT verified
- `confidence:` per-axiom + per-lesson
- `skeptical_PI_questions:` top-3

Missing or thin → step rejected, retry once, then halt.

## Permission boundary (per user-directive 2026-04-27)

- File writes ONLY within `${SPRINT_DIR}/axioms/`. Reads from `survey/` allowed; reads/writes elsewhere prohibited.
- Opus 4.7 sub-agent invoked via Agent tool (`subagent_type=general-purpose, model=opus`); inherits this command's permission scope.
- No external network calls in this stage (axiom enumeration is purely from already-collected literature.md). If Opus reaches out to the web, that's a permission violation.

## Multi-round consult policy (per user-directive 2026-04-27)

Codex and Gemini are CHEAP. Being wrong is EXPENSIVE. For axiom enumeration specifically:

- Whenever Opus marks an axiom `load_bearing: yes` but is not 100% sure, IMMEDIATELY invoke `codex-academic novelty` to ask: "is there a peer-reviewed result that would invalidate this axiom?" — verify the literature.
- If Opus is brainstorming a candidate axiom that "feels novel as a question to ask", invoke `gemini-academic challenger-feasibility` mode with the axiom phrased as a candidate target — let Gemini surface 3-5 hidden assumptions about the axiom itself.
- Up to 2 extra rounds per uncertain axiom; second round MUST disagree with first round on at least one point or the verification is just rubber-stamping.
- Cap: total ≤ 6 sub-consults per /research-axiom invocation. Beyond that, surface remaining uncertainty in `disclosure:not_checked:` and defer to user.

## Steps

### Step 1 — Distill cross-domain lessons (Opus 4.7, fresh context)

Spawn one Opus 4.7 sub-agent. The job is **one level up abstraction**, not technical recap.

```
Agent invocation:
  subagent_type: general-purpose
  model: opus
  description: "Distill cross-domain lessons (Opus)"
  prompt: <see below>
```

Sub-agent prompt:

```
You are an Opus 4.7 critic doing one-level-up abstraction.

Read $SPRINT_DIR/survey/cross-domain.md. For EACH surviving candidate paper, do NOT explain how the math works. Instead extract:

1. PHILOSOPHICAL MOVE — the one-sentence operation the paper performs at the level of "what counted as a problem before, what counts now". Examples (do NOT copy verbatim — these are the abstraction level you should hit, not the content):
   - "shift complexity from inference-time to training-time"
   - "replace coordinate regression with proof-artifact generation"
   - "treat noisy supervision as posterior observation, not ground truth"

2. HISTORICAL HABIT BROKEN — which prior assumption ("everyone does X because we always have") this paper overthrew.

3. TRANSFERABILITY VECTOR — what kinds of target-domain axioms its move would attack. Describe the abstract operation type, not domain-specific.

EXTERNALIZATION (per user-directive 2026-04-27, this is HARD; Opus is the model best at this):
You must surface what you almost didn't say. DO NOT volunteer only your most polished moves — also include the alternative interpretations you considered but rejected, and your real reason for rejecting each.

Write to $SPRINT_DIR/axioms/lessons.md. STRICT FORMAT:

# Cross-domain lessons — Sprint $SPRINT_TAG

## Lesson 1 (from arxiv:<id>)
- evidence_pointer: arxiv:<id>  cross-domain.md:<line>
- philosophical_move: <one sentence, abstract>
- historical_habit_broken: <one sentence>
- transferability_vector: <abstract operation type, e.g. "complexity-locus shift", "representation-type swap">

## Lesson 2 ...

## Disclosure
priors_used: |
  ...
alternatives_considered: |
  ...   (include alternative interpretations of each paper that you rejected; state the real reason)
not_checked: |
  ...
confidence: high | medium | low — <reason>
skeptical_PI_questions:
  - q: ...
    a: ...
  - q: ...
    a: ...
  - q: ...
    a: ...
```

**Min byte size 1200. Min lessons: 2 (one per surviving cross-domain candidate).**

### Step 2 — Enumerate target-domain hidden axioms (Opus 4.7, FRESH sub-agent context)

Spawn a SECOND Opus 4.7 sub-agent (fresh context, do NOT re-use the lessons sub-agent — we want independent enumeration).

Sub-agent prompt:

```
You are an Opus 4.7 critic enumerating hidden axioms.

Read $SPRINT_DIR/survey/literature.md (NOT cross-domain.md — cross-domain comes later in /research-propose). The job: list HIDDEN AXIOMS — assumptions that:

(a) every paper in the target domain accepts without argument
(b) are load-bearing (results would change if reversed)
(c) are NOT explicitly defended in the literature

For each axiom, mark:
- id: A1, A2, ...
- axiom: the verbatim assumption (one sentence)
- evidence: which papers in literature.md accept this without defense (cite obsidian:<path>:<line>)
- load_bearing: yes | no
- cosmetic_or_real: cosmetic = breaking it doesn't unlock anything; real = breaking it changes the problem type
- default_metric_dependency: does the standard evaluation metric DEPEND on this axiom? (yes/no)
- comfort_to_question: comfortable | uncomfortable — uncomfortable means questioning it would invalidate metric-driven SOTA work in this domain

EXTERNALIZATION (mandatory per user-directive 2026-04-27):
- Include axioms YOU find uncomfortable to question. List at least 2 axioms with comfort_to_question=uncomfortable. The temptation to skip them is real — surface them anyway. This is what differentiates this stage from a Sonnet-level enumeration.
- For each uncomfortable axiom, in disclosure section, write 1 sentence on why questioning it is uncomfortable.

Write to $SPRINT_DIR/axioms/axioms.md. STRICT FORMAT:

# Hidden axioms — Sprint $SPRINT_TAG

## A1
- axiom: <one sentence>
- evidence: [obsidian:<path>:<line>, obsidian:<path>:<line>]
- load_bearing: yes | no
- cosmetic_or_real: cosmetic | real
- default_metric_dependency: yes | no
- comfort_to_question: comfortable | uncomfortable

## A2 ...

(... ≥6 axioms; minimum 2 with comfort_to_question=uncomfortable ...)

## Disclosure
priors_used: |
  ...
alternatives_considered: |
  - axioms I considered but classified as cosmetic: ...
  - axioms I considered but couldn't find evidence for in this literature.md: ...
axioms_uncomfortable_to_question: |
  - A<i>: <why uncomfortable>
  - A<j>: <why uncomfortable>
not_checked: |
  - did NOT cross-reference against full ICLR/NeurIPS 2025 proceedings
  - did NOT verify load_bearing flags via ablation literature search
confidence: <high|medium|low> per axiom in a short table
skeptical_PI_questions:
  - q: ...
    a: ...
  - q: ...
    a: ...
  - q: ...
    a: ...
```

**Min byte size 2000. Min axioms 6 (per case-study calibration where 6 hidden assumptions emerged). Min uncomfortable: 2.**

If <6 axioms or <2 uncomfortable, retry the sub-agent ONCE with: "your previous attempt only produced N axioms / M uncomfortable; the literature is rich enough to support 6+ — re-read and try again, surface the uncomfortable ones".

### Step 3 — Update TODO + decision_trace

```bash
LESSONS_BYTES=$(wc -c < "$SPRINT_DIR/axioms/lessons.md")
AXIOMS_BYTES=$(wc -c < "$SPRINT_DIR/axioms/axioms.md")
N_AXIOMS=$(grep -c '^## A[0-9]' "$SPRINT_DIR/axioms/axioms.md")
N_UNCOMFORTABLE=$(grep -c 'comfort_to_question: uncomfortable' "$SPRINT_DIR/axioms/axioms.md")

cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 2: /research-axiom  ($(date -Iseconds))  lessons.md=${LESSONS_BYTES}B  axioms.md=${AXIOMS_BYTES}B  axioms=${N_AXIOMS}  uncomfortable=${N_UNCOMFORTABLE}
EOF

echo '{"ts":"'$(date -Iseconds)'","cycle":0,"niche":null,"event":"axiom_complete","lessons_bytes":'$LESSONS_BYTES',"axioms_bytes":'$AXIOMS_BYTES',"n_axioms":'$N_AXIOMS',"n_uncomfortable":'$N_UNCOMFORTABLE'}' >> "$SPRINT_DIR/decision_trace.jsonl"
```

## Output contract
- `axioms/lessons.md` ≥ 1.2KB, ≥2 lessons
- `axioms/axioms.md` ≥ 2KB, ≥6 axioms, ≥2 uncomfortable
- Both with disclosure blocks
- TODO.md appended
- Hands off to: `/research-propose`

## Halt conditions
- <6 axioms after retry → halt; surface "literature snapshot too narrow for axiom-level work — broaden /research-survey topic"
- <2 uncomfortable axioms after retry → halt; the externalization gate is failing
- Disclosure missing/marketing-speak → reject, retry once, halt
