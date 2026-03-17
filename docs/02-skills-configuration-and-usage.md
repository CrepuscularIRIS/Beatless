# Beatless Skills 配置与使用手册

## 1. Skills 来源与安装机制

Beatless 的安装脚本默认从这里复制 skills：

- `/home/yarizakurahime/claw/openclaw/skills`

脚本中当前默认安装集合：

- `coding-agent`
- `gemini`
- `github`
- `gh-issues`
- `session-logs`
- `healthcheck`
- `tmux`

目标目录：

- `~/.openclaw/workspace-<agent>/skills/<skill>`

---

## 2. 一次性安装（推荐）

```bash
bash /home/yarizakurahime/claw/Beatless/scripts/setup_openclaw_beatless.sh
```

这个命令会：

1. 创建/更新 Beatless 各 agent workspace
2. 将 skills 同步到每个 workspace
3. 写入 AGENTS/SOUL/HEARTBEAT 等基础文件
4. patch `~/.openclaw/openclaw.json`

---

## 3. 手动增删 Skills

## 3.1 给某个 Agent 增加 skill

示例：给 `methode` 增加 `my-skill`

```bash
cp -R /home/yarizakurahime/claw/openclaw/skills/my-skill \
  /home/yarizakurahime/.openclaw/workspace-methode/skills/my-skill
```

## 3.2 从某个 Agent 移除 skill

```bash
rm -rf /home/yarizakurahime/.openclaw/workspace-methode/skills/my-skill
```

## 3.3 批量同步给全部 Beatless Agent

```bash
for a in lacia methode satonus kouka snowdrop codex-builder gemini-researcher claude-architect; do
  mkdir -p /home/yarizakurahime/.openclaw/workspace-$a/skills
  rsync -a --delete /home/yarizakurahime/claw/openclaw/skills/github/ \
    /home/yarizakurahime/.openclaw/workspace-$a/skills/github/
done
```

---

## 4. Skills 在任务中的调用建议

## 4.1 lacia（规划）

建议 skill：
- `session-logs`（追踪上下文）
- `healthcheck`（状态巡检）

用途：
- 读取当前状态、生成分派计划、发起升级路径

## 4.2 methode（执行）

建议 skill：
- `coding-agent`
- `github`
- `tmux`

用途：
- 编码、运行、验证、提交变更

## 4.3 satonus（审查）

建议 skill：
- `healthcheck`
- `github`

用途：
- 质量门禁检查、构建/测试结论回写

## 4.4 ACP 专家

- `codex-builder`: 复杂编码工作优先
- `gemini-researcher`: research/资料补全/方案比较
- `claude-architect`: 架构评审/分层重构路线

---

## 5. 使用策略（避免乱调用）

1. 常规任务先走 `methode`
2. 出现复杂逻辑/大规模生成/疑难 bug 再升级 `codex-builder`
3. 需要外部资料或竞品参考时调用 `gemini-researcher`
4. 涉及系统重构时调用 `claude-architect`
5. 所有升级都要写回 TASKS.yaml 与 DONE/DOING/BLOCKED/NEXT

---

## 6. 验证 Skills 是否生效

检查目录存在：

```bash
find ~/.openclaw/workspace-methode/skills -maxdepth 2 -type f -name 'SKILL.md'
```

检查 agent 工作区路径：

```bash
jq '.agents.list[] | {id,workspace}' ~/.openclaw/openclaw.json
```

若你替换了 skills 后无效果，先重启 Gateway 再测：

```bash
pkill -f 'openclaw/dist/index.js gateway run' || true
nohup node /home/yarizakurahime/claw/openclaw/dist/index.js gateway run --bind loopback --port 18789 --force >/tmp/openclaw-gateway.log 2>&1 &
```

---

## 7. 常见故障

1. 报 `No API key found for provider "kimi-coding"`
- 检查 `~/.openclaw/agents/<agent>/agent/auth-profiles.json`
- 从已有可用 agent 复制 auth-profiles

2. 飞书无回复
- 检查 `~/.openclaw/openclaw.json` 的 `bindings` 是否仍指向 `lacia`
- 检查 Gateway 端口是否监听 `127.0.0.1:18789`

3. 任务只“口头承诺”不落地
- 强制要求每轮输出 DONE/DOING/BLOCKED/NEXT
- 必须附文件路径/命令/报错原文

