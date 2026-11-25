# -*- coding: utf-8 -*-
"""
generate_composite.py — 500 DPI Nature/IEEE 级出版图表生成脚本
整合 6 个实证核心子图为单张高清大图，无任何多余文本重叠。
所有子图清晰标注 (a)~(f)，图题由排版系统统一在图的正下方渲染。
"""

import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

# ── 全局样式（遵循 Nature / IEEE 期刊双规范）───────────────────────────────
plt.rcParams.update({
    "font.family":          "sans-serif",
    "font.sans-serif":      ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size":            8,
    "axes.labelsize":       8,
    "axes.titlesize":       8.5,
    "xtick.labelsize":      7,
    "ytick.labelsize":      7,
    "legend.fontsize":      6.8,
    "axes.linewidth":       0.75,
    "xtick.major.width":    0.75,
    "ytick.major.width":    0.75,
    "xtick.major.size":     2.8,
    "ytick.major.size":     2.8,
    "axes.spines.top":      False,
    "axes.spines.right":    False,
    "figure.dpi":           500,
    "savefig.dpi":          500,
    "savefig.bbox":         "tight",
    "savefig.pad_inches":   0.04,
    "pdf.fonttype":         42,
    "ps.fonttype":          42,
    "axes.grid":            True,
    "grid.linewidth":       0.35,
    "grid.alpha":           0.3,
    "grid.color":           "#CCCCCC",
})

# Okabe-Ito 色盲友好调色板
OI = {
    "orange":    "#E69F00",
    "sky":       "#56B4E9",
    "green":     "#009E73",
    "blue":      "#0072B2",
    "vermilion": "#D55E00",
    "pink":      "#CC79A7",
    "gray":      "#999999",
    "black":     "#000000",
}

STRAT_STYLE = {
    "single_agent": {"color": OI["gray"],      "label": "Single-Agent"},
    "full_context":  {"color": OI["blue"],     "label": "Full-Context"},
    "summary":       {"color": OI["orange"],   "label": "Summary"},
    "action_state":  {"color": OI["sky"],      "label": "Action-State"},
    "lightcomm":     {"color": OI["green"],    "label": "LightComm"},
}
STRATEGY_ORDER = ["single_agent", "full_context", "summary", "action_state", "lightcomm"]

TASK_LABEL = {
    "multihop":   "Multi-hop\nQA",
    "bug_triage": "Bug Triage",
    "doc_edit":   "Doc Edit",
}
TASKS = ["multihop", "bug_triage", "doc_edit"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "results", "figures")
os.makedirs(OUT_DIR, exist_ok=True)


def load():
    path = os.path.join(os.path.dirname(__file__), "results", "results.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["results"]

def is_infra(r):
    vd = r.get("verify_detail") or {}
    return r.get("tokens", 0) == 0 and "error" in vd

def aggregate(results):
    groups = defaultdict(list)
    for r in results:
        if is_infra(r):
            continue
        groups[(r["task"], r["strategy"])].append(r)
    rows = []
    for (task, strat), items in groups.items():
        n   = len(items)
        sr  = sum(1 for i in items if i["success"]) / n
        tok = [i["tokens"]      for i in items if i.get("tokens", 0) > 0]
        lat = [i["wall_time_s"] for i in items if i.get("wall_time_s", 0) > 0]
        rows.append({
            "task": task, "strategy": strat, "n": n,
            "success_rate":  sr,
            "avg_tokens":  np.mean(tok) if tok else 0,
            "std_tokens":  np.std(tok, ddof=1) if len(tok) > 1 else 0,
            "avg_wall_s":  np.mean(lat) if lat else 0,
            "std_wall_s":  np.std(lat, ddof=1) if len(lat) > 1 else 0,
        })
    return rows


# ── 子图绘制函数 ──────────────────────────────────────────────────────────────

def draw_token_bar(ax, data):
    """(a) Token 消耗对比柱状图"""
    x      = np.arange(len(TASKS))
    n_s    = len(STRATEGY_ORDER)
    width  = 0.135
    offs   = np.linspace(-(n_s-1)/2, (n_s-1)/2, n_s) * width

    for i, strat in enumerate(STRATEGY_ORDER):
        vals = [data.get((t, strat), {}).get("avg_tokens", 0) for t in TASKS]
        errs = [data.get((t, strat), {}).get("std_tokens", 0) for t in TASKS]
        ax.bar(x + offs[i], vals, width * 0.88,
               yerr=errs, capsize=1.8,
               color=STRAT_STYLE[strat]["color"],
               label=STRAT_STYLE[strat]["label"],
               edgecolor="white", linewidth=0.35,
               error_kw={"linewidth": 0.6, "ecolor": "#444444"},
               zorder=3)

    for ti, t in enumerate(TASKS):
        base = data.get((t, "single_agent"), {}).get("avg_tokens", 0)
        if base > 0:
            ax.hlines(base, x[ti] - 0.36, x[ti] + 0.36,
                      colors=OI["gray"], linewidths=0.75, linestyles="--", zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS], fontsize=7)
    ax.set_ylabel("Mean Tokens", fontsize=7.5)
    ax.set_title("(a) Token Consumption by Strategy", fontweight="bold", pad=4)
    ax.set_ylim(0, 4300)
    ax.legend(loc="upper left", ncol=2, frameon=False, columnspacing=0.8,
              handlelength=0.9, handletextpad=0.3, fontsize=6.2)
    ax.text(0.98, 0.80, "dashed: Single-Agent",
            transform=ax.transAxes, va="top", ha="right",
            fontsize=5.8, color=OI["gray"])


def draw_latency_bar(ax, data):
    """(b) 延迟对比（对数轴）"""
    strats = ["single_agent", "full_context", "action_state", "lightcomm"]
    x      = np.arange(len(TASKS))
    width  = 0.17
    offs   = np.linspace(-(len(strats)-1)/2, (len(strats)-1)/2, len(strats)) * width

    for i, strat in enumerate(strats):
        vals = [max(data.get((t, strat), {}).get("avg_wall_s", 0.01), 0.01) for t in TASKS]
        errs = [data.get((t, strat), {}).get("std_wall_s", 0) for t in TASKS]
        ax.bar(x + offs[i], vals, width * 0.88,
               yerr=errs, capsize=1.8,
               color=STRAT_STYLE[strat]["color"],
               label=STRAT_STYLE[strat]["label"],
               edgecolor="white", linewidth=0.35,
               error_kw={"linewidth": 0.6, "ecolor": "#444444"},
               zorder=3)

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v:.0f}" if v >= 10 else f"{v:.1f}"))
    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS], fontsize=7)
    ax.set_ylabel("Latency (s, log scale)", fontsize=7.5)
    ax.set_title("(b) End-to-End Latency", fontweight="bold", pad=4)
    ax.set_ylim(0.3, 3000)
    ax.legend(loc="upper left", ncol=2, frameon=False, columnspacing=0.8,
              handlelength=0.9, handletextpad=0.3, fontsize=6.2)

    for ti, t in enumerate(TASKS):
        fc = data.get((t, "full_context"), {}).get("avg_wall_s", 1)
        lc = data.get((t, "lightcomm"),    {}).get("avg_wall_s", 1)
        if fc > 0 and lc > 0:
            mult = lc / fc
            sd = data.get((t, "lightcomm"), {}).get("std_wall_s", 0)
            ax.text(x[ti] + offs[3], (lc + sd) * 1.18,
                    f"{mult:.1f}×", ha="center", fontsize=6,
                    color=OI["vermilion"], fontweight="bold", zorder=5)


def draw_amplification(ax, data):
    """(c) Token 倍增比热力图"""
    strats = ["full_context", "summary", "action_state", "lightcomm"]
    s_lbl  = ["Full-Ctx", "Summary", "Act-State", "LightComm"]
    t_short = {"multihop": "QA", "bug_triage": "Bug", "doc_edit": "Doc"}
    t_lbl  = [t_short[t] for t in TASKS]

    mat = np.zeros((len(TASKS), len(strats)))
    for ti, t in enumerate(TASKS):
        base = data.get((t, "single_agent"), {}).get("avg_tokens", 1) or 1
        for si, s in enumerate(strats):
            r = data.get((t, s))
            mat[ti, si] = r["avg_tokens"] / base if r else 0

    im = ax.imshow(mat, cmap="RdYlGn_r", vmin=1.0, vmax=8.5, aspect="auto")
    ax.set_xticks(range(len(strats)))
    ax.set_xticklabels(s_lbl, fontsize=6.2, rotation=25, ha="right")
    ax.set_yticks(range(len(TASKS)))
    ax.set_yticklabels(t_lbl, fontsize=7)
    for ti in range(len(TASKS)):
        for si in range(len(strats)):
            v = mat[ti, si]
            color = "white" if v > 5.5 else "black"
            ax.text(si, ti, f"{v:.1f}×", ha="center", va="center",
                    fontsize=7.5, fontweight="bold", color=color)
    cb = plt.colorbar(im, ax=ax, fraction=0.044, pad=0.04)
    cb.set_label("Ratio vs. Single", fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    ax.set_title("(c) Token Amplification Ratio", fontweight="bold", pad=4)
    ax.grid(False)


def draw_ablation(ax, data):
    """(d) 消融研究：组件对延迟的影响"""
    strats = ["full_context", "action_state", "lightcomm"]
    labels = ["Full-Context", "Action-State", "LightComm"]
    colors = [OI["blue"], OI["sky"], OI["green"]]
    
    x = np.arange(len(TASKS))
    w = 0.24
    
    for i, (strat, label, color) in enumerate(zip(strats, labels, colors)):
        vals = [data.get((t, strat), {}).get("avg_wall_s", 0) for t in TASKS]
        errs = [data.get((t, strat), {}).get("std_wall_s", 0) for t in TASKS]
        ax.bar(x + (i - 1) * w, vals, w * 0.88,
               yerr=errs, capsize=1.8,
               color=color, label=label,
               edgecolor="white", linewidth=0.35,
               error_kw={"linewidth": 0.6, "ecolor": "#444444"},
               zorder=3)
        # 在 LightComm 柱顶标出绝对延迟数值
        if strat == "lightcomm":
            for ti, v in enumerate(vals):
                sd = errs[ti]
                ax.text(x[ti] + (i - 1) * w, v + sd + 3.0, f"{v:.0f}s",
                        ha="center", fontsize=6, color=OI["vermilion"], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS], fontsize=7)
    ax.set_ylabel("Latency (s)", fontsize=7.5)
    ax.set_ylim(0, 200)
    ax.set_title("(d) Latency Ablation", fontweight="bold", pad=4)
    ax.legend(loc="upper left", frameon=False, fontsize=6.2, handlelength=0.9)


def draw_compression_theory(ax):
    """(e) 自适应压缩理论模型"""
    out_len   = np.linspace(0, 700, 500)
    threshold = 96
    saved     = np.clip(out_len * 0.58 - 25, 0, None)
    overhead  = np.full_like(out_len, 125)
    net       = saved - overhead

    ax.fill_between(out_len, net, 0,
                    where=net >= 0, alpha=0.22,
                    color=OI["green"], label="Net saving", zorder=2)
    ax.fill_between(out_len, net, 0,
                    where=net < 0, alpha=0.22,
                    color=OI["vermilion"], label="Net cost", zorder=2)
    ax.plot(out_len, net, color=OI["blue"], lw=1.5,
            label="Net saving curve", zorder=3)
    ax.axvline(threshold, color=OI["orange"], lw=1.2, ls="--",
               label=f"Threshold ({threshold}ch)", zorder=4)
    ax.axhline(0, color="black", lw=0.6, zorder=3)

    ax.text(threshold + 8, 25, "skip rule", fontsize=6.0, color=OI["orange"])

    ax.set_xlabel("Output Length (chars)", fontsize=7.5)
    ax.set_ylabel("Net Token Savings", fontsize=7.5)
    ax.set_xlim(0, 700)
    ax.set_title("(e) Analytical Break-Even Model", fontweight="bold", pad=4)
    ax.set_ylim(-160, 300)
    ax.legend(loc="lower right", frameon=False, fontsize=5.8, handlelength=1.0)


def draw_compression_empirical(ax, data):
    """(f) 实测压缩开销对比"""
    fc_tok = [data.get((t, "full_context"),  {}).get("avg_tokens", 0) for t in TASKS]
    as_tok = [data.get((t, "action_state"),  {}).get("avg_tokens", 0) for t in TASKS]
    lc_tok = [data.get((t, "lightcomm"),     {}).get("avg_tokens", 0) for t in TASKS]
    t_lbl  = [TASK_LABEL[t] for t in TASKS]

    x = np.arange(len(TASKS))
    w = 0.24

    ax.bar(x - w, fc_tok, w, color=OI["blue"],  label="Full-Context", edgecolor="white", linewidth=0.35, zorder=3)
    ax.bar(x,     as_tok, w, color=OI["sky"],   label="Action-State", edgecolor="white", linewidth=0.35, zorder=3)
    ax.bar(x + w, lc_tok, w, color=OI["green"], label="LightComm",    edgecolor="white", linewidth=0.35, zorder=3)

    for i, (f, a, l) in enumerate(zip(fc_tok, as_tok, lc_tok)):
        if f > 0:
            da = (a - f) / f * 100
            dl = (l - f) / f * 100
            top = max(a, l)
            ax.text(x[i],     top + max(fc_tok) * 0.05, f"{da:+.0f}%", ha="center", fontsize=5.6, color="#2A7FB8")
            ax.text(x[i] + w, top + max(fc_tok) * 0.15, f"{dl:+.0f}%", ha="center", fontsize=5.6, color=OI["vermilion"])

    ax.set_xticks(x)
    ax.set_xticklabels(t_lbl, fontsize=7)
    ax.set_ylabel("Mean Tokens", fontsize=7.5)
    ax.set_ylim(0, max(lc_tok) * 1.45)
    ax.set_title("(f) Empirical Token Inflation", fontweight="bold", pad=4)
    ax.legend(loc="upper left", frameon=False, fontsize=6.2, handlelength=0.9)


def main():
    print("Loading data...")
    results = load()
    rows    = aggregate(results)
    data    = {(r["task"], r["strategy"]): r for r in rows}

    print("Building clear composite figure (500 dpi, Nature/IEEE layout)...")
    from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

    # 宽 18.0cm × 高 11.5cm（完美黄金比例，清爽无遮挡）
    fig = plt.figure(figsize=(18.0 / 2.54, 11.5 / 2.54), dpi=500)

    gs = GridSpec(
        2, 3,
        figure=fig,
        hspace=0.38,
        wspace=0.40,
        left=0.065, right=0.985,
        top=0.93,   bottom=0.08,
    )

    # 第一行
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])
    draw_token_bar(ax_a, data)
    draw_latency_bar(ax_b, data)
    draw_amplification(ax_c, data)

    # 第二行：(d) 消融对比, (e) 理论模型, (f) 实测开销
    ax_d = fig.add_subplot(gs[1, 0])
    draw_ablation(ax_d, data)

    ax_e = fig.add_subplot(gs[1, 1])
    draw_compression_theory(ax_e)

    ax_f = fig.add_subplot(gs[1, 2])
    draw_compression_empirical(ax_f, data)

    # 保存 500 DPI PNG & PDF
    out_png = os.path.join(OUT_DIR, "fig_composite_results.png")
    out_pdf = os.path.join(OUT_DIR, "fig_composite_results.pdf")
    fig.savefig(out_png, dpi=500)
    fig.savefig(out_pdf)
    plt.close(fig)
    print(f"  → {out_png}")
    print(f"  → {out_pdf}")
    print("Done.")


if __name__ == "__main__":
    main()
