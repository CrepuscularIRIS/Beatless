---
description: Stage 5 of 6 — One autoresearch experiment cycle. Edit → commit → run → grep metric → keep/reset → R3 seed check → R7 failure condition → R2 ablation gate → mandatory surface_implicit. NEVER STOP discipline. Anti-gaming + externalization hardened.
argument-hint: "<idea-description>"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# /research-loop

**Pipeline position**: Stage 5 of 6.
**Engine**: Sonnet 4.6 (autoresearch loop discipline per `~/research/autoresearch/program.md`).

**Why Sonnet here, not Opus**: per memory roster academic mode — Sonnet is the workhorse for orchestration + execution loops; Opus's premium reasoning is wasted on autoresearch's tight 5-min single-GPU iterations.

**Cronjob-safe**: idempotent on resume (decision_trace.jsonl is append-only; results.tsv has commit-SHA primary key; rerun on same SHA is a no-op).

## Constitutional anchor (read FIRST every cycle)

`/home/lingxufeng/research/rgmare-lite/contracts/constitution.v0.1.0.yaml` — 12 rules. Specifically:
- R2 — complexity guilty until ablation proves necessity
- R3 — seed distribution mandatory (≥3 seeds)
- R7 — every improvement registers a failure condition
- R8 — direction changes leave decision-trace
- Principle 3 (surface implicit knowledge) — non-negotiable

Violating any → cycle is `incomplete`, NOT eligible for ledger, NOT eligible for keep.

## Permission boundary (per user-directive 2026-04-27)

Tight scope — the cron driver uses `--dangerously-skip-permissions`, so the harness will NOT enforce. Self-restrict:

- File writes ONLY within `${SPRINT_DIR}/` (`ledgers/<tag>/`) and the single `file_to_mutate` declared in the dispatch proposal. Writes elsewhere = experiment malformed → halt.
- External calls: Codex/Gemini ONLY via `~/.hermes/skills/routing/{codex-academic,gemini-academic}/` wrappers. Never raw `codex exec` without `</dev/null --skip-git-repo-check`.
- Network: HTTPS to arxiv.org / OpenReview / GitHub allowed for citation-verify side-calls; no raw `curl` of unknown URLs.
- Subagent inheritance: peer subagents inherit `permission_mode` from this command — they MUST self-restrict to the same scope.

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
SPRINT_TAG="$(git -C $RGMARE_ROOT branch --show-current | sed 's|^research/||')"
SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"

IDEA="$ARGUMENTS"
test -n "$IDEA" || { echo "ERROR: idea description required as argument"; exit 1; }
test -f "$SPRINT_DIR/sprint.yaml" || { echo "ERROR: not in a sprint — run /research-init"; exit 1; }

# Idea should match a recent dispatch proposal (or pass --standalone)
LATEST_DISPATCH=$(ls -d "$SPRINT_DIR/dispatch/cycle-"* 2>/dev/null | tail -1)
[ -z "$LATEST_DISPATCH" ] && [ "$1" != "--standalone" ] && { echo "ERROR: no dispatch found and --standalone not set"; exit 1; }
```

## Anti-gaming rules (hardened per user-directive 2026-04-27)

| Gate | Check | If failed |
|---|---|---|
| Single-file mutation | edit ONLY the file in dispatch proposal's `file_to_mutate` (or train.py if standalone) | step rejected |
| Commit before run | `git rev-parse HEAD` advances before training starts | step rejected |
| Output redirect | `> run.log 2>&1` (no tee, no console flood) | step rejected |
| Hard timeout | 600s wall-clock; SIGKILL beyond | mark crash, revert |
| Implicit block | every keep AND every discard appends `event=surface_implicit` | reject status, retry once |
| Evidence pointers | every claim cites `commit-sha` or `run.log:line` | reject |
| TSV format | tab-separated; commit\tval_bpb\tmemory_gb\tstatus\tdescription | reject row |

## Externalization gate

Every cycle (keep OR discard OR crash) appends a `surface_implicit` row to `decision_trace.jsonl`. Missing or marketing-speak → cycle is `incomplete`, does NOT consume budget; retry. After 2 retry-fails, halt; the model is gaming externalization.

## Steps

### Step 0 — GPU precondition gate (cron-safe; per user-directive 2026-04-27)

Before mutating any file, check GPU headroom. If GPUs are saturated by another workload, yield gracefully — DO NOT crash, DO NOT block-wait.

```bash
GPU_BUSY=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | awk -F', ' '
  ($1+0) > 80 || (($2+0)/($3+0)) > 0.9 { busy=1 }
  END { print busy ? "busy" : "free" }
')

if [ "$GPU_BUSY" = "busy" ]; then
  echo "[loop] GPUs saturated — yielding (cron will retry next tick)"
  echo '{"ts":"'$(date -Iseconds)'","event":"gpu_yield","reason":"gpu_busy","sha":null}' >> "$SPRINT_DIR/decision_trace.jsonl"
  exit 0   # NOT a crash; cron retries
fi

# nvidia-smi missing = not on a GPU host; assume the experiment is CPU-only and proceed
[ "$GPU_BUSY" = "free" ] || [ -z "$GPU_BUSY" ] || echo "[loop] no nvidia-smi; assuming CPU experiment"
```

### Step 1 — Read niche-designated mutation target

```bash
# If running in chain after /research-dispatch, pull file_to_mutate from the niche YAML matching this idea.
# Else if --standalone, default to train.py.

NICHE_FILE=$(grep -l "$IDEA" "$LATEST_DISPATCH"/*.yaml 2>/dev/null | head -1)
if [ -n "$NICHE_FILE" ]; then
  NICHE=$(basename "$NICHE_FILE" .yaml)
  MUTATE_FILE=$(awk '/^file_to_mutate:/{print $2}' "$NICHE_FILE")
  FAILURE_COND=$(awk '/^failure_condition:/{sub(/^failure_condition: */,""); print}' "$NICHE_FILE")
else
  NICHE="standalone"
  MUTATE_FILE="train.py"
  FAILURE_COND="<unspecified — standalone mode>"
fi
echo "[loop] niche=$NICHE  mutate=$MUTATE_FILE"
```

### Step 2 — Mutate the single allowed file

Apply the experimental change described in `$IDEA`. Mutate ONLY `$MUTATE_FILE`. Do NOT touch `prepare.py` (per autoresearch program.md), eval harness, or any other file. If the change requires touching a second file, the experiment is malformed → halt.

### Step 3 — Commit BEFORE running

```bash
git add "$MUTATE_FILE"
git commit -m "$IDEA"
SHORT_SHA=$(git rev-parse --short HEAD)
echo "[loop] committed: $SHORT_SHA"
```

### Step 4 — Run with hard timeout + redirect

```bash
RUN_LOG="$SPRINT_DIR/runs/$SHORT_SHA.log"
mkdir -p "$SPRINT_DIR/runs"

timeout --kill-after=10 600 uv run train.py > "$RUN_LOG" 2>&1
EXIT_CODE=$?
```

### Step 5 — Read metric

```bash
VAL_BPB=$(grep -E "^val_bpb:" "$RUN_LOG" | awk '{print $2}' | head -1)
PEAK_VRAM_MB=$(grep -E "^peak_vram_mb:" "$RUN_LOG" | awk '{print $2}' | head -1)

if [ -z "$VAL_BPB" ]; then
  # Crash — show last 50 lines of log
  echo "[loop] CRASH — last 50 lines of $RUN_LOG:"
  tail -n 50 "$RUN_LOG"
  STATUS="crash"
  VAL_BPB="0.000000"
  MEMORY_GB="0.0"
else
  MEMORY_GB=$(echo "scale=1; $PEAK_VRAM_MB / 1024" | bc)
  STATUS="pending_decision"
fi
```

If `STATUS=crash`: ONE brief fix attempt (edit, recommit, rerun). If still broken, leave `status=crash`, move on (per autoresearch discipline).

### Step 6 — Append TSV row

Tab-separated (per autoresearch program.md):

```bash
printf "%s\t%s\t%s\t%s\t%s\n" "$SHORT_SHA" "$VAL_BPB" "$MEMORY_GB" "$STATUS" "$IDEA" >> "$SPRINT_DIR/results.tsv"
```

### Step 7 — Decide keep/reset

```bash
PREV_BEST=$(awk -F'\t' 'NR>1 && $4=="keep" {print $2}' "$SPRINT_DIR/results.tsv" | sort -n | head -1)

if [ "$STATUS" = "crash" ]; then
  git reset --hard HEAD~1
  echo "[loop] crash → reverted"
elif [ -z "$PREV_BEST" ] || awk "BEGIN{exit !($VAL_BPB < $PREV_BEST)}"; then
  STATUS="keep"
  echo "[loop] metric improved $PREV_BEST → $VAL_BPB → keep"
else
  STATUS="discard"
  git reset --hard HEAD~1
  echo "[loop] metric did not improve ($VAL_BPB ≥ $PREV_BEST) → reverted"
fi

# Update TSV with final status (in-place edit on the row we just appended)
sed -i "$ s/pending_decision/$STATUS/" "$SPRINT_DIR/results.tsv"
```

### Step 8 — R3 seed check (only if keep)

```bash
if [ "$STATUS" = "keep" ]; then
  SEEDS=( $(date +%s) $(($(date +%s) + 1)) )  # 2 additional seeds
  declare -a SEED_RESULTS=("$VAL_BPB")

  for s in "${SEEDS[@]}"; do
    SEED_LOG="$SPRINT_DIR/runs/$SHORT_SHA.seed$s.log"
    SEED=$s timeout --kill-after=10 600 uv run train.py > "$SEED_LOG" 2>&1
    SEED_BPB=$(grep -E "^val_bpb:" "$SEED_LOG" | awk '{print $2}' | head -1)
    [ -n "$SEED_BPB" ] && SEED_RESULTS+=("$SEED_BPB")
  done

  # Compute mean ± std across 3 seeds (best + 2 new)
  MEAN_STD=$(printf "%s\n" "${SEED_RESULTS[@]}" | awk '{sum+=$1; sq+=$1*$1; n++} END{m=sum/n; s=sqrt(sq/n - m*m); printf "%f %f", m, s}')
  MEAN=$(echo "$MEAN_STD" | awk '{print $1}')
  STD=$(echo "$MEAN_STD" | awk '{print $2}')

  # If best - mean > 2*std, R3 fails: best was a lucky seed
  R3_FAIL=$(awk "BEGIN{exit !(($MEAN - $VAL_BPB) > 2 * $STD)}")
  if [ "$R3_FAIL" = "0" ]; then  # exit code 0 means condition true
    echo "[loop] R3 FAIL: best($VAL_BPB) - mean($MEAN) > 2*std($STD) — flipping keep → discard"
    sed -i "$ s/keep/discard/" "$SPRINT_DIR/results.tsv"
    git revert --no-edit HEAD
    STATUS="discard"
  fi
fi
```

### Step 9 — R7 failure_condition append (if still keep)

```bash
if [ "$STATUS" = "keep" ]; then
  echo '{"ts":"'$(date -Iseconds)'","cycle":<n>,"niche":"'$NICHE'","event":"keep","commit":"'$SHORT_SHA'","metric":{"val_bpb_mean":'$MEAN',"val_bpb_std":'$STD',"n_seeds":3},"failure_condition":"'$FAILURE_COND'"}' >> "$SPRINT_DIR/decision_trace.jsonl"
fi
```

### Step 10 — R2 ablation gate (if keep AND added new component)

If the diff added a new component (heuristic: ≥1 new function or ≥1 new module), run an ablation:

```bash
git stash  # save kept state
# Programmatically remove the new component → recommit → run 1 seed
# If ablated metric ≥ kept metric: R2 fails → flip keep → discard, revert
git stash pop
```

If R2 fails: flip TSV row, `git revert`, log `event=R2_ablation_fail`.

### Step 11 — Surface Implicit Knowledge (Principle 3 — MANDATORY for ALL outcomes)

This is the load-bearing externalization. Append `event=surface_implicit` to `decision_trace.jsonl` with FULL block — even for crashes and discards.

> **Schema note (per user-directive 2026-04-27)**: the `implicit:` block below IS the unified `disclosure:` per the anti-gaming/externalization contract across all /research-* commands. Tooling (grep, yq) should match either `^disclosure:|^implicit:|event":"surface_implicit"` to find externalization output regardless of stage.

```yaml
explicit:
  reasoning_trace: |
    <3-6 lines: what you did this cycle>
  result: |
    <metric delta + commit-sha + status>

implicit:
  silent_priors: |
    <assumptions you made the prompt did NOT ask you to state — e.g. "I assumed batch_size doesn't change this comparison because ...">
  unspoken_alternatives: |
    <approaches considered but skipped, AND the real reason — technical judgment / intuition / prior bias, NOT "token budget">
  failure_dna: |
    <one level deeper than the commit message; surface reason vs likely real cause>
  hidden_dependencies: |
    <env priors this conclusion silently rests on: seed, CUDA version, dataset column ordering, race conditions>
  what_a_skeptical_PI_would_ask: |
    <The top-3 questions you'd LEAST want to answer; first-pass honest answers below each>

evidence_pointers:
  - commit:<sha>
  - run.log:<line-N>
  - results.tsv:<row>
  - decision_trace.jsonl:<line>
```

**HARD GATE**: missing or marketing-speak `implicit` block ⇒ cycle = `incomplete`, NOT eligible for keep regardless of metric. Re-run cycle; this run does NOT consume budget. After 2 retry-fails, halt.

### Step 12 — Hand off to /research-review (only if STATUS=keep AND surviving R3 + R2 + Principle-3 gates)

The cycle is NOT closed until /research-review's triple-heterogeneous audit completes (per Principle 2). Pass the implicit block to all 3 reviewers.

### Step 13 — Update TODO

```bash
cat >> "$SPRINT_DIR/TODO.md" <<EOF
- [x] Stage 5 cycle <CYCLE_N>: /research-loop  ($(date -Iseconds))  niche=$NICHE  sha=$SHORT_SHA  status=$STATUS  val_bpb=$VAL_BPB
EOF
```

## NEVER STOP discipline (autoresearch program.md)

Once invoked (especially when chained in a session), do NOT pause to ask the human "should I continue". Loop until manually interrupted. If stuck on ideas, reread `proposals/proposals.md` + `Idea.md` from automated-w2s-research; combine near-misses; try more radical changes.

## Output contract
- `results.tsv` row appended (with final status)
- `runs/<sha>.log` (training output)
- `decision_trace.jsonl` rows: `event=keep` (if kept) + `event=surface_implicit` (always) + possibly `event=R2_ablation_fail` / `event=R3_seed_fail` / `event=incomplete`
- TODO.md appended

## Halt conditions
- 2 consecutive crashes on same idea → escalate to `/codex:rescue --model gpt-5.3-codex` with findings.md
- Constitution violation detected → halt, emit `event=halt`, surface to user
- Implicit block fails 2x → halt, externalization is being gamed
- Mutation touches >1 file → halt, surface "experiment malformed"
