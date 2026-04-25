# Research Paradigm — Phase 2 Complete (Dev Commands + Verification)

**Created**: 2026-04-25
**Owner**: CrepuscularIRIS
**Supersedes / extends**: `2026-04-24-research-constitution-paradigm-phase-1.md`
**Status**: Phase 2 shipped — 4 thin dev commands, rgmare-lite git-tracked, end-to-end skeleton verified

---

## 0. What Phase 2 was

Per yesterday's handoff (§5): write the minimal dev-command set replacing what was deprecated, init `rgmare-lite/` as a real git repo, and dry-run the Phase 1 skeleton end-to-end to confirm the wiring works.

---

## 1. What shipped

### 1.1 Four new thin commands (all ≤30 lines, all read paradigm doc)

| Command | Lines | Role | Replaces |
|---|---|---|---|
| `/paradigm` | 22 | read-only opener for the canonical doc + active constitution YAML | (new) |
| `/plan` | 21 | wraps `planning-with-files:plan`; auto-detects research context | `deprecated:plan` |
| `/commit` | 30 | Conventional Commits + R4 gate (test feedback can't leak into training) | `deprecated:commit` |
| `/verify` | 32 | wraps `superpowers:verification-before-completion`; research-context R3/R7/R10 extras | `deprecated:verify` |

### 1.2 rgmare-lite is now a git repo

- `git init -b main` at `/home/lingxufeng/research/rgmare-lite/`
- Identity: `CrepuscularIRIS <serenitygp@qq.com>` (matches Beatless config)
- Initial commit: `52a0e7d init: research paradigm v0.1.0 + constitution v0.1.0` (392 insertions, 2 files)
- `.git/` clean, only `main` branch, no untracked files

### 1.3 End-to-end dry-run verified

Ran `/research-bootstrap test-20260425` manually per spec, confirmed:

- ✅ Branch `research/test-20260425` created.
- ✅ TSV header byte-exact match to `autoresearch/program.md` spec (`commit\tval_bpb\tmemory_gb\tstatus\tdescription`, tab-separated, verified with `cat -A`).
- ✅ `decision_trace.jsonl` exists, empty (0 lines), writable.
- ✅ `sprint.yaml` correctly pins `constitution_version: v0.1.0` and lists all 9 active niches.
- ✅ `/research-status` simulation parses all artifacts cleanly, reports `0 kept, 0 discarded, 0 crashed` without crash on empty inputs.
- ✅ `/research-constitution --view` simulation renders all 12 rules (R1–R12), `review_chain:` block (3 passes, 3 model families), and 9 niche specs.

Test sprint torn down after verification: branch deleted, `ledgers/test-20260425/` removed, `ledgers/` directory removed. rgmare-lite back to pristine `main` with only the initial commit.

---

## 2. Active command surface (current state)

```
~/.claude/commands/
├── paradigm.md            (Phase 2)
├── plan.md                (Phase 2)
├── commit.md              (Phase 2)
├── verify.md              (Phase 2)
├── research-bootstrap.md  (Phase 1)
├── research-parallel.md   (Phase 1)
├── research-loop.md       (Phase 1)
├── research-review.md     (Phase 1)
├── research-status.md     (Phase 1)
├── research-constitution.md  (Phase 1)
└── deprecated/            (84 files preserved, accessible as deprecated:*)
```

10 active commands, ~400 lines total. Down from 51 / 7889 lines pre-pivot.

---

## 3. Tomorrow's tasks (2026-04-26) — Phase 3

### 3.1 Decide: baselines now, or PR/content commands first?

Two reasonable paths from here. Need user to pick before we proceed.

**Path A — baselines (Pratical.md §第七 第一阶段):**
1. Fork `automated-w2s-research` into `rgmare-lite/` as a subtree or sibling.
2. `uv sync` in the fork. Run `python scripts/prepare_data.py` to materialize the 23MB labeled dataset.
3. Run all 5 baselines (`vanilla_w2s`, `critic`, `ue_zeroshot`, `ue_fewshot`, `train_only_on_confident_labels`) with seeds 42–46.
4. Collect baseline TSV → confirm `evaluate_predictions` Flask oracle works as PGR ground truth.
5. This is what unlocks `/research-loop` actually running real experiments.

**Path B — PR/content commands:**
1. Write `/pr` (thin wrapper over the deprecated `/github-pr` heterogeneous-review pattern).
2. Write `/sessions` (session continuity / handoff).
3. Optional: lightweight `/blog-note` for the Hermes Agent stage-3 blog-writing role.

**My recommendation: Path A.** The whole point of Phase 1+2 was to make the experiment loop runnable. We've never actually run an experiment under the new paradigm. Path B is paperwork; Path A is the proof.

### 3.2 Whichever path: also do these small items

- Move `2026-04-24-research-constitution-paradigm-phase-1.md` mention from "current" to "phase complete" in any cross-referencing doc.
- Verify the deprecated-namespace commands still work if invoked (`deprecated:tdd`, `deprecated:rebuttal` etc.) — confirms the move didn't break anything.
- Stretch: `/home/lingxufeng/research/rgmare-lite/README.md` — one-screen index of paradigm + constitution + commands.

### 3.3 Phase 3 explicit non-goals

- Do NOT write `/tdd` or `/code-review` (they were deferred to "later" — research-review covers research, /commit + /verify cover dev).
- Do NOT amend constitution (still v0.1.0; first amendment after we have real experimental data).
- Do NOT touch Zotero pipeline (still Phase 4+).

---

## 4. Open questions parked for tomorrow

1. **Path A vs Path B** (see §3.1).
2. **Fork strategy for automated-w2s-research:** subtree, submodule, or sibling clone? Subtree gives us one repo (cleaner); sibling keeps upstream pulls easy.
3. **Where do baseline TSV ledgers live?** `rgmare-lite/ledgers/baseline/results.tsv` or upstream-style `automated-w2s-research/results.tsv`?

---

## 5. Cross-references

| Doc | Path |
|---|---|
| Phase 1 handoff | `~/claw/Beatless/plan/2026-04-24-research-constitution-paradigm-phase-1.md` |
| Paradigm doc | `/home/lingxufeng/research/rgmare-lite/plan/research-paradigm.md` |
| Constitution v0.1.0 | `/home/lingxufeng/research/rgmare-lite/contracts/constitution.v0.1.0.yaml` |
| Active commands | `~/.claude/commands/{paradigm,plan,commit,verify,research-*}.md` (10 files) |
| Pratical.md | `/home/lingxufeng/research/Report/Pratical.md` |
| Deprecated.md | `/home/lingxufeng/research/Report/Deprecated.md` |
| Idea.md (8 directions) | `/home/lingxufeng/research/automated-w2s-research/Idea.md` |
| Karpathy program.md | `/home/lingxufeng/research/autoresearch/program.md` |

---

_Phase 1 = paradigm + constitution + 6 research commands._
_Phase 2 = 4 dev commands + git-tracked rgmare-lite + skeleton verified._
_Phase 3 = baselines (recommended) OR PR/content commands. Pick at start of next session._
