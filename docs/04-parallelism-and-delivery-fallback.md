# 并行机制与回执降级（2026-03-18）

## 1) 当前并发上限

- `TASKS.yaml`：`max_parallel_subtasks = 8`
- `openclaw.json`：`acp.maxConcurrentSessions = 8`

## 2) 任务是否可以并行给 Subagent？

可以。

- `sessions_spawn` 可以并行派发多个子任务。
- 子任务会并发执行，最终回到主会话汇总。

## 3) 为什么还会感觉顺序卡住？

因为主会话仍是单线收口：

- 主会话在等待关键子任务结果时，看起来像“顺序处理”。
- 这不是不能并行，而是汇总阶段的收口行为。

## 4) SessionBlock 影响点

- 同一个会话的 turn 仍有顺序边界。
- 但子会话可并发，只要通过 `sessions_spawn` 派发。

## 5) 自动降级回执（Feishu失败兜底）

当 Feishu 回执失败（如 DNS 抖动）时：

1. 最终结论先本地落盘：
   - `/home/yarizakurahime/claw/Report/final-summary-YYYYMMDD-HHMMSS.md`
2. 待补发写入：
   - `~/.openclaw/beatless/pending-delivery.json`
3. Lacia 心跳优先处理待补发队列。
4. REPLAY 任务只处理 `status=pending` 项，忽略 `delivered` 历史项。

## 6) 判定原则

- 文件证据优先于消息回执。
- “报告文件已存在 + 结论已落盘”视为执行完成。
