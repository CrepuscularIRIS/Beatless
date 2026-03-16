# Beatless Soul Pack for OpenClaw

This repository contains a multi-Soul configuration derived from the five Beatless hIE models, rewritten for practical OpenClaw usage.

## Purpose

This pack is designed as an engineering-ready Soul set, not roleplay content.

- Preserve persona differences and decision philosophy
- Remove destructive original goals
- Keep clear safety and operating boundaries
- Support long-term maintainability and refactoring

## Structure

- `docs/00-system-matrix.md`: system matrix, switching path, risks, shared base suggestions
- `souls/001-kouka/SOUL.md`: siege mode (short-term blocker removal)
- `souls/002-snowdrop/SOUL.md`: chaos mode (divergent branching only)
- `souls/003-satonus/SOUL.md`: order mode (structure, governance, durability)
- `souls/004-methode/SOUL.md`: execution mode (fast implementation)
- `souls/005-lacia/SOUL.md`: default mode (planning, integration, final convergence)

## Recommended Runtime Model

Use one active Soul per session. Suggested flow:

1. Start with `005-lacia` for scope, planning, and route design.
2. Switch to `004-methode` for fast delivery when scope is clear.
3. Switch to `003-satonus` when documentation, standards, or long-term maintenance is needed.
4. Use `001-kouka` only as temporary wartime mode, then switch back.
5. Use `002-snowdrop` only for branching ideas; converge outcomes through `005-lacia` or `001-kouka`.

## Integration Notes

For OpenClaw workspace integration, copy a chosen Soul file to your active workspace `SOUL.md`.

Example:

```bash
cp souls/005-lacia/SOUL.md ~/.openclaw/workspace/SOUL.md
```

If you maintain multiple agents, assign each Soul to a dedicated agent workspace and route tasks by mode.

## Current Source

These files were imported from Opus output package:

- `/home/yarizakurahime/claw/Opus/files.zip`

## License

No license file has been defined yet. Add one before public redistribution.
