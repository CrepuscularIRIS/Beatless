# Research Constitution Paradigm — Phase 1 Complete

**Created**: 2026-04-24
**Owner**: CrepuscularIRIS
**Supersedes / extends**: `2026-04-23-autonomous-research-os-roadmap.md`, `2026-04-23-personal-research-automation-system.md`
**Status**: Phase 1 shipped — commands + paradigm doc + constitution v0.1.0 in place

---

## 0. The pivot

From "prompt-as-main-engine methodology" (V5.2: 道/器/术/势, first-principles, devil's advocate, MVE, TACTIS) to **Research Constitution + Automated Research Ecology** — rules as *selection pressure*, multi-agent as *orthogonal variation*, verifiable eval as *natural selection*.

Canonical guide: `/home/lingxufeng/research/Report/Pratical.md`.
Deprecated V5.2 (now safety/falsification/logging layer only): `/home/lingxufeng/research/Report/Deprecated.md`.

**Rules are selection pressures, not workflow steps.** "Any complexity must be beaten by a simpler solution first" ✓. "Read papers → formulate hypothesis → write code" ✗.

---

## 1. What shipped today

### 1.1 Anchor files (single source of truth)

| Path | Purpose | Size |
|---|---|---|
| `/home/lingxufeng/research/rgmare-lite/plan/research-paradigm.md` | 12-section canonical doc every command reads first | ~290 lines |
| `/home/lingxufeng/research/rgmare-lite/contracts/constitution.v0.1.0.yaml` | 12 rules + review_chain + 9 niches as data | ~120 lines |

### 1.2 Six thin commands (all read anchors; no embedded logic)

| Command | Lines | Role |
|---|---|---|
| `/research-bootstrap <tag>` | 41 | new sprint: branch + TSV ledger + JSONL trace, pin constitution version |
| `/research-parallel` | 44 | dispatches ≤9 peer Sonnet 4.6 Task calls in ONE message; merges; flags R11 convergence |
| `/research-loop "<idea>"` | 56 | one 5-min experiment cycle: edit → commit → run → grep → keep-or-reset → R2/R3/R7 gates |
| `/research-review` | 55 | heterogeneous 3-pass: Codex 5.4-mini → Gemini 3.1-pro → Sonnet-4.6 red-team peer |
| `/research-status` | 59 | read-only dashboard: ledger tail, niche coverage, R11 entropy alert, pending reviews |
| `/research-constitution` | 42 | `--view` on Sonnet; `--amend` → Opus 4.7 (only hot-path Opus use) |

**Total active command surface: 297 lines** (down from 7889 = 96% reduction).

### 1.3 Old commands → deprecated

84 files moved to `~/.claude/commands/deprecated/` (51 top-level + 33 `sc/`). Nothing deleted. All still invocable under `deprecated:*` namespace if needed.

### 1.4 Memory updates

- `memory/feedback_model_routing.md` — 6-engine roster (Sonnet 4.6 mainhand, Opus 4.7 idea+regulations, Codex 5.4-mini review, 5.3-codex debug, Gemini 3-flash research, 3.1-pro dual-review, Hermes/Kimi later).
- `memory/project_research_constitution_paradigm.md` — paradigm shift fact with fork paths and execution-order lock.

---

## 2. Architectural invariants (enforced by the commands)

1. **No GPT reviews GPT.** Generator (Sonnet) → Pass 1 (Codex) → Pass 2 (Gemini) → Pass 3 (peer-branch Sonnet in fresh Task). Cross-family enforced by `constitution.yaml § review_chain`.
2. **Parallel thinking, no hierarchy.** `/research-parallel` refuses >9 branches and forbids nested spawning. Sonnet 4.6 peers only. AgentTeam P10/P9/P8/P7 hierarchy rejected as token-too-expensive.
3. **Constitution as data.** Rules live in YAML with `gate_at:` field — commands check only the rules for their phase, not all 12 at every step.
4. **Single mutable file + 5-min budget + TSV ledger** (Karpathy `autoresearch/program.md` discipline).
5. **NEVER STOP** once `/research-loop` starts. No "should I continue?" prompts.
6. **Phase order locked**: commands (done) → baselines (next) → Zotero (later).

---

## 3. The 12-rule Constitution (summary)

Canonical: `contracts/constitution.v0.1.0.yaml`. Summary:

1. Score ≠ discovery; transferable mechanism is.
2. Complexity guilty until ablation proves necessity.
3. Report seed distribution, not just best.
4. Test feedback cannot become training signal.
5. Mechanism must validate on >1 dataset.
6. Must explain why weak supervision fails but this doesn't.
7. Any improvement comes with a failure condition.
8. Agents free to change direction; must leave decision trace.
9. Compress explanations, don't stack tricks.
10. If score and explanation conflict, suspect the score.
11. Agent convergence → raise exploration temperature or reassign.
12. Low-performing directions with clear failure signals get a diagnostic chance.

---

## 4. Nine orthogonal niches

`paper-filter`, `prior-elicitor` (UE), `noisy-channel` (EM), `data-reweighter`, `distiller`, `gradient-free-evolver`, `interpretability`, `red-team`, `theory-compressor`. Directions fuzzy; goals sharp; forbidden behaviors explicit (see YAML).

---

## 5. Tomorrow's tasks (2026-04-25)

### 5.1 Phase 2 — dev-loop command set (thin replacements for deprecated)

Minimal rewrite of essential dev commands — same thin-pointer pattern. Each ≤30 lines.

| New command | Replaces | Role |
|---|---|---|
| `/plan` | `deprecated:plan` | `planning-with-files:plan` wrapper with research-paradigm hook |
| `/commit` | `deprecated:commit` | Conventional Commits + pre-commit constitution check (R4 specifically) |
| `/verify` | `deprecated:verify` | `superpowers:verification-before-completion` wrapper |

Target: three 25-line files. Decision needed before writing: do we also need `/tdd` / `/code-review` in Phase 2, or let those stay deprecated until Phase 3?

### 5.2 Dry-run Phase 1 in a scratch sprint

Actually execute `/research-bootstrap test-20260425` end-to-end. Verify:

- [ ] Sprint YAML created with correct constitution version pinned.
- [ ] TSV header row exactly matches `autoresearch/program.md` spec (`commit\tval_bpb\tmemory_gb\tstatus\tdescription`).
- [ ] `decision_trace.jsonl` exists and is writable.
- [ ] `/research-status` correctly reads empty ledger and reports 0/0/0 counts without crashing.
- [ ] `/research-constitution --view` renders all 12 rules and the review_chain correctly.

Do NOT dispatch `/research-parallel` yet — that consumes 9 Sonnet contexts. Save for Phase 3 once Phase 2 ergonomics are proven.

### 5.3 Initialize `rgmare-lite/` as git repo

```bash
cd /home/lingxufeng/research/rgmare-lite
git init -b main
git add plan/ contracts/
git commit -m "init: research paradigm v0.1.0 + constitution v0.1.0"
```

Enables `/research-bootstrap` to branch off cleanly.

### 5.4 Stretch (only if 5.1-5.3 finish early)

- Draft Phase 3 plan: PR/content/meta commands (`/pr`, `/paradigm`, `/sessions`).
- Write one "golden path" README at `/home/lingxufeng/research/rgmare-lite/README.md` that indexes the paradigm doc, constitution, and the 6 commands.

### 5.5 Explicit non-goals for tomorrow

- Do NOT reproduce `automated-w2s-research` baselines — that's Phase 4+.
- Do NOT touch Zotero → Obsidian pipeline — that's Phase 5+.
- Do NOT amend constitution (stay on v0.1.0 until we have real data to force a rule revision).

---

## 6. References

| Doc | Path |
|---|---|
| Paradigm doc (canonical) | `/home/lingxufeng/research/rgmare-lite/plan/research-paradigm.md` |
| Constitution v0.1.0 | `/home/lingxufeng/research/rgmare-lite/contracts/constitution.v0.1.0.yaml` |
| Active commands | `~/.claude/commands/research-*.md` (6 files) |
| Deprecated commands | `~/.claude/commands/deprecated/` (84 files) |
| Pratical.md (current paradigm source) | `/home/lingxufeng/research/Report/Pratical.md` |
| Deprecated.md (old V5.2 source) | `/home/lingxufeng/research/Report/Deprecated.md` |
| Idea.md (8 research directions) | `/home/lingxufeng/research/automated-w2s-research/Idea.md` |
| Karpathy autoresearch discipline | `/home/lingxufeng/research/autoresearch/program.md` |
| Model routing memory | `~/.claude/projects/-home-lingxufeng-claw/memory/feedback_model_routing.md` |
| Paradigm memory | `~/.claude/projects/-home-lingxufeng-claw/memory/project_research_constitution_paradigm.md` |

---

## 7. Open questions (for tomorrow's decision)

1. **`/tdd` and `/code-review` in Phase 2 or Phase 3?** Arguments both ways — TDD is daily dev, but code-review is covered by `/research-review` pattern for research work.
2. **Should `research-paradigm.md` also live as a symlink inside Beatless** for version-tracked evolution, or stay as source of truth only inside `rgmare-lite/`? (Current: only in rgmare-lite, Beatless just holds the handoff docs.)
3. **When Phase 2 dev commands land, do we want a `/paradigm` command** that opens the paradigm doc for reading, or is it enough that every research command already reads it?

---

_End of Phase 1 handoff. Tomorrow: Phase 2 (dev commands) + dry-run verification._
