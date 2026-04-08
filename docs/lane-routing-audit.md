# Lane Configuration and Routing Audit Report

**Date:** 2026-04-07
**Scope:** Beatless Phase 2 Task A (5 MainAgents + Core Lanes)

## 1. MainAgent AGENTS.md Configuration Consistency
**Status:** ✅ Consistent

All 5 MainAgents (`kouka`, `lacia`, `methode`, `satonus`, `snowdrop`) have been audited. Their `AGENTS.md` files maintain strict architectural boundaries between the Main Control Plane and Execution/Data Plane. 

The `Plugin Logical Tools (execution only)` block is identical across all 5 agents:
- `ClaudeArchitectCli`: architecture design and prompt/context/harness engineering
- `ClaudeBuildCli`: day-to-day coding implementation and delivery
- `CodexReviewCli`: code review, difficult patching, and second-opinion checks
- `SearchCli`: engineering documentation and live technical search
- `GeminiResearchCli`: research, brainstorming, and evidence synthesis

*Note:* Lacia's configuration includes an expected supplementary `Search Dispatch Contract (strict)` as the primary dispatcher, which does not conflict with the base lane definitions.

## 2. Core Lane Routing Validation
**Status:** ✅ Validated

Routing is strictly enforced via the `openclaw-rawcli-router` plugin (`.openclaw/extensions/openclaw-rawcli-router/index.js`) and aligns with the `MODEL_BASELINE.md` specification.

### ClaudeArchitectCli
- **Backend:** `claude` (via local CLI)
- **Model:** `opus-4.6`
- **Validation Steps:** The router intercepts the `claude_architect_cli` tool call, injects the orchestration mode prompt (`AgentTeam-oriented orchestration mode`), and invokes the `claude` executable with the `--model opus-4.6` flag.
- **Exception Handling:** In the event of a crash or empty output, it captures `stderr` and propagates an explicit error format (`LANE=claude_architect_cli\nERROR=...`) back to the agent. Timeout is strictly enforced.

### ClaudeBuildCli
- **Backend:** `claude` (via local CLI)
- **Model:** `kimi k2.5`
- **Validation Steps:** Routed to the `claude` executable using the implementation worker prompt. The `kimi k2.5` model parameter is passed successfully. 
- **Exception Handling:** Reuses the same robust error capture and buffer overflow protection (max 8MB) as the architect lane.

### CodexReviewCli
- **Backend:** `codex` (via local CLI) / Fallback: `minimax`
- **Model:** `gpt-5.3-codex` (Reasoning: `high`)
- **Validation Steps:** Intercepts `codex_review_cli`. Spawns `codex exec` with the `--search` flag disabled by default, explicitly setting `-c model_reasoning_effort="high"`.
- **Exception Handling:** If `codex` fails with a recoverable error (e.g., `payment required`, `deactivated_workspace`, `model is not supported`), the router automatically falls back to `minimax-review-agent` using the `MiniMax-M2.7` model via the REST API to guarantee review continuity.

### GeminiResearchCli
- **Backend:** `gemini` (via local CLI)
- **Model:** `gemini-3.1-pro-preview`
- **Validation Steps:** Invokes `gemini --yolo` with the research-specific prompt focused on iterative retrieval and evidence synthesis.
- **Exception Handling:** Built-in array of fallbacks (`gemini-2.5-pro`, `gemini-3-flash-preview`). If the primary model times out or errors, it cascades through the fallback list before throwing an error to the dispatcher.

## 3. Runtime Routing Correctness
**Status:** ✅ Confirmed (No Misrouting)

- The router strictly maps abstract tool calls (`claude_architect_cli`, etc.) to their specific subprocess executions.
- `process.env` boundaries are respected.
- Buffer overflow protections (8MB limits) and timeouts (default 240s) are securely implemented to prevent runaway CLI processes.
- No bleeding of roles: Prompts injected at the router level strictly enforce the persona for each lane (e.g., GeminiResearchCli is instructed to "use iterative retrieval and evidence-first synthesis").

## 4. Recommendations
1. **Tool Naming Alignment:** There is a slight case difference between the abstract documentation names (`ClaudeArchitectCli`) and the actual JSON schema tool names (`claude_architect_cli`). The router handles this via mapping, but updating `TOOLS.md` to reflect the snake_case tool names might reduce LLM hallucination risks.
2. **Review Lane Fallback:** The CodexReviewCli fallback to MiniMax is robust, but consider alerting the user when the fallback is triggered so the Codex workspace/billing issues can be addressed proactively.
