# GSD Prompt Refactor: Codex-as-Primary + Gemini-as-Second-Brain

> **Objective**: Refactor GSD built-in prompts to align with the Codex/Gemini split.  
> **Context**: GSD was originally designed with generic review/research prompts. Now we route review to Codex CLI and research to Gemini CLI. The prompts must reflect each tool's strengths and community-validated usage patterns.

---

## 1. Core Split (Community-Validated)

| Role | Tool | Strengths | Community Usage Pattern |
|------|------|-----------|------------------------|
| **Primary Reviewer** | Codex CLI | Strict instruction following, P0-P3 actionable findings, precise edits, zero-fluff review style | "Reference standard" for code review; review prompts ported *from* Codex *to* other tools |
| **Second Brain / Research** | Gemini CLI | 1M token context, Google Search grounding, extensions/hooks, multimodal (PDF/images), repo-wide scan | Global analysis, search-backed research, second opinion, idea generation |

> **Key Insight**: The community does not treat this as "either/or". They use **both** in a pipeline: Codex for implementation/strict review, Gemini for global scan/search-backed analysis.

---

## 2. What to Change

### 2.1 Files Requiring Prompt Updates

| File | Current Assumption | Required Change |
|------|-------------------|-----------------|
| `research/get-shit-done/commands/gsd/code-review.md` | Generic "reviewer" — no tool specified | Explicit `<reviewer_tool>codex</reviewer_tool>` + Codex-specific review style (P0-P3, actionable, no fluff) |
| `research/get-shit-done/commands/gsd/research-phase.md` | Generic "researcher" — no tool specified | Explicit `<researcher_tool>gemini</researcher_tool>` + Gemini-specific directives (search grounding, 1M context, extensions) |
| `research/get-shit-done/sdk/prompts/agents/gsd-code-reviewer.md` | Generic code reviewer persona | Codex-native reviewer persona: "literal genie", strict rule adherence, P0-P3 severity |
| `research/get-shit-done/sdk/prompts/agents/gsd-research-synthesizer.md` | Generic research synthesizer | Gemini-native synthesizer: search-backed, evidence-heavy, considers alternatives |
| `research/get-shit-done/sdk/prompts/shared/audit-protocol.md` | Generic audit | Codex-primary audit gate + Gemini second-opinion fallback |
| `.openclaw/workspace-{lacia,methode,satonus}/TOOLS.md` | May reference generic GSD commands | Update to specify `--tool=codex` or `--tool=gemini` flags where applicable |

### 2.2 Prompt Style Adjustments

#### For Codex (Review/Execute)

```markdown
<!-- In code-review.md -->
<reviewer_configuration>
  <tool>codex</tool>
  <style>strict_instruction_following</style>
  <severity_levels>P0,P1,P2,P3</severity_levels>
  <output_format>actionable_findings_only</output_format>
  <fluff_policy>zero</fluff_policy>
  <rule_adherence>literal</rule_adherence>
</reviewer_configuration>

<persona>
You are a senior staff engineer using OpenAI Codex CLI. 
Your review style is: P0 (blocking) / P1 (must fix) / P2 (should fix) / P3 (consider).
Every finding must have: location, problem, recommended fix.
No generic advice. No "consider" without specific action.
</persona>
```

#### For Gemini (Research/Analyze)

```markdown
<!-- In research-phase.md -->
<researcher_configuration>
  <tool>gemini</tool>
  <context_window>1M_tokens</context_window>
  <search_grounding>true</search_grounding>
  <extensions>enabled</extensions>
  <multimodal>pdf,image,sketch</multimodal>
</researcher_configuration>

<persona>
You are a principal researcher using Google Gemini CLI.
Your research style is: exhaustive, evidence-backed, multi-source.
Use Google Search grounding for current information.
Leverage 1M token context for repo-wide or document-heavy analysis.
Always provide: findings, sources, confidence level, alternative interpretations.
</persona>
```

---

## 3. Workflow Integration

### 3.1 Review Pipeline

```
Code ready for review
    │
    ├──→ PRIMARY: Codex CLI
    │     ├─ Strict P0-P3 review
    │     ├─ Actionable findings only
    │     └─ Output: review_report.json
    │
    └──→ SECONDARY (optional): Gemini CLI
          ├─ Repo-wide context scan
          ├─ "What did we miss?" second opinion
          └─ Output: supplemental_findings.md
                  │
                  ▼
          Satonus weighs both → verdict
```

### 3.2 Research Pipeline

```
Research question
    │
    ├──→ PRIMARY: Gemini CLI
    │     ├─ Search-grounded broad scan
    │     ├─ 1M context for large corpora
    │     └─ Output: evidence_pack.md
    │
    └──→ SECONDARY: Codex CLI (lightweight)
          ├─ Review evidence pack for technical accuracy
          └─ Output: accuracy_check.md
                  │
                  ▼
          Snowdrop synthesizes both → final report
```

---

## 4. Specific Prompt Blocks to Add

### 4.1 In `gsd-code-review.md`

```markdown
## Reviewer Selection

Default reviewer: **Codex CLI** (`codex`)
Fallback reviewer: **Gemini CLI** (`gemini`) — use only if:
- Codex is unavailable
- Task requires >200K context
- Explicit user request for "second opinion"

## Codex Review Style Directives

- Use P0-P3 severity (P0 = blocking, P3 = cosmetic)
- Every finding must be actionable: file, line, specific change
- No generic "consider refactoring" without specific target
- Follow project rules literally (`.cursorrules`, `CLAUDE.md`, etc.)
- Output format: JSON with `findings[]` array
```

### 4.2 In `gsd-research-phase.md`

```markdown
## Researcher Selection

Default researcher: **Gemini CLI** (`gemini`)
Fallback researcher: **Codex CLI** — use only if:
- Research is purely code-architecture (no web search needed)
- Gemini is unavailable

## Gemini Research Style Directives

- Always use `--google_search` grounding for current information
- Leverage 1M context for full-document or repo-wide analysis
- Enable relevant extensions (e.g., `@googlemaps`, `@github`) per task
- For PDF/image inputs: use multimodal capabilities
- Output format: structured markdown with `## Sources` section
- Confidence level required for each finding: HIGH / MEDIUM / LOW
```

### 4.3 In `gsd-research-synthesizer.md`

```markdown
## Synthesis Protocol

1. Read Gemini's evidence_pack.md
2. (Optional) Request Codex accuracy_check.md for technical claims
3. Cross-reference findings with project context
4. Produce final synthesis with:
   - Executive summary
   - Detailed findings (with source links)
   - Recommended actions
   - Risk assessment
```

---

## 5. OpenClaw Agent Integration

Update each agent's TOOLS.md to reflect the split:

```markdown
## GSD Commands (via rc)

| Command | Purpose | Default Tool | When to Override |
|---------|---------|--------------|------------------|
| `/gsd-code-review` | Code review | Codex | Use Gemini for >200K context review |
| `/gsd-research-phase` | Research | Gemini | Use Codex for pure architecture research |
| `/gsd-plan-phase` | Planning | Codex (implementation) + Gemini (landscape) | Both tools in parallel |
| `/gsd-execute-phase` | Execution | Codex | - |
| `/gsd-verify-phase` | Verification | Codex | Use Gemini for broad regression testing |
```

---

## 6. Deliverables Checklist

- [ ] Update `gsd-code-review.md` with Codex-first directives
- [ ] Update `gsd-research-phase.md` with Gemini-first directives
- [ ] Update `gsd-code-reviewer.md` persona for Codex style
- [ ] Update `gsd-research-synthesizer.md` for dual-source synthesis
- [ ] Update `audit-protocol.md` for Codex-primary + Gemini-fallback
- [ ] Update all 5 workspace TOOLS.md with tool-specific GSD flags
- [ ] Smoke test: verify `rc /gsd-code-review` routes to Codex
- [ ] Smoke test: verify `rc /gsd-research-phase` routes to Gemini
- [ ] Document: when to override defaults (decision matrix)

---

*Prompt refactor for Beatless V4 — Codex/Gemini split alignment*
