# Beatless — Autonomous Agent Constellation

Hybrid AI orchestration system for open-source contribution, technical blogging, and ML research. Hermes Agent handles scheduling and information gathering; Claude Code handles deep execution.

## Current State: Constellation v3

```
Hermes Agent (Kimi K2.6 orchestrator)
  ├── Cron: 4 active jobs
  │     ├── GitHub Response    — hourly PR comment triage
  │     ├── GitHub PR Pipeline — hourly issue discovery → full PR submission
  │     ├── Auto Research      — 4h experiment analysis cycles
  │     └── Blog Maintenance   — 12h content audit + writing (MiniMax M2.7)
  │
  ├── Models
  │     ├── Kimi K2.6      — orchestration, planning, review
  │     ├── Step 3.5 Flash — fast execution, tool chains, web search
  │     └── MiniMax M2.7   — writing, image gen, TTS, video, documents
  │
  └── Wake-gate scripts → Claude Code (on-demand)
        ├── /github-pr       — 12-phase PR pipeline with triple review
        ├── /pr-followup     — maintainer comment response
        └── /exp-*           — ML experiment lifecycle (see below)
```

## Experiment Command Pack (exp-*)

Five commands encoding a two-path research methodology for ML experiments:

| Command | Purpose |
|---------|---------|
| `/exp-status` | Workspace readiness diagnostic (GPU, data, plugins) |
| `/exp-init` | Initialize experiment branch, planning files, baseline run |
| `/exp-discover` | Generate hypotheses via idea-first or application-first path |
| `/exp-run` | Autonomous experiment loop (quick: single-GPU / full: dual-GPU A/B) |
| `/exp-review` | Multi-agent review with continue/pivot/rollback/halt verdict |

Integrates: Codex (code edits), Gemini (literature + direction review), Superpowers (brainstorming), GSD (verification), Planning-with-files (state persistence).

## PR Pipeline

12-phase process from issue discovery to PR submission:

1. Discover claimable issues (good first issue, help wanted, bug)
2. Evaluate repo (CONTRIBUTING.md, recent PRs, test infrastructure)
3. Fork, clone, baseline tests
4. Implement fix (Codex write-mode)
5. Triple review (Gemini correctness + Codex architecture + Claude quality gate)
6. Submit PR with evidence-based scoring

Quality controls: anti-inflation (no self-review), revert-test-reapply verification, minimum 7.5/10 score gate.

## Repository Structure

```
commands/exp/           # Active: exp-* command pack (903 lines)
design/                 # Architecture: CONSTELLATION v1 → v3 evolution
standards/              # PR guidelines, contribution protocols
pipelines/              # Active pipeline specs (github-pr.md, blog-maintenance.md)
docs/                   # HERMES integration, migration status
agents/aoi/             # Aoi — scheduler persona (SOUL.md)
archive/                # Deprecated v2 infrastructure
  ├── v2-deprecated/    #   Heartbeat agents, shell runners, harness scripts
  └── deprecated-commands/  #   research-analyze.md, research-train-loop.md
```

## Planned (Next Stages)

- **Aoi** — Digital persona on [OpenRoom](https://github.com/MiniMax-AI/OpenRoom) platform. Currently scheduler-only; planned evolution into embodied agent with visual presence.
- **OpenRoom Integration** — MiniMax-powered desktop environment for Aoi. Workspace, apps, real-time interaction.
- **Beatless Framework Rewrite** — Current repo serves as architecture documentation and archive. Future rewrite planned to consolidate the Hermes + ClaudeCode hybrid pattern into a clean framework.

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.10.0+ (gateway + cron)
- Claude Code CLI (`claude`) with Opus/Sonnet
- GitHub CLI (`gh`, authenticated)
- Codex and Gemini available as Claude Code plugins
- `uv` for Python, `pnpm` for JS/TS

## License

MIT
