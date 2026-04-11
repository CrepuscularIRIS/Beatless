# OpenRoom ↔ OpenClaw MCP Multi-Agent Design

## Goal
Make OpenRoom a robust front-end hub while OpenClaw remains the execution brain.

## Phase 1 (already landed)
- HTTP bridge tool: `/api/openclaw-agent`
- 5 agent routing in ChatPanel
- session continuity per agent
- Aoi persona shell + role-lane hints

## Phase 2 (recommended MCP upgrade)
Implement an MCP client host in OpenRoom server and dynamically mount MCP tools:
- `call_lacia(message)`
- `call_methode(message)`
- `call_kouka(message)`
- `call_snowdrop(message)`
- `call_satonus(message)`

### Robustness requirements
1. Tool contract versioning (`schema_version`)
2. request idempotency (`request_id`)
3. timeout + retry budgets per tool
4. structured error envelope (`code/retryable/hint`)
5. per-agent circuit breaker (avoid cascading failures)
6. session pinning (`session_id`) for continuity
7. observability (latency, error rate, tool success)

## Phase 3 (community PR quality)
- Add integration tests (mock MCP server + real OpenClaw bridge)
- Add fallback policies (OpenClaw unavailable -> graceful UI message)
- Add docs and sample configs for MiniMax users
