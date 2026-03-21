# Beatless 当前架构（RawCli V2 + Soul Slim）

Updated: 2026-03-21 (Asia/Shanghai)

## 1. 总体形态
Beatless 当前采用「5 Core Agent + 4 RawCli Tool Pool + tmux dispatch hook」架构：
- 决策层：`owner_agent`
- 执行层：`executor_tool`

核心目标：避免 wrapper 嵌套，保证 RawCli 直连执行、快速 ACK、结构化回执。

## 2. Core Agent 层（任务所有权）
- `lacia`: 入口调度/收敛/回执
- `kouka`: 快速响应与应急止血
- `methode`: 日常开发执行与整合
- `satonus`: 评审与裁决
- `snowdrop`: 探索与发散控制

## 3. RawCli Tool Pool（执行层）
- `codex_cli`: 开源检索/复杂代码/疑难复现
- `claude_generalist_cli`: 日常前后端/API开发
- `claude_architect_opus_cli`: 架构边界/重构设计
- `gemini_cli`: 学术推理/第一性分析

兼容别名仍保留在 `TOOL_POOL.yaml`（如 `claude_opus_cli`），但新任务统一使用上述主名称。

## 4. 路由与调度合同
- 路由合同：`owner_agent + executor_tool`
- 工具定义 SSOT：`~/.openclaw/beatless/TOOL_POOL.yaml`
- 路由规则 SSOT：`~/.openclaw/beatless/ROUTING.yaml`
- 入队文件：`~/.openclaw/beatless/dispatch-queue.jsonl`
- 结果文件：`~/.openclaw/beatless/dispatch-results/<task_id>.json`

## 5. 运行时链路
1. Feishu 消息进入 `lacia`
2. 入口 ACK（两行）立即返回
3. `executor_tool != null` 时写入 dispatch queue
4. tmux hook 事件驱动执行 CLI（独立 pane）
5. 结果写回 result json + cli 输出证据
6. 最终回执通过 schema gate 后发送

## 6. 输出治理（已落地）
- ACK 脚本化：`rawcli_ingress_ack_submit.sh`
- 回执门禁：`receipt_schema_gate.sh`
- 输出校验：`expect_regex` / `expect_exact_line`
- 事件模板：`templates/event-phrases.yaml`
- 飞书硬约束：禁止调试元数据、过程独白、内部路径泄漏

## 7. Soul Slim（2026-03-21）
已完成 5 Soul 的统一瘦身结构，按 7 章节组织：
- Identity
- Core Truths
- Boundaries
- Vibe
- Operating Rules
- Core Focus
- Taboos

效果：单 Soul 运行时文本收敛为约 50 行，减少上下文负担并降低路由歧义。

## 8. 自动化与实验层（2026-03-21 落地）
- `rawcli_cron_tick.sh`: 统一自动化 tick（dual-loop + experiments + screenshot normalize）
- `rawcli_experiment_batch.sh`: 三组实验跑批（dispatch / receipt / screenshot）
- `rawcli_observability_panel.sh`: 统一观测面板（metrics+health+alert+trace+visual+experiments）
- `codex_state_repair.sh`: Codex sqlite migration mismatch 自动修复

## 9. 当前剩余增强项（不阻塞可用）
1. 外部 observability 平台（Prometheus/Grafana）对接
2. 上下文熵治理策略引擎化（当前为阈值触发）
3. 多天实验趋势面板（当前已有批处理和事件落盘）
