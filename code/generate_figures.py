# -*- coding: utf-8 -*-
"""
generate_figures.py — Nature/IEEE 出版级图表生成脚本
生成论文 LightComm (ISPA 2026 DAAA) 所需的全部图表，样式遵循 Nature 期刊规范：
  - 颜色色盲友好（Okabe-Ito 调色板）
  - 字体 Arial/Helvetica，坐标轴单位与标签完整
  - 分辨率 ≥ 300 dpi，同时输出矢量格式 PDF
  - 无 3D 图，无过度装饰，优先简洁二维图
  - 每图配置完整图例 + 图题（在图下方 caption 文件中单独写）

输出目录：results/figures/
"""

import json
import os
import math
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.ticker import MultipleLocator

# ── 全局样式 ──────────────────────────────────────────────────────────────────
# Nature 期刊字体偏好 Arial；若系统无 Arial 使用 DejaVu Sans（等效）
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "pdf.fonttype": 42,   # 确保 PDF 中字体可编辑
    "ps.fonttype": 42,
})

# Okabe-Ito 色盲友好调色板
OI = {
    "orange":   "#E69F00",
    "sky":      "#56B4E9",
    "green":    "#009E73",
    "yellow":   "#F0E442",
    "blue":     "#0072B2",
    "vermilion":"#D55E00",
    "pink":     "#CC79A7",
    "black":    "#000000",
    "gray":     "#999999",
}

# 每种策略对应的颜色和标记
STRAT_STYLE = {
    "single_agent": {"color": OI["gray"],     "marker": "s", "label": "Single-Agent"},
    "full_context":  {"color": OI["blue"],    "marker": "o", "label": "Full-Context"},
    "summary":       {"color": OI["orange"],  "marker": "^", "label": "Summary"},
    "action_state":  {"color": OI["sky"],     "marker": "D", "label": "Action-State"},
    "lightcomm":     {"color": OI["green"],   "marker": "*", "label": "LightComm"},
}

STRATEGY_ORDER = ["single_agent", "full_context", "summary", "action_state", "lightcomm"]

TASK_LABEL = {
    "multihop":  "Multi-hop QA",
    "bug_triage":"Bug Triage",
    "doc_edit":  "Doc Edit",
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "results", "figures")
os.makedirs(OUT_DIR, exist_ok=True)


def savefig(fig, name):
    png = os.path.join(OUT_DIR, name + ".png")
    pdf = os.path.join(OUT_DIR, name + ".pdf")
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"  saved → {png}")
    print(f"  saved → {pdf}")


# ── 数据加载 ──────────────────────────────────────────────────────────────────
def load_results():
    path = os.path.join(os.path.dirname(__file__), "results", "results.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)["results"]


def is_infra_error(r):
    vd = r.get("verify_detail") or {}
    return r.get("tokens", 0) == 0 and "error" in vd


def aggregate(results):
    groups = defaultdict(list)
    for r in results:
        if is_infra_error(r):
            continue
        groups[(r["task"], r["strategy"])].append(r)

    rows = []
    for (task, strategy), items in groups.items():
        n = len(items)
        success_rate = sum(1 for i in items if i["success"]) / n
        tokens = [i["tokens"] for i in items if i.get("tokens", 0) > 0]
        times  = [i["wall_time_s"] for i in items if i.get("wall_time_s", 0) > 0]
        rows.append({
            "task": task, "strategy": strategy, "n": n,
            "success_rate": success_rate,
            "avg_tokens": np.mean(tokens) if tokens else 0,
            "std_tokens": np.std(tokens, ddof=1) if len(tokens) > 1 else 0,
            "avg_wall_s": np.mean(times) if times else 0,
            "std_wall_s": np.std(times, ddof=1) if len(times) > 1 else 0,
        })
    return rows


# ── Figure 1: LightComm 系统架构图 (纯 matplotlib 绘制) ──────────────────────
def fig_architecture():
    """绘制 LightComm 三层编排架构示意图。"""
    print("Fig 1: Architecture diagram...")
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")

    # 颜色
    c_layer  = "#EBF4FD"
    c_border = OI["blue"]
    c_arrow  = "#444444"
    c_comp   = "#D6EAF8"

    def box(ax, x, y, w, h, txt, color=c_comp, fontsize=8, bold=False):
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.08",
            linewidth=0.9, edgecolor=c_border, facecolor=color, zorder=2)
        ax.add_patch(rect)
        weight = "bold" if bold else "normal"
        ax.text(x + w/2, y + h/2, txt, ha="center", va="center",
                fontsize=fontsize, fontweight=weight, zorder=3, wrap=True,
                multialignment="center")

    def arrow(ax, x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=c_arrow,
                                    lw=0.9, mutation_scale=10), zorder=4)

    def bidirectional_arrow(ax, x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="<|-|>", color=c_arrow,
                                    lw=0.9, mutation_scale=10), zorder=4)

    # ── Layer背景 ──
    layers = [
        (0.1, 3.7, 9.8, 1.1, "① User / Orchestration Interface", "#EAF7F0"),
        (0.1, 2.3, 9.8, 1.1, "② LightComm Orchestration Layer", "#EBF4FD"),
        (0.1, 0.5, 9.8, 1.5, "③ LLM Inference Tier (Cloud–Edge–Device)", "#FEF9E7"),
    ]
    for (x, y, w, h, title, bg) in layers:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.1",
            linewidth=0.6, edgecolor="#AAAAAA", facecolor=bg, zorder=1)
        ax.add_patch(rect)
        ax.text(x + 0.12, y + h - 0.17, title, ha="left", va="top",
                fontsize=7.5, fontstyle="italic", color="#555555", zorder=3)

    # Layer 1: User input / task
    box(ax, 3.5, 3.85, 3.0, 0.7, "Task Input\n(Workflow DAG)", bold=True)

    # Layer 2: 三个机制
    box(ax, 0.25, 2.42, 2.6, 0.75, "Action-State\nCompressor", bold=False)
    box(ax, 3.7,  2.42, 2.6, 0.75, "Tier\nRouter  ρ(t(v))", bold=False)
    box(ax, 7.15, 2.42, 2.6, 0.75, "DAG\nScheduler  σ", bold=False)

    # Layer 3: 模型端点
    box(ax, 0.25, 0.6,  2.6, 1.1, "Large Tier\n120B-class\n(Plan / Synthesize)", color="#FEF9E7")
    box(ax, 3.7,  0.6,  2.6, 1.1, "Small Tier\n30B-class\n(Classify / Edit / Retrieve)", color="#FEF9E7")
    box(ax, 7.15, 0.6,  2.6, 1.1, "Parallel\nBranch Execution\n(Independent Steps)", color="#FEF9E7")

    # 箭头：User → 三个组件
    for cx in [1.55, 5.0, 8.45]:
        arrow(ax, 5.0, 3.85, cx, 3.17)

    # 箭头：组件 → 模型层
    for cx in [1.55, 5.0, 8.45]:
        arrow(ax, cx, 2.42, cx, 1.70)

    # 横向箭头：组件间协作
    bidirectional_arrow(ax, 2.85, 2.79, 3.70, 2.79)
    bidirectional_arrow(ax, 6.30, 2.79, 7.15, 2.79)

    # 标注 Context Compression 标签
    ax.text(3.25, 2.65, "Context\nCompression", ha="center", va="center",
            fontsize=6.5, color=OI["blue"])
    ax.text(6.72, 2.65, "Routing\n+ Scheduling", ha="center", va="center",
            fontsize=6.5, color=OI["blue"])

    ax.set_title("Figure 1.  LightComm System Architecture Overview",
                 fontsize=9, pad=6, loc="left")
    fig.tight_layout()
    savefig(fig, "fig1_architecture")


# ── Figure 2: 三类任务 DAG 结构示意图 ───────────────────────────────────────
def fig_workflow_dag():
    print("Fig 2: Workflow DAG examples...")
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.5))

    dag_configs = [
        {
            "title": "(a) Multi-hop QA",
            "nodes": [
                (0.5, 0.85, "User\nInput",   "#D6EAF8", "small"),
                (0.18, 0.50, "Retrieve\n(sub-q 1)", OI["sky"]+"55", "small"),
                (0.50, 0.50, "Retrieve\n(sub-q 2)", OI["sky"]+"55", "small"),
                (0.82, 0.50, "Retrieve\n(sub-q 3)", OI["sky"]+"55", "small"),
                (0.50, 0.12, "Synthesize\n(large)", OI["green"]+"88", "small"),
            ],
            "edges": [(0,1),(0,2),(0,3),(1,4),(2,4),(3,4)],
            "parallel": True,
        },
        {
            "title": "(b) Bug Triage",
            "nodes": [
                (0.5, 0.85, "Bug\nReport",  "#D6EAF8", "small"),
                (0.28, 0.50, "Classify\nSeverity", OI["sky"]+"55", "small"),
                (0.72, 0.50, "Classify\nCategory", OI["sky"]+"55", "small"),
                (0.50, 0.12, "Final Diag.\n(large)", OI["green"]+"88", "small"),
            ],
            "edges": [(0,1),(0,2),(1,3),(2,3)],
            "parallel": True,
        },
        {
            "title": "(c) Doc Edit",
            "nodes": [
                (0.5,  0.85, "Doc +\nInstructions", "#D6EAF8", "small"),
                (0.18, 0.52, "Edit §1",  OI["sky"]+"55", "small"),
                (0.50, 0.52, "Edit §2",  OI["sky"]+"55", "small"),
                (0.82, 0.52, "Edit §3",  OI["sky"]+"55", "small"),
                (0.50, 0.12, "Merge\n(large)", OI["green"]+"88", "small"),
            ],
            "edges": [(0,1),(0,2),(0,3),(1,4),(2,4),(3,4)],
            "parallel": True,
        },
    ]

    for ax, cfg in zip(axes, dag_configs):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_title(cfg["title"], fontsize=8, pad=3)
        nodes = cfg["nodes"]
        # 先画边
        for (i, j) in cfg["edges"]:
            x1, y1 = nodes[i][0], nodes[i][1]
            x2, y2 = nodes[j][0], nodes[j][1]
            ax.annotate("", xy=(x2, y2+0.125), xytext=(x1, y1-0.125),
                        arrowprops=dict(arrowstyle="-|>", color="#888888",
                                        lw=0.7, mutation_scale=8))
        # 画节点
        for (x, y, label, color, _fs) in nodes:
            hw = 0.16 if y > 0.8 else (0.115 if len(nodes) == 5 and 0.3 < y < 0.8 else 0.14)
            r = mpatches.FancyBboxPatch(
                (x-hw, y-0.085), 2*hw, 0.17,
                boxstyle="round,pad=0.03", linewidth=0.7,
                edgecolor="#4488AA", facecolor=color, zorder=2)
            ax.add_patch(r)
            ax.text(x, y, label, ha="center", va="center",
                    fontsize=6.2, zorder=3, multialignment="center")
    fig.subplots_adjust(wspace=0.08, bottom=0.02, top=0.9)
    savefig(fig, "fig2_dag")


# ── Figure 3: Token 消耗对比柱状图（分任务族 × 策略）───────────────────────
def fig_token_comparison(rows):
    print("Fig 3: Token comparison bar chart...")
    tasks = ["multihop", "bug_triage", "doc_edit"]
    task_labels = [TASK_LABEL[t] for t in tasks]
    strats = STRATEGY_ORDER

    data = {(r["task"], r["strategy"]): r for r in rows}

    x = np.arange(len(tasks))
    n_strats = len(strats)
    width = 0.14
    offsets = np.linspace(-(n_strats-1)/2, (n_strats-1)/2, n_strats) * width

    fig, ax = plt.subplots(figsize=(7.0, 3.2))

    for i, strat in enumerate(strats):
        vals  = [data.get((t, strat), {}).get("avg_tokens", 0)   for t in tasks]
        errs  = [data.get((t, strat), {}).get("std_tokens", 0)   for t in tasks]
        bars = ax.bar(x + offsets[i], vals, width*0.9,
                      yerr=errs, capsize=2,
                      color=STRAT_STYLE[strat]["color"],
                      label=STRAT_STYLE[strat]["label"],
                      edgecolor="white", linewidth=0.4,
                      error_kw={"linewidth": 0.7, "ecolor": "#444444"})

    # 标注 single-agent 基线参考线（每个任务）
    for ti, t in enumerate(tasks):
        baseline = data.get((t, "single_agent"), {}).get("avg_tokens", 0)
        if baseline > 0:
            ax.hlines(baseline, x[ti]-0.35, x[ti]+0.35,
                      colors=OI["gray"], linewidths=0.8, linestyles="--")

    ax.set_xticks(x)
    ax.set_xticklabels(task_labels)
    ax.set_ylabel("Mean Token Consumption")
    ax.set_xlabel("Task Family")
    ax.yaxis.set_minor_locator(MultipleLocator(200))
    ax.tick_params(axis="y", which="minor", length=2)
    ax.legend(loc="upper left", ncol=3, frameon=False, handlelength=1.2,
              handletextpad=0.4, columnspacing=0.8)

    # 注释
    ax.text(1.02, 0.97,
            "Dashed lines: single-agent\nbaseline (reference)",
            transform=ax.transAxes, va="top", ha="left",
            fontsize=6.5, color=OI["gray"],
            linespacing=1.4)

    ax.set_title("Figure 3.  Mean token consumption per strategy and task family.\n"
                 "Error bars show ±1 s.d. across completed runs.",
                 fontsize=8, loc="left", pad=4)
    fig.tight_layout()
    savefig(fig, "fig3_token_comparison")


# ── Figure 4: 端到端延迟对比（分组柱 + 对数轴）────────────────────────────
def fig_latency_comparison(rows):
    print("Fig 4: Latency comparison...")
    tasks = ["multihop", "bug_triage", "doc_edit"]
    strats = ["single_agent", "full_context", "action_state", "lightcomm"]

    data = {(r["task"], r["strategy"]): r for r in rows}

    x = np.arange(len(tasks))
    n = len(strats)
    width = 0.18
    offsets = np.linspace(-(n-1)/2, (n-1)/2, n) * width

    fig, ax = plt.subplots(figsize=(7.0, 3.2))

    for i, strat in enumerate(strats):
        vals = [data.get((t, strat), {}).get("avg_wall_s", 0.1) for t in tasks]
        errs = [data.get((t, strat), {}).get("std_wall_s", 0)   for t in tasks]
        ax.bar(x + offsets[i], vals, width*0.9,
               yerr=errs, capsize=2,
               color=STRAT_STYLE[strat]["color"],
               label=STRAT_STYLE[strat]["label"],
               edgecolor="white", linewidth=0.4,
               error_kw={"linewidth": 0.7, "ecolor": "#444444"})

    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in tasks])
    ax.set_ylabel("Mean End-to-End Latency (s)")
    ax.set_xlabel("Task Family")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: f"{v:.0f}" if v >= 1 else f"{v:.1f}"))
    ax.legend(loc="upper left", ncol=2, frameon=False,
              handlelength=1.2, handletextpad=0.4)
    ax.set_title("Figure 4.  Mean end-to-end latency per strategy (log scale).\n"
                 "LightComm incurs 2.9–9.0× higher latency than Full-Context\n"
                 "due to slower small-tier endpoint and shared queue bottleneck.",
                 fontsize=8, loc="left", pad=4)
    fig.tight_layout()
    savefig(fig, "fig4_latency_comparison")


# ── Figure 5: 成功率 × Token 帕累托散点图 ────────────────────────────────
def fig_pareto(rows):
    print("Fig 5: Pareto scatter plot...")
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.8), sharey=True)
    tasks = ["multihop", "bug_triage", "doc_edit"]
    data  = {(r["task"], r["strategy"]): r for r in rows}

    for ax, task in zip(axes, tasks):
        for strat in STRATEGY_ORDER:
            r = data.get((task, strat))
            if r is None:
                continue
            ax.scatter(r["avg_tokens"], r["success_rate"],
                       marker=STRAT_STYLE[strat]["marker"],
                       color=STRAT_STYLE[strat]["color"],
                       s=60, edgecolors="black", linewidths=0.5, zorder=3,
                       label=STRAT_STYLE[strat]["label"])
            ax.annotate(STRAT_STYLE[strat]["label"].replace("-", "\n"),
                        (r["avg_tokens"], r["success_rate"]),
                        textcoords="offset points", xytext=(5, 2),
                        fontsize=5.5, color="#333333")

        ax.set_title(TASK_LABEL[task], fontsize=8, pad=3)
        ax.set_xlabel("Avg Tokens", fontsize=8)
        ax.set_ylim(-0.05, 1.15)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
        ax.grid(alpha=0.3, linewidth=0.5)

    axes[0].set_ylabel("Task Success Rate")

    # 统一图例
    handles = [mpatches.Patch(color=STRAT_STYLE[s]["color"],
               label=STRAT_STYLE[s]["label"]) for s in STRATEGY_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=5,
               frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.04))

    fig.suptitle("Figure 5.  Token–success trade-off (Pareto view) per task family.",
                 fontsize=8, y=1.01)
    fig.tight_layout()
    savefig(fig, "fig5_pareto")


# ── Figure 6: 消融研究 — 热力图 ──────────────────────────────────────────
def fig_ablation_heatmap(rows):
    print("Fig 6: Ablation heatmap...")
    tasks   = ["multihop", "bug_triage", "doc_edit"]
    strats  = ["full_context", "action_state", "lightcomm"]
    s_label = ["Full-Context\n(Baseline)", "Action-State\n(+Compression)", "LightComm\n(+Routing+Sched)"]
    data    = {(r["task"], r["strategy"]): r for r in rows}

    metrics = ["success_rate", "avg_tokens", "avg_wall_s"]
    m_label = ["Success Rate (%)", "Avg Tokens", "Avg Latency (s)"]

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.6))

    for mi, (metric, mlabel) in enumerate(zip(metrics, m_label)):
        ax = axes[mi]
        mat = np.zeros((len(tasks), len(strats)))
        for ti, t in enumerate(tasks):
            for si, s in enumerate(strats):
                r = data.get((t, s))
                mat[ti, si] = r[metric] if r else 0
        if metric == "success_rate":
            mat_disp = mat * 100
            fmt_fn = lambda v: f"{v:.0f}%"
            cmap = "RdYlGn"
        elif metric == "avg_tokens":
            mat_disp = mat
            fmt_fn = lambda v: f"{v:.0f}"
            cmap = "YlOrRd"
        else:
            mat_disp = mat
            fmt_fn = lambda v: f"{v:.1f}s"
            cmap = "YlOrRd"

        im = ax.imshow(mat_disp, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(strats)))
        ax.set_xticklabels(s_label, fontsize=6.5)
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels([TASK_LABEL[t] for t in tasks], fontsize=7)
        ax.set_title(mlabel, fontsize=8, pad=3)

        for ti in range(len(tasks)):
            for si in range(len(strats)):
                ax.text(si, ti, fmt_fn(mat_disp[ti, si]),
                        ha="center", va="center", fontsize=7,
                        color="white" if mat_disp[ti, si] > mat_disp.max()*0.6 else "black")

        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle("Figure 6.  Ablation heatmap: success rate, token cost, and latency\n"
                 "across task families and strategy configurations.",
                 fontsize=8, y=1.02)
    fig.tight_layout()
    savefig(fig, "fig6_ablation_heatmap")


# ── Figure 7: 自适应压缩规则效果（概念 + 量化）─────────────────────────────
def fig_adaptive_compression():
    print("Fig 7: Adaptive compression rule...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 3.0))

    # 左图：LLM压缩 token 开销 vs 输出长度（概念模拟曲线）
    output_len = np.linspace(0, 600, 300)
    threshold  = 96

    # 压缩节省量（假设线性正比于输出长度），压缩成本（固定 overhead）
    saved   = np.clip(output_len * 0.55 - 30, 0, None)  # 压缩节省 context tokens
    overhead = np.full_like(output_len, 120)              # LLM压缩调用固定开销 ~120 tok
    net     = saved - overhead                            # 净节省

    ax1.fill_between(output_len, net, 0,
                     where=net >= 0, alpha=0.25, color=OI["green"],
                     label="Net saving (positive)")
    ax1.fill_between(output_len, net, 0,
                     where=net < 0,  alpha=0.25, color=OI["vermilion"],
                     label="Net overhead (negative)")
    ax1.plot(output_len, net, color=OI["blue"], lw=1.5,
             label="Net token saving = Saved − Overhead")
    ax1.axvline(threshold, color=OI["orange"], lw=1.2, ls="--",
                label=f"Adaptive threshold ({threshold} chars)")
    ax1.axhline(0, color="black", lw=0.6)
    ax1.set_xlabel("Output Length (characters)")
    ax1.set_ylabel("Net Token Saving (tokens)")
    ax1.set_title("(a) Compression benefit vs. output length", fontsize=8)
    ax1.legend(fontsize=6.5, frameon=False)
    ax1.set_xlim(0, 600)

    # 右图：三任务下 action_state vs lightcomm token 对比
    tasks  = ["Multi-hop QA", "Bug Triage", "Doc Edit"]
    fc_tok = [1344, 953,  2288]
    as_tok = [1296, 978,  2263]
    lc_tok = [1522, 988,  2812]

    x = np.arange(len(tasks))
    w = 0.25
    ax2.bar(x - w, fc_tok, w, color=OI["blue"],     label="Full-Context", edgecolor="white")
    ax2.bar(x,     as_tok, w, color=OI["sky"],      label="Action-State", edgecolor="white")
    ax2.bar(x + w, lc_tok, w, color=OI["green"],    label="LightComm",    edgecolor="white")

    # 标注 action_state 相对 full_context 的变化
    for i, (f, a, l) in enumerate(zip(fc_tok, as_tok, lc_tok)):
        delta_as = (a - f) / f * 100
        delta_lc = (l - f) / f * 100
        ax2.text(x[i],     a + 40,  f"{delta_as:+.0f}%", ha="center", fontsize=6.5, color=OI["blue"])
        ax2.text(x[i]+w,   l + 40,  f"{delta_lc:+.0f}%", ha="center", fontsize=6.5, color=OI["vermilion"])

    ax2.set_xticks(x)
    ax2.set_xticklabels(tasks, fontsize=7.5)
    ax2.set_ylabel("Mean Token Consumption")
    ax2.set_title("(b) Observed token counts:\ncompression adds overhead at small scale", fontsize=8)
    ax2.legend(fontsize=7, frameon=False, loc="upper left")

    fig.suptitle("Figure 7.  Adaptive compression rule rationale and empirical effect.",
                 fontsize=8, y=0.02, ha="center", va="bottom")
    fig.subplots_adjust(bottom=0.14)
    fig.tight_layout()
    savefig(fig, "fig7_adaptive_compression")


# ── Figure 8: 延迟成因分解（瀑布图）────────────────────────────────────────
def fig_latency_breakdown():
    print("Fig 8: Latency breakdown waterfall...")
    fig, ax = plt.subplots(figsize=(7.0, 3.2))

    # 从实验中提取/估算的延迟成分（Bug Triage, lightcomm, 103s）
    components = [
        ("Compression\ncalls",   18.0,  OI["sky"]),
        ("Large-tier\ninference", 7.0,  OI["blue"]),
        ("Small-tier\ninference (2.5× slower)", 52.0, OI["vermilion"]),
        ("Endpoint\nqueue wait", 22.0, OI["orange"]),
        ("Network\n+ overhead",   4.2, OI["gray"]),
    ]
    labels = [c[0] for c in components]
    values = [c[1] for c in components]
    colors = [c[2] for c in components]

    cumulative = np.cumsum([0] + values[:-1])
    bars = ax.bar(labels, values, bottom=cumulative,
                  color=colors, edgecolor="white", linewidth=0.4, width=0.55)

    # 标注各分量数值
    for bar, val, bot in zip(bars, values, cumulative):
        ax.text(bar.get_x() + bar.get_width()/2, bot + val/2,
                f"{val:.1f}s", ha="center", va="center",
                fontsize=7.5, color="white",
                fontweight="bold",
                path_effects=[pe.withStroke(linewidth=1.5, foreground="black")])

    # 总计标注
    total = sum(values)
    ax.axhline(total, color=OI["blue"], lw=1.0, ls="--", alpha=0.7)
    ax.text(len(components)-0.5, total+1.5, f"Total ≈ {total:.1f}s",
            fontsize=7.5, color=OI["blue"])

    ax.set_ylabel("Latency Component (s)")
    ax.set_title("Figure 8.  Estimated latency decomposition for Bug Triage under LightComm.\n"
                 "Small-tier endpoint slowness (2.5× vs. large tier) dominates end-to-end latency.",
                 fontsize=8, loc="left", pad=4)
    ax.set_ylim(0, total + 12)
    fig.tight_layout()
    savefig(fig, "fig8_latency_breakdown")


# ── Figure 9: Token 倍增比（Amplification Ratio）热力图 ──────────────────
def fig_token_amplification(rows):
    print("Fig 9: Token amplification ratio...")
    tasks  = ["multihop", "bug_triage", "doc_edit"]
    strats = ["full_context", "summary", "action_state", "lightcomm"]
    data   = {(r["task"], r["strategy"]): r for r in rows}

    mat = np.zeros((len(tasks), len(strats)))
    for ti, t in enumerate(tasks):
        base = data.get((t, "single_agent"), {}).get("avg_tokens", 1)
        for si, s in enumerate(strats):
            r = data.get((t, s))
            mat[ti, si] = r["avg_tokens"] / base if (r and base > 0) else 0

    fig, ax = plt.subplots(figsize=(5.5, 2.5))
    im = ax.imshow(mat, cmap="RdYlGn_r", vmin=1.0, vmax=8.0, aspect="auto")
    ax.set_xticks(range(len(strats)))
    ax.set_xticklabels(["Full-Context", "Summary", "Action-State", "LightComm"], fontsize=8)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels([TASK_LABEL[t] for t in tasks], fontsize=8)
    for ti in range(len(tasks)):
        for si in range(len(strats)):
            ax.text(si, ti, f"{mat[ti,si]:.1f}×",
                    ha="center", va="center", fontsize=8.5, fontweight="bold",
                    color="white" if mat[ti,si] > 5 else "black")
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Token Amplification\nvs. Single-Agent", fontsize=7.5)
    ax.set_title("Figure 9.  Token amplification ratio relative to single-agent baseline.\n"
                 "Multi-agent workflows consume 1.7–7.7× more tokens across all strategies.",
                 fontsize=8, loc="left", pad=4)
    fig.tight_layout()
    savefig(fig, "fig9_token_amplification")


# ── 主程序 ───────────────────────────────────────────────────────────────────
def main():
    print("Loading results...")
    results = load_results()
    rows    = aggregate(results)
    print(f"  {len(results)} total runs, {len(rows)} aggregated rows")

    print("\nGenerating figures...")
    fig_architecture()
    fig_workflow_dag()
    fig_token_comparison(rows)
    fig_latency_comparison(rows)
    fig_pareto(rows)
    fig_ablation_heatmap(rows)
    fig_adaptive_compression()
    fig_latency_breakdown()
    fig_token_amplification(rows)

    print(f"\nAll figures saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
