# VNext Routing And Read Policy

## Read Layers
- START/CLOSE: read `USER_SOUL + MEMORY + TASKS`
- CHECK (normal): read `TASKS` only
- CHECK (review/blocked/escalation): add `MEMORY`
- CHECK (goal/priority conflict): add `USER_SOUL`

## Routing Tree
- casual chat/simple Q&A -> `lacia` direct reply
- quick search/screenshot/quick verify -> `kouka` (quick mode, timeout 300s)
- review queue non-empty -> `satonus`
- ready queue:
  - `mode=explore` -> `snowdrop` phase-A, then force phase-B dual search (`codex-builder` + `gemini-researcher`), then phase-C merge
  - `mode=emergency` -> `kouka`, escalate to experts if needed
  - daily engineering -> `claude-generalist`
  - complex code/open-source repro -> `codex-builder`
  - academic/theorem/math-physics -> `gemini-researcher`
  - architecture boundary/rollback -> `claude-architect-opus`
  - fallback -> `methode`

## Rebuttal Chain
- Trigger: hypothesis conflict or `needs_arbitration=true`
- Evidence pair: `codex-builder` (engineering/open-source) + `gemini-researcher` (theory/academic)
- Final arbitration: `satonus` with evidence citations

## Guardrails
- Keep user model/version strings exact; if no evidence, mark `UNVERIFIED`
- Research/news tasks must include absolute dates
- TASKS state update by scripts, not direct edit
