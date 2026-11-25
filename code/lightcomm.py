# -*- coding: utf-8 -*-
"""
lightcomm.py — LightComm：面向分布式 LLM 多智能体工作流的成本-延迟感知编排框架。

三层机制（可独立开关，构成论文中的消融）：
  1. Action-State Communication (comm)  —— agent 间只传紧凑结构化状态记录，不传全量上下文
  2. Tiered Model Routing (router)      —— 按步骤类型把简单步骤路由到小模型，规划/综合路由到大模型
  3. Dependency-Aware Parallel Scheduling (sched) —— DAG 化工作流，独立分支并行执行

策略组合（用于实验对比）：
  - single_agent      : 单个大模型一步完成（不经过工作流）
  - full_context      : 多 agent 串行，全量上下文逐级传递（最贵基线）
  - summary           : 多 agent 串行，每步传摘要
  - action_state      : 只开通信压缩（全 large、串行）
  - lightcomm         : 三机制全开（本文方法）
"""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from llm_client import LLMClient


# ============================================================
# 1. 工作流定义
# ============================================================

class WorkflowStep:
    """一个 agent 步骤。kind 决定默认路由档位。"""
    TIER_MAP = {
        "plan": "large",
        "synthesize": "large",
        "verify": "large",
        "final": "large",
        "act": "small",
        "retrieve": "small",
        "edit": "small",
        "classify": "small",
        "inspect": "small",
        "extract": "small",
    }

    def __init__(self, id: str, kind: str, prompt: Callable[[dict], str],
                 depends_on: Optional[List[str]] = None,
                 model_tier: Optional[str] = None,
                 temperature: float = 0.3,
                 max_tokens: int = 1024):
        self.id = id
        self.kind = kind
        self.prompt = prompt          # callable(context_view) -> user prompt 文本
        self.depends_on = depends_on or []
        self.model_tier = model_tier or self.TIER_MAP.get(kind, "large")
        self.temperature = temperature
        self.max_tokens = max_tokens


class Workflow:
    def __init__(self, steps: List[WorkflowStep]):
        self.steps = {s.id: s for s in steps}

    def topological_order(self) -> List[str]:
        """Kahn 拓扑排序；无环假设。"""
        indeg = {sid: 0 for sid in self.steps}
        for sid, s in self.steps.items():
            for dep in s.depends_on:
                indeg[sid] += 1
        ready = [sid for sid, d in indeg.items() if d == 0]
        order = []
        while ready:
            ready.sort()
            sid = ready.pop(0)
            order.append(sid)
            for other, s in self.steps.items():
                if sid in s.depends_on:
                    indeg[other] -= 1
                    if indeg[other] == 0:
                        ready.append(other)
        if len(order) != len(self.steps):
            raise ValueError("工作流存在环，无法调度")
        return order


# ============================================================
# 2. Action-State 通信压缩
# ============================================================

ACTION_STATE_SCHEMA = {
    "action": "本步骤执行的动作（短语）",
    "object": "操作对象（如文件/问题/代码片段）",
    "status": "done | partial | failed",
    "summary": "关键结果或证据（<=80 词）",
    "next_needs": "下游步骤还需要什么（<=30 词）",
}

COMPRESS_PROMPT = (
    "把下面的 agent 输出压缩成一行 JSON：{\"action\":\"动作短语\",\"object\":\"操作对象\","
    "\"status\":\"done|partial|failed\",\"summary\":\"关键结果<=80词\","
    "\"next_needs\":\"下游还需要什么<=30词\"}。只输出 JSON。\n\nAgent 输出：\n{text}"
)


class ActionStateCompressor:
    def __init__(self, client: LLMClient, tier: str = "small"):
        self.client = client
        self.tier = tier

    def compress(self, step_id: str, text: str) -> dict:
        text = text or ""
        if not text.strip():
            return {"action": step_id, "object": "", "status": "done",
                    "summary": "", "next_needs": ""}
        # 自适应压缩：短输出（约 48 token 以下）无需 LLM 压缩，直接状态化，避免固定开销
        if len(text.strip()) < 96:
            return {"action": step_id, "object": "", "status": "done",
                    "summary": text.strip()[:240], "next_needs": ""}
        try:
            usage = self.client.chat(
                self.tier,
                [{"role": "system", "content": "只输出 JSON。"},
                 {"role": "user", "content": COMPRESS_PROMPT.format(text=text[:2000])}],
                max_tokens=160, temperature=0.0,
            )
            raw = usage["text"].strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
            data = json.loads(raw)
            return {
                "action": str(data.get("action", step_id))[:80],
                "object": str(data.get("object", ""))[:120],
                "status": str(data.get("status", "done"))[:16],
                "summary": str(data.get("summary", ""))[:240],
                "next_needs": str(data.get("next_needs", ""))[:120],
            }
        except Exception:
            # 降级：取首 200 字符作为摘要（不中断实验）
            return {"action": step_id, "object": "", "status": "done",
                    "summary": text[:200], "next_needs": ""}


# ============================================================
# 3. 分层模型路由
# ============================================================

class TierRouter:
    """启发式路由：步骤类型 -> 模型档位。可被实验配置覆盖。"""

    def __init__(self, overrides: Optional[Dict[str, str]] = None):
        self.overrides = overrides or {}

    def route(self, step: WorkflowStep) -> str:
        return self.overrides.get(step.id, step.model_tier)


# ============================================================
# 4. 依赖感知并行调度 + 编排器
# ============================================================

class StepResult:
    def __init__(self, step_id: str, kind: str, model: str, output: str,
                 action_state: Optional[dict], prompt_tokens: int,
                 completion_tokens: int, wall_time: float, success: bool):
        self.step_id = step_id
        self.kind = kind
        self.model = model
        self.output = output
        self.action_state = action_state
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.wall_time = wall_time
        self.success = success


class Orchestrator:
    """
    strategy: "single_agent" | "full_context" | "summary" | "action_state" | "lightcomm"
    对 single_agent，不执行工作流，直接把任务交一个大模型。
    """

    def __init__(self, client: LLMClient, strategy: str,
                 router: Optional[TierRouter] = None,
                 compressor: Optional[ActionStateCompressor] = None,
                 max_concurrency: int = 4,
                 budget_tokens: int = 100000):
        self.client = client
        self.strategy = strategy
        self.router = router or TierRouter()
        self.compressor = compressor
        self.max_concurrency = max_concurrency
        self.budget_tokens = budget_tokens
        self.total_tokens = 0

    # ---------- 单 agent 基线 ----------
    def run_single_agent(self, task_input: str, task_prompt: str) -> dict:
        t0 = time.time()
        usage = self.client.chat(
            "large",
            [{"role": "system", "content": task_prompt},
             {"role": "user", "content": task_input}],
            max_tokens=2048, temperature=0.0,
        )
        return {
            "final_output": usage["text"],
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "wall_time": time.time() - t0,
            "model": usage["model"],
            "steps": [],
        }

    # ---------- 多 agent 工作流 ----------
    def run_workflow(self, workflow: Workflow, task_input: str, task_prompt: str) -> dict:
        t0 = time.time()
        order = workflow.topological_order()
        results: Dict[str, StepResult] = {}
        results_lock = threading.Lock()
        total_prompt = 0
        total_completion = 0
        total_calls = 0
        counters = {"calls": 0}

        def deps_of(sid: str) -> List[StepResult]:
            step = workflow.steps[sid]
            return [results[d] for d in step.depends_on if d in results]

        def context_view(sid: str) -> str:
            """按策略构造步骤 sid 的上下文视图。"""
            deps = deps_of(sid)
            if not deps:
                return ""
            if self.strategy in ("full_context",):
                return "\n\n".join(
                    f"[步骤 {d.step_id} ({d.kind}) 输出]\n{d.output}" for d in deps)
            if self.strategy in ("summary",):
                return "\n\n".join(
                    f"[步骤 {d.step_id}] 摘要：{d.output[:500]}" for d in deps)
            # action_state / lightcomm：结构化状态记录
            lines = []
            for d in deps:
                if d.action_state:
                    st = d.action_state
                    lines.append(
                        f"[步骤 {d.step_id}] 动作={st.get('action','')} | "
                        f"对象={st.get('object','')} | 状态={st.get('status','')} | "
                        f"要点={st.get('summary','')} | 下游需要={st.get('next_needs','')}")
                else:
                    lines.append(f"[步骤 {d.step_id}] 输出：{d.output[:300]}")
            return "\n".join(lines)

        def execute_step(sid: str) -> None:
            nonlocal total_prompt, total_completion, total_calls
            step = workflow.steps[sid]
            tier = self.router.route(step) if self.strategy == "lightcomm" else "large"
            view = context_view(sid)
            messages = [{"role": "system", "content": task_prompt}]
            if task_input.strip():
                messages.append({"role": "user", "content": task_input})
            if view.strip():
                messages.append({"role": "user", "content": "上一步结果：\n" + view})
            messages.append({"role": "user", "content": step.prompt(view)})

            t_step = time.time()
            usage = self.client.chat(
                tier, messages, max_tokens=step.max_tokens, temperature=step.temperature)
            output = usage["text"]
            wall = time.time() - t_step

            action_state = None
            if self.strategy in ("action_state", "lightcomm") and self.compressor:
                action_state = self.compressor.compress(sid, output)

            with results_lock:
                results[sid] = StepResult(
                    step_id=sid, kind=step.kind, model=usage["model"], output=output,
                    action_state=action_state,
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                    wall_time=wall, success=bool(output.strip()),
                )
                total_prompt += usage["prompt_tokens"]
                total_completion += usage["completion_tokens"]
                total_calls += 1
                counters["calls"] = total_calls

        # 依赖感知调度：只有依赖全部完成才执行（线程池并行独立分支）
        pending = set(order)
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            while pending:
                runnable = [
                    sid for sid in pending
                    if all(d in results for d in workflow.steps[sid].depends_on)
                ]
                if not runnable:
                    raise RuntimeError("调度死锁：存在未满足的依赖")
                futures = [pool.submit(execute_step, sid) for sid in runnable]
                for f in futures:
                    f.result()          # 收集异常
                pending -= set(runnable)

        # 按拓扑序汇总最终输出：取最后一个 final/synthesize 步骤
        final_ids = [sid for sid in order if workflow.steps[sid].kind in ("final", "synthesize")]
        final_id = final_ids[-1] if final_ids else order[-1]
        final_output = results[final_id].output

        return {
            "final_output": final_output,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "wall_time": time.time() - t0,
            "model": "workflow",
            "steps": [
                {
                    "id": sid, "kind": workflow.steps[sid].kind,
                    "model": results[sid].model,
                    "tokens": results[sid].prompt_tokens + results[sid].completion_tokens,
                    "wall_time": round(results[sid].wall_time, 3),
                    "success": results[sid].success,
                }
                for sid in order
            ],
        }

    def run(self, workflow: Optional[Workflow], task_input: str, task_prompt: str) -> dict:
        if self.strategy == "single_agent" or workflow is None:
            return self.run_single_agent(task_input, task_prompt)
        return self.run_workflow(workflow, task_input, task_prompt)
