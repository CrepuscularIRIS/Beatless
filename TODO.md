# Beatless TODO (Gap to Ideal)

Updated: 2026-03-21 (Asia/Shanghai)
Owner: CrepuscularIRIS

## P0 (Completed)
1. 运行时硬化：故障分类 + 重试矩阵
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/dispatch_hook_loop.sh`
  - `failure_type`: `auth_error|timeout|network_error|cli_argument_error|runtime_error|output_validation_failed`
  - 按类别重试预算 + 指数退避 + provider error hint

2. 健康检查与稳定重启收敛
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/rawcli_healthcheck.sh`
  - `scripts/rawcli/rawcli_supervisor.sh`
- 关键能力:
  - 检查队列可写、结果目录可写、submit->dispatch 延迟阈值
  - 失败阈值重启 + queue_lag_p95 超阈值重启 + 重启原因落盘

3. 统一指标与告警出站
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/rawcli_metrics_rollup.sh`
  - `scripts/rawcli/rawcli_alert_check.sh`
  - `scripts/rawcli/rawcli_alert_notify.sh`
- 关键能力:
  - 指标: `ack_latency`, `dispatch_duration`, `queue_lag`, `fail_rate`, `queue_depth`
  - critical/warn 级告警推送（Feishu）
  - cooldown + dedup

4. 端到端 trace_id 链路
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `dispatch_submit.sh` 写入 `trace_id`
  - `dispatch_hook_loop.sh` 结果/事件保留 `trace_id`
  - `receipt_schema_gate.sh` gate 事件保留 `trace_id`
  - `rawcli_trace_lookup.sh` 一键反查 ingress/submit/dispatch/receipt

5. 自动化治理（CI 合同门禁）
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/ci/validate_rawcli_contracts.py`
  - `scripts/ci/validate_routing_contracts.sh`
  - `scripts/ci/validate_receipt_contracts.sh`
  - `scripts/ci/test_receipt_schema_gate.sh`
  - `scripts/ci/replay_runner.sh`
  - `.github/workflows/rawcli-governance.yml`

## P1 (Completed)
6. PCE / Dual-loop 可运行闭环
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/pce_cycle.sh`
  - `scripts/rawcli/dual_loop_runner.sh`
  - `scripts/rawcli/backlog_groomer.sh`
  - `scripts/rawcli/context_entropy_compact.sh`
  - `scripts/rawcli/rawcli_cron_tick.sh`
- 说明:
  - 已具备 Planner/Critic/Executor 提交链路、outer/inner loop、定时 tick 入口

7. 截图与网页阅读证据统一展示
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/normalize_visual_evidence.sh`
  - 统一输出: `/home/yarizakurahime/claw/Report/screenshots`
  - manifest: `manifest-latest.json` / `manifest-latest.md`

8. Codex 本地状态迁移清理
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/codex_state_repair.sh`
- 结果:
  - 已清理 `state_5.sqlite` / `logs_1.sqlite` migration mismatch 告警

9. 统一可观测面板
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/rawcli_observability_panel.sh`
- 汇总项:
  - runtime metrics + health + alert + trace + screenshots + experiments

10. 三组实验持续跑批（CI/cron）
- 状态: ✅ completed (2026-03-21)
- 落地:
  - `scripts/rawcli/rawcli_experiment_batch.sh`
  - `.github/workflows/rawcli-experiments.yml`（dry-run）
  - `scripts/rawcli/install_cron_example.sh`

## Residual (Not Blocking Usable)
1. 外部 observability 平台（Prometheus/Grafana 或等价 SaaS）
- 状态: ⏳ optional
- 说明: 当前为本地面板 + 飞书告警，已可用；外部平台属于增强项。

2. 全自动策略化上下文熵治理（按策略库动态裁剪）
- 状态: ⏳ optional
- 说明: 当前是阈值触发 compaction，可继续升级为策略引擎。

3. 大规模长期实验调度（多天多批次统计回归）
- 状态: ⏳ optional
- 说明: 当前已有批处理入口和 CI/cron 脚手架，长期统计可后续补仪表板。
