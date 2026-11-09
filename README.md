# 基模爷大学习

这套笔记讲三件事：**后训练到底在训什么**、**训练集群怎么把吞吐和显存稳住**、**为什么有的团队换一个人还能复现，有的团队换一次脚本就全乱了**。

预训练好比把人送进图书馆读完通识；后训练好比做题、改错、学规矩、上岗考核。算力大头在预训练，但模型好不好用、讲不讲人话、会不会按工具格式输出、数学代码能不能做对，几乎都在后训练这一段决定。

仓库是否能打开、论文标题是否与 arXiv 摘要页一致，核对日期是 **2026-11-09**。已经搬家的仓库直接写新地址。

## 怎么用这套材料

1. 直接打开 `release/基模爷大学习.html`（或仓库根目录的 `index.html`）。导图、五篇笔记、论文目录和仓库目录都在同一个页面里，顶部切换即可。
2. 点正文里的任何一篇论文标题，右侧会直接展开**内嵌 PDF 阅读面板**，不用跳出页面，也不用边看笔记边找窗口。
3. 55 篇 arXiv 论文已经下好，放在 `论文/` 目录。只有 1952 年的 Bradley-Terry 是统计期刊论文，没有 arXiv 编号。
4. 想改文字时，直接改 `.md` 源文件，然后运行 `python3 构建.py render`，单文件合集和分页 HTML 会一起更新。

| 章节 | 讲什么 |
|---|---|
| [后训练底层技术](01-后训练底层技术.html) | 监督微调、造数据、离线偏好、可验证奖励强化学习、长上下文、模型合并 |
| [训练基础设施](02-训练基础设施.html) | 集群、调度、显存、通信、算力池化、算子与吞吐、强化学习采样系统 |
| [工作链与落地](03-工作链与落地.html) | 八个不变的制品、消融纪律、小模型探针、上线契约、线上回灌 |
| [论文索引](04-论文索引.html) | 55 篇论文，点击即在页面右侧看 PDF |
| [仓库索引](05-仓库索引.html) | 训练、对齐、并行、调度、评测、推理的开源仓库 |

## 全流程一眼看懂

```text
基座检查点
  → 继续预训练 / 领域退火（可选：补行业知识或拉长上下文）
  → 监督微调 SFT（先学会说话格式、工具调用、长思维链写法）
  → 离线偏好优化（DPO 等）或可验证奖励强化学习（GRPO / DAPO 等）
  → 安全补丁与专项能力补齐
  → 评测门禁 → 量化与蒸馏 → 上线服务
  → 线上真实交互脱敏后回到数据仓
```

两条最常见的路线：

- **通用对话路线**：`监督微调 → DPO 一族或 PPO`。重点是语气自然、听懂指令、少胡说。
- **推理与智能体路线**：`少量长思维链冷启动 → GRPO / DAPO（拿核对器或单测当裁判）→ 通用偏好对齐`。先学会把题做对，再把说话习惯修好，免得只会刷题、不会正常交流。

## 已经换了入口的仓库

核对时下面几个常见地址已经重定向或归档，笔记里统一用新入口：

| 旧地址 | 现在用 |
|---|---|
| `OpenAccess-AI-Collective/axolotl` | [axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl) |
| `hiyouga/LLaMA-Factory` | [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory) |
| `pytorch/torchtune` | [meta-pytorch/torchtune](https://github.com/meta-pytorch/torchtune) |
| `microsoft/DeepSpeed` | [deepspeedai/DeepSpeed](https://github.com/deepspeedai/DeepSpeed) |
| `volcengine/verl` | [verl-project/verl](https://github.com/verl-project/verl) |
| `NVIDIA/NeMo` | 原地址已指向语音仓；大模型看 [Megatron-LM](https://github.com/NVIDIA/Megatron-LM)、[Megatron-Bridge](https://github.com/NVIDIA-NeMo/Megatron-Bridge)、[NeMo-RL](https://github.com/NVIDIA-NeMo/RL) |
| `NVIDIA/NeMo-Aligner` | 仓库仍在但已归档；对齐与强化学习改看 [NVIDIA-NeMo/RL](https://github.com/NVIDIA-NeMo/RL) |
