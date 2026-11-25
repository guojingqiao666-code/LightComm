# -*- coding: utf-8 -*-
"""并发测速：对候选模型各发 1 个短请求，比较响应时间（key 从环境变量读）。"""
import concurrent.futures as cf
import json
import os
import time
import urllib.request
import urllib.error

KEY = os.environ.get("NVIDIA_API_KEY", "")
BASE = "https://integrate.api.nvidia.com/v1/chat/completions"

CANDIDATES = [
    "deepseek-ai/deepseek-v4.1-flash",
    "z-ai/glm-5.3-flash",
    "z-ai/glm-5.3",
    "moonshotai/kimi-k3",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
]

def probe(mid):
    body = json.dumps({
        "model": mid,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 16, "temperature": 0.0, "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(BASE, data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            out = json.load(r)
            dt = time.time() - t0
            return (mid, "OK", round(dt, 1), out.get("model", ""))
    except urllib.error.HTTPError as e:
        return (mid, f"HTTP {e.code}", round(time.time() - t0, 1), "")
    except Exception as e:
        return (mid, type(e).__name__, round(time.time() - t0, 1), "")

with cf.ThreadPoolExecutor(max_workers=len(CANDIDATES)) as pool:
    futs = [pool.submit(probe, m) for m in CANDIDATES]
    for f in cf.as_completed(futs):
        mid, st, dt, real = f.result()
        print(f"{dt:7.1f}s  {st:12s} {mid}  ->  {real}")
