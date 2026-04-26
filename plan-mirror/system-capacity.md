# Autonomous Research System — Capacity & Task Map

**Status**: living document (2026-04-26)
**Owner**: CrepuscularIRIS (Beatless / Hermes / ClaudeCode)
**Predecessor**: `2026-04-23-autonomous-research-os-roadmap.md` Phase 3-4

This doc answers a single question: **what tasks can the system actually execute end-to-end without me sitting in a chat window?** Each row below has a real, runnable trigger.

---

## 0. Operating model

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Hermes cron (the second brain — schedules + persists state)             │
│   → fires research-host-cron.py / blog-translate.py / etc.              │
│   → each cron driver builds a state file + invokes `claude -p`          │
│   → ClaudeCode runs the corresponding /command in autonomous loop       │
│   → output lands on disk; next cron tick resumes from disk only         │
└─────────────────────────────────────────────────────────────────────────┘
```

The user is **not in the loop**. State is on disk, cron is the heartbeat, ClaudeCode is the executor with three tool-using sub-models (Codex / Gemini / Sonnet-fresh) plus Skills (Superpowers, planning-with-files).

---

## 1. Task taxonomy (what the system can run end-to-end today)

### Tier A — production, currently running on cron

| Task | Cron driver | Schedule | Outputs |
|---|---|---|---|
| Paper harvest (arXiv / OpenReview / ACL → Zotero metadata) | `paper-harvest.py` | every 360m | Zotero entries with `auto-harvest` tag |
| Zotero → Obsidian sync (metadata + abstract → stub note) | `zotero-to-obsidian.py` | every 360m | `~/obsidian-vault/papers/literature/@<citekey>.md` |
| Feed crawl (lab blogs + tech reports → vault) | `feed-crawl.py` | every 720m | `~/obsidian-vault/feeds/<date>/<lab>-<slug>.md` |
| Blog translate (EN ↔ ZH bilingual pairs) | `blog-translate.py` | every 10m | `~/obsidian-vault/blog-drafts/<slug>-zh/index.mdx` |
| Blog draft (Obsidian → multi-stage hIE-tagged drafts) | `blog-draft.py` | every 30m | `~/obsidian-vault/blog-drafts/<slug>/index.mdx` |
| Daily evolution audit (3-model parallel audit + Opus synthesis) | `daily-evolution.py` | every 1440m | `~/claw/blog/src/content/blogs/daily-evolution-<date>/` |
| GitHub PR follow-up (CI fix + reply + escalation) | `github-response.py` | every 60m | replies + `git push` on existing branches |
| GitHub PR pipeline (issue claim + repo policy filter + open PR) | `github-pr.py` | every 150m | new PRs with constitution-bound preflight |
| Auto-research wake gate (detects unfinished workspaces) | `auto-research.py` | every 240m | invokes `/exp-run resume` (LEGACY — being replaced) |
| Blog maintenance (audit-only — flag stale posts) | `blog-maintenance.py` | every 720m | `~/.hermes/shared/.blog-audit.md` |

### Tier B — built this session, ready to schedule

| Task | Cron driver | Recommended schedule | Outputs |
|---|---|---|---|
| **Hosted research host** (autonomous /research-host loop) | `research-host-cron.py` | every 360m (6h) | sprint ledger rows, decision_trace events, MAP-Elites archive, progress.md |

This one is the headline. It runs `/research-host` — see `~/.claude/commands/research-host.md` — which embeds the 3 Core Principles (P1 parallel-orthogonal, P2 triple-heterogeneous review, P3 surface implicit knowledge) and the new paradigm's QD / mutation operators / stepping stones. **One command per cron tick covers Phase 0–6 of the autonomous loop.**

### Tier C — feasible now, needs a cron driver (one afternoon each)

| Task | What's needed | Existing pieces |
|---|---|---|
| **Long GPU jobs (3-4h training)** | A `gpu-job-cron.py` that reads a `~/research/<ws>/queue/*.yaml` of pending experiments, claims one (atomic flock), launches `nohup uv run train.py > log &`, monitors mid-run, parses metrics on exit. /research-host's Phase 3c already does this for short cycles — extend to long-budget mode (the deprecated `/exp-run` Full Mode discipline). | `/exp-run` Full Mode template (deprecated but well-designed); `daily-evolution.py` cron pattern; `nvidia-smi` polling code in `/exp-run`. |
| **Leaderboard chasing / eval loops** | `eval-loop-cron.py` that reads a benchmark suite spec (yaml of (model, dataset, metric) tuples), runs each missing combo, writes to a CSV, posts top-N changes to a webhook. Convergence criterion = N consecutive cycles with no new top-1. | `paper-harvest.py` for spec discovery; `/research-host` Phase 4 review chain for sanity-checking new SOTAs (catches cherry-picked seeds). |
| **Dataset / model download orchestration** | `download-cron.py` that reads a `~/research/<ws>/downloads.yaml` (HF model ids, dataset URLs, expected SHA256), runs `huggingface-cli download` or `curl -L` in parallel-bounded workers, verifies SHA256, retries. Already covered for the Google workspace by `download_all.py`+`resilient_download.py` — generalize. | `~/research/Google/download_all.py` + `resilient_download.py` (already production-quality). Just needs a Hermes shim. |
| **Research workflow per `Plan.md`** | `/research-host` IS this. The Google workspace is the first real trial — see Plan.md gates G3.1/G3.2/G3.3. The cron driver kicks the loop; halt conditions handle when to stop. | `research-host-cron.py` (built this session). |

### Tier D — needs dedicated design, deferred

| Task | Why deferred |
|---|---|
| Full-paper PDF → Markdown KB | User decision 2026-04-26 — MinerU output average vs cost. Lightweight Zotero-stub + Obsidian-feed is enough for current needs. `paper-fulltext.py` preserved as on-demand. |
| Multi-machine / RunPod orchestration (AAR Mode B/C) | Single-machine local mode covers the immediate research; multi-node is a separate infra investment. AAR README has the Docker / RunPod recipe — leverage when needed. |
| Real-time leaderboard public dashboard | Static blog at `~/claw/blog/` is the current public surface; leaderboard would be a separate Astro page. Build when there's a leaderboard worth showing. |

---

## 2. The four task families in practice

### 2.1 Long GPU jobs (3-4h training / benchmarking)

**Trigger path**: cron fires `gpu-job-cron.py` → drains the `queue/` dir → writes `progress.md` with PID + start time → enters monitor-idle mode (per `/exp-run` Full Mode) → at 50%/80%/final checkpoints, parses `val_metric` → keep/discard via P2 triple-review.

**Hardware envelope** (current machine):
- 2× GPUs (per `/exp-run` Full Mode VRAM ceiling discipline: ≤40 GB target / ≤48 GB hard)
- VRAM budget per run forced into `Task.md`; mid-run kill at budget+1h
- GPU isolation via `CUDA_VISIBLE_DEVICES=0` / `=1` per script (never two on one GPU)

**Halt conditions** (inherit from `/research-host`):
- Hardware fault (GPU unreachable mid-run) → cron driver writes `status=hw-fault`, surface to user
- 4 consecutive no-improvement → trigger `/research-host` discover-refresh
- Compute ≥ 2× baseline with no hard-class gain → kill direction (R7 in constitution)

**Verification today**: `/research-host` Phase 3c can run short cycles (Karpathy autoresearch's 5-min budget). Extending to 3-4h needs `Task.md` parsing + `nohup` discipline lift from `/exp-run` Full Mode. ~1 afternoon's work.

### 2.2 Leaderboard chasing / eval loops

**Trigger path**: `eval-loop-cron.py` reads `eval-suite.yaml` (e.g. `(model=Qwen2.5-VL-7B, dataset=RefChartQA-val, metric=AECS)`), runs missing combos in parallel-bounded workers, writes per-combo JSONL to `eval-results/`, aggregates a top-N table. Sanity-check via `/research-host` Phase 4 (catches cherry-picked seeds).

**Why P2 triple-review matters here**: leaderboard chasing is THE place spec-gaming bites. A cycle that reports "best AECS" by silently picking the seed that happened to overfit val is exactly what Codex correctness + Gemini challenge + Sonnet-fresh red-team are supposed to catch. The implicit-knowledge block (P3) surfaces "I picked seed 42 because the others looked worse" — without that, the leaderboard becomes a benchmark-overfitting machine.

**First trial target**: the Google workspace's existing 12,000-record matrix in `Plan.md §0` — re-score with the relaxed metric family (§4 #1-#4) without re-running models. Pure CPU work, perfect first cycle.

### 2.3 Download / preparation (datasets + models)

**Trigger path**: `download-cron.py` reads `downloads.yaml` (entries: `{kind: hf-model | hf-dataset | http, id-or-url, expected-sha256, target-path}`), runs parallel-bounded workers (default 4), verifies SHA256 on completion, writes `downloads.tsv` (`url, status, bytes, sha256_match`).

**Existing prior art**: `~/research/Google/download_all.py` + `resilient_download.py` are already production-quality (network resume, SHA verification, parallel workers, modelscope SSL workaround). Generalizing them into a Hermes cron driver is mostly wiring + a `downloads.yaml` schema. ~1 morning's work.

### 2.4 Research workflows like `Plan.md`

This is exactly what `/research-host` does. Concrete trial — Google workspace, Plan.md v3 "Proof-Carrying Visual Answers for Chart QA":

```
~/research/Google/
├── Plan.md                                     ← v3 with G3.1/G3.2/G3.3 gates
├── contracts/constitution.v0.1.0.yaml          ← 12 R-rules + 5 niches
├── ledgers/sprint-2026-04-26-google/
│   ├── sprint.yaml                             ← 5 orthogonal niches
│   └── results.tsv                             ← cycle ledger (header-only now)
└── traces/decision_trace.jsonl                 ← event log (empty now)
```

**Cron tick #1** (the verification run we're doing this session): kicks Phase 0 status → Phase 1 discover (5 hypotheses, Gemini for lit search) → Phase 2 niche selection + orthogonality check → Phase 3 same-message dispatch of 5 peer Sonnet branches → Phase 4 triple-heterogeneous review on the top proposal → write back to disk → halt or loop.

**Cron tick #2** (next 6h): resume from disk via `/research-host resume` — reads `progress.md`, picks up at the next subphase, continues. No human in the loop.

---

## 3. Capacity envelopes (honest limits)

### What it CAN do
- Run autonomous research cycles for hours / days without human intervention, provided:
  - Cron is healthy (Hermes uptime)
  - Codex + Gemini quotas are healthy
  - Disk has space, GPUs are available
- Handle the full discover → propose → execute → review → reflect loop with mutation operators
- Preserve diversity via MAP-Elites archive (won't collapse to a single hill-climbed local optimum)
- Detect spec-gaming via P2 triple-review chain
- Surface implicit knowledge per cycle (P3) so the next cycle starts on a more complete cognitive base
- Resume from disk after restart / context reset (state on disk discipline)

### What it CANNOT do (yet)
- **Autonomous design of fundamentally new benchmarks** — `/research-host` works within a Plan.md scope. New scope still needs human seed.
- **Multi-day GPU training (>24h)** — current cycle timeout is 3h per cron tick. Long jobs would need a job-queue + monitor pattern (Tier C above).
- **Cross-machine orchestration** — single-machine only. AAR-style RunPod / Docker isolation is documented in their README but not wired in.
- **Fully resolve novel research blockers without human input** — when Phase 1 discover stagnates twice in a row, the loop halts and asks for human re-orientation. This is by design (Halt condition #4).

### What it SHOULD NOT do
- Run a model family judging itself (P2 hard rule)
- Promote a `keep` row to ledger without P2 triple-review pass (constitutional R rules)
- Skip the implicit-knowledge block (P3 enforcement — incomplete branches dropped, not retried at budget cost)
- Override constitution at runtime (constitution amendment requires `/research-constitution --amend` with Opus 4.7 — rare, deliberate)

---

## 4. Recommended cron line-up (proposal — current state in §1 Tier A)

After this session's work, the recommended steady state:

| Schedule | Cron job | Purpose |
|---|---|---|
| every 60m | github-response.py | PR follow-ups + CI debug (Tier-1 → Tier-4 escalation) |
| every 150m | github-pr.py | New PR pipeline (preflight + claim + open) |
| every 360m | research-host-cron.py | **NEW — autonomous research cycles** |
| every 360m | paper-harvest.py | Zotero ingest |
| every 360m | zotero-to-obsidian.py | Stub-note sync |
| every 720m | feed-crawl.py | Lab blog / tech report ingest |
| every 720m | blog-maintenance.py | Audit-only blog freshness |
| every 1440m | daily-evolution.py | Audit-only system-health report |
| every 10m | blog-translate.py | Bilingual pair fill (drafts dir, human reviews before live) |
| every 30m | blog-draft.py | Multi-stage paper-spotlight drafts |

Total: **10 cron jobs**, no overlap on the same workspace, all read from / write to disk so any job can be killed and resumed.

---

## 5. How to add a new task family

The recipe (~1 afternoon per family):

1. Write a state-gathering function (Phase 1) — what does the cron tick need to know to start?
2. Write a prompt builder — what command does ClaudeCode run, with what context?
3. Write the corresponding `/command-name.md` if it doesn't exist (or extend `/research-host`)
4. Wire `claude -p --model sonnet "/command <state-file>"` with `stdin=DEVNULL`
5. Write status JSON + JSONL log on exit
6. Register with `hermes cron create --name "..." --script research-host-cron.py --interval-minutes 360`

The `daily-evolution.py` and `research-host-cron.py` scripts are the canonical templates.

---

## 6. Open questions for next session

- Whether to merge `auto-research.py` (legacy `/exp-run` driver) into `research-host-cron.py` or retire it. Likely retire — `/research-host` covers the same ground with better discipline.
- Whether `paper-fulltext.py` should run on a slow cadence (e.g. 1 paper / week) for high-value papers tagged manually — currently on-demand only.
- Whether to add a `gpu-budget.yaml` per workspace so the cron driver knows when to back off (e.g. yield to interactive dev work between 09:00-18:00 local).
