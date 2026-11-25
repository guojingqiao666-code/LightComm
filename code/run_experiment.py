# -*- coding: utf-8 -*-
"""
run_experiment.py — 运行 LightComm 论文实验。

用法：
   1. 把 config.json 中的 API 配置改为你的服务商；设置环境变量（或 .env 文件）:
        set DEEPSEEK_API_KEY=sk-xxx     (Windows PowerShell: $env:DEEPSEEK_API_KEY="sk-xxx")
   2. python run_experiment.py
   3. 结果写入 results/results.json 与 results/results.csv
   4. python analyze_results.py 生成论文表格与帕累托图

策略对比：single_agent / full_context / summary / action_state / lightcomm
消融开关在 config["experiment"]["strategies"] 中配置。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time

from llm_client import LLMClient, LLMError, load_config
from lightcomm import ActionStateCompressor, Orchestrator, TierRouter
from tasks import TASKS

STRATEGIES = ["single_agent", "full_context", "summary", "action_state", "lightcomm"]


def make_client(cfg: dict) -> LLMClient:
    llm_cfg = cfg["llm"]
    key = os.environ.get(llm_cfg.get("api_key_env", "LLM_API_KEY"), "").strip()
    if not key:
        raise LLMError(
            f"未找到 API Key：请设置环境变量 {llm_cfg.get('api_key_env', 'LLM_API_KEY')}"
        )
    return LLMClient(
        base_url=llm_cfg["base_url"],
        api_key=key,
        models=llm_cfg["models"],
        prices=llm_cfg.get("prices", {}),
        timeout=llm_cfg.get("timeout", 120),
        max_retries=llm_cfg.get("max_retries", 3),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LightComm experiments")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--strategies", default="",
                        help="覆盖配置中的策略列表，逗号分隔")
    parser.add_argument("--limit", type=int, default=0,
                        help="每个任务只跑前 N 个实例（0=全部）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    exp = cfg["experiment"]
    strategies = (args.strategies.split(",") if args.strategies.strip()
                  else exp.get("strategies", STRATEGIES))
    strategies = [s for s in strategies if s in STRATEGIES]
    if not strategies:
        print("没有有效的策略；可选：", STRATEGIES)
        return 1

    client = make_client(cfg)
    max_concurrency = int(exp.get("max_concurrency", 4))
    runs_per_config = int(exp.get("runs_per_config", 3))
    budget_usd = float(exp.get("budget_usd_limit", 5.0))
    seed = int(exp.get("seed", 42))
    random.seed(seed)

    router = TierRouter(overrides=exp.get("router_overrides", {}))
    compressor = ActionStateCompressor(client, tier=exp.get("compressor_tier", "small"))

    task_names = exp.get("tasks", list(TASKS.keys()))
    results = []
    total_cost = 0.0
    task_idx = 0

    print(f"策略: {strategies}")
    print(f"任务: {task_names} | 每配置重复: {runs_per_config} | 预算: ${budget_usd}")
    print("-" * 70)

    for task_name in task_names:
        if task_name not in TASKS:
            print(f"跳过未知任务: {task_name}")
            continue
        spec = TASKS[task_name]
        task_idx += 1
        data = spec["data"]
        if args.limit:
            data = data[:args.limit]
        print(f"\n===== 任务 {task_idx}/{len(task_names)}: {task_name} "
              f"({spec['description']}) — {len(data)} 实例 =====")

        for strategy in strategies:
            for run_i in range(1, runs_per_config + 1):
                if total_cost >= budget_usd:
                    print(f"\n[预算上限] 累计成本 ${total_cost:.4f} >= ${budget_usd}，停止。")
                    break
                for item in data:
                    if total_cost >= budget_usd:
                        break
                    orch = Orchestrator(
                        client=client, strategy=strategy,
                        router=router, compressor=compressor,
                        max_concurrency=max_concurrency,
                    )
                    workflow = spec["make_workflow"](item)
                    sys_prompt = spec["system_prompt"]
                    task_input = item.get("input_doc", item.get("input", ""))
                    t0 = time.time()
                    try:
                        res = orch.run(workflow, task_input, sys_prompt)
                        ok, detail = spec["verify"](res["final_output"], item)
                        cost = client.cost({
                            "model": res.get("model", ""),
                            "prompt_tokens": res["prompt_tokens"],
                            "completion_tokens": res["completion_tokens"],
                        })
                        total_cost += cost
                        record = {
                            "task": task_name,
                            "instance": item["id"],
                            "strategy": strategy,
                            "run": run_i,
                            "success": ok,
                            "tokens": res["prompt_tokens"] + res["completion_tokens"],
                            "prompt_tokens": res["prompt_tokens"],
                            "completion_tokens": res["completion_tokens"],
                            "wall_time_s": round(time.time() - t0, 3),
                            "cost_usd": round(cost, 6),
                            "verify_detail": detail,
                            "steps": res.get("steps", []),
                        }
                        results.append(record)
                        flag = "OK " if ok else "FAIL"
                        print(f"[{flag}] {task_name}/{item['id']} | {strategy:14s} | "
                              f"run{run_i} | tok={record['tokens']:6d} | "
                              f"t={record['wall_time_s']:6.2f}s | ${record['cost_usd']:.5f}")
                    except Exception as exc:
                        print(f"[ERR ] {task_name}/{item['id']} | {strategy:14s} | "
                              f"run{run_i} | {type(exc).__name__}: {exc}")
                        results.append({
                            "task": task_name, "instance": item["id"],
                            "strategy": strategy, "run": run_i, "success": False,
                            "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                            "wall_time_s": 0.0, "cost_usd": 0.0,
                            "verify_detail": {"error": f"{type(exc).__name__}: {exc}"}, "steps": [],
                        })

    # ---------- 写结果 ----------
    os.makedirs("results", exist_ok=True)
    with open("results/results.json", "w", encoding="utf-8") as fh:
        json.dump({"config": cfg, "results": results}, fh, ensure_ascii=False, indent=2)

    with open("results/results.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["task", "instance", "strategy", "run", "success",
                         "tokens", "wall_time_s", "cost_usd"])
        for r in results:
            writer.writerow([r["task"], r["instance"], r["strategy"], r["run"],
                             int(r["success"]), r["tokens"],
                             r["wall_time_s"], r["cost_usd"]])

    print("\n" + "=" * 70)
    print(f"完成。总成本 ${total_cost:.4f}，共 {len(results)} 条记录。")
    print("结果已写入 results/results.json 与 results/results.csv")
    print("运行 python analyze_results.py 生成论文表格与图。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
