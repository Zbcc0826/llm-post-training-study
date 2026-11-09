#!/usr/bin/env python3
# 把 Markdown 笔记、思维导图与 PDF.js 阅读器合成为单文件学习站，并生成分页版 HTML。
# 用法：
#   python3 构建.py render
#   python3 构建.py download
#   python3 构建.py all

import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
PAPER_DIR = ROOT / "论文"
RELEASE_DIR = ROOT / "release"
VENDOR_DIR = ROOT / "vendor"

SECTIONS = [
    ("overview", "README.md", "总览"),
    ("algo", "01-后训练底层技术.md", "后训练算法"),
    ("infra", "02-训练基础设施.md", "训练基建"),
    ("workflow", "03-工作链与落地.md", "工作链与落地"),
    ("papers", "04-论文索引.md", "论文库 (55)"),
    ("repos", "05-仓库索引.md", "开源仓库"),
]

HTML_TO_TAB = {src[:-3] + ".html": key for key, src, _ in SECTIONS}

MINDMAP_TREE = {
    "t": "基模后训练全体系",
    "s": "从基座检查点到线上闭环",
    "h": "README.html",
    "c": [
        {
            "t": "后训练算法",
            "s": "决定训什么",
            "h": "01-后训练底层技术.html#pipeline",
            "color": "#8c3a1e",
            "c": [
                {
                    "t": "监督微调 SFT",
                    "s": "只对回答算下一词交叉熵",
                    "h": "01-后训练底层技术.html#sft",
                    "c": [
                        {"t": "全参微调", "s": "上限最高，后续对齐起点", "h": "01-后训练底层技术.html#sft"},
                        {"t": "LoRA", "s": "冻结主干，只训低秩 BA", "h": "01-后训练底层技术.html#lora"},
                        {"t": "QLoRA", "s": "4 bit NF4 基座 + LoRA", "h": "01-后训练底层技术.html#qlora"},
                        {"t": "DoRA", "s": "幅度向量与方向拆开训", "h": "01-后训练底层技术.html#dora"},
                        {"t": "rsLoRA", "s": "除以 √r 稳住大秩梯度", "h": "01-后训练底层技术.html#rslora"},
                        {"t": "PiSSA", "s": "用主奇异向量初始化", "h": "01-后训练底层技术.html#pissa"},
                        {"t": "AdaLoRA", "s": "按重要性动态分配秩预算", "h": "01-后训练底层技术.html#adalora"},
                        {"t": "GaLore", "s": "梯度低秩投影省全参优化器状态", "h": "01-后训练底层技术.html#galore"},
                        {"t": "NEFTune", "s": "词嵌入加随机噪声防死记", "h": "01-后训练底层技术.html#neftune"},
                        {"t": "序列打包 Packing", "s": "多条短样本拼长消灭 padding", "h": "01-后训练底层技术.html#packing"},
                        {"t": "拒绝采样与 STaR", "s": "筛出做对轨迹做冷启动自举", "h": "01-后训练底层技术.html#rft-star"},
                        {"t": "知识蒸馏", "s": "教师轨迹或学生自采样纠偏", "h": "01-后训练底层技术.html#distill"},
                    ],
                },
                {
                    "t": "合成与清洗数据",
                    "s": "指令、偏好、可验证题三仓分管",
                    "h": "01-后训练底层技术.html#self-instruct",
                    "c": [
                        {"t": "Self-Instruct", "s": "种子指令自举生成再过滤", "h": "01-后训练底层技术.html#self-instruct-method"},
                        {"t": "Evol-Instruct", "s": "向深度与广度改写难题", "h": "01-后训练底层技术.html#evol-instruct"},
                        {"t": "Magpie", "s": "利用对话模板前缀空手套指令", "h": "01-后训练底层技术.html#magpie"},
                    ],
                },
                {
                    "t": "离线与半在线偏好对齐",
                    "s": "用好坏对比替代手写答案",
                    "h": "01-后训练底层技术.html#bradley-terry",
                    "c": [
                        {"t": "Bradley-Terry 模型", "s": "分差过 sigmoid 得胜率", "h": "01-后训练底层技术.html#bradley-terry-model"},
                        {"t": "奖励模型 ORM / PRM", "s": "整段打分 vs 逐步骤打分", "h": "01-后训练底层技术.html#reward-model"},
                        {"t": "PPO-RLHF", "s": "策略/参考/奖励/价值四模型协同", "h": "01-后训练底层技术.html#ppo-rlhf"},
                        {"t": "DPO", "s": "对数概率比直代奖励，省掉 RM", "h": "01-后训练底层技术.html#dpo"},
                        {"t": "IPO", "s": "平方目标限制过拟合", "h": "01-后训练底层技术.html#ipo"},
                        {"t": "KTO", "s": "前景理论，只需单条赞踩标签", "h": "01-后训练底层技术.html#kto"},
                        {"t": "ORPO", "s": "SFT 加优势比惩罚一步到位", "h": "01-后训练底层技术.html#orpo"},
                        {"t": "SimPO", "s": "长度归一平均对数概率 + 固定间隔", "h": "01-后训练底层技术.html#simpo"},
                        {"t": "在线偏好 OAIF", "s": "当前策略实时采样再判高下", "h": "01-后训练底层技术.html#online-dpo"},
                        {"t": "宪法式 AI", "s": "按明文原则自批自改与 AI 反馈", "h": "01-后训练底层技术.html#cai"},
                        {"t": "过程奖励 PRM", "s": "步骤级监督配合推理搜索", "h": "01-后训练底层技术.html#prm"},
                    ],
                },
                {
                    "t": "可验证奖励强化学习 RLVR",
                    "s": "用核对器、单测、编译器当硬裁判",
                    "h": "01-后训练底层技术.html#grpo",
                    "c": [
                        {"t": "GRPO", "s": "组内均值标准差算优势，砍掉 Critic", "h": "01-后训练底层技术.html#grpo-algo"},
                        {"t": "RLOO", "s": "留一法同组其余样本均值做基线", "h": "01-后训练底层技术.html#rloo"},
                        {"t": "REINFORCE++", "s": "全局批次优势归一化", "h": "01-后训练底层技术.html#reinforce-pp"},
                        {"t": "DAPO", "s": "解耦上裁剪、滤全对全错组、词级损失", "h": "01-后训练底层技术.html#dapo"},
                        {"t": "GSPO", "s": "序列级似然比与裁剪，稳住 MoE", "h": "01-后训练底层技术.html#gspo"},
                        {"t": "DeepSeek-R1 四阶段配方", "s": "冷启动 → RLVR → 拒绝采样 SFT → 全场景 RL", "h": "01-后训练底层技术.html#r1"},
                    ],
                },
                {
                    "t": "长上下文、合并与框架选型",
                    "h": "01-后训练底层技术.html#yarn",
                    "c": [
                        {"t": "RoPE 与长窗口外推", "s": "PI、YaRN、调大基频 ABF、LongRoPE", "h": "01-后训练底层技术.html#rope"},
                        {"t": "权重空间合并", "s": "SLERP、TIES-Merging、DARE", "h": "01-后训练底层技术.html#merging"},
                        {"t": "训练框架选型表", "s": "TRL、LlamaFactory、ms-swift、verl、OpenRLHF", "h": "01-后训练底层技术.html#tool-choice"},
                    ],
                },
            ],
        },
        {
            "t": "训练基础设施",
            "s": "决定能不能稳住 MFU 与吞吐",
            "h": "02-训练基础设施.html#cluster",
            "color": "#1d4e89",
            "c": [
                {
                    "t": "集群硬件",
                    "s": "算力、网络、存储三件套配平",
                    "h": "02-训练基础设施.html#cluster",
                    "c": [
                        {"t": "机内 NVLink 与机间 IB / RoCE", "h": "02-训练基础设施.html#cluster"},
                        {"t": "GPUDirect RDMA 网卡直读显存", "h": "02-训练基础设施.html#cluster"},
                        {"t": "并行文件系统与分钟级检查点带宽", "h": "02-训练基础设施.html#cluster"},
                    ],
                },
                {
                    "t": "集群调度",
                    "s": "成组同时拉起，坏节点自动重排",
                    "h": "02-训练基础设施.html#schedule",
                    "c": [
                        {"t": "Slurm 超算队列与抢占", "h": "02-训练基础设施.html#schedule"},
                        {"t": "Kueue 与 Volcano 云原生编排", "h": "02-训练基础设施.html#schedule"},
                        {"t": "Ray 训推分离进程编排", "h": "02-训练基础设施.html#schedule"},
                        {"t": "SkyPilot 跨云跨集群提交", "h": "02-训练基础设施.html#schedule"},
                    ],
                },
                {
                    "t": "显存优化",
                    "s": "拆解权重、梯度、优化器状态与激活",
                    "h": "02-训练基础设施.html#memory",
                    "c": [
                        {"t": "BF16 / FP8 混合精度", "h": "02-训练基础设施.html#memory"},
                        {"t": "激活检查点与选择性重计算", "h": "02-训练基础设施.html#memory"},
                        {"t": "ZeRO-1/2/3 与 PyTorch FSDP2", "h": "02-训练基础设施.html#memory"},
                        {"t": "张量并行、序列并行与专家并行", "h": "02-训练基础设施.html#memory"},
                        {"t": "CPU / NVMe 卸载兜底", "h": "02-训练基础设施.html#memory"},
                    ],
                },
                {
                    "t": "通信优化",
                    "s": "把通信藏进计算里",
                    "h": "02-训练基础设施.html#comm",
                    "c": [
                        {"t": "NCCL 梯度分桶与计算重叠", "h": "02-训练基础设施.html#comm"},
                        {"t": "1F1B 与交错式流水线", "h": "02-训练基础设施.html#comm"},
                        {"t": "Zero Bubble 零气泡流水线", "h": "02-训练基础设施.html#comm"},
                        {"t": "Ring Attention 环状长序列并行", "h": "02-训练基础设施.html#comm"},
                        {"t": "DeepSpeed Ulysses 头切分转置", "h": "02-训练基础设施.html#comm"},
                    ],
                },
                {
                    "t": "算力自由化",
                    "s": "作业不绑死单集群与固定切分",
                    "h": "02-训练基础设施.html#compute-pool",
                    "c": [
                        {"t": "统一作业配置描述", "h": "02-训练基础设施.html#compute-pool"},
                        {"t": "配额池化与闲时抢占", "h": "02-训练基础设施.html#compute-pool"},
                        {"t": "DCP 检查点任意并行度重切分", "h": "02-训练基础设施.html#compute-pool"},
                        {"t": "内存异步写检查点秒级恢复", "h": "02-训练基础设施.html#compute-pool"},
                    ],
                },
                {
                    "t": "算子与吞吐调优",
                    "s": "盯紧 MFU，打破显存带宽墙",
                    "h": "02-训练基础设施.html#throughput",
                    "c": [
                        {"t": "FlashAttention 1 / 2 / 3 片上分块", "h": "02-训练基础设施.html#throughput"},
                        {"t": "算子融合、torch.compile 与 CUDA Graph", "h": "02-训练基础设施.html#throughput"},
                        {"t": "Transformer Engine FP8 加速", "h": "02-训练基础设施.html#throughput"},
                        {"t": "黄金配置 MFU 回归拦截", "h": "02-训练基础设施.html#throughput"},
                    ],
                },
                {
                    "t": "强化学习采样运行时",
                    "s": "70% 耗时在采样，必须训推解耦",
                    "h": "02-训练基础设施.html#rl-system",
                    "c": [
                        {"t": "FSDP / Megatron 训练进程组", "h": "02-训练基础设施.html#rl-system"},
                        {"t": "vLLM / SGLang 连续批处理与前缀缓存", "h": "02-训练基础设施.html#rl-system"},
                        {"t": "NCCL / IPC 毫秒级权重同步", "h": "02-训练基础设施.html#rl-system"},
                        {"t": "CPU 容器池并发沙箱验证器", "h": "02-训练基础设施.html#rl-system"},
                        {"t": "长尾截断续写与轨迹落盘缓存", "h": "02-训练基础设施.html#rl-system"},
                    ],
                },
                {"t": "硬件观测与慢节点抓捕", "s": "DCGM、RDMA 监控与 Rank 级超时定位", "h": "02-训练基础设施.html#observe"},
            ],
        },
        {
            "t": "工作链与落地",
            "s": "决定换人隔月还能不能复现",
            "h": "03-工作链与落地.html#eight",
            "color": "#3d6b4f",
            "c": [
                {
                    "t": "八个标准制品",
                    "h": "03-工作链与落地.html#eight",
                    "c": [
                        {"t": "1. 版本化数据包（含去重去污染）", "h": "03-工作链与落地.html#data"},
                        {"t": "2. 单一配方文件（锁死全部超参）", "h": "03-工作链与落地.html#recipe"},
                        {"t": "3. 统一训练启动器", "h": "03-工作链与落地.html#recipe"},
                        {"t": "4. 自动实验记录（W&B / SwanLab）", "h": "03-工作链与落地.html#tracking"},
                        {"t": "5. 能力 / 回归 / 安全三张评测表", "h": "03-工作链与落地.html#eval-gate"},
                        {"t": "6. 带晋升状态的可重切分检查点", "h": "03-工作链与落地.html#promotion"},
                        {"t": "7. 训推一致契约（模板与工具 Schema）", "h": "03-工作链与落地.html#serving"},
                        {"t": "8. 带 GPU 小时成本的晋升单", "h": "03-工作链与落地.html#promotion"},
                    ],
                },
                {"t": "验证器与裁判校准集", "h": "03-工作链与落地.html#reward-service"},
                {"t": "失败预算与采样缓存恢复", "h": "03-工作链与落地.html#failure"},
                {"t": "单变量消融纪律", "h": "03-工作链与落地.html#ablation"},
                {"t": "小模型探针先试错", "s": "算清 GPU 小时账再放大", "h": "03-工作链与落地.html#proxy"},
                {
                    "t": "生产上线与数据飞轮",
                    "h": "03-工作链与落地.html#serving",
                    "c": [
                        {"t": "分词器与 Jinja 聊天模板强绑定", "h": "03-工作链与落地.html#serving"},
                        {"t": "AWQ / GPTQ / FP8 量化后再过门禁", "h": "03-工作链与落地.html#serving"},
                        {"t": "EAGLE 投机解码无损提速", "h": "03-工作链与落地.html#serving"},
                        {"t": "TTFT / TPOT 与单卡并发吞吐", "h": "03-工作链与落地.html#serving"},
                        {"t": "线上错题脱敏回灌与比例上限", "h": "03-工作链与落地.html#feedback"},
                    ],
                },
            ],
        },
        {
            "t": "速查索引",
            "s": "55 篇论文 PDF 与开源仓库",
            "h": "04-论文索引.html",
            "color": "#6b4c7a",
            "c": [
                {"t": "论文索引（点击页内直接读 PDF）", "h": "04-论文索引.html"},
                {"t": "开源仓库索引", "h": "05-仓库索引.html"},
            ],
        },
    ],
}

MATH_TOKENS = {
    r"\Delta": "Δ",
    r"\beta": "β",
    r"\Psi": "Ψ",
    r"\times": "×",
    r"\sigma": "σ",
    r"\pi^*": "π*",
    r"\pi_\theta": "π_θ",
    r"\pi_{\text{ref}}": "π_ref",
    r"\varepsilon_{\text{high}}": "ε_high",
    r"\alpha": "α",
    r"\gamma": "γ",
    r"\dots": "…",
    r"\log": "log ",
}


def parse_paper_catalog():
    text = (ROOT / "04-论文索引.md").read_text(encoding="utf-8")
    catalog = {}
    for line in text.splitlines():
        m = re.match(
            r"\|\s*([^|]+?)\s*\|\s*\[(\d+\.\d+)\]\(https://arxiv\.org/abs/\d+\.\d+\)",
            line,
        )
        if m:
            catalog[m.group(2)] = m.group(1).strip()
    return catalog


def paper_ids():
    text = (ROOT / "04-论文索引.md").read_text(encoding="utf-8")
    return list(dict.fromkeys(re.findall(r"arxiv\.org/abs/(\d+\.\d+)", text)))


def pdf_ok(aid: str) -> bool:
    path = PAPER_DIR / f"{aid}.pdf"
    if not path.exists() or path.stat().st_size < 8000:
        return False
    return path.read_bytes()[:5] == b"%PDF-"


def download_one(aid: str) -> str:
    dest = PAPER_DIR / f"{aid}.pdf"
    if pdf_ok(aid):
        return f"skip {aid}"
    url = f"https://arxiv.org/pdf/{aid}.pdf"
    last = "unknown"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF-"):
                last = f"not-pdf {data[:40]!r}"
                time.sleep(3 + attempt * 4)
                continue
            dest.write_bytes(data)
            return f"ok {aid} {len(data)}"
        except Exception as exc:
            last = str(exc)
            time.sleep(3 + attempt * 5)
    return f"ERR {aid} {last}"


def download_all():
    PAPER_DIR.mkdir(exist_ok=True)
    ids = paper_ids()
    print(f"papers {len(ids)}", flush=True)
    ok = err = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(download_one, aid) for aid in ids]
        for fut in as_completed(futures):
            line = fut.result()
            print(line, flush=True)
            if line.startswith("ERR"):
                err += 1
            else:
                ok += 1
    print(f"done ok={ok} err={err}", flush=True)
    return err


def replace_math(text: str) -> str:
    def repl(match):
        inner = match.group(1)
        inner = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1 / \2)", inner)
        inner = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", inner)
        inner = re.sub(r"\\text\{([^{}]+)\}", r"\1", inner)
        for src, dst in MATH_TOKENS.items():
            inner = inner.replace(src, dst)
        inner = inner.replace(r"\{", "{").replace(r"\}", "}")
        inner = inner.replace("{", "").replace("}", "")
        inner = inner.replace("\\", "")
        return f'<span class="math">{html.escape(inner)}</span>'

    return re.sub(r"\\\((.+?)\\\)", repl, text)


def replace_mermaid(text: str) -> str:
    def repl(match):
        body = match.group(1)
        known = {}
        steps = []
        for raw in body.splitlines():
            line = raw.strip()
            if "-->" not in line:
                continue
            labels = []
            for part in line.split("-->"):
                found = re.match(r"\s*([A-Za-z0-9_]+)(?:\[([^\]]+)\])?", part.strip())
                if not found:
                    labels.append(part.strip())
                    continue
                node_id, label = found.group(1), found.group(2)
                if label:
                    known[node_id] = label
                labels.append(known.get(node_id, label or node_id))
            steps.append(" → ".join(labels))
        if not steps:
            return "<pre><code>" + html.escape(body.strip()) + "</code></pre>"
        rows = "".join(f"<p>{html.escape(step)}</p>" for step in steps)
        return f'<div class="flow">{rows}</div>'

    return re.sub(r"```mermaid\n(.*?)```", repl, text, flags=re.S)


def prepare_markdown(text: str, pdf_prefix: str) -> str:
    text = replace_math(text)
    text = replace_mermaid(text)
    text = text.replace(".md#", ".html#").replace(".md)", ".html)")

    def paper(match):
        aid = match.group(1)
        if pdf_ok(aid):
            return f"{pdf_prefix}{aid}.pdf"
        return match.group(0)

    return re.sub(r"https://arxiv\.org/abs/(\d+\.\d+)", paper, text)


def decorate_rendered_html(rendered: str, catalog: dict, for_bundle: bool) -> str:
    def paper_repl(match):
        href = match.group(1)
        aid = match.group(2)
        label = match.group(3)
        title = catalog.get(aid, re.sub(r"<.*?>", "", label)).strip()
        esc_title = html.escape(title, quote=True)
        return (
            f'<a class="paper-link" href="{href}" data-paper="{aid}" '
            f'data-title="{esc_title}">{label}'
            f'<span class="read-pill">页内读 PDF</span></a>'
            f' <a class="arxiv" target="_blank" rel="noopener" '
            f'href="https://arxiv.org/abs/{aid}">arXiv ↗</a>'
        )

    rendered = re.sub(
        r'<a href="((?:\.\./)?论文/(\d+\.\d+)\.pdf)">(.*?)</a>',
        paper_repl,
        rendered,
    )

    if for_bundle:
        def internal_repl(match):
            page = match.group(1)
            anchor = match.group(2) or ""
            tab = HTML_TO_TAB.get(page)
            if not tab:
                return match.group(0)
            target = f"{tab}:{anchor.lstrip('#')}" if anchor else f"{tab}:"
            return f'<a href="#{target}" data-goto="{target}">'

        rendered = re.sub(
            r'<a href="([^":#]+\.html)(#[A-Za-z0-9_-]+)?">',
            internal_repl,
            rendered,
        )

    rendered = rendered.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    return rendered


def render_section_body(src_name: str, catalog: dict, pdf_prefix: str, for_bundle: bool) -> str:
    raw = (ROOT / src_name).read_text(encoding="utf-8")
    prepared = prepare_markdown(raw, pdf_prefix=pdf_prefix)
    body = markdown.markdown(
        prepared,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )
    return decorate_rendered_html(body, catalog=catalog, for_bundle=for_bundle)


def build_bundle_html(catalog: dict, pdf_prefix: str, vendor_prefix: str) -> str:
    panes = []
    for key, src_name, _ in SECTIONS:
        body = render_section_body(
            src_name,
            catalog=catalog,
            pdf_prefix=pdf_prefix,
            for_bundle=True,
        )

        def prefix_anchor(m, tk=key):
            aid = m.group(1)
            return f'<a id="{tk}--{aid}" data-anchor="{aid}"></a>'

        body = re.sub(r'<a id="([^"]+)"></a>', prefix_anchor, body)
        panes.append(
            f'<section class="tab-pane" id="pane-{key}" data-pane="{key}" hidden>\n'
            f"<article>\n{body}\n</article>\n</section>"
        )

    nav_buttons = [
        '<button type="button" class="tab-btn is-active" data-tab="mindmap">思维导图</button>'
    ]
    for key, _, label in SECTIONS:
        nav_buttons.append(
            f'<button type="button" class="tab-btn" data-tab="{key}">{html.escape(label)}</button>'
        )

    paper_options = [
        '<option value="">选择一篇论文在右侧直接阅读（共 55 篇）…</option>'
    ]
    for aid in paper_ids():
        title = catalog.get(aid, aid)
        paper_options.append(
            f'<option value="{aid}">[{aid}] {html.escape(title)}</option>'
        )

    tree_json = json.dumps(MINDMAP_TREE, ensure_ascii=False)
    catalog_json = json.dumps(catalog, ensure_ascii=False)

    # 内联 pdf.min.js，确保单文件直接打开即可用 Canvas 逐页渲染 PDF
    pdfjs_code = ""
    pdfjs_path = VENDOR_DIR / "pdf.min.js"
    if pdfjs_path.exists():
        pdfjs_code = pdfjs_path.read_text(encoding="utf-8").replace("</script", "<\\/script")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基模爷大学习 · 后训练、AI Infra 与实验工作链</title>
<style>
  :root {{
    --paper: #f4f0e8;
    --paper-deep: #ebe4d6;
    --ink: #1c1915;
    --muted: #665d52;
    --line: #dcd3c4;
    --card: #fffcf7;
    --accent: #8c3a1e;
    --link: #1d4e89;
    --pill-bg: #efe5d8;
    --reader-w: 48%;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; min-height: 100%; }}
  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Source Han Sans SC", sans-serif;
    font-size: 16px;
    line-height: 1.72;
  }}
  .topbar {{
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    flex-wrap: wrap;
    gap: 10px 16px;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    background: color-mix(in srgb, var(--paper) 94%, white);
    border-bottom: 1px solid var(--line);
    backdrop-filter: blur(8px);
  }}
  .brand {{
    display: flex;
    align-items: baseline;
    gap: 10px;
  }}
  .brand strong {{
    font-family: "Iowan Old Style", "Palatino Linotype", "Songti SC", serif;
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 0.01em;
  }}
  .brand span {{
    font-size: 12px;
    color: var(--muted);
  }}
  .tabs {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }}
  .tab-btn {{
    font: inherit;
    font-size: 14px;
    color: var(--ink);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 999px;
    padding: 5px 12px;
    cursor: pointer;
  }}
  .tab-btn:hover {{ background: var(--paper-deep); }}
  .tab-btn.is-active {{
    background: var(--accent);
    color: #fff;
    font-weight: 500;
  }}
  .quick-tools {{
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }}
  .paper-select {{
    font: inherit;
    font-size: 13px;
    max-width: 240px;
    padding: 5px 10px;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink);
  }}
  .search-input {{
    font: inherit;
    font-size: 13px;
    width: 145px;
    padding: 5px 10px;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink);
  }}
  .ghost-btn {{
    font: inherit;
    font-size: 13px;
    color: var(--ink);
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 5px 12px;
    cursor: pointer;
  }}
  .ghost-btn:hover {{ border-color: #b5a795; }}
  .workspace {{
    display: flex;
    align-items: flex-start;
    min-height: calc(100vh - 58px);
  }}
  .main-stage {{
    flex: 1 1 auto;
    min-width: 0;
  }}
  .mindmap-pane {{
    padding: 24px 28px 80px;
  }}
  .mindmap-head {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    max-width: 980px;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
  }}
  .mindmap-head p {{ margin: 0; font-size: 14px; color: var(--muted); }}
  .mindmap-actions {{ display: flex; gap: 8px; }}
  ul.tree, ul.tree ul {{ list-style: none; margin: 0; padding: 0; }}
  li.branch {{ margin: 8px 0; }}
  li.branch > ul {{
    margin: 8px 0 6px 14px;
    padding-left: 16px;
    border-left: 2px solid var(--c, var(--line));
  }}
  li.branch > ul[hidden] {{ display: none; }}
  .node {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: min(720px, 100%);
    min-height: 36px;
    padding: 5px 12px 5px 8px;
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--c, #8a8175);
    border-radius: 8px;
  }}
  .root > .node {{
    font-family: "Iowan Old Style", "Palatino Linotype", "Songti SC", serif;
    font-size: 18px;
    padding: 8px 14px;
    border-left-width: 4px;
  }}
  .twist {{
    width: 22px;
    height: 22px;
    padding: 0;
    border: 0;
    border-radius: 4px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    line-height: 1;
  }}
  .twist[aria-expanded="true"] {{ transform: rotate(90deg); }}
  .node a {{
    color: var(--ink);
    text-decoration: none;
    font-weight: 500;
  }}
  .node a:hover {{ color: var(--accent); text-decoration: underline; }}
  .hint {{ color: var(--muted); font-weight: 400; font-size: 12.5px; }}
  .spacer {{ width: 22px; flex: none; }}

  article {{
    max-width: 900px;
    margin: 0 auto;
    padding: 28px 24px 90px;
  }}
  h1, h2, h3 {{
    font-family: "Iowan Old Style", "Palatino Linotype", "Songti SC", serif;
    font-weight: 500;
    line-height: 1.32;
    scroll-margin-top: 74px;
  }}
  h1 {{ font-size: 32px; margin: 0 0 12px; }}
  h2 {{ font-size: 24px; margin: 36px 0 10px; padding-top: 10px; border-top: 1px solid var(--line); }}
  h3 {{ font-size: 19px; margin: 24px 0 8px; }}
  p {{ margin: 10px 0; }}
  a {{ color: var(--link); }}
  .paper-link {{
    font-weight: 500;
    text-decoration: none;
    border-bottom: 1px solid color-mix(in srgb, var(--link) 35%, transparent);
  }}
  .paper-link:hover {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .read-pill {{
    display: inline-block;
    margin-left: 6px;
    padding: 1px 7px;
    font-size: 11px;
    font-weight: 500;
    color: var(--accent);
    background: var(--pill-bg);
    border-radius: 999px;
    vertical-align: 1px;
  }}
  a.arxiv {{
    margin-left: 5px;
    font-size: 12px;
    color: var(--muted);
    text-decoration: none;
  }}
  a.arxiv:hover {{ text-decoration: underline; }}
  ul, ol {{ padding-left: 1.35em; }}
  li {{ margin: 5px 0; }}
  code {{
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 0.88em;
    background: #efe8dc;
    padding: 0.12em 0.38em;
    border-radius: 4px;
  }}
  pre {{
    overflow: auto;
    padding: 12px 14px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 8px;
  }}
  pre code {{ background: transparent; padding: 0; }}
  .table-wrap {{
    overflow-x: auto;
    margin: 14px 0 22px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 8px;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{
    text-align: left;
    vertical-align: top;
    padding: 9px 12px;
    border-bottom: 1px solid var(--line);
  }}
  tr:last-child td {{ border-bottom: 0; }}
  th {{ font-weight: 600; background: color-mix(in srgb, var(--paper) 65%, white); }}
  .math {{
    font-family: "Iowan Old Style", "Palatino Linotype", "Times New Roman", serif;
    font-style: italic;
  }}
  .flow {{
    margin: 14px 0 20px;
    padding: 12px 16px;
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
  }}
  .flow p {{ margin: 4px 0; font-size: 14.5px; }}
  .flash-target {{
    outline: 2px solid var(--accent);
    outline-offset: 4px;
    border-radius: 4px;
  }}

  /* 右侧分栏内嵌 PDF 阅读器 */
  .pdf-dock {{
    flex: 0 0 var(--reader-w);
    width: var(--reader-w);
    position: sticky;
    top: 58px;
    height: calc(100vh - 58px);
    display: flex;
    flex-direction: column;
    background: #2b2927;
    color: #f6f2eb;
    border-left: 1px solid var(--line);
  }}
  .pdf-dock[hidden] {{ display: none; }}
  .pdf-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: #1f1d1b;
    border-bottom: 1px solid #3c3834;
  }}
  .pdf-meta {{
    min-width: 0;
    flex: 1 1 180px;
  }}
  .pdf-meta strong {{
    display: block;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .pdf-meta span {{
    font-size: 11.5px;
    color: #b7afa4;
  }}
  .pdf-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    align-items: center;
  }}
  .pdf-actions a, .pdf-actions button {{
    font: inherit;
    font-size: 12px;
    color: #f6f2eb;
    background: #35322e;
    border: 1px solid #4d4842;
    border-radius: 6px;
    padding: 3px 8px;
    text-decoration: none;
    cursor: pointer;
  }}
  .pdf-actions a:hover, .pdf-actions button:hover {{ background: #47433d; }}
  .pdf-stage {{
    flex: 1;
    overflow: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    background: #3a3734;
  }}
  .pdf-stage canvas {{
    max-width: 100%;
    height: auto;
    background: #fff;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.35);
  }}
  .pdf-frame {{
    width: 100%;
    height: 100%;
    border: 0;
    background: #fff;
  }}
  @media (max-width: 640px) {{
    .pdf-dock {{
      position: fixed;
      inset: 58px 0 0 0;
      width: 100%;
      z-index: 40;
    }}
  }}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">
    <strong>基模爷大学习</strong>
    <span>后训练算法 · AI Infra · 实验工作链 · 55 篇论文页内阅读</span>
  </div>
  <nav class="tabs" aria-label="学习板块">
    {''.join(nav_buttons)}
  </nav>
  <div class="quick-tools">
    <input type="search" id="search-box" class="search-input" placeholder="筛选导图或章节词…">
    <select id="paper-picker" class="paper-select" aria-label="选择论文内嵌阅读">
      {''.join(paper_options)}
    </select>
  </div>
</header>

<div class="workspace">
  <main class="main-stage" id="main-stage">
    <section class="mindmap-pane" id="pane-mindmap" data-pane="mindmap">
      <div class="mindmap-head">
        <p>点左侧箭头展开层级；点任意条目直接跳到对应笔记章节。在笔记里点论文标题即可在页面右侧分栏直接看 PDF。</p>
        <div class="mindmap-actions">
          <button type="button" class="ghost-btn" id="open-all">全部展开</button>
          <button type="button" class="ghost-btn" id="close-all">收起到第二层</button>
        </div>
      </div>
      <ul class="tree" id="map"></ul>
    </section>
    {''.join(panes)}
  </main>

  <aside class="pdf-dock" id="pdf-dock" hidden aria-label="论文阅读器">
    <div class="pdf-bar">
      <div class="pdf-meta">
        <strong id="pdf-title">未选择论文</strong>
        <span id="pdf-sub">点击正文或论文索引里的任意论文标题即可在页内分栏阅读</span>
      </div>
      <div class="pdf-actions">
        <button type="button" id="pdf-prev">上一页</button>
        <span id="pdf-page-indicator" style="font-size:12px;padding:0 4px;">1 / 1</span>
        <button type="button" id="pdf-next">下一页</button>
        <button type="button" id="pdf-wide">加宽/还原</button>
        <a id="pdf-local" href="#" target="_blank" rel="noopener">新窗口</a>
        <a id="pdf-arxiv" href="#" target="_blank" rel="noopener">arXiv</a>
        <button type="button" id="pdf-close">关闭 ✕</button>
      </div>
    </div>
    <div class="pdf-stage" id="pdf-stage">
      <canvas id="pdf-canvas"></canvas>
      <iframe class="pdf-frame" id="pdf-frame" title="论文 PDF 阅读器" hidden></iframe>
    </div>
  </aside>
</div>

<script>{pdfjs_code}</script>
<script>
const TREE = {tree_json};
const PAPER_CATALOG = {catalog_json};
const PDF_PREFIX = {json.dumps(pdf_prefix)};
const VENDOR_PREFIX = {json.dumps(vendor_prefix)};
const HTML_TO_TAB = {json.dumps(HTML_TO_TAB, ensure_ascii=False)};

if (window.pdfjsLib) {{
  window.pdfjsLib.GlobalWorkerOptions.workerSrc = VENDOR_PREFIX + "pdf.worker.min.js";
}}

const mapEl = document.getElementById("map");
const dockEl = document.getElementById("pdf-dock");
const canvasEl = document.getElementById("pdf-canvas");
const frameEl = document.getElementById("pdf-frame");
const titleEl = document.getElementById("pdf-title");
const subEl = document.getElementById("pdf-sub");
const pageIndEl = document.getElementById("pdf-page-indicator");
const localLink = document.getElementById("pdf-local");
const arxivLink = document.getElementById("pdf-arxiv");
const pickerEl = document.getElementById("paper-picker");
const searchEl = document.getElementById("search-box");

let currentPdf = null;
let currentPage = 1;
let totalPages = 1;

function parseTarget(href) {{
  if (!href) return {{ tab: "overview", anchor: "" }};
  const parts = href.split("#");
  const file = parts[0];
  const anchor = parts[1] || "";
  const tab = HTML_TO_TAB[file] || "overview";
  return {{ tab, anchor }};
}}

function activateTab(tabKey, anchor) {{
  document.querySelectorAll(".tab-btn").forEach((btn) => {{
    btn.classList.toggle("is-active", btn.dataset.tab === tabKey);
  }});
  const mindmapPane = document.getElementById("pane-mindmap");
  mindmapPane.hidden = tabKey !== "mindmap";
  document.querySelectorAll(".tab-pane").forEach((pane) => {{
    pane.hidden = pane.dataset.pane !== tabKey;
  }});

  if (anchor && tabKey !== "mindmap") {{
    const target =
      document.getElementById(tabKey + "--" + anchor) ||
      document.querySelector(`#pane-${{tabKey}} [data-anchor="${{anchor}}"]`);
    if (target) {{
      const block = target.nextElementSibling || target;
      block.scrollIntoView({{ behavior: "smooth", block: "start" }});
      block.classList.add("flash-target");
      setTimeout(() => block.classList.remove("flash-target"), 1600);
      return;
    }}
  }}
  window.scrollTo({{ top: 0, behavior: "smooth" }});
}}

async function renderPdfPage(pageNum) {{
  if (!currentPdf) return;
  currentPage = Math.max(1, Math.min(pageNum, totalPages));
  pageIndEl.textContent = currentPage + " / " + totalPages;
  const page = await currentPdf.getPage(currentPage);
  const baseVp = page.getViewport({{ scale: 1.35 }});
  const ctx = canvasEl.getContext("2d");
  canvasEl.width = baseVp.width;
  canvasEl.height = baseVp.height;
  await page.render({{ canvasContext: ctx, viewport: baseVp }}).promise;
}}

async function openPaper(aid, customTitle) {{
  if (!aid) return;
  const title = customTitle || PAPER_CATALOG[aid] || ("arXiv:" + aid);
  const pdfUrl = PDF_PREFIX + aid + ".pdf";
  titleEl.textContent = title;
  subEl.textContent = "arXiv:" + aid + " · 本地 PDF";
  localLink.href = pdfUrl;
  arxivLink.href = "https://arxiv.org/abs/" + aid;
  pickerEl.value = aid;
  dockEl.hidden = false;
  document.body.classList.add("reader-open");

  if (window.pdfjsLib && location.protocol !== "file:") {{
    try {{
      canvasEl.hidden = false;
      frameEl.hidden = true;
      pageIndEl.textContent = "加载中…";
      currentPdf = await window.pdfjsLib.getDocument(pdfUrl).promise;
      totalPages = currentPdf.numPages;
      await renderPdfPage(1);
      return;
    }} catch (err) {{
      console.warn("PDF.js 回退到原生内嵌:", err);
    }}
  }}
  canvasEl.hidden = true;
  frameEl.hidden = false;
  frameEl.src = pdfUrl;
  pageIndEl.textContent = "原生视图";
}}

function closePaper() {{
  dockEl.hidden = true;
  document.body.classList.remove("reader-open");
}}

function draw(node, depth, color) {{
  const tone = node.color || color || "#8a8175";
  const li = document.createElement("li");
  li.className = depth === 0 ? "branch root" : "branch";
  li.style.setProperty("--c", tone);

  const card = document.createElement("div");
  card.className = "node";
  card.style.setProperty("--c", tone);

  if (node.c && node.c.length) {{
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "twist";
    btn.textContent = "▸";
    const open = depth < 2;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", (open ? "收起 " : "展开 ") + node.t);
    btn.addEventListener("click", () => toggleBranch(li, btn));
    card.appendChild(btn);
  }} else {{
    const pad = document.createElement("span");
    pad.className = "spacer";
    card.appendChild(pad);
  }}

  const link = document.createElement("a");
  const dest = parseTarget(node.h);
  link.href = "#" + dest.tab + (dest.anchor ? ":" + dest.anchor : "");
  link.textContent = node.t;
  link.addEventListener("click", (ev) => {{
    ev.preventDefault();
    activateTab(dest.tab, dest.anchor);
  }});
  card.appendChild(link);

  if (node.s) {{
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.textContent = node.s;
    card.appendChild(hint);
  }}
  li.appendChild(card);

  if (node.c && node.c.length) {{
    const ul = document.createElement("ul");
    if (depth >= 2) ul.hidden = true;
    node.c.forEach((child) => ul.appendChild(draw(child, depth + 1, tone)));
    li.appendChild(ul);
  }}
  return li;
}}

function toggleBranch(li, btn) {{
  const ul = li.querySelector(":scope > ul");
  if (!ul) return;
  ul.hidden = !ul.hidden;
  const open = !ul.hidden;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
}}

function depthOf(li) {{
  let d = 0;
  let cur = li.parentElement;
  while (cur && !cur.classList.contains("tree")) {{
    if (cur.tagName === "LI") d += 1;
    cur = cur.parentElement;
  }}
  return d;
}}

function setAllBranches(open) {{
  document.querySelectorAll("li.branch > ul").forEach((ul) => {{
    const li = ul.parentElement;
    const show = open || depthOf(li) < 2;
    ul.hidden = !show;
    const btn = li.querySelector(":scope > .node > .twist");
    if (btn) btn.setAttribute("aria-expanded", show ? "true" : "false");
  }});
}}

mapEl.appendChild(draw(TREE, 0));

document.getElementById("open-all").addEventListener("click", () => setAllBranches(true));
document.getElementById("close-all").addEventListener("click", () => setAllBranches(false));

document.querySelectorAll(".tab-btn").forEach((btn) => {{
  btn.addEventListener("click", () => activateTab(btn.dataset.tab, ""));
}});

document.getElementById("main-stage").addEventListener("click", (ev) => {{
  const paperAnchor = ev.target.closest("a[data-paper]");
  if (paperAnchor) {{
    ev.preventDefault();
    openPaper(paperAnchor.dataset.paper, paperAnchor.dataset.title);
    return;
  }}
  const gotoAnchor = ev.target.closest("a[data-goto]");
  if (gotoAnchor) {{
    ev.preventDefault();
    const [tab, anchor] = gotoAnchor.dataset.goto.split(":");
    activateTab(tab, anchor || "");
  }}
}});

pickerEl.addEventListener("change", () => {{
  if (pickerEl.value) openPaper(pickerEl.value);
}});

document.getElementById("pdf-prev").addEventListener("click", () => renderPdfPage(currentPage - 1));
document.getElementById("pdf-next").addEventListener("click", () => renderPdfPage(currentPage + 1));
document.getElementById("pdf-close").addEventListener("click", closePaper);

let wideMode = false;
document.getElementById("pdf-wide").addEventListener("click", () => {{
  wideMode = !wideMode;
  document.documentElement.style.setProperty("--reader-w", wideMode ? "62%" : "48%");
}});

searchEl.addEventListener("input", () => {{
  const q = searchEl.value.trim().toLowerCase();
  if (!q) {{
    document.querySelectorAll("li.branch").forEach((li) => {{ li.style.display = ""; }});
    setAllBranches(false);
    return;
  }}
  setAllBranches(true);
  document.querySelectorAll("li.branch").forEach((li) => {{
    const text = li.textContent.toLowerCase();
    li.style.display = text.includes(q) ? "" : "none";
  }});
}});
</script>
</body>
</html>
"""


def render_standalone_pages(catalog: dict):
    nav_items = [("思维导图.html", "导图")] + [
        (src[:-3] + ".html", label) for _, src, label in SECTIONS
    ]
    for _, src_name, _ in SECTIONS:
        body = render_section_body(
            src_name, catalog=catalog, pdf_prefix="论文/", for_bundle=False
        )
        out_name = src_name[:-3] + ".html"
        links = []
        for href, label in nav_items:
            cls = ' class="here"' if href == out_name else ""
            links.append(f'<a{cls} href="{href}">{label}</a>')
        links.append('<a href="release/基模爷大学习.html">合成单页版 ✦</a>')
        page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(src_name[:-3])} · 基模爷大学习</title>
<link rel="stylesheet" href="笔记.css">
</head>
<body>
<nav>{''.join(links)}</nav>
<div class="page-split" id="page-split">
  <article>{body}</article>
  <aside class="inline-reader" id="inline-reader" hidden>
    <div class="inline-reader-bar">
      <strong id="ir-title">论文阅读</strong>
      <div>
        <a id="ir-open" href="#" target="_blank" rel="noopener">新窗口</a>
        <button type="button" id="ir-close">关闭 ✕</button>
      </div>
    </div>
    <iframe id="ir-frame" title="论文 PDF"></iframe>
  </aside>
</div>
<script>
document.addEventListener("click", (e) => {{
  const a = e.target.closest("a[data-paper]");
  if (!a) return;
  e.preventDefault();
  const box = document.getElementById("inline-reader");
  const frame = document.getElementById("ir-frame");
  document.getElementById("ir-title").textContent = a.dataset.title || a.textContent;
  document.getElementById("ir-open").href = a.getAttribute("href");
  frame.src = a.getAttribute("href");
  box.hidden = false;
  document.getElementById("page-split").classList.add("has-reader");
}});
document.getElementById("ir-close").addEventListener("click", () => {{
  document.getElementById("inline-reader").hidden = true;
  document.getElementById("page-split").classList.remove("has-reader");
}});
</script>
</body>
</html>
"""
        (ROOT / out_name).write_text(page, encoding="utf-8")
        print("render", out_name, flush=True)


def render_all():
    catalog = parse_paper_catalog()
    RELEASE_DIR.mkdir(exist_ok=True)

    release_html = build_bundle_html(
        catalog=catalog, pdf_prefix="../论文/", vendor_prefix="../vendor/"
    )
    release_file = RELEASE_DIR / "基模爷大学习.html"
    release_file.write_text(release_html, encoding="utf-8")
    print("render", release_file.relative_to(ROOT), len(release_html), flush=True)

    root_bundle = build_bundle_html(
        catalog=catalog, pdf_prefix="论文/", vendor_prefix="vendor/"
    )
    (ROOT / "index.html").write_text(root_bundle, encoding="utf-8")
    (ROOT / "思维导图.html").write_text(root_bundle, encoding="utf-8")
    print("render index.html & 思维导图.html", len(root_bundle), flush=True)

    render_standalone_pages(catalog=catalog)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    errors = download_all() if cmd in ("download", "all") else 0
    if cmd in ("render", "all"):
        render_all()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
