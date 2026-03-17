# Beatless 测试与验收清单

## A. 基础可用性

1. Gateway 运行
- [ ] `127.0.0.1:18789` 在监听

2. Agent 拓扑
- [ ] `lacia/methode/satonus/kouka/snowdrop` 存在
- [ ] `codex-builder/gemini-researcher/claude-architect` 存在

3. 模型统一
- [ ] `agents.defaults.model.primary = kimi-coding/k2p5`
- [ ] 各 agent 的 primary 仍为 `kimi-coding/k2p5`

4. 飞书绑定
- [ ] `bindings` 中 Feishu 对应 `agentId = lacia`

---

## B. 编排可用性

1. 路由测试
- [ ] 飞书下达任务后，能看到 `lacia` 接旨与拆解

2. 分工测试
- [ ] 常规开发由 `methode` 执行
- [ ] 复杂任务可升级 `codex-builder`
- [ ] 研究任务可升级 `gemini-researcher`
- [ ] 架构任务可升级 `claude-architect`

3. 汇报规范
- [ ] 每轮都有 DONE/DOING/BLOCKED/NEXT
- [ ] BLOCKED 包含报错原文和修复动作

---

## C. 长时任务稳定性

1. 30分钟节奏
- [ ] 能稳定输出阶段汇报
- [ ] 汇报带绝对时间（例如 2026-03-17 10:30 GMT+8）

2. 防跑偏
- [ ] 不再出现“系统级无法修复”式误判
- [ ] 遇到权限问题能给出可执行替代路径

3. 产物可验收
- [ ] 输出文件路径清单
- [ ] 输出可复现命令
- [ ] 输出测试结果与风险说明

---

## D. 一键自检命令

```bash
jq '.agents.defaults.model,.agents.list[]|{id,model:(.model.primary),runtime}' ~/.openclaw/openclaw.json
jq '.bindings' ~/.openclaw/openclaw.json
ss -ltnp | rg 18789
find ~/.openclaw/workspace-lacia ~/.openclaw/workspace-methode ~/.openclaw/workspace-satonus -maxdepth 2 -name 'AGENTS.md' -o -name 'SOUL.md' -o -name 'HEARTBEAT.md'
```

