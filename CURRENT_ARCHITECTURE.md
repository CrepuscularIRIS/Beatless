# Beatless 当前架构说明（2026-03-18）

## 1. 当前真实生效架构

当前 OpenClaw 入口仍是 **Lacia**，运行模式是「主编排 + 任务账本 + cron 周期驱动 + 报告落盘」。

- 模型层：统一 `kimi-coding/k2p5`
- 入口绑定：Feishu -> `lacia`
- 任务真相源：`~/.openclaw/beatless/TASKS.yaml`
- 调度方式：`~/.openclaw/cron/jobs.json`（isolated cron sessions）
- 报告目录：`/home/yarizakurahime/claw/Report/`

当前 agents.list（运行层）为：
- `lacia`
- `methode`
- `satonus`
- `kouka`
- `snowdrop`
- `codex-builder`（ACP -> codex）
- `gemini-researcher`（ACP -> gemini）
- `claude-architect`（ACP -> claude）
- `claude-architect-opus`（ACP -> claude-opus）
- `claude-architect-sonnet`（ACP -> claude-sonnet）

并发配置（2026-03-18 已更新）：
- `TASKS.yaml` -> `max_parallel_subtasks: 8`
- `openclaw.json` -> `acp.maxConcurrentSessions: 8`

---

## 2. 主执行链路（从触发到收口）

1. 触发源
- Feishu 消息触发 `lacia`
- cron 触发 `lacia`（START/CHECK/CLOSE/REPLAY）

2. Lacia 读取顺序（强制）
- `USER_SOUL.md`
- `MEMORY.md`
- `TASKS.yaml`

3. 任务推进
- `ready -> in_progress`：进入执行
- `in_progress -> review`：进入评审
- `review -> done / ready / dead_letter`：收口或重试

4. 收口标准
- 必需产物文件存在（`required_reports`）
- 质量门禁通过（`quality_gate.sh`）
- 状态机合法流转
- 回执失败可补发（`pending-delivery.json` + REPLAY）

---

## 3. 5 个 Beatless 如何触发

这里按你常用的五角色理解：`Lacia / Methode / Satonus / Kouka / Snowdrop`。

### 3.1 Lacia（规划/协调）
触发条件：
- Feishu 指令到达（绑定入口）
- cron 的 `START/CHECK/CLOSE/REPLAY` 到点

动作：
- 读取三件套（SOUL -> MEMORY -> TASKS）
- 选择任务、更新状态、安排执行或评审

### 3.2 Methode（执行）
触发条件：
- 存在 `in_progress` 任务，且 CHECK 周期判定需要执行

动作：
- 按任务 acceptance_criteria 产出文件
- 写入 `Report/`
- 任务改为 `review`

### 3.3 Satonus（评审语义）
触发条件：
- 任务状态进入 `review`
- 或手动要求 `mode=review`

动作：
- 跑门禁（quality gate）
- 判定 PASS/FAIL
- 写评审报告并回写状态

### 3.4 Kouka（emergency 模式）
触发条件：
- 任务标记 `mode=emergency`
- 或出现关键阻塞（构建挂、服务挂、核心路径报错）

动作：
- 走最小修复路径
- 优先恢复可用性
- 非关键检查可降级

说明：当前主要由模式标签触发；可按任务显式调度。

### 3.5 Snowdrop（explore 模式）
触发条件：
- 任务标记 `mode=explore`
- 或需要方案探索、原型验证

动作：
- 允许试错与草案
- 强制标注不确定项
- 输出进入 review 再收敛

说明：当前主要由模式标签触发；可按任务显式调度。

---

## 4. 与三专家（Codex/Gemini/Claude）的关系

三专家目前是「能力增强通道」：
- `codex-builder`：复杂编码/审查
- `gemini-researcher`：调研与发散
- `claude-architect`：架构边界与评审

触发方式：
- 由 `lacia` 或 `methode` 在复杂任务时调用
- 保持“主流程轻量，复杂问题升级专家”

---

## 5. 当前你需要知道的关键点

- 现在主架构是：**Lacia 中枢 + TASKS 状态机 + cron 周期推进 + Report 证据落盘**。
- V1 Full 回归和值守联调均已通过（PASS），可继续进入真实开发任务。
- 回执补发链路已修复旧路径报错：`pending-delivery.json` 已清理历史悬挂项，REPLAY 手动复验通过。
- 如果后续要更强“全自治”，下一步应补齐：工具权限隔离（allow/deny）、sandbox 分角色、memory scope guard。
