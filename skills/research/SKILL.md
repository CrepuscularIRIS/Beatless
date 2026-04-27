---
name: research-workflow
description: "Master meta-router for the 7-stage research pipeline. Use when user discusses research at the workflow level — 'how do I start research', 'what's the research pipeline', 'I have a research idea, what's next', 'guide me through a research sprint', 'what stage am I at', 'is my sprint working', '我有个研究想法', '下一步该做什么', '研究流程'. Routes to the right /research-* command based on sprint state + user intent."
---

# research-workflow — meta-router for the 7-stage research pipeline

The user has 7 specialized research commands at `~/.claude/commands/research-*.md`. This skill is the **natural-language entry point** when the user describes research-shaped work without specifying a stage. Map intent → the right command.

## The 7-stage chain

```
0. /research-init <tag>          ← initialize sprint (creates branch + ledger + TODO chain)
1. /research-survey [topic]      ← Obsidian SOTA + Gemini Flash cross-domain mining + Codex novelty pre-screen
2. /research-axiom               ← Opus 4.7 first-principles distillation + hidden axiom enumeration
3. /research-propose             ← cross-product reframing + Codex novelty + Gemini challenger + 3-step MVE
4. /research-dispatch            ← parallel niche subagents (single-message peer Sonnet 4.6)
5. /research-loop "<idea>"       ← autoresearch experiment cycle (5min single-GPU + R3 seed + R7 failure + surface_implicit)
6. /research-review              ← triple-heterogeneous review (Codex correctness + Gemini challenger + Sonnet red-team)
                                 ↺ back to /research-dispatch for next cycle until SOTA / budget / BLOCK / human halt
```

Plus 2 admin commands:
- `/research-status` — read-only dashboard (ledger tail, niche coverage, entropy alert)
- `/research-constitution` — view/amend the 12-rule constitution (rare; Opus 4.7 for amend)

## Intent → command routing table

| User intent (paraphrased) | Sprint state required | Command to invoke |
|---|---|---|
| "Start research on X", "create new sprint" | NO active sprint | `/research-init <tag>` |
| "Survey literature on X", "what's been done in field Y" | sprint exists | `/research-survey [topic]` |
| "Apply first principles", "find hidden axioms" | survey done | `/research-axiom` |
| "Generate research proposal", "check novelty", "design MVE" | axioms done | `/research-propose` |
| "Dispatch parallel niches", "spawn 9 subagent branches" | proposals done | `/research-dispatch` |
| "Run experiment X", "try this idea on train.py" | dispatch done OR --standalone | `/research-loop "<idea>"` |
| "Audit kept result", "triple review", "red-team this" | results.tsv has keep row | `/research-review` |
| "Show me sprint status", "what stage are we at" | any | `/research-status` |
| "Edit the constitution", "view the 12 rules" | any | `/research-constitution` |

## Sprint-state detection (run BEFORE routing)

Before dispatching, check current state:

```bash
RGMARE_ROOT="${RGMARE_ROOT:-$HOME/research/rgmare-lite}"
CURRENT_BRANCH=$(git -C "$RGMARE_ROOT" branch --show-current 2>/dev/null)

# Has active sprint?
case "$CURRENT_BRANCH" in
  research/*)
    SPRINT_TAG="${CURRENT_BRANCH#research/}"
    SPRINT_DIR="$RGMARE_ROOT/ledgers/$SPRINT_TAG"
    test -f "$SPRINT_DIR/TODO.md" && grep -E '^\s*-\s*\[' "$SPRINT_DIR/TODO.md"
    ;;
  *)
    echo "no_active_sprint"
    ;;
esac
```

If `no_active_sprint` AND user intent is anything past stage 0 → route to `/research-init` first, ask for tag, THEN chain to user's intended stage.

## Hard rules (DO NOT violate)

1. **Don't skip stages.** If user asks for `/research-propose` but `axioms/axioms.md` is missing, route to `/research-axiom` first; explain why. Each command's HARD GATE will refuse anyway.

2. **Don't auto-chain past stage 6.** After `/research-review`, the user picks: continue cycling (back to dispatch) or halt. Never auto-advance without user signal — this is autoresearch's NEVER STOP discipline applies inside a single `/research-loop`, NOT across review verdicts.

3. **Honor halt conditions.** If `~/.hermes/shared/.research-halt` exists, OR last review verdict was BLOCK, OR results.tsv shows SOTA reached, refuse to advance. Surface to user.

4. **Don't bypass externalization gate.** Each command requires a `disclosure:` / `surface_implicit` block. If asked to skip it ("just give me the answer"), refuse — that's the load-bearing trust mechanism per user-directive 2026-04-27.

5. **Cron orchestration is separate.** The Hermes cron driver `~/.hermes/scripts/research-cycle.py` runs unattended every 360m. This skill is for INTERACTIVE invocations. Never modify cron state here.

## When to invoke vs decline

**Invoke when:**
- User describes research-shaped work (sprint, experiment, paper, proposal, axiom, novelty, review)
- User has a research workspace at `~/research/rgmare-lite/` or asks to create one
- User mentions any of the trigger keywords in this skill's description

**Decline (route to other skills) when:**
- User wants engineering code review → `codex:codex-rescue` or `gemini:gemini-consult`
- User wants to write a blog post about research → `blog-*` skills
- User wants to plan a non-research feature → `planning-with-files:plan` or `superpowers:writing-plans`
- User wants to debug a single training crash → `gsd:gsd-debug` or direct Claude work, NOT a full sprint

## Cross-tool routing

Within the research pipeline, the academic-mode wrappers handle external models:

- **Codex GPT-5.4** academic novelty / citation-verify / claim-vs-code-vs-numbers → `~/.hermes/skills/routing/codex-academic/`
- **Gemini 3.1 Pro / Flash** challenger feasibility / cross-domain mining / arxiv-probe → `~/.hermes/skills/routing/gemini-academic/`
- **Hermes cron** autonomous stage advance → `~/.hermes/skills/cron-jobs/research-cycle/`

The 7 commands invoke these wrappers internally; this skill should not call them directly.

## Anti-patterns

- ❌ DO NOT execute the entire 7-stage chain in one turn. Each stage has its own externalization + audit gate; skipping invocations defeats them.
- ❌ DO NOT invoke `/research-loop` without an active dispatch (or `--standalone`). It needs a niche-scoped proposal.
- ❌ DO NOT decide PASS / BLOCK on a kept experiment in this skill — that's `/research-review`'s job; here we only route.
- ❌ DO NOT explain to the user "this is what stage X does" — invoke the command, let its body explain via the user-visible output.
