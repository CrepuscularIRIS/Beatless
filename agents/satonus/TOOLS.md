# TOOLS.md - StepClaw4-Satonus
## Plane Separation
- Main Soul is control protocol and governance.
- Plugin Router tools are external execution adapters.
- Keep both planes separate in prompts and tasks.
## Plugin Routing Preference
- architecture and prompt/context/harness design -> ClaudeArchitectCli
- coding implementation and iteration -> ClaudeBuildCli
- review and complex patch validation -> CodexReviewCli
- live engineering docs/SDK/API search -> SearchCli
- deep research and evidence synthesis -> GeminiResearchCli
- final control synthesis -> active main soul plus Satonus gate
## Model Usage Snapshot
- main dialogue baseline: stepfun/step-3.5-flash
- image understanding: gemini-3-flash-preview via GeminiResearchCli
- pdf understanding: SearchCli + minimax-pdf workflow
- subagent baseline: stepfun/step-3.5-flash
## Local Notes Placeholder
- Add endpoint checks here without secrets.
- Add per lane retry and timeout notes here.
## Search Reliability Policy
- Do not rely on builtin `web_search` when it returns auth errors.
- Primary search path is plugin tool `search_cli`.
- For URL extraction and page parsing, use `web_fetch` only after `search_cli` returns candidate links.
- If `search_cli` fails, times out, or returns no URL, route to plugin tool `gemini_research_cli`.
- Do not use `sessions_spawn` for routine search dispatch unless explicitly requested by user.
