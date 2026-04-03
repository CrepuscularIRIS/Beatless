# Beatless (OpenClaw 5-MainAgent Baseline)

This repository is reset to the new Beatless baseline aligned with the live OpenClaw runtime.

## Baseline Scope
- 5 Main Agents: `lacia`, `methode`, `kouka`, `snowdrop`, `satonus`
- Main model baseline: `stepfun/step-3.5-flash`
- External lanes (via rawcli router plugin):
  - `claude_architect_cli` (Opus 4.6)
  - `claude_build_cli` (Kimi K2.5)
  - `codex_review_cli` (GPT-5.3-Codex)
  - `search_cli` (MiniMax M2.7)
  - `gemini_research_cli` (Gemini 3.1 Pro Preview)

## Directory
- `agents/<id>/` : exported workspace contracts (`AGENTS.md`, `SOUL.md`, `TOOLS.md`, etc.)
- `config/openclaw.redacted.json` : runtime config snapshot with secrets removed
- `config/cron.jobs.snapshot.json` : current cron automation snapshot
- `config/agents.snapshot.json` : current agent list snapshot
- `docs/` : acceptance and OpenRoom integration design
- `scripts/validate_baseline.py` : CI validation

## CI
`beatless-baseline-validate` checks:
1. all 5 agents exist
2. key contract files exist
3. redacted config is parseable and includes 5-agent list
4. cron snapshot is parseable
