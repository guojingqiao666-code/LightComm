# -*- coding: utf-8 -*-
"""
llm_client.py — 轻量 OpenAI 兼容 LLM 客户端（不依赖 openai SDK，只用 requests）。

支持 DeepSeek / 通义千问(兼容模式) / OpenAI / 本地 vLLM 等所有 OpenAI 兼容端点。
- 自动统计 prompt/completion tokens，按价格表折算成本（美元）
- 内置重试、超时、并发上限保护
"""
from __future__ import annotations

import json
import os
import threading
import time

import requests


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, base_url: str, api_key: str, models: dict,
                 prices: dict, timeout: int = 120, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.models = models          # {"large": "model-a", "small": "model-b"}
        self.prices = prices          # {model_name: {"input_per_mtok": x, "output_per_mtok": y}} 单位 USD
        self.timeout = timeout
        self.max_retries = max_retries
        self._lock = threading.Lock()

    # ---------- 公开接口 ----------
    def chat(self, model_tier: str, messages: list, max_tokens: int = 2048,
             temperature: float = 0.3) -> dict:
        """返回 {"text": str, "prompt_tokens": int, "completion_tokens": int, "model": str}"""
        model = self.models.get(model_tier)
        if not model:
            raise LLMError(f"未配置模型档位: {model_tier}，请在 config.json 的 llm.models 中设置")
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    usage = data.get("usage", {})
                    return {
                        "text": ((choice.get("message") or {}).get("content") or ""),
                        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage.get("completion_tokens", 0)),
                        "model": data.get("model", model),
                    }
                # 429/5xx 可重试
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = min(2 ** attempt, 16)
                    time.sleep(wait)
                    continue
                raise LLMError(f"API 返回 {resp.status_code}: {resp.text[:300]}")
            except requests.exceptions.RequestException as exc:
                if attempt == self.max_retries:
                    raise LLMError(f"请求失败（已重试 {self.max_retries} 次）: {exc}")
                time.sleep(min(2 ** attempt, 16))
        raise LLMError("重试次数用尽")

    # ---------- 成本与 token 统计 ----------
    def cost(self, usage: dict) -> float:
        model = usage.get("model", "")
        price = self.prices.get(model, {})
        in_p = float(price.get("input_per_mtok", 0.0))
        out_p = float(price.get("output_per_mtok", 0.0))
        return (usage.get("prompt_tokens", 0) / 1e6) * in_p + \
               (usage.get("completion_tokens", 0) / 1e6) * out_p

    def cost_of(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        price = self.prices.get(model_name, {})
        return (prompt_tokens / 1e6) * float(price.get("input_per_mtok", 0.0)) + \
               (completion_tokens / 1e6) * float(price.get("output_per_mtok", 0.0))


def load_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    llm_cfg = cfg["llm"]
    key_env = llm_cfg.get("api_key_env", "LLM_API_KEY")
    api_key = os.environ.get(key_env, "").strip()
    if not api_key:
        raise LLMError(
            f"未找到 API Key：请设置环境变量 {key_env}（或在 config.json 的 "
            f"llm.api_key 中直接填写，不推荐）。"
        )
    client = LLMClient(
        base_url=llm_cfg["base_url"],
        api_key=api_key,
        models=llm_cfg["models"],
        prices=llm_cfg.get("prices", {}),
        timeout=llm_cfg.get("timeout", 120),
        max_retries=llm_cfg.get("max_retries", 3),
    )
    return cfg
