---
description: "Literature survey + cross-domain mining — use when user says 'do a literature survey', 'find papers on X', 'check what's been done in field Y', 'mine cross-domain breakthroughs', 'search Obsidian for related work', '调研', '查文献', '看一下这个领域'. Stage 1 of 6: Obsidian SOTA mining + Gemini Flash cross-domain breakthrough sourcing + Codex novelty pre-screen. Outputs literature.md + cross-domain.md."
argument-hint: "[<topic-override>]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# /research-survey

**Pipeline position**: Stage 1 of 6.

**Engines** (per `~/.claude/.../memory/feedback_model_routing.md` academic-mode roster):
- Sonnet 4.6 — orchestrator + Obsidian search (file reads, paper synthesis)
- Gemini 3-flash-preview — cross-domain breakthrough mining (bulk academic search; non-adjacent fields)
- Codex GPT-5.4 — novelty pre-screen on each cross-domain candidate (academic mode, NOT github wrapper)

**Why this split**: Sonnet reads cheap; Gemini Flash has the broadest academic database for cross-domain search; Codex is the only one conservative enough to cite-anchor without speculation. Per memory rule, Gemini citations MUST be Codex-verified to catch fabrication.

**Cronjob-safe**: yes — reads sprint.yaml, writes survey/*.md atomically, idempotent (reruns overwrite same paths).

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"
OBSIDIAN="${OBSIDIAN_VAULT:-$HOME/obsidian-vault}"

test -f "$SPRINT_DIR/sprint.yaml" || { echo "ERROR: missing sprint.yaml — run /research-init first"; exit 1; }
test -f "$SPRINT_DIR/TODO.md"     || { echo "ERROR: missing TODO.md"; exit 1; }
test -d "$OBSIDIAN/papers" -o -d "$OBSIDIAN/methodology" || { echo "ERROR: $OBSIDIAN missing papers/ or methodology/"; exit 1; }

which gemini codex >/dev/null || { echo "ERROR: gemini or codex CLI not in PATH"; exit 1; }
```

## Anti-gaming gates (constitution layer per user-directive 2026-04-27)

| Gate | Check | If failed |
|---|---|---|
| Evidence pointers | every paper claim cites `arxiv:<id>` or `obsidian:<path>:<line>` or `doi:<doi>` | step rejected |
| File artifact | step writes a file ≥ stated min byte size | step not executed → halt |
| Citation verify | every Gemini-emitted arxiv-id passes Codex citation-verify | drop hallucinated entries |
| TODO chain | append entry to `$SPRINT_DIR/TODO.md` after each step | next command refuses to run |

## Externalization gate (per user-directive 2026-04-27)

Each output file ENDS with `disclosure:` block (mandatory; missing = step rejected, retry once, then halt):

```yaml
disclosure:
  priors_used: <assumptions you applied without being asked>
  alternatives_considered: <approaches considered and skipped, with the real reason — technical judgment, not "token budget">
  not_checked: <load-bearing inferences NOT verified this turn>
  confidence: high | medium | low — <one-sentence reason>
  skeptical_PI_questions:
    - q: <hardest question>
      a: <first-pass honest answer>
    - q: ...
      a: ...
    - q: ...
      a: ...
```

## Steps

### Step 1 — Resolve topic + budget

```bash
TOPIC="$ARGUMENTS"
[ -z "$TOPIC" ] && TOPIC="$(awk '/^goal:/{flag=1; next} /^[a-z]/{flag=0} flag' $SPRINT_DIR/sprint.yaml | head -3 | tr '\n' ' ')"
TARGET_METRIC="$(grep '^target_metric:' $SPRINT_DIR/sprint.yaml | sed 's/^target_metric: *//')"
echo "[survey] topic: $TOPIC"
echo "[survey] target metric: $TARGET_METRIC"
```

### Step 2 — Obsidian target-domain SOTA snapshot (Sonnet 4.6, native)

Search `$OBSIDIAN/{papers,methodology,experiments}/` with Grep for terms in `$TOPIC`. Read the top 8-15 most relevant notes. For each paper:

- Title (verbatim from frontmatter `title:` or first H1)
- arxiv-id (from frontmatter `arxiv:` or first `https://arxiv.org/abs/...` link)
- 1-2 line claim summary
- Distinguishing axis — what makes THIS paper different from prior work in this exact corner
- **Default-axiom-accepted** — what hidden assumption does this paper accept without defending?

Write `$SPRINT_DIR/survey/literature.md`. **Min byte size 2000. Min entries 5.**

If <5 papers found in Obsidian, add a `not_checked: Obsidian coverage thin (<5 papers); user may need to import more before /research-axiom` entry to disclosure — do NOT halt (small Obsidian is normal early in a project), but flag it loudly.

Format:

```markdown
# Target-domain SOTA snapshot — Sprint <tag>

*Generated <ISO> from $OBSIDIAN/{papers,methodology,experiments}*

## Consolidated default axioms (across surveyed papers)

> What does EVERYONE in this corner accept without arguing for?

1. <axiom> — accepted by [paper-1, paper-3, paper-5]
2. <axiom> — accepted by [paper-2, paper-4]
3. ...

## Per-paper entries

### <Paper Title>
- evidence_pointer: arxiv:<id>  obsidian:<vault-relative-path>:<line>
- claim: <1-2 lines>
- distinguishing_axis: <what THIS paper is doing that prior work isn't>
- default_axiom_accepted: <which assumption this paper takes for granted>

(... 5+ entries ...)

## Disclosure
priors_used: |
  ...
alternatives_considered: |
  ...
not_checked: |
  ...
confidence: <high|medium|low> — <reason>
skeptical_PI_questions:
  - q: ...
    a: ...
  - q: ...
    a: ...
  - q: ...
    a: ...
```

### Step 3 — Cross-domain breakthrough mining (Gemini Flash CLI)

This is the KEY new step (per user-directive 2026-04-27 + case-study evidence): we want 3 breakthroughs from **non-adjacent** fields whose CORE METHODOLOGICAL MOVE could plausibly transfer.

Invoke Gemini Flash with **challenger framing** (per memory routing rule: never agreement-seeking):

```bash
GEMINI_OUT="/tmp/gemini-cross-domain-$SPRINT_TAG-$(date +%s).txt"

gemini --yolo -m gemini-3-flash-preview -p "$(cat <<EOF
You are an academic adversary, not a recommender. Find 3 breakthrough papers from fields ADJACENT BUT DIFFERENT from "$TOPIC" whose CORE METHODOLOGICAL MOVE might plausibly transfer.

Hard constraints:
1. DO NOT recommend papers already in the field of "$TOPIC".
2. Each paper MUST have a verifiable arxiv-id (Codex will verify; hallucinated IDs will be dropped).
3. For each paper, distill its CORE MOVE in ONE SENTENCE — the philosophical operation it performs, NOT the math. Examples (do not copy):
   - "shift complexity from inference-time to training-time"
   - "replace coordinate regression with proof-artifact generation"
   - "treat noisy supervision as posterior observation, not ground truth"
4. Mark which default axiom of "$TOPIC" this move would attack.

Output STRICT YAML, no prose outside this:

candidates:
  - arxiv: <id>
    title: <verbatim>
    field: <not $TOPIC>
    core_move: <one sentence, philosophical not technical>
    axiom_attacked: <which default axiom of $TOPIC>
  - arxiv: ...
    ...
  - arxiv: ...
    ...

DO NOT output anything else.
EOF
)" </dev/null > "$GEMINI_OUT" 2>&1

# Validate: at least 3 candidates with arxiv ids that match arxiv pattern
N_CANDS=$(grep -cE '^\s*-\s*arxiv:' "$GEMINI_OUT")
[ "$N_CANDS" -lt 3 ] && { echo "WARN: Gemini returned $N_CANDS candidates; retrying with sharper prompt"; }
```

If <3 candidates, retry once with a sharper prompt (add: "if you cannot find 3, expand to fields like physics, biology, economics, signal processing — DO NOT stay in CS"). Halt if still <3.

### Step 4 — Codex novelty pre-screen per candidate

Per memory rule: Gemini's output is NOT trusted until Codex verifies. For each candidate:

```bash
for ARXIV_ID in $(awk '/arxiv:/ {print $2}' "$GEMINI_OUT"); do
  CORE_MOVE=$(awk -v id="$ARXIV_ID" '$0 ~ "arxiv: "id {found=1} found && /core_move:/ {sub(/^.*core_move: */,""); print; exit}' "$GEMINI_OUT")
  AXIOM=$(awk -v id="$ARXIV_ID" '$0 ~ "arxiv: "id {found=1} found && /axiom_attacked:/ {sub(/^.*axiom_attacked: */,""); print; exit}' "$GEMINI_OUT")

  codex exec --model gpt-5.4 --skip-git-repo-check </dev/null "$(cat <<EOF
Academic novelty audit (conservative, citation-anchored, no speculation):

Paper: arxiv:$ARXIV_ID
Proposed transfer: apply CORE_MOVE \"$CORE_MOVE\" to target domain \"$TOPIC\", attacking axiom \"$AXIOM\".

Q1 — Citation match: does arxiv:$ARXIV_ID resolve to a real paper? (yes / no / cannot-verify) — verify by checking the arxiv abstract page or your training-data knowledge of arxiv IDs.

Q2 — Transfer novelty: is there ANY existing peer-reviewed work that already executes this exact transfer (this CORE_MOVE applied to $TOPIC)? If yes, list arxiv-id + 1-line claim. If no, state 'no exact match'. If 3 closest near-matches, list them with their distinguishing axes.

Output STRICT YAML, no prose:
arxiv: $ARXIV_ID
citation_match: yes | no | cannot-verify
transfer_status: published | near-matches | no-match
existing_work:
  - arxiv: ...
    claim: ...
near_matches:
  - arxiv: ...
    distinguishing_axis: ...

If unsure on citation_match, say cannot-verify — DO NOT speculate.
EOF
)" >> "$SPRINT_DIR/survey/codex_novelty.yaml"
done
```

### Step 5 — Aggregate to cross-domain.md (Sonnet 4.6)

Combine `$GEMINI_OUT` + `$SPRINT_DIR/survey/codex_novelty.yaml`. Drop:
- `citation_match: no` (Gemini hallucinated the arxiv id)
- `transfer_status: published` (this transfer is already done)

Keep `transfer_status: near-matches` BUT explicitly write the distinguishing axis vs the near-match.

Write `$SPRINT_DIR/survey/cross-domain.md`. **Min byte size 1500. Min surviving candidates 2.**

If <2 surviving candidates → halt; surface to user that the topic needs widening or seed candidates manually.

Format:

```markdown
# Cross-domain breakthrough candidates — Sprint <tag>

## Surviving candidates (post Codex novelty pre-screen)

### Candidate 1
- evidence_pointer: arxiv:<id>
- title: <verbatim>
- field: <non-$TOPIC>
- core_move: <one sentence, philosophical>
- axiom_attacked (in $TOPIC): <axiom>
- novelty: no-match | near-match (distinguishing-axis: <X>)
- transferability_flag: ours-to-do | risky-because-<Y>

### Candidate 2
...

## Dropped candidates (audit trail — keep for /research-axiom to see)

### Dropped: arxiv:<id> "<title>"
reason: citation_match=no  (Gemini fabricated this ID)

OR

### Dropped: arxiv:<id> "<title>"
reason: transfer_status=published — already done at arxiv:<other-id>: "<their claim>"

## Disclosure
priors_used: ...
alternatives_considered: |
  - searched fields X, Y, Z but found nothing meeting "non-adjacent" bar
  - considered candidate <arxiv-id> but Codex flagged as published — dropped
not_checked: |
  - did NOT HTTP-fetch each arxiv URL; only Codex-verified by ID lookup
  - did NOT cross-check against ICLR/NeurIPS 2025-2026 proceedings (Codex's training cutoff may miss latest)
confidence: high | medium | low — <reason>
skeptical_PI_questions:
  - q: ...
    a: ...
  - q: ...
    a: ...
  - q: ...
    a: ...
```

### Step 6 — Update TODO + decision_trace

```bash
LIT_BYTES=$(wc -c < "$SPRINT_DIR/survey/literature.md")
XD_BYTES=$(wc -c < "$SPRINT_DIR/survey/cross-domain.md")
N_SURVIVING=$(grep -c '^### Candidate' "$SPRINT_DIR/survey/cross-domain.md")

cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 1: /research-survey  ($(date -Iseconds))  literature.md=${LIT_BYTES}B  cross-domain.md=${XD_BYTES}B  surviving=${N_SURVIVING}
EOF

echo '{"ts":"'$(date -Iseconds)'","cycle":0,"niche":null,"event":"survey_complete","literature_bytes":'$LIT_BYTES',"crossdomain_bytes":'$XD_BYTES',"crossdomain_surviving":'$N_SURVIVING'}' >> "$SPRINT_DIR/decision_trace.jsonl"
```

## Output contract
- `survey/literature.md` ≥ 2KB, ≥5 papers, has disclosure block
- `survey/cross-domain.md` ≥ 1.5KB, ≥2 surviving candidates, has disclosure block
- `survey/codex_novelty.yaml` (full audit trail incl. dropped candidates)
- TODO.md appended with Stage 1 [x]
- Hands off to: `/research-axiom`

## Halt conditions
- Obsidian vault missing or empty → exit 1
- <5 Obsidian entries: do NOT halt; flag in disclosure
- <2 surviving cross-domain candidates after Codex pre-screen → halt; ask user to widen topic or seed manually
- Gemini emits 0 valid arxiv-ids on retry → halt; CLI is broken
- >50% Codex citation_match=cannot-verify → halt; network or Codex tool in bad state
- Disclosure block missing/marketing-speak → reject step, retry once, then halt
