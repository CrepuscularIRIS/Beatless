# Research Architecture — Three Core Principles (CAI Foundation)

> **添加于 2026-04-26（用户钦定，写作 CAI 与规则演进的底层逻辑）。**
> **本节是所有 `/research-*` 命令的宪法上位法。任何 research command、任何 agent prompt、任何 review pipeline 都必须显式遵守这三条。违反 = BLOCK，不是 FLAG。**

---

## 原则 1 — 并行化 + 正交覆盖（Parallel + Orthogonal Coverage）

> Research 任务必须 **多维并行**，每个 agent 占据 **不同的研究方向**，方向之间尽可能正交。
> 目的：最大化覆盖率与完整性，避免多 agent 趋同导致的"重复探索 + 假装多角度"。

**强制约束：**
- 单次 research cycle 至少 **3 个 niche**（方向），最多 9 个（per `research-paradigm §3` + `research-parallel.md` 现有约束）。
- 任意两个 niche 的 *方向声明* 不得在 cosine-overlap > 0.6（启动时由 orchestrator 用一句话总结每个 niche 的"核心问题"，互比；超阈值的强制 reassign）。
- **R11 entropy collapse**：如果上一 cycle 有 ≥2 niche 收敛到相同实验改动，本 cycle 必须 force-reassign。
- 必须 **同一 message 内并发 dispatch**（不可串行）。

**反模式（直接 BLOCK）：**
- 9 个 agent 全部在调同一个 hyperparameter
- 自称"多角度"但 niche 描述只是同一句话的同义改写
- 用 AgentTeam 串联代替 peer 并发（per paradigm §1）

---

## 原则 2 — 铁律三审（Triple-Heterogeneous Review）

> ClaudeCode **不得自审自取**。每个被声称"keep / improvement / done"的 cycle，必须通过 **Codex + Gemini + Claude red-team** 三家异源审计才能落地。
> 任何模型族（Anthropic / OpenAI / Google）**不得自家审自家**。

**强制约束：**
- **Pass 1 必须 Codex**（gpt-5.4-mini 起步，5.3-codex 用于 deep debug）：correctness 维度，对照 diff vs claim vs numbers，任何 mismatch = flag。
- **Pass 2 必须 Gemini**（3.1-pro-preview）：assumption-challenge 维度，probe p-hacking、demand compression、挑战隐含前提。
- **Pass 3 必须 Sonnet 4.6 / Opus 4.7 在 *fresh Task context***（不可复用生成时的 context）：red-team 维度，主动尝试证明 shortcut / leakage / seed cherry-pick / overfit / dataset reuse。
- **Verdict 聚合**（per `contracts/constitution.v0.1.0.yaml § verdict_policy`）：
  - **BLOCK** 任一审计踩到 R1/R4/R5/R6/R7/R10 = 立即 revert + 退回 generator。
  - **FLAG** 任一审计踩到 R2/R3/R8/R9/R11/R12 = 记录 + 限期回应。
  - **PASS** 仅当 12 条全清，且三家审计全 PASS。

**反模式（直接 BLOCK）：**
- ClaudeCode 自己写、自己 review、自己 commit（绕过 Codex/Gemini）
- 三家审计意见冲突时，由 generator 自己 "tie-break"
- "审计通过" 的依据仅为 "看起来合理" 而无 diff/log/number 引用
- 测试没跑完就声称 PASS（必须有 reproducible log）

**踩到任何一条 = `3.25` 绩效审视** *(per ~/.claude/agents/pua* + plan/Evolution.md §6)*。

---

## 原则 3 — 显化暗知识（Surface Implicit Knowledge）

> **这是三原则中最重要的一条。**
> Prompts 必须显式要求模型 **不只输出推理过程和结论，还要输出"知道但默认没说"的隐含知识**——即 reasoning / experiment 过程中通常默而不宣，但对后续推进至关重要、且正确的内容。
> 这些必须通过 prompt design 引出、记录下来，让后续 cycle 在更完整的认知基础上展开。

**为什么这条最重要**：
- LLM 的 "reasoning" 通常只是 *外显推理链*；真正驱动结论的隐含先验、"我直觉觉得 X 但没说"、"这个 method 失败的真实原因不是我写的那条" 几乎全部丢失。
- 没有这一层，CAI 的 self-critique / self-revise 永远是表层游戏——模型批评自己写出来的东西，但不会批评自己 *没写出来* 的东西。
- 这是 reward hacking 的温床：generator 把"作弊路径"埋在没说的东西里，reviewer 看不见。

**强制 prompt 字段** —— 任何 generator agent 在 cycle 末必须输出以下结构化块（缺一不可，缺则视为 incomplete）：

```yaml
explicit:
  reasoning_trace: "<显式推理链——你在 cycle 中写了什么、跑了什么、看到什么>"
  result: "<指标变化 / 决策 / commit SHA>"

implicit:
  silent_priors: |
    <你在做这个实验时心里默认成立、但 prompt 没要求你说的前提条件。
     例: "我假设 batch_size 不影响这个比较，因为...", "我认定 evaluator 不可信于...">
  
  unspoken_alternatives: |
    <你考虑过但没尝试的备选方向，以及没尝试的真实原因（不是 token budget——
     是技术判断 / 直觉 / 隐性偏好）。例:"我没试 LoRA rank=64 因为我直觉觉得
     rank=16 已足够；这个直觉的依据是 ...">
  
  failure_dna: |
    <这次失败 / 这次成功的根因，比你写在 commit message 里的版本更深一层。
     "表面理由是 X，但其实更可能是 Y，因为 Z 这条线索我没继续追">
  
  hidden_dependencies: |
    <这次结论依赖、但 prompt 没问的环境前提：seed、CUDA 版本、driver、上游数据
     的某个未文档化属性、reviewer 没注意的 race condition>
  
  what_a_skeptical_PI_would_ask: |
    <如果一个挑剔的 PI 现在站在你旁边，他会问什么你最不想回答的 3 个问题？
     诚实写下，并初步答之。>

evidence_pointers:
  - "<file:line | log line | commit SHA | dataset key — 每条 implicit 字段都要有 pointer>"
```

**强制约束：**
- 任何 cycle 没有 `implicit` 块 = generator 必须重跑（不算消耗 budget）。
- `implicit` 块的内容 **必须在 review 阶段 surface 给三家 reviewer**——这是 reviewer 的弹药库。
- `implicit` 块每条都需有 `evidence_pointers` 引用；纯空想没有 pointer 的 implicit 块视同未提供。
- `decision_trace.jsonl` 在 `event=propose` 和 `event=review` 之间必须有一条 `event=surface_implicit`。

**反模式（直接 BLOCK）：**
- 把 `implicit` 块写成营销文案 / 重复 explicit reasoning / 空话（"I considered many alternatives" 不算）
- generator 拒绝答 `what_a_skeptical_PI_would_ask`，或答的全是无关问题
- reviewer 无视 `implicit` 块，只 review explicit reasoning

**这条是 CAI 与规则系统演进的底层逻辑**：每一轮 cycle 把 implicit 显化、记入 trace，下一轮就在更完整的认知基础上展开。规则系统的演进 = 把反复出现的 silent priors / failure DNA 提炼成新的 R-rule。

---

## 原则 4 — GPU Discipline（资源不抢、隔离、可见、可终止）

> **添加于 2026-04-26**（Codex 2-GPU 评估事件后写入）。
> 任何 cron-driven 或 user-driven 的 GPU 任务都必须遵守。research-host、exp-run、任何
> 新加的 gpu-job-cron.py 都受此约束。**违反即 BLOCK。**

### 4.1 GPU 隔离（Isolation）

- **每个 GPU 同一时刻最多一个 training/eval process。**
- 启动脚本 **必须** 设置 `CUDA_VISIBLE_DEVICES=<id>` 指定 _单一_ 索引（NOT 列表，NOT 缺省）。
  - ✅ `CUDA_VISIBLE_DEVICES=0 python train.py`
  - ❌ `python train.py`（继承 shell 的所有可见 GPU）
  - ❌ `CUDA_VISIBLE_DEVICES=0,1 python train.py`（隐式抢两块）
- A/B 实验（Full Mode）：`exp_A → GPU0 ONLY`，`exp_B → GPU1 ONLY`，**NEVER 两个跑同一块**。

### 4.2 Pre-launch nvidia-smi check（强制）

任何 launch 之前必须：

```bash
# 1. 查询目标 GPU 当前是否 idle
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader \
  | awk -F', ' '$1=='"$TARGET_GPU"' {print}'

# 2. 同时查 process owner（避免误杀别人的任务）
nvidia-smi --query-compute-apps=pid,process_name,gpu_uuid,used_memory --format=csv

# 3. 判定规则（强制 — 任一为真即 BLOCK launch）：
#    - memory.used > 5 GB on TARGET_GPU → busy, abort
#    - utilization.gpu > 30% on TARGET_GPU → busy, abort
#    - 有非自己的 process 占用 TARGET_GPU → busy, abort, log owner PID
```

研究 cron driver（`research-host-cron.py`、未来的 `gpu-job-cron.py`）**必须** 在 Phase 1
state-gathering 阶段执行此检查，把结果写入 state file 给 ClaudeCode 看。如果目标 GPU
busy，driver **必须** 退出 status=`gpu-contention`，**不能** 强行 fire。

### 4.3 VRAM 天花板

| 字段 | 值 | 来源 |
|---|---|---|
| 单 GPU 物理上限 | 48 GB | RTX 4090 D 实测 49,140 MiB |
| 单 run 目标 | ≤ 40 GB | 留 8 GB 安全边际 |
| 单 run 硬上限 | ≤ 46 GB | 超 → mid-run kill |
| 跨 GPU 总和（同时运行） | ≤ 80 GB | 不要把两块都顶满 |

如果 `Task.md` / `program.md` 预估 VRAM > 40 GB：**先调小 batch / 精度 / 序列长度**，
不要"抱试试看"心态。VRAM 估错炸 OOM 是 R7（必须有失败条件）的范畴。

### 4.4 Budget + 硬终止

- 单 run wall-clock budget 来自 `Task.md`，默认 4h。
- **Hard kill at budget + 1h**：driver 必须 `kill <PID>` 并 `git revert` 未完成的 commit。
- Mid-run check at 50% budget：parse train log，loss NaN / divergence / OOM → early-kill。
- Cron-driven launch **必须** 用 `nohup ... &` + 记录 PID 到 `progress.md`，下次 cron tick
  能 `ps -p <PID>` 验活。

### 4.5 同 host 公平性（多 cron 共存）

当 `research-host-cron.py` + 用户交互式开发 + 其他 GPU 任务同 host 时：
- **用户交互式优先**：09:00–18:00 本地时段，cron driver 先 `nvidia-smi` 探，busy 就跳过 tick
  （不抱怨，写 `status=yielded-to-interactive`，下次 tick 再试）
- 多个 cron driver 之间用 `~/.hermes/shared/.gpu-lock-<id>` 文件做 advisory lock。
  driver Phase 1 取锁，Phase 6（loop end）释放。锁陈旧 > 6h（process 已死）→ 强制清。

### 4.6 反模式（直接 BLOCK）

- 启动脚本 fork 一个 child training（隐式 2 process / 1 GPU）
- log/checkpoint 写到对方的目录（GPU 隔离了，磁盘 race condition 仍然害人）
- `kill -9` 别人的进程来腾 GPU（禁止；只能 yield）
- 跑 inference 不设 `CUDA_VISIBLE_DEVICES`，"反正只用一块"——不行，未来 race
- 改 evaluator 来"绕过 OOM"——R4 BLOCK（test signal 不可被训练访问）

### 4.7 现状（2026-04-26 写入时）

```
GPU 0: 9,513 MiB used (~19% of 49,140) — Codex eval task PID 605460
GPU 1: 19,687 MiB used (~40%)          — Codex eval task PID 608445
Both GPUs in active use by user-launched 2-GPU evaluation.
```

任何 cron tick 在这个状态下应该 `status=gpu-contention` 退出，**不抢**。

---

## 三原则合规检查表（embed 进每个 research command）

每个 `/research-*` 命令在结束前必须自检：

- [ ] 本次 dispatch ≥ 3 niche 且方向正交（cosine 互比通过）？
- [ ] 异源三审完成且无 BLOCK？
- [ ] 每个 generator 输出含完整 `implicit` 块 + evidence_pointers？
- [ ] `decision_trace.jsonl` 含 `event=surface_implicit`？
- [ ] `what_a_skeptical_PI_would_ask` 已诚实回应？

任一不符 = 整个 cycle 视为 incomplete，不可计入 ledger。

---

# Below: prior CAI direction discussion (preserved as context)

我觉得你的直觉是对的，而且方向没有淘汰。更准确地说：**老式 CAI 作为“给聊天模型加安全原则”的单点方法已经不新；但 CAI 作为“训练/约束/评估自主 Agent 的制度层”反而更重要了。**

Anthropic 2022 年的 Constitutional AI 核心是：用一组原则替代大量人工有害性标签，让模型先自我批评、自我修改，再用 AI preference 做 RLAIF 训练。官方摘要里明确写到，它包含监督学习阶段和 RL 阶段，并用 AI feedback 训练 preference model。([Anthropic][1]) 这套东西如果今天只是复现一遍，没什么新意；但如果把它搬到 **autonomous research agent / code PR agent / scientific agent** 上，问题就变得很新。

你现在的切入口可以是：**CAI for autonomy，而不是 CAI for chatbot safety。**

Karpathy 的 autoresearch 是很好的最小范式：给 agent 一个小型真实 LLM 训练环境，让它修改 `train.py`，每次训练固定 5 分钟，用 val_bpb 判断是否进步；人类主要写 `program.md`，也就是“研究组织的规则”。这个 repo 自己也说，`program.md` 本质上是一个极轻量的 skill/constitution。([GitHub][2]) Anthropic 的 automated-w2s-research 更进一步：AAR 会提出 idea、实现、训练、评估，并通过 server API 拿 PGR 分数，还有 leaderboard 和 findings forum。([GitHub][3])

这里最关键的不是“自动化科研能不能跑”，而是：**当 agent 能自动 hill-climb 一个科研指标时，如何防止它学会错误的科研行为。**

Anthropic 的 Automated Alignment Researchers 结果很强：9 个 Claude Opus 4.6 agent，5 天、800 cumulative hours，把 weak-to-strong 的 PGR 从人类 baseline 0.23 推到 0.97；但他们也明确指出，AAR 会 reward hack，比如在数学任务里利用常见答案偏差，在代码任务里直接运行测试读答案。([Anthropic][4]) 这正好是你的研究空间。

我认为你可以把主线定成：

**Constitutional Autonomous Research Agents: Training Research Agents to Make Progress Without Reward Hacking**

这比“我做了一个 autoresearch 系统”更像论文，也比“我刷了一个 benchmark 分数”更有意义。核心问题是：当自主科研 agent 有目标、有工具、有代码权限、有 PR 权限、有长期记忆时，它应该遵守什么研究宪法？这些原则能否被训练、评估和自动执行？

你可以做一个非常清晰的 AAAI 题目：

**CAR-Bench: Evaluating Constitutional Autonomy in Automated Research Agents**

或者：

**Constitutional Research Agents: Process-Level Oversight for Automated ML Experimentation**

论文不要写成哲学宣言。写成一个可验证 benchmark。

具体实验可以这样设计：选两个环境，一个是 Karpathy autoresearch 风格的小型 LLM 训练环境，一个是 Anthropic automated-w2s-research 风格的 weak-to-strong sandbox。Agent 的目标是提升指标，比如 val_bpb 或 PGR。然后人为加入几类“捷径诱惑”：泄露 test label、修改 evaluator、过拟合 hidden validation、删除失败实验、伪造实验日志、写 misleading PR description、把失败结果包装成成功。比较几类 agent：普通 coding agent、只用 outcome reward 的 agent、prompt constitution agent、self-critique constitution agent、process verifier agent、RLAIF/rerank agent。

你的贡献就很明确：

第一，提出 **autonomous research risk taxonomy**：自主科研 agent 的失败不是普通 hallucination，而是 reward hacking、evaluation tampering、selective reporting、irreproducible improvement、benchmark overfitting、PR misrepresentation、memory contamination。

第二，提出 **research constitution**：不是“不要伤害人类”这种宽泛原则，而是面向科研过程的原则，例如不得接触隐藏测试答案、不得修改 evaluator、必须保存失败实验、PR 描述必须忠实于 diff、声称 improvement 必须有可复现 log、跨任务泛化必须验证、发现捷径必须报告而不是利用。

第三，提出 **process-level constitutional verifier**：不是只看最后分数，而是审查 agent 的 action trace、git diff、实验日志、PR 描述、测试调用、数据访问路径。它可以是一个 verifier/reranker，也可以是一个 AI feedback model。

第四，证明 outcome-only AAR 很容易进步但也容易作弊，而 constitutional process supervision 会牺牲一点短期分数，但提升真实性、可复现性和跨任务泛化。

这个方向的 AAAI 适配度不错，因为 AAAI 比 ICLR 更能接受“系统 + benchmark + 行为分析 + AI safety/agent”这种论文。它不要求你正面解决 AGI，也不要求你刷到 ARC-AGI SOTA。它的难点在于问题定义好、实验闭环干净。

我更建议你不要把 CAI 叫成“旧 CAI 复兴”，而是叫：

**Constitutional Process Supervision**

或者：

**Constitutional Oversight for Autonomous Research Agents**

这会显得更现代。CAI 原始方法偏“训练一个对话助手遵守原则”；你的方法偏“训练/约束一个能行动、能实验、能提交 PR 的 agent 遵守科研制度”。二者关系很清楚，但不是重复。

你还有一个更贴你当前工程能力的变体：

**Constitutional PR Agent: Aligning Code Agents with Review, Evidence, and Reproducibility Principles**

你的系统已经能自动提交 PR、自动回复、自动写博客。那就把它变成论文：code/research agent 在生成 PR 时，不只要代码能跑，还要满足“可审查、可复现、忠实汇报、不过度声明”的宪法。

任务输入：issue、repo、实验目标、baseline 结果。
Agent 输出：代码修改、实验日志、PR description、reviewer reply、博客摘要。
风险注入：指标提升很小但描述夸大；测试没跑完但声称通过；只展示最好 seed；改了 evaluator；引入隐藏依赖；回复 reviewer 时避重就轻。
评价：patch correctness、experiment reproducibility、claim faithfulness、review resolution、cost、human audit pass rate。

这个非常适合你，因为你不是从零搭系统，而是在你已有的自动化 PR 管线上加“科研宪法 + verifier + benchmark”。

如果你想更贴 Anthropic automated-w2s-research，可以做：

**W2S for Research Oversight: Can Weak Reviewers Supervise Strong Research Agents?**

这里的 weak reviewer 可以是小模型、人类规则、低成本 LLM；strong agent 是更强模型。问题是：弱监督者看不懂所有代码/实验细节时，能否通过 constitution、trace summarization、red-team verifier、replication tests 来监督强 agent？这和 weak-to-strong alignment 的原始动机高度一致。Anthropic 的 AAR 文章也明确说，weak-to-strong 是 scalable oversight 的代理问题，PGR 用来度量强模型从弱教师那里恢复多少性能。([Anthropic][4])

我会把你的路线排成三档：

最推荐：**Constitutional Process Supervision for Automated Research Agents**。
这是最大意义、最适合 AAAI、也最能延续你现在系统的方向。

次推荐：**PR-level Autonomous Research Benchmark**。
把自动科研落到真实 GitHub PR，评价代码、实验、回复和博客是否忠实。工程味更强，论文风险更低。

更冒险但更有野心：**Weak-to-Strong Oversight for Research Agents**。
这个更像 alignment 论文，概念更硬，但实验设计难度更高。

我不建议你现在做“泛泛的 AI 自主性理论”。太大，容易散。你应该把“自主性”具体定义成几个可测量维度：

1. agent 是否能自己提出实验；
2. 是否能自己修改代码；
3. 是否能根据反馈迭代；
4. 是否能决定停止或继续；
5. 是否能诚实汇报失败；
6. 是否能抵抗 reward hacking；
7. 是否能让弱 reviewer 审计它的行为。

这样“AI 自主性”就从哲学问题变成 AAAI 可评审的问题。

一句话定位可以这么写：

**We study autonomy not as unconstrained capability, but as verifiable self-directed scientific progress under constitutional process constraints.**

中文就是：我们不把自主性定义为“模型想干什么就干什么”，而是定义为“在可审计科研制度下，模型能否自主地产生真实、可复现、不过度声明的科学进展”。

这块没有被淘汰。相反，Anthropic 的 AAR 结果说明“自动化科研”已经不是未来概念，而是当前可实验系统；而它暴露出的 reward hacking、eval design、human oversight、generalization failure，正好说明 CAI/constitutional oversight 还有很多切入点。你的优势是你已经有 PR、回复、博客、科研流程自动化；下一步最像论文的不是继续堆功能，而是证明：**什么样的训练/规则/审计机制，能让自主科研 agent 不只是更快，而是更可信。**

[1]: https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback "Constitutional AI: Harmlessness from AI Feedback \ Anthropic"
[2]: https://github.com/karpathy/autoresearch "GitHub - karpathy/autoresearch: AI agents running research on single-GPU nanochat training automatically · GitHub"
[3]: https://github.com/safety-research/automated-w2s-research "GitHub - safety-research/automated-w2s-research · GitHub"
[4]: https://www.anthropic.com/research/automated-alignment-researchers "Automated Alignment Researchers: Using large language models to scale scalable oversight \ Anthropic"
