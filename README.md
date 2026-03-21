# Beatless (RawCli V2)

Beatless is a RawCli-first orchestration profile for OpenClaw.

## Architecture

- 5 core agents: `lacia`, `kouka`, `methode`, `satonus`, `snowdrop`
- 4 executor tools: `codex_cli`, `claude_generalist_cli`, `claude_architect_opus_cli`, `gemini_cli`
- Dispatch contract: `owner_agent + executor_tool`
- Runtime chain: Feishu ingress -> ACK -> dispatch queue -> tmux hook -> result -> schema-gated receipt

## Key Properties

- No wrapper-as-model ambiguity
- Raw CLI direct execution
- Fast ACK and evidence-backed final receipt
- Event-layer phrase templates (not Soul pollution)

## Repository Layout

- `docs/`: architecture, routing, validation, runtime hardening
- `souls/`: slim Soul definitions for 5 core agents
- `scripts/`: setup/bootstrap and operational scripts

Archived legacy docs are moved to `docs/_archived/`.

## Runtime Notes

- Source-of-truth routing: `~/.openclaw/beatless/ROUTING.yaml`
- Source-of-truth tools: `~/.openclaw/beatless/TOOL_POOL.yaml`
- Event phrases: `~/.openclaw/beatless/templates/event-phrases.yaml`

## Current Status

See [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md) and [TODO.md](./TODO.md).
DR closure mapping is tracked in [docs/13-dr-closure-status-20260321.md](./docs/13-dr-closure-status-20260321.md).
