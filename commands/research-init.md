---
description: Stage 0 of 6 — Initialize a research sprint. Validates tag, creates branch + ledger files + TODO chain + sprint.yaml. Replaces /research-bootstrap. Engine = Sonnet 4.6 mainhand.
argument-hint: "<sprint-tag>"
allowed-tools: Bash, Read, Write, Edit
---

# /research-init

**Pipeline position**: Stage 0 of 6 (init → survey → axiom → propose → dispatch → loop → review).
**Engine**: Sonnet 4.6 (no model invocation — pure orchestration).
**Cronjob-safe**: refuses to overwrite existing branch/ledger; safe to re-attempt with same tag only after rollback.

## Inputs (HARD GATE)

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
TAG="$ARGUMENTS"

# Gate 1: tag format
echo "$TAG" | grep -qE '^[a-z0-9][a-z0-9-]*$' || { echo "ERROR: tag must match ^[a-z0-9][a-z0-9-]*$"; exit 1; }

# Gate 2: rgmare-lite is a git work tree
test -d "$RGMARE_ROOT/.git" || { echo "ERROR: $RGMARE_ROOT is not a git repo. Init it first."; exit 1; }

# Gate 3: branch must NOT exist (no overwrite)
git -C "$RGMARE_ROOT" rev-parse --verify "research/$TAG" 2>/dev/null && { echo "ERROR: branch research/$TAG already exists"; exit 1; }

# Gate 4: paradigm + constitution must exist (we don't write them — user already pinned them)
test -f "$RGMARE_ROOT/plan/research-paradigm.md"        || { echo "ERROR: missing plan/research-paradigm.md"; exit 1; }
test -f "$RGMARE_ROOT/contracts/constitution.v0.1.0.yaml" || { echo "ERROR: missing constitution"; exit 1; }
```

## Steps

### Step 1 — Create branch + ledger structure

```bash
cd "$RGMARE_ROOT"
git checkout -b "research/$TAG"
mkdir -p "ledgers/$TAG"/{survey,axioms,proposals,dispatch,reviews}
printf "commit\tval_bpb\tmemory_gb\tstatus\tdescription\n" > "ledgers/$TAG/results.tsv"
: > "ledgers/$TAG/decision_trace.jsonl"
```

### Step 2 — Interactively gather sprint metadata

Ask user (block on response):
1. **Goal** (1-3 sentences) — what bottleneck does this sprint try to crack?
2. **Target metric** (single scalar) — what gets graded each cycle? e.g. `val_bpb`, `AECS`, `FID`.
3. **Target value** (threshold) — what triggers SOTA halt?
4. **Budget cycles** (default 50) — how many experiment cycles total?

Write to `ledgers/<tag>/sprint.yaml`:

```yaml
tag: <tag>
created_at: <ISO timestamp>
constitution_version: v0.1.0
active_niches:
  - paper-filter
  - prior-elicitor
  - noisy-channel
  - data-reweighter
  - distiller
  - gradient-free-evolver
  - interpretability
  - red-team
  - theory-compressor
goal: |
  <verbatim from user>
target_metric: <user>
target_value: <user>
budget_cycles: <user, default 50>
```

### Step 3 — Write TODO chain (chain-of-thought continuity per user-directive 2026-04-27)

Write `ledgers/<tag>/TODO.md` — this is the durable plan. **Never delete prior entries** in subsequent commands.

```markdown
# Sprint <tag> — TODO chain

> Append-only. Subsequent /research-* commands check this file off; never rewrite.
> Each entry must include: timestamp, command, output-file paths, byte sizes, disclosure-block presence.

## Pipeline progress
- [ ] Stage 1: /research-survey      — Obsidian + cross-domain mining
- [ ] Stage 2: /research-axiom       — first-principles + lesson distillation
- [ ] Stage 3: /research-propose     — cross-product reframing + heterogeneous audit
- [ ] Stage 4: /research-dispatch    — parallel niche dispatch (per cycle)
- [ ] Stage 5: /research-loop        — autoresearch experiment cycle (per niche-pick)
- [ ] Stage 6: /research-review      — triple heterogeneous review (per keep)

## Sprint contract
goal: <pasted from sprint.yaml>
target_metric: <pasted>
target_value: <pasted>
budget_cycles: <pasted>

## History (append-only)
- <ISO ts> /research-init — sprint created on branch research/<tag>
```

### Step 4 — Append decision_trace + initial commit

```bash
echo '{"ts":"'$(date -Iseconds)'","cycle":0,"niche":null,"event":"sprint_init","tag":"'$TAG'","branch":"research/'$TAG'"}' >> "ledgers/$TAG/decision_trace.jsonl"

git add "ledgers/$TAG/"
git commit -m "init(sprint): start research/$TAG with goal=<short>"
```

### Step 5 — Print confirmation

```
Sprint:        <tag>
Branch:        research/<tag>
Ledger:        ledgers/<tag>/
Constitution:  v0.1.0 (pinned)
Goal:          <one-line>
Target:        <metric> ≥ <value>
Budget:        <N> cycles

Next: /research-survey  (Obsidian + cross-domain mining)
```

## Output contract
- Writes: `ledgers/<tag>/{sprint.yaml, TODO.md, results.tsv, decision_trace.jsonl}` + 5 sub-dirs
- Hands off to: `/research-survey`

## Halt conditions
- Any HARD GATE fails → exit 1, no partial state
- User refuses to provide goal/metric/target → halt; this is not a sprint, it's a wish
