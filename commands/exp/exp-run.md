---
description: "Autonomous experiment loop. Quick mode: single-GPU, short budget, fast keep/discard. Full mode: dual-GPU A/B, long budget, convergence-era judging, Deep Research Pass. Auto-detects from workspace. Runs until SOTA or halt."
argument-hint: "<experiment description> or \"resume\""
allowed-tools: Bash, Read, Write, Grep, Glob, Agent, Skill, mcp__plugin_gsd_gsd__*
---

# Experiment Run: Autonomous Loop

Experiment: **$ARGUMENTS**

---

## Step 0: Mode Detection and Resume

### Detect mode
- `Task.md` with dual-GPU config or `mode: full` → **Full Mode**
- `program.md` + `train.py` without Task.md → **Quick Mode**
- Task.md with `mode: quick` → **Quick Mode** (override)

### Resume check
If `$ARGUMENTS` is "resume" or `progress.md` exists with prior rounds:
- Read `progress.md` for last completed round N and any running PIDs
- Check PIDs: `ps -p <PID>` — if alive, enter monitor-idle mode
- If last round finished → continue at round N+1
- NEVER restart from round 1 if higher rounds are recorded

### Integration readiness (test once at startup)

| Integration | Invocation | Fallback |
|-------------|-----------|----------|
| Codex CLI | Agent tool → subagent_type `codex-cli` | Claude Edit + Bash test |
| Gemini CLI | Agent tool → subagent_type `gemini-cli` | WebSearch + Claude reads key files |
| GSD | MCP `mcp__plugin_gsd_gsd__gsd_record_metric` | Direct file writes |
| Planning-with-files | Skill `planning-with-files:plan` | Direct file writes |
| Superpowers | Skill `superpowers:brainstorming` | Claude generates ideas directly |

For Codex CLI and Gemini CLI, invoke each Agent once with prompt:
```
Readiness check only. Verify the local CLI bridge is usable. Do not edit files.
```

Record `READY` / `UNAVAILABLE` in `progress.md`. Do NOT retry failed integrations during the loop.

---

## Hard Constraints (both modes)

1. **Never edit read-only files** (prepare.py, or files marked in Task.md/program.md)
2. **Never add dependencies** (only what's in pyproject.toml / requirements.txt)
3. **results.tsv is append-only** and intentionally untracked by git
4. **Autonomy**: Once loop starts, NEVER ask "should I continue?" Human may be asleep. Run until halt condition.
5. **Session continuity**: All state on disk. `/exp-run resume` must auto-resume from any point.
6. **No destructive ops** (checkpoint deletion, git reset --hard on non-experiment commits, force push) without human confirmation. Only `git reset --hard` of the current experiment commit on discard is allowed.

---

## QUICK MODE

Single GPU, short budget, fast iteration. Target: 10-12 experiments per hour.

### Guardrails
- Only edit files listed in program.md (typically `train.py`)
- Budget: from program.md (default 5 min + 2 min overhead)
- Single GPU

### Quick Loop (repeat until halt)

#### Q1. Capture Start Point
```bash
START_COMMIT=$(git rev-parse --short HEAD)
```
Read best prior metric from `results.tsv` (lowest non-zero val_bpb or primary metric).

#### Q2. Implement Experiment

Invoke Codex for code changes:
```
Agent tool:
  subagent_type: "codex-cli"
  prompt: "Apply this single experiment to train.py only: [experiment description].
  Keep changes minimal and coherent. Do not add imports for new packages.
  Do not modify prepare.py or any other file."
```
**Fallback**: Claude edits via Edit tool directly.

#### Q3. Commit
```bash
git add train.py  # or whichever files were modified
git commit -m "exp: [short description]"
```

#### Q4. Run Timed Experiment
```bash
timeout <budget+120> uv run train.py > run.log 2>&1
```
Do NOT use tee. Do NOT let output flood context. Redirect everything.

#### Q5. Parse Results
```bash
grep "^val_bpb:\|^peak_vram_mb:" run.log
```
If grep returns empty → crash. Run `tail -n 50 run.log` for the stack trace.

#### Q6. Log to results.tsv
```
<commit>	<val_bpb>	<memory_gb>	<status>	<description>
```
- `val_bpb`: parsed value or `0.000000` on crash
- `memory_gb`: `peak_vram_mb / 1024` rounded to .1f, or `0.0` on crash
- `status`: `keep` / `discard` / `crash`

#### Q7. Keep/Discard Decision
- **Improved** (metric better than best prior) → keep commit, update best
- **Equal or worse** → append row with `discard`, then `git reset --hard $START_COMMIT`
- **Crash** → append row with `crash`, then `git reset --hard $START_COMMIT`
  - If crash was a fixable typo/import: fix and re-run ONCE. If it fails again, discard.
  - If crash was fundamental (OOM, design flaw): discard immediately.

**Simplicity criterion**: A tiny improvement (< 0.001) that adds complexity → discard. An improvement of ~0 from deleting code → keep. Weigh complexity cost against gain magnitude.

#### Q8. Update Planning Files
- `findings.md`: metrics, memory, observations, what was learned
- `progress.md`: keep/discard decision, timestamp, round number
- `task_plan.md`: next experiment idea based on what was learned

Use GSD to record metric: MCP `mcp__plugin_gsd_gsd__gsd_record_metric`. Fallback: write to findings.md.

#### Q9. Next Iteration Decision
- **Normal**: design next experiment from findings, loop back to Q2
- **Stagnation** (4 consecutive no-improvement): invoke `/exp-discover` for fresh hypotheses, then resume
- **Out of ideas**: think harder — re-read program.md, past findings, try combining near-misses, try more radical changes. NEVER stop just because ideas feel scarce.

### Quick Mode Halt Conditions
1. 4 consecutive rounds after `/exp-discover` still no improvement
2. Hardware fault (GPU unreachable)
3. Human interrupts

---

## FULL MODE

Dual-GPU A/B experiments, long budget, structured research escalation.

### Guardrails
- **GPU isolation**: Experiment A → `CUDA_VISIBLE_DEVICES=0` ONLY. Experiment B → `CUDA_VISIBLE_DEVICES=1` ONLY. NEVER two experiments on same GPU.
- **VRAM ceiling**: ≤48 GB per GPU. Target ≤40 GB (8 GB margin). If config predicts >40 GB, cut batch size / precision first.
- **Budget**: from Task.md (default 4h per run). Hard kill at budget + 1h.
- **Before every launch**: `nvidia-smi` to confirm target GPU is idle.

### Convergence-Era Judging (critical)
Record `val_metric` at three checkpoints:
- (a) 50% of budget (~plateau entry)
- (b) 80% of budget
- (c) Final best

A direction is "genuinely ahead" only if it wins at ≥2 of 3 checkpoints. Peak-only comparison hides overfit wins. Report all three columns in `findings.md`.

### Full Loop (repeat until halt)

#### F1. Kill-Switch Check (every round)

Halt a direction if ≥2 of these trigger:
1. Metric fails to improve for 2+ consecutive evals
2. Gains only from easy classes — hard-class delta ≤ 0
3. Training diverges / NaN / checkpoint corrupt
4. Compute ≥2× baseline with no hard-class gain
5. Task.md kill condition fired

Write kill-switch verdict per direction to `findings.md`.

#### F2. Design Two Experiments (A + B)

- **A (mainline improvement)**: extend winning direction, push headline metric
- **B (localization / falsification)**: isolate one hypothesis, rule in or out

For each, specify in `task_plan.md`:
- Experiment ID (unique, suffix `_gpu0` / `_gpu1`)
- Hypothesis (one sentence, falsifiable)
- Change scope (files + functions)
- Success metric + numeric threshold
- Kill trigger (specific condition to abort mid-run)
- Budget: epochs + expected wall-clock
- GPU binding (A=0, B=1)
- Expected peak VRAM (must be ≤40 GB)

#### F3. Delegate Code Changes (Codex)

```
Agent tool:
  subagent_type: "codex-cli"
  prompt: "Implement two experiments for [project root]:

  Experiment A (GPU0): [hypothesis]
  - Target files: [paths]
  - Change: [diff scope]
  - Output: run_<exp_A>_gpu0.sh with CUDA_VISIBLE_DEVICES=0

  Experiment B (GPU1): [hypothesis]
  - Target files: [paths]
  - Change: [diff scope]
  - Output: run_<exp_B>_gpu1.sh with CUDA_VISIBLE_DEVICES=1

  Constraints: separate log/checkpoint dirs, VRAM ≤40GB each, wall-clock ≤[budget]h.
  Return: diff summary, .sh paths, VRAM estimate, any sanity checks."
```

**Verify** returned scripts:
```bash
grep -n CUDA_VISIBLE_DEVICES run_*_gpu{0,1}.sh  # each has exactly one, values match
```
Neither script forks a second training. Log dirs are separated. If any check fails, send failure back to Codex.

**Fallback**: Claude writes scripts directly.

#### F4. Delegate Literature Check (Gemini)

```
Agent tool:
  subagent_type: "gemini-cli"
  prompt: "For hypotheses A: [one line] and B: [one line] in [project domain]:
  1. 3-5 closest 2025+ papers (title, venue, year, takeaway)
  2. Closest to hypothesis A? Closest to B?
  3. Strongest counter-argument to A
  4. Alternative angle we're not testing"
```

Paste reply verbatim into `findings.md` under `## Prior Art — Round N`. Do NOT paraphrase.

**Fallback**: WebSearch for arxiv queries. Mark `[UNVERIFIED]`.

#### F5. Launch Dual-GPU Training

1. Final `nvidia-smi` check — both GPUs idle
2. `nohup bash run_<A>_gpu0.sh > logs/<A>.log 2>&1 &` → record PID
3. `nohup bash run_<B>_gpu1.sh > logs/<B>.log 2>&1 &` → record PID
4. Append to `progress.md`:
   ```
   | Round | Exp ID | GPU | PID | Start | Expected End | Status |
   ```

**Monitor-idle mode** (default state between launch and completion):
- Every 20-30 min: `ps -p <PID>`, `tail -n 50 logs/<exp>.log`, parse recent val metric
- At ~50% budget: execute F6 midpoint check
- If PID disappears: jump to F7 (endpoint analysis)
- If wall-clock > budget + 1h: `kill <PID>`, mark crash, revert commit
- Do NOT generate code or start unrelated work during monitoring
- NEVER ask "should I continue monitoring?"

#### F6. Midpoint Check (~50% budget)

1. `nvidia-smi` — confirm GPUs held by correct PIDs, VRAM < 46 GB
2. Tail each log, parse loss + eval metric trend
3. Per run: **continue** if trending as expected, **early-kill** if loss NaN / diverging / OOM / kill trigger fired
4. Write midpoint verdict to `findings.md`

#### F7. Endpoint Analysis (when both complete)

1. Extract: headline metric, per-class breakdown, peak VRAM, wall-clock
2. Compare to: baseline, current best, last round
3. Append to `findings.md` answering:
   - **Pain point localized?** (yes / no / partial, cite evidence)
   - **Gain from hard classes or easy-class tide?** (numeric delta per hard class)
   - **Next round: continue / pivot / stop?**
4. Append results.tsv row per experiment:
   ```
   commit	exp_id	gpu	metric	hard_metric	peak_vram_gb	status	description
   ```
5. If "keep" → record checkpoint path as new current-best

#### F8. Next Round Decision

- **Continue** → back to F1
- **Pivot** → update mainline, fresh hypothesis for other GPU
- **Deep Research Pass** triggered if ANY of:
  - 2 consecutive rounds no improvement
  - Gap to SOTA ≥ 0.05
  - Every 4 rounds (scheduled, prevents tunnel vision)
  → Execute `/exp-discover` with current context, then resume with chosen hypotheses
- **Halt** → 4 consecutive rounds no improvement (including post-research), or SOTA hit

### Full Mode Halt Conditions
1. SOTA target in Task.md achieved on val set
2. 4 consecutive rounds fail to improve (including post-discover rounds)
3. Hardware fault (GPU unreachable, both experiments crash twice on same config)
4. Human interrupts

---

## File Contract (both modes, every round writes all three)

| File | Mode | Content |
|------|------|---------|
| `task_plan.md` | Rewritten per round | Current experiment design, hypotheses, scope, kill triggers |
| `findings.md` | Append-only, newest on top | Per-round: literature, midpoint, endpoint, ≥1 falsifiable statement |
| `progress.md` | Live-updated | GPU occupancy, run table (PID/start/end/status), results.tsv tail |
| `results.tsv` | Append-only | Per-experiment row with metrics and status |

`findings.md` must contain **at least one falsifiable statement per round** — a prediction the next experiment can disprove.

---

## Output Style

- Conclusion first, details second
- Every recommendation cites: file path, exp ID, metric delta, or commit hash
- No generic advice ("try tuning hyperparameters") — always be specific
- Long analyses → `findings.md`, not console output
- Keep human-facing messages short (human may be reading on phone after waking up)
