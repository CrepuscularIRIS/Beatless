# Architecture & Research State — 2026-04-25

**Created**: 2026-04-25
**Owner**: CrepuscularIRIS
**Purpose**: Snapshot of what exists, what's running, what's left. Written at the moment the system went from "config" to "running" — Google P0 downloads firing, blog drafts producing every 10 min.

---

## 1. Architecture (top-down)

```
┌────────────────────────────────────────────────────────────────────┐
│  YOU (interactive)                                                 │
│   ├── hermes chat -q "..."   → Kimi K2.6 (no thinking, fast)       │
│   ├── claude (Claude Code)   → for multi-file code work            │
│   └── direct edit on ~/research/* and ~/claw/*                     │
└────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────┐
│  HERMES AGENT (the autonomous layer)                               │
│   • systemd user service: hermes-gateway.service (PID 2098)        │
│   • Cron registry: ~/.hermes/cron/jobs.json (9 jobs)               │
│   • Memory: ~/.hermes/memories/                                    │
│   • Skills: ~/.hermes/skills/{blog/, mmx-cli, gif-search, ...}     │
│   • Config: ~/.hermes/config.yaml                                  │
└────────────────────────────────────────────────────────────────────┘
                  │
                  ├──→ [content writing tasks]
                  │     └── Python script → MiniMax M2.7 API
                  │         (blog-translate.py, blog-draft.py)
                  │
                  ├──→ [code work tasks]
                  │     └── Python script → claude -p --model sonnet
                  │         (github-pr.py, github-response.py, auto-research.py)
                  │
                  ├──→ [delegated subagents]
                  │     └── Step 3.5 Flash (verified working)
                  │
                  └──→ [routine I/O tasks]
                        └── Python script (no LLM)
                            (paper-harvest.py, feed-crawl.py,
                             zotero-to-obsidian.py, blog-maintenance.py)
```

### Two-agent division of labor (per `2026-04-23-personal-research-automation-system.md` §2)

| Hermes Agent owns | Claude Code owns |
|---|---|
| Long-term memory | Complex execution chains |
| Task scheduling (cron + self-paced loops) | Code workflows (edit / test / PR) |
| Information organization (filing, tagging) | Research analysis (`/research-*`) |
| Cross-session context continuity | Automated pipelines (PR, experiments) |
| Routine document drafts, blog content | Live reasoning over large contexts |

**Rule of thumb**: outlives the conversation → Hermes. Multi-file code/refactor → Claude Code.

### Model routing (verified 2026-04-25)

| Role | Engine | Where set |
|---|---|---|
| Orchestrator (decides what to do) | **Kimi K2.6** (thinking OFF) | `model.default` + `model.reasoning.enabled: false` |
| Subagents (parallel delegation) | **Step 3.5 Flash** | `delegation.provider: step` |
| Blog content writing | **MiniMax M2.7** | per-script (blog-translate.py / blog-draft.py call MMX directly) |
| Code work (PR, refactor) | **Claude Sonnet** | per-script (github-pr.py / github-response.py invoke `claude -p`) |
| Auxiliary tasks (vision, web_extract, compression) | Kimi (fallback) | Hermes architectural limit — per-role custom endpoint not honored |

---

## 2. Cron jobs — 9 active in Hermes Cron

```
hermes cron list:

  GitHub Response       60m    script + claude -p     ✅ healthy
  GitHub PR Pipeline    150m   script + claude -p     ✅ healthy
  Auto Research         240m   script + claude -p     ✅ healthy
  Paper Harvest         360m   script (HF API)        ✅ healthy
  Zotero Sync           360m   script (Zotero API)    ✅ healthy
  Feed Crawl            720m   script (RSS)           ✅ healthy
  Blog Maintenance      720m   script (audit only)    ✅ healthy
  Blog Translate        10m    script + MMX           ✅ producing drafts
  Blog Draft            30m    script + MMX           ✅ first pair OK
```

All 9 jobs live in `~/.hermes/cron/jobs.json`. Fired by `hermes-gateway.service`. **There is no second cron system** (Hermes earlier hallucinated a separate systemd cron — verified false: `crontab -l` empty, no related systemd timers).

---

## 3. Research commands (`~/.claude/commands/`)

After the 2026-04-24 paradigm pivot to Research Constitution + Automated Research Ecology (see `~/claw/Beatless/plan/2026-04-24-research-constitution-paradigm-phase-1.md`):

### Active commands (10 total, ~400 lines, 96% reduction from 7889)

**Research family** (6, Phase 1 of paradigm pivot):
- `/research-bootstrap <tag>` — new sprint: branch + TSV ledger + JSONL trace + pin constitution
- `/research-parallel` — dispatches up to 9 peer Sonnet 4.6 Task calls in one message; merges; flags R11 entropy collapse
- `/research-loop "<idea>"` — one 5-min experiment cycle: edit → commit → run → grep → keep-or-reset
- `/research-review` — heterogeneous 3-pass: Codex 5.4-mini → Gemini 3.1-pro → Sonnet red-team peer
- `/research-status` — read-only dashboard
- `/research-constitution` — view (Sonnet) or amend (Opus 4.7 — only hot-path Opus use)

**Dev family** (4, Phase 2):
- `/paradigm` — opens canonical paradigm doc + active constitution YAML (read-only)
- `/plan` — wraps `planning-with-files:plan` skill
- `/commit` — Conventional Commits + R4 gate (test feedback can't leak into training)
- `/verify` — wraps `superpowers:verification-before-completion`

### Deprecated commands

84 old commands moved to `~/.claude/commands/deprecated/`. Still callable as `/deprecated:<name>` but not surfaced. Includes the old `/exp-*` family superseded by `/research-*`.

### Anchor docs the commands point at

| Doc | Path |
|---|---|
| Paradigm canonical | `/home/lingxufeng/research/rgmare-lite/plan/research-paradigm.md` |
| Constitution v0.1.0 (12 selection-pressure rules) | `/home/lingxufeng/research/rgmare-lite/contracts/constitution.v0.1.0.yaml` |
| Pratical.md (paradigm source) | `/home/lingxufeng/research/Report/Pratical.md` |
| Deprecated.md (V5.2 — now safety layer only) | `/home/lingxufeng/research/Report/Deprecated.md` |

---

## 4. Two active research projects

### 4.1 BeliefARC — AAAI track (theoretical)

- **Path**: `/home/lingxufeng/research/Belief/`
- **State**: Two extensive Chinese deep-research markdown docs. **No code, no dataset, no experiments yet.**
- **Topic**: Belief-conditioned visual analogical reasoning under partial observability. Hidden bottleneck = MLLMs conflate world-state with belief-state.
- **Plan in docs**: 50-line synthetic 2D grid generator → 3 task families → world/belief disentanglement head → 6-8 weeks to AAAI Oral candidate.
- **Best fit niches in current paradigm**: paper-filter, prior-elicitor, interpretability, theory-compressor, red-team.
- **Constitution risks**: looks like "another ToM benchmark" — R5 (transfer) and R7 (failure-condition) are critical mitigations.
- **Compute**: 2x4090 plenty (frozen backbone + tiny disentanglement head, <5M trainable params).

### 4.2 Google — TIP/CVPR track (industry pipeline)

- **Path**: `/home/lingxufeng/research/Google/`
- **State**: **Actively bootstrapping.**
  - 13 GitHub repos cloned at pinned commits
  - `experiment_manifest.yaml` (P0–P3 priorities, 5 datasets + 8 models)
  - `download_all.py` + `setup_env.sh` ready
  - `STORAGE_RULES.md` (`/data/` for big files; project tree for code/notes)
  - `Idea.md` + `Method.md` + `deep-research-report.md`
- **Pivot from earlier discussion**: Not Vision Banana / ERNIE-Image as initially considered. Actual direction:
  - **Topic**: RefChartQA — answer + bbox evidence map pipeline (chart understanding under text-rich/layout-rich perception)
  - **P0 base models**: Qwen2.5-VL-3B/7B-Instruct, DeepSeek-VL2-tiny
  - **P0 dataset**: RefChartQA (55789 train / 6223 val / 11690 test)
  - **P1 datasets**: InfoChartQA (OOD), ChartAlignBench (dense grounding)
  - **Phase 2 (P3)**: ERNIE-Image — evidence rendering, hard-negative synthesis, deferred
- **Compute**: 2x4090 (49GB each), 5.4TB free on `/data/`
- **HF auth**: token in `~/claw/.env` as `Huggingface_Token`, validated as user `CrepuscularIRIS`

---

## 5. What's been done (chronological)

### 2026-04-23 — Foundation laid

- Roadmap doc + personal-research-automation-system doc written
- Hermes Agent set up with 4 cron jobs (GitHub Response, PR Pipeline, Auto Research, Blog Maintenance)
- MiniMax skill pack installed via `hermes skills tap`
- Model routing wired (Kimi default, Step delegation, MiniMax for blog)
- Zotero → Obsidian sync script written (manual run only)
- Paper harvester + feed crawler scripts written

### 2026-04-24 — Research paradigm pivot

- `/exp-*` commands deprecated, moved to `~/.claude/commands/deprecated/`
- New `/research-*` family written (6 commands, thin pointers to paradigm doc)
- 12-rule Research Constitution YAML created
- Anchor doc `plan/research-paradigm.md` written + git-init on `rgmare-lite/`
- Beatless commit `5524077`: Phase 1 handoff

### 2026-04-25 (today) — Phase 2 + research bootstrap

**Architecture**:
- Phase 2 dev commands written: `/paradigm`, `/plan`, `/commit`, `/verify`
- End-to-end skeleton verified via dry-run sprint `test-20260425`
- Beatless commit `67fe1d0`: Phase 2 handoff

**Hermes**:
- Verified two-agent architecture per §2 of canonical doc
- Confirmed `claude -p` in github scripts is BY DESIGN, not a fault
- 5 more Hermes cron jobs added (Paper Harvest, Zotero Sync, Feed Crawl, Blog Translate, Blog Draft) → 9 total

**Blog pipeline**:
- 3-section writing template arrived (`AI博客写作模板指南.md`) — unblocks Phase 2 blog upgrade
- `~/.hermes/skills/blog/{blog-translate,blog-draft}/SKILL.md` written
- `~/.hermes/scripts/blog-translate.py` written + tested live (script-mode, MMX direct)
- `~/.hermes/scripts/blog-draft.py` written + tested live (bilingual paper spotlight)
- Cron jobs registered: Blog Translate (10m), Blog Draft (30m)
- **17 drafts produced** in `~/obsidian-vault/blog-drafts/` (16 translations + 1 fresh bilingual pair on `anthropic2026aar`)

**Hermes routing**:
- Disabled Kimi K2.6 thinking mode (`model.reasoning.enabled: false`)
- Verified subagent delegation uses Step 3.5 Flash (live test: 2 parallel agents)
- Auxiliary per-role config tried, reverted (Hermes architectural limit — `_try_custom_endpoint` reads global, not per-role)

**Google project**:
- 13 repos cloned at pinned commits
- Manifest + download script + storage rules + env setup all written
- **P0 download fired in background** (PID 321005, log at `~/research/Google/logs/download_p0.log`)
- ~30GB downloading: RefChartQA + Qwen2.5-VL-3B + Qwen2.5-VL-7B + DeepSeek-VL2-tiny

---

## 6. What's left

### Immediate (this session or tomorrow)

- [ ] **Wait for P0 download to finish** (~30 min on highspeed network)
- [ ] **Inspect RefChartQA** Day 1: fill `bbox_coord_system: TBD` and `image_resize_rule: TBD` in `experiment_manifest.yaml`
- [ ] **First MinLoop run** on RefChartQA with Qwen2.5-VL-3B once Day 1 inspection done
- [ ] **P1 downloads** after P0 finishes (InfoChartQA, ChartAlignBench, TinyChart, ChartGemma)
- [ ] **Review the 17 blog drafts** in `~/obsidian-vault/blog-drafts/` — pick keepers, commit Chinese pairs to live blog

### Belief project (parallel track, not yet started)

- [ ] Write 50-line synthetic 2D grid generator (`Family 1: Occlusion False-Belief Grid` per the doc)
- [ ] Implement Baseline 1 (World-state Oracle) and Baseline 2 (symbolic belief tracker)
- [ ] MVE: verify falsification setup works (belief==world subset proves no measurement bug)
- [ ] Implement minimal disentanglement head (frozen backbone + 2 linear heads + invariance loss)
- [ ] 6-8 week timeline to AAAI submission per doc § H

### Architectural debt (not blocking, but worth fixing later)

- [ ] **Auxiliary per-role provider** — Hermes' `_try_custom_endpoint` reads global custom-runtime, not per-role. Per-role overrides silently ignored. To fix: modify Hermes source OR accept Kimi fallback for vision/web_extract/compression.
- [ ] **github-response.py / github-pr.py / auto-research.py use `claude -p`** — by-design per architecture, but the user briefly considered this a "fault." Re-confirmed: NOT a fault. Document doesn't need updating.
- [ ] **Update Phase 2 stale roadmap** — already partially done (added §10 status update to `2026-04-23-autonomous-research-os-roadmap.md`).

### Roadmap phases not yet started

- [ ] **Phase 3** — `/exp-discover` wired to KB. Superseded by `/research-*` paradigm pivot, but the KB-grounded literature search is still missing.
- [ ] **Phase 4** — Daily Evolution Loop with Opus 4.7 reflection (daily 03:30 ET, consumes git commits + cron status + Obsidian deltas + session transcripts).
- [ ] **Phase 5** — Multi-direction progress dashboard.

### Memory / housekeeping

- [ ] Update Hermes memory with the verified routing config and the corrected understanding of github cron architecture (so Hermes stops hallucinating about a second cron system).
- [ ] Periodically review `~/obsidian-vault/blog-drafts/` (it'll fill fast at 10m intervals).

---

## 7. Open questions parked

1. **P1 download timing**: kick off immediately after P0, or wait for first P0 experiments to validate the env? (Suggest: kick off P1 immediately — bandwidth, not GPU, is the bottleneck.)
2. **Belief project start order**: build the synthetic generator now (in parallel with Google P0 downloads), or wait until Google P0 experiments are running?
3. **Blog drafts review cadence**: daily? weekly? Whatever the cadence, define a `keepers/` subdir or a Friday curation ritual to avoid pile-up.
4. **T3 (auto-commit blog drafts to live blog)**: still gated. Activate once you've reviewed ~5 keepers and trust the quality.
5. **Phase 4 daily reflection**: when the architecture stabilizes, write `daily-reflect.py` (Opus 4.7, daily 03:30 ET).

---

## 8. Verification commands (quick reference)

```bash
# Hermes status
hermes cron list                                   # all 9 cron jobs
hermes cron status                                 # gateway alive?
hermes config show                                 # routing
hermes skills list | grep -E "blog|research"      # custom skills

# Blog drafts produced today
ls ~/obsidian-vault/blog-drafts/
cat ~/.hermes/shared/.last-blog-translate-status
cat ~/.hermes/shared/.last-blog-draft-status

# Google P0 download progress
tail -f ~/research/Google/logs/download_p0.log
du -sh /data/datasets/* /data/models/*
ps -p 321005

# Research paradigm artifacts
cat ~/research/rgmare-lite/plan/research-paradigm.md          # canonical doc
cat ~/research/rgmare-lite/contracts/constitution.v0.1.0.yaml  # 12 rules
ls ~/.claude/commands/research-*.md                            # 6 commands
ls ~/.claude/commands/deprecated/ | wc -l                      # 84 archived

# Memory state
ls ~/.claude/projects/-home-lingxufeng-claw/memory/
```

---

## 9. Cross-references

| Doc | Purpose |
|---|---|
| `~/claw/Beatless/plan/2026-04-24-research-constitution-paradigm-phase-1.md` | Phase 1 (paradigm pivot) handoff |
| `~/claw/Beatless/plan/2026-04-25-research-paradigm-phase-2-dev-commands.md` | Phase 2 (dev commands) handoff |
| `~/claw/plan/2026-04-23-personal-research-automation-system.md` | Two-agent architecture canonical |
| `~/claw/plan/2026-04-23-autonomous-research-os-roadmap.md` | Phase 1–5 roadmap (with §10 status update) |
| `~/claw/plan/AI博客写作模板指南.md` | Blog 3-section template + style commandments |
| `~/research/Report/Pratical.md` | Research Constitution paradigm (12 rules + 9 niches) |
| `~/research/Report/Deprecated.md` | Old V5.2 methodology (now safety layer) |
| `~/research/Belief/` | AAAI track — 2 docs, no code yet |
| `~/research/Google/` | TIP/CVPR track — 13 repos cloned, P0 downloading |
| `~/research/rgmare-lite/` | Paradigm overlay (paradigm + constitution + ledgers) |
| `~/.hermes/skills/blog/` | Blog skill files (translate + draft) |
| `~/.hermes/scripts/blog-{translate,draft}.py` | Blog content scripts (MMX direct) |

---

_End of state snapshot. Next time you ask "what's the state?", read this first — it's faster than asking me to re-derive it._

---

## 11. Status update — 2026-04-25 evening (post-multi-stage upgrade)

### What just shipped this turn

**A. PR-followup loop verified**
- `github-response.py` (cron every 60m) invokes `claude -p` with `/pr-followup` workflow
- When maintainer asks for changes: agent evaluates technically (`superpowers:receiving-code-review`), fixes CI FIRST if red, pushes to same branch, replies humbly with commit SHA
- When maintainer is wrong: pushes back politely with technical reasoning (no blind compliance)
- Internal pua rigor stays in `findings.md`; never reaches the maintainer
- Last GitHub PR Pipeline run: created **PR #44 to Neko-Protocol/neko-contracts** with triple-review mean **9.0**

**B. Blog drafting upgraded to multi-stage pipeline**
- `~/.hermes/scripts/blog-draft.py` rewritten from single-call to 3-stage:
  - **Stage 1** (Python): read paper note from Obsidian
  - **Stage 2** (Step 3.5 Flash via `-m step`): structured JSON extraction (title, authors, key_results, limitations, hook, method_intuition)
  - **Stage 3** (MiniMax M2.7 via `--provider minimax`, with `blog-draft` skill loaded): bilingual Paper Spotlight written from scratch in each language per template
- Verified live on `@peng2025kgmark.md` — 163s end-to-end, en (4776B) + zh (4201B), audit clean (no banned phrases), proper hooks + curatorial judgment in both languages
- This concretely leverages each model's strength — not just `--provider minimax` everywhere

**C. CLI quirk discovered + worked around**
- `hermes chat --provider step` fails: `step` not in CLI's hardcoded `--provider` allowlist
- Workaround: use `-m step` (resolves via `model_aliases.step` in config.yaml)
- Documented in script comments

**D. Blog drafts produced this session**
- Total: **67 drafts** in `~/obsidian-vault/blog-drafts/` (16 from old API-direct era, 50+ from cron firing every 10m, 1 fresh bilingual pair from new pipeline)

### What's left (from §6 of this doc, updated)

#### Immediate (next session or background)

- [ ] **Wait for Google P0 download** to finish (still grinding via highspeed WLAN)
- [ ] **Day 1 RefChartQA inspection** — fill `bbox_coord_system` and `image_resize_rule` in `experiment_manifest.yaml`
- [ ] **First MinLoop run** — Qwen2.5-VL-3B on RefChartQA after Day-1 inspection
- [ ] **Review the 67 blog drafts** — pick keepers, commit Chinese pairs to `~/claw/blog/`, discard duds
- [ ] **P1 downloads** — kick off `python3 download_all.py P1` once P0 finishes (InfoChartQA, ChartAlignBench, TinyChart, ChartGemma)

#### Belief project (parallel track, NOT YET STARTED)

- [ ] Write 50-line synthetic 2D grid generator (Family 1: Occlusion False-Belief Grid)
- [ ] Implement Baseline 1 (World-state Oracle) + Baseline 2 (symbolic belief tracker)
- [ ] MVE: verify falsification setup (belief==world subset)
- [ ] Implement minimal disentanglement head
- [ ] 6–8 week timeline to AAAI submission

#### Pipeline integration (the user's "level up" remaining work)

- [ ] **Extend multi-stage pipeline to blog-translate.py** — currently single-stage MMX. For richer translations, add: stage 1 read source → stage 2 Step extracts terminology table → stage 3 MMX translates with terminology grounded.
- [ ] **Cross-job status tracking** — add `status: blogged` field to paper notes when a draft is created. Currently each cron job is independent; add a frontmatter update so we know what's been processed.
- [ ] **Feed-driven Signal Posts** — `blog-draft.py` only handles Paper Spotlight from `papers/literature/`. Add Signal Post handling from `feeds/<date>/` with the same multi-stage shape. Right now feed snapshots accumulate but don't feed the blog.

#### Architectural debt (not blocking)

- [ ] **Auxiliary per-role provider** — Hermes' `_try_custom_endpoint` reads global custom-runtime, not per-role. Per-role overrides silently ignored. Reverted to defaults; would need Hermes source patch to fix.
- [ ] **`--provider step` CLI allowlist gap** — minor; `-m step` works as workaround.

#### Roadmap phases not started

- [ ] **Phase 4** — Daily Evolution Loop (Opus 4.7 reflection, daily 03:30 ET)
- [ ] **Phase 5** — Multi-direction progress dashboard
- [ ] **Stock track** — still blocked on user's methodology handoff

### Three-model leverage map (final)

```
                                Hermes Cron Scheduler
                                         │
           ┌─────────────────────────────┼─────────────────────────────┐
           ▼                             ▼                             ▼
    Code work                    Content writing                Routine I/O
    (PR/research)                (blog)                         (no LLM)
           │                             │                             │
           ▼                             ▼                             ▼
    claude -p --model sonnet     blog-translate.py:            paper-harvest.py
    (Sonnet does heavy work)       hermes chat --provider      feed-crawl.py
                                   minimax -s blog-translate    zotero-to-obsidian.py
                                                                blog-maintenance.py
                                 blog-draft.py:                 (pure Python)
                                   Stage 2: hermes -m step
                                   Stage 3: hermes --provider
                                            minimax
                                            -s blog-draft

    Subagent delegation (any task that calls Hermes' delegate tool):
       Hermes orchestrator → spawns Step 3.5 Flash subagents (verified)
```

Each model fills one role. No overlap. No single-model-everywhere fallback (except auxiliary, which is a Hermes architectural limit).

