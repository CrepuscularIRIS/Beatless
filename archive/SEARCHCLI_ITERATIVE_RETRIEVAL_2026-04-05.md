# SearchCli Iterative Retrieval Profile (2026-04-05)

## 目标
- 修复 OpenRoom 场景下 SearchCli 偶发“无回包/长时间无显示”问题。
- 提升 SearchCli 检索深度：Iterative Search + Recursive Retrieval。

## 已实施
1. SearchCli Prompt 升级（插件内默认）
- 文件：`~/.openclaw/extensions/openclaw-rawcli-router/index.js`
- 策略：
  - Round 1：广覆盖搜集候选来源
  - Round 2：递归下钻关键主张到一手来源
  - Round 3：冲突校验与不确定性标记
- 输出结构强化：结论 / 证据链 / 来源链接 / 冲突与不确定性 / 下一步建议。

2. SearchCli 解析鲁棒性增强
- 扩展 MiniMax 返回文本提取逻辑，兼容 `output_text`、`choices[].message.content`、`content[].text` 多种形态。
- 降低“空响应但实际返回存在”的概率。

3. 架构对齐
- `Beatless/config/openclaw.redacted.json` 已与运行态对齐：
  - `openclaw-openroom-bridge.config.baseUrl` -> `http://127.0.0.1:3001`

## 运行注意
- 插件新增行为走“插件内部默认值”，不向 `openclaw.json` 添加额外字段（避免 schema 校验失败）。
- SearchCli 仍由 `search_cli` lane + MiniMax M2.7 驱动。

## 验收结果（本地）
- `openclaw gateway health`：OK
- `openclaw agent -> lacia -> search_cli`：可返回结构化结果
- `OpenRoom /api/openclaw-agent`：可收到 SearchCli 结果并回显
