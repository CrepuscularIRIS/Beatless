# Beatless 架构蓝图（OpenClaw 版）

## 1. 目标

Beatless 在 OpenClaw 内的目标是：

1. 入口统一：飞书统一进入 `lacia`
2. 分工稳定：规划/执行/审查职责分离
3. 长时可控：可持续运行、可追踪、可回滚
4. 高风险降级：失败可回退，不伪造结果

---

## 2. 核心拓扑

当前设计采用 2+3 常驻 + 3 模式标签结构：

1. 主链路（常驻）
- `lacia`：规划与调度（Planner）
- `methode`：执行实现（Executor）

2. 模式标签（非常驻 Agent）
- `mode=emergency`：Kouka 策略（高压攻坚）
- `mode=explore`：Snowdrop 策略（发散探索）
- `mode=review`：Satonus 策略（严苛验收）

3. 外挂专家（三 ACP）
- `codex-builder`：复杂代码与疑难问题
- `gemini-researcher`：外部调研与方案对比
- `claude-architect`：架构设计与演进路径

建议的主流程：

`lacia -> methode -> experts(mode-aware) -> lacia`

复杂任务时由 `lacia/methode` 升级调用 ACP：

`methode -> codex-builder`
`lacia -> gemini-researcher`
`lacia -> claude-architect`

---

## 3. 角色职责边界

## 3.1 lacia

负责：
- 读取任务池并做优先级决策
- 将模糊需求拆成可执行子任务
- 分派给 methode/satonus 或 ACP 专家

不负责：
- 长时直接编码执行
- 在无证据情况下宣称“已完成”

## 3.2 methode

负责：
- 常规工程实现
- 功能开发、修复、改造、联调
- 产出可运行结果和变更清单

不负责：
- 自行放行质量门禁（必须经过 satonus）

## 3.3 ACP 专家

- `codex-builder`：复杂算法、疑难 bug、大规模重构
- `gemini-researcher`：资料调研、方案候选、开源对比
- `claude-architect`：边界定义、模块分层、迁移计划

## 3.4 模式策略（Soul 内核）

- `mode=emergency`：Codex 主冲刺，Claude 辅助兜底
- `mode=explore`：Gemini 主探索，Codex 做可行性样例
- `mode=review`：Claude 主评审，Codex 做代码级审计

---

## 4. 数据与状态面

Beatless 的单一事实源（SSOT）：

- `~/.openclaw/beatless/TASKS.yaml`

质量规则：

- `~/.openclaw/beatless/QUALITY_GATES.md`

长期记忆：

- `~/.openclaw/beatless/MEMORY.md`

每次执行必须写 `DONE/DOING/BLOCKED/NEXT`，禁止口头完成。

---

## 5. 任务状态机（建议）

推荐状态：

`backlog -> ready -> in_progress -> review -> done`

异常分支：

- `in_progress -> blocked`
- `review -> ready`（审查不通过退回）
- 任意状态 -> `cancelled`

最小字段建议：

```yaml
id: BT-20260317-001
title: "FoodDB 前后端修复"
priority: high
status: ready
assigned_agent: methode
context_hash: "..."
acceptance_criteria:
  - "frontend build pass"
  - "backend health endpoint ok"
outputs: []
notes: ""
```

---

## 6. 长时任务运行策略（8小时级）

原则：

1. 心跳只做调度与巡检，不做重活
2. 重任务放到独立执行回合（隔离上下文）
3. 每 30 分钟固定汇报一次（带绝对时间）

汇报模板：

```text
[时间] 2026-03-17 02:00 GMT+8
[任务ID] ...
[DONE] ...
[DOING] ...
[BLOCKED] ...
[NEXT] ...
```

遇到阻塞 > 30 分钟：

- 立即上报 `BLOCKED`
- 附报错原文 + 已尝试动作 + 下一步建议

---

## 7. 反跑偏规则

1. 禁止伪完成：没有命令/日志/文件证据，不能报完成
2. 禁止角色越权：
- `lacia` 不长期代替 `methode` 写代码
- `methode` 不绕过 `satonus` 直接放行
3. 禁止无边界发散：`snowdrop` 产出必须回到 `lacia` 收敛
4. 禁止会话幻觉：必须优先读任务池和当前文件状态

---

## 8. 与 Edict 的关系

- Beatless 是你当前主编排
- Edict 可以保留为备份设计，不参与当前主路由
- 飞书绑定仅保留 `lacia` 主入口，避免双入口冲突

---

## 9. 启动与生效

```bash
bash /home/yarizakurahime/claw/Beatless/scripts/setup_openclaw_beatless.sh
```

完成后检查：

```bash
jq '.agents.list[].id' ~/.openclaw/openclaw.json
jq '.bindings' ~/.openclaw/openclaw.json
```

应看到：
- agents 包含 `lacia/methode/satonus/...`
- Feishu 绑定到 `lacia`
