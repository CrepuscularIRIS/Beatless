# Personal Research & Knowledge Automation System — Long-Term Plan

**Created**: 2026-04-23
**Owner**: CrepuscularIRIS (maintained by Hermes Agent + Claude Code)
**Status**: living document — revise as the system matures

---

## 1. North Star

One unified workflow that, concurrently:

1. **Auto-generates outputs and runs pipelines** (code, PRs, experiment runs, blog posts, data captures).
2. **Supports direction-finding, knowledge accumulation, and methodological development** (ideation, paper triage, writing, synthesis, cross-session context).

The same system does routine execution *and* long-horizon thinking — not two separate stacks.

---

## 2. Two-Agent Division of Labor

| Hermes Agent | Claude Code |
|---|---|
| Long-term memory | Complex execution chains |
| Task scheduling (cron + self-paced loops) | Code workflows (edit / test / PR) |
| Information organization (filing, tagging) | Research analysis (`/exp-*`, triple-review) |
| Cross-session context continuity | Automated pipelines (PR, experiments) |
| "Second brain" — document drafts, routine tasks, retrieval | Live reasoning over large contexts |

**Rule of thumb**: if it needs to outlive the current conversation, it belongs to Hermes. If it needs to burn tokens against a big codebase or a multi-file edit, it belongs to Claude Code.

**Interface between them**: Hermes cron wake-gates call `claude -p --model sonnet` with a specific `/command`. Hermes owns the schedule + the memory; Claude Code owns the execution.

---

## 3. Knowledge Infrastructure

### 3.1 Foundation (owned, durable)

- **Local paper repository** (Zotero + PDFs on disk) — durable, offline, versionable.
- **Obsidian vault** — long-term notes graph: reading notes, methodology summaries, research direction judgments, experiment records.

**Priorities for paper intake**:
- Top-tier conferences post-2025 (NeurIPS, ICML, ICLR, ACL, AAAI, COLM, KDD, CVPR, ICCV, ECCV).
- A-level journals (Nature, Science, Cell, PNAS).
- Reading-note schema: one short "what / why-surprising / how-useful-to-me" block per paper, plus a methodology tag.

### 3.2 Fast surface (query-oriented)

- **NotebookLM** — topic-scoped grounded Q&A over PDF / web / video collections. Used when a new direction needs rapid cross-reading without committing to long-form notes.

### 3.3 Retrieval contract

- Hermes `memory` holds: user profile, project state, references to external systems (Zotero collections, Obsidian folders, NotebookLM notebooks).
- Hermes does NOT duplicate paper content — it points to where the content lives.
- Claude Code reads the paper / note directly when needed.

---

## 4. Google Ecosystem (planned integration)

Phased rollout — don't wire everything at once.

| Service | Role | Entry point | Status |
|---|---|---|---|
| Google Workspace (Docs/Drive/Calendar) | Shared documents, calendar-driven scheduling | Hermes MCP / Workspace API | planned |
| Gemini CLI | Second-model consult (already wired in Claude Code via `gemini:gemini-consult`) | Subagent | ✅ wired |
| Deep Research (Gemini) | Long-horizon research agent for direction-finding | Wrapper command calling Gemini Deep Research | planned |
| Vertex AI — Imagen | Batch image generation for blog, slides, posters | Hermes job or standalone CLI | planned |

**Use cases the ecosystem must support**:
- Data acquisition (scraped web, paper PDFs, datasets).
- Research assistance (literature maps, devil's-advocate critiques).
- Image generation (blog headers, diagrams, posters).
- Document processing (PDF → structured notes, Docs editing).
- Automated collaboration (share drafts, schedule reviews).

---

## 5. Current State (2026-04-23)

### 5.1 Running autonomously (Hermes cron)

| Job | Schedule | Model routing | Status |
|---|---|---|---|
| GitHub Response | every 60m | default (Kimi K2.6 for summary, Sonnet for `-p` work) | ✅ healthy, new regulations in force |
| GitHub PR Pipeline | every 150m | default + Sonnet via `-p` | ✅ preflight (AI policy, CLA, duplicates) active |
| Auto Research | every 240m | default | ⚠ wired to deprecated `/analyze-results` — fix in §7 |
| Blog Maintenance | every 720m | MiniMax M2.7 per-job override | ⚠ stub only — fix in §7 |

Gateway: systemd user unit, 17h uptime, no crashes.

### 5.2 Claude Code commands (active)

**Research & experiments (current)**:
- `/exp-discover` — two-path hypothesis generator (combined rewrite of old `/autoresearch` + `/research-analyze`)
- `/exp-init` — bootstrap experiment workspace
- `/exp-run` — autonomous experiment loop (quick or full mode)
- `/exp-review` — multi-plugin review of experiment state
- `/exp-status` — workspace readiness check

**Deprecated research commands** (to retire):
- `/research-init` — superseded by `/exp-init`
- `/research-analyze` — superseded by `/exp-discover`
- `/research-train-loop` — superseded by `/exp-run`
- These still sit in `~/.claude/commands/` dated 2026-04-20 and contain stale `/home/yarizakurahime/` paths. Archive them.

**GitHub pipeline** (recently hardened):
- `/github-pr` v8 — preflight → evaluate → setup → reproduce → plan → implement → verify → triple-review → submit → report. Bound to all 7 `Beatless/standards/` files + pua methodology for internal rigor.
- `/pr-followup` v3 — triage, fix-CI-first, priority order, human reply tone enforced from `PullRequest.md` §6 and `mention.md`.

**Knowledge / writing**:
- `/zotero-review`, `/zotero-notes` — Zotero collection reading.
- `/blog-maintenance` (command wrapper — the skill file it references doesn't exist yet).

### 5.3 Model routing

- **Kimi K2.6** (orchestrator) — default for all non-overridden jobs. Verified via logs.
- **Step 3.5 Flash** (delegation / subagents) — works via config + job-level override. ⚠ CLI `--provider step` fails because `step` is not in the hardcoded CLI allowlist; use `--base-url` instead.
- **MiniMax M2.7** — wired for Blog Maintenance. Verified: logs show `Auxiliary auto-detect: using main provider minimax (MiniMax-M2.7)`.

Minor noise fixed this session: `step-3.5-flash` and `MiniMax-M2.7` now declare `context_length` in `config.yaml`, silencing the repeated "probe-down" warning.

### 5.4 MiniMax skill pack (installed via `hermes skills tap`)

Installed skills under `~/.hermes/skills/`:
- `minimax-docx`, `minimax-pdf`, `minimax-xlsx` — document generation
- `minimax-multimodal-toolkit` — image/video/audio toolkit
- `minimax-music-gen` — music generation
- `blogwatcher` (research category) — relevant for blog pipeline

---

## 6. Deferred Work (explicit, not forgotten)

### 6.1 Blog upgrade (waiting on user spec for "3 sections")

- Bundle `~/claw/blog` (Astro site, 182 posts, 39 already `-zh` bilingual pairs) with MiniMax skill pack.
- **Goal stated by user**: rewrite past posts, create new ones, EN + CN bilingual, 3 sections per post.
- **Blocked on**: the 3-section template (the user will specify what the sections are — intro/body/takeaways? theory/code/results? etc.).
- **Intermediate step we can take now**: upgrade `blog-maintenance.py` from stub → real prompt that loads MiniMax skills and opens `~/claw/blog`. Leave the 3-section template as a placeholder to fill when the spec arrives.

### 6.2 Stock job (waiting on user methodology)

- Will be bundled with **Polymarket** + the user's own stock methodology skills.
- **Blocked on**: the methodology-skill handoff from the user.
- Until then, do NOT create a stock cron job or stub — a stub job that never fires adds noise to `hermes cron list`.

### 6.3 Stock-review skill (referenced in `SOUL.md` and `IMPLEMENTATION-STATUS.md` but never created)

- Same blocker as 6.2. Remove the "stock analysis" line from `SOUL.md` if the methodology is long-postponed, or leave it as an explicit TODO anchor.

---

## 7. Immediate Infrastructure Fixes (this session)

1. **Retire deprecated research commands** — archive `research-init.md`, `research-analyze.md`, `research-train-loop.md` OR rewrite their top lines to `DEPRECATED — see /exp-*` so they can't be accidentally run.
2. **Rewire `auto-research.py`** from `/analyze-results` (which still exists but is the old path) to `/exp-run resume` so the cron actually uses the current research pipeline.
3. **Clean stale `/home/yarizakurahime/` references** in any remaining command files.
4. **Upgrade `blog-maintenance.py`** from stub to real prompt — invokes `/blog-maintenance` slash command with MiniMax model override, points at `~/claw/blog`. Leave 3-section template as TODO placeholder.
5. **Confirm model routing still healthy** after config changes (context_length additions).

Stock is intentionally left untouched — postponed per user instruction.

---

## 8. Success Criteria (how we know the system is working)

- [ ] Every open PR in `CrepuscularIRIS/*` has either passing CI or a human-tone reply explaining the status, within one cron tick of an event.
- [ ] At least one new blog post per week, bilingual EN+CN, 3-section format (once template is defined).
- [ ] Obsidian vault grows by ≥3 reading notes per week with methodology tags.
- [ ] `/exp-run` can execute a dual-GPU A/B loop to convergence without manual intervention.
- [ ] Hermes memory answers "what was I working on last week?" accurately from persisted context, without needing to re-read the full conversation.
- [ ] No fatal errors in `~/.hermes/logs/errors.log` for 7 consecutive days.

---

## 9. Risks & Guardrails

| Risk | Mitigation |
|---|---|
| PR pipeline submits AI-forbidden work | Preflight 2a scans CONTRIBUTING + closed-PR history (already in place). |
| Blog pipeline writes generic AI-flavored posts | `writing-anti-ai` skill + manual review before `git push`. |
| Experiment loop destroys uncommitted work | `/exp-run` hard constraint: no `git reset --hard` on non-experiment commits. |
| Cron floods API quotas | Intervals: 60m / 150m / 240m / 720m — capped at 5 simultaneous subagents in Hermes config. |
| Credentials leak in logs | `security-guard.js` hook scans write/edit ops; `.env` gitignored. |
| Methodology skills arrive and don't fit the stock placeholder | No placeholder exists — we wait for the user to hand them over before wiring anything. |

---

## 10. Review Cadence

- **Weekly** (Sunday): glance over section 5 — does "current state" still match reality?
- **Monthly**: update section 4 (Google ecosystem) — which services moved from planned → wired?
- **On each major user directive**: revise sections 6–7 before acting.
