# -*- coding: utf-8 -*-
"""
analyze_results.py — 汇总实验结果，输出论文用表格与图。

用法：python analyze_results.py
产出：
  - results/summary_table.md   论文主结果表（Table 2）素材
  - results/ablation_table.md  消融表（Table 3）素材
  - results/pareto.png         成本-成功率帕累托图（Figure 2，需要 matplotlib）
"""
from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict

OUT = "results"


def load_results(path="results/results.json") -> list:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)["results"]


def is_infra_error(r: dict) -> bool:
    """基础设施错误（端点超时/重试耗尽）：tokens 为 0 且 verify_detail 含 error。"""
    vd = r.get("verify_detail") or {}
    return (r.get("tokens", 0) == 0 and "error" in vd)


def aggregate(results: list):
    """按 (task, strategy) 聚合；排除基础设施错误记录，成功率以 completed runs 为分母。"""
    groups = defaultdict(list)
    for r in results:
        if is_infra_error(r):
            continue
        groups[(r["task"], r["strategy"])].append(r)

    rows = []
    for (task, strategy), items in sorted(groups.items()):
        n = len(items)
        success_rate = sum(1 for i in items if i["success"]) / n
        tokens = [i["tokens"] for i in items if i["tokens"] > 0]
        times = [i["wall_time_s"] for i in items if i["wall_time_s"] > 0]
        costs = [i["cost_usd"] for i in items if i["cost_usd"] > 0]
        rows.append({
            "task": task, "strategy": strategy, "n": n,
            "success_rate": success_rate,
            "avg_tokens": statistics.mean(tokens) if tokens else 0,
            "avg_wall_s": statistics.mean(times) if times else 0,
            "avg_cost_usd": statistics.mean(costs) if costs else 0,
        })
    return rows


def render_md_table(rows, caption: str) -> str:
    lines = [f"### {caption}", "",
             "| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) | Avg Cost (USD) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['task']} | {r['strategy']} | {r['success_rate']:.0%} | {r['n']} "
            f"| {r['avg_tokens']:.0f} | {r['avg_wall_s']:.2f} | {r['avg_cost_usd']:.5f} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    results = load_results()
    rows = aggregate(results)
    if not rows:
        print("没有可聚合的数据；请先运行 run_experiment.py。")
        return 1

    # 主结果：按任务分组，策略并列
    per_task = defaultdict(list)
    for r in rows:
        per_task[r["task"]].append(r)
    md = ["# 实验结果汇总", "",
          f"共 {len(results)} 条记录；其中基础设施错误（端点超时/重试耗尽）"
          f"{sum(1 for r in results if is_infra_error(r))} 条已排除，"
          "成功率按 completed runs 判定，Token/延迟/成本取均值。", ""]
    for task in sorted(per_task):
        md.append(render_md_table(per_task[task], f"Task: {task}"))
        md.append("")
    # 消融：lightcomm vs 组件关闭（按任务平均）
    abl = []
    for task, items in per_task.items():
        by_strategy = {r["strategy"]: r for r in items}
        if "lightcomm" not in by_strategy:
            continue
        base = by_strategy["lightcomm"]
        abl.append(base)
        for key, label in [("full_context", "full_context (no comm)"),
                           ("action_state", "action_state (no router/sched)")]:
            if key in by_strategy:
                r = dict(by_strategy[key]); r["strategy"] = label
                abl.append(r)
    md.append("### 消融视角（lightcomm 与关闭部分机制的策略对比）")
    md.append("")
    md.append("| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) |")
    md.append("|---|---|---|---|---|---|")
    for r in abl:
        md.append(f"| {r['task']} | {r['strategy']} | {r['success_rate']:.0%} | {r['n']} "
                  f"| {r['avg_tokens']:.0f} | {r['avg_wall_s']:.2f} |")
    md.append("")

    with open(os.path.join(OUT, "summary_table.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    # 帕累托图（可选 matplotlib）
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 5))
        markers = {"single_agent": "s", "full_context": "o", "summary": "^",
                   "action_state": "D", "lightcomm": "*"}
        colors = {"single_agent": "#999999", "full_context": "#d62728",
                  "summary": "#ff7f0e", "action_state": "#1f77b4", "lightcomm": "#2ca02c"}
        for task in sorted(per_task):
            for r in per_task[task]:
                ax.scatter(r["avg_tokens"], r["success_rate"],
                           marker=markers[r["strategy"]], s=110,
                           color=colors[r["strategy"]],
                           edgecolors="black", linewidths=0.6,
                           label=f"{task}-{r['strategy']}")
        ax.set_xlabel("Avg Tokens (cost proxy, USD per Mtok = 0 on free tier)")
        ax.set_ylabel("Success Rate")
        ax.set_title("Token–Success Trade-off by Strategy and Task")
        ax.grid(alpha=0.3)
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, fontsize=6, ncol=2, loc="lower right")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "pareto.png"), dpi=200)
        print("已生成 results/pareto.png")
    except Exception as exc:
        print(f"跳过绘图（未安装 matplotlib 或绘图失败）: {exc}")

    print("已生成 results/summary_table.md")
    print("\n--- 预览（各任务 lightcomm 对比 full_context） ---")
    for r in rows:
        if r["strategy"] in ("lightcomm", "full_context"):
            print(f"{r['task']:10s} {r['strategy']:14s} "
                  f"成功率={r['success_rate']:.0%} tok={r['avg_tokens']:.0f} "
                  f"t={r['avg_wall_s']:.2f}s $={r['avg_cost_usd']:.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
