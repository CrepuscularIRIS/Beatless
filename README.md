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
- `docs/01-beatless-architecture-blueprint.md`: 完整架构蓝图（角色分工、状态机、长时任务策略）
- `docs/02-skills-configuration-and-usage.md`: Skills 配置与调用手册（安装、同步、验证、故障）
- `docs/03-test-and-acceptance-checklist.md`: 测试与验收清单（可直接按项执行）
- `docs/04-parallelism-and-delivery-fallback.md`: 并行机制与飞书回执降级策略
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

## Beatless Runtime (Edict Replacement)

This repo now includes an OpenClaw bootstrap script that provisions a full Beatless runtime:

- Core roles: `lacia` (planner), `methode` (executor)
- Mode labels (non-resident): `emergency` (Kouka strategy), `explore` (Snowdrop strategy), `review` (Satonus strategy)
- Helper runtimes: `codex-builder`, `gemini-researcher`, `claude-architect`
- Shared task ledger: `~/.openclaw/beatless/TASKS.yaml`
- Feishu binding switched to `lacia`
- Edict agent list disabled from active routing (config is backed up automatically)

### One-command setup

```bash
bash /home/yarizakurahime/claw/Beatless/scripts/setup_openclaw_beatless.sh
```

### What the setup script does

1. Backs up `~/.openclaw/openclaw.json`
2. Creates/updates Beatless workspaces under `~/.openclaw/workspace-*`
3. Installs role-specific `SOUL.md` + operational `AGENTS.md/HEARTBEAT.md/TOOLS.md`
4. Installs common Claw skills into each Beatless workspace
5. Replaces active `agents.list` with Beatless topology
6. Rebinds Feishu ingress to `lacia`

## Current Source

These files were imported from Opus output package:

- `/home/yarizakurahime/claw/Opus/files.zip`

## License

No license file has been defined yet. Add one before public redistribution.
