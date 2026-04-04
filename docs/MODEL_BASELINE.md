# OpenClaw 模型配置基线（V3）

本文档用于固定当前 V3 策略：`Step 为核心主链路`，`MiniMax 为专长侧路`。

## 1) Main Agents（核心链路）

- 适用对象：`lacia` / `methode` / `kouka` / `snowdrop` / `satonus`
- 统一模型：`stepfun/step-3.5-flash`
- 目标：降低 5 Main Agent 跨会话漂移，保证 Harness 可复现性。

## 2) ClaudeCode AgentTeams（并行构建链路）

- 适用对象：`team-feature` / `team-debug` / `team-review` / `team-spawn`
- 统一模型：`Kimi K2.5`
- 落地方式：
  - `~/.claude/settings.json`: `ANTHROPIC_MODEL = "kimi k2.5"`
  - AgentTeams 角色统一 `model: inherit`

## 3) RawCli Lane（外部工具链）

- `ClaudeArchitectCli`: `opus-4.6`
- `ClaudeBuildCli`: `kimi k2.5`
- `CodexReviewCli`: `gpt-5.3-codex`（`reasoning=high`）
- `SearchCli`: `MiniMax-M2.7`
- `GeminiResearchCli`: `gemini-3.1-pro-preview`

说明：Search 走 `SearchCli(MiniMax-M2.7)`，内置 web search 保持禁用避免冲突。

## 4) MiniMax 技能混用策略

- Snowdrop（研究侧）：
  - `minimax-multimodal-toolkit`
  - `minimax-pdf`
- Kouka（发布/文档侧）：
  - `minimax-docx`
  - `minimax-pdf`
  - `minimax-xlsx`
  - `pptx-generator`

约束：MiniMax 技能只作为专长侧路，不替代 Step 主推理链。

## 5) Heartbeat 与稳定性

- Main Agents Heartbeat：`30m`
- 核心指标：`cycle_success_rate`、`task_value_score`、`false_pass_rate`
