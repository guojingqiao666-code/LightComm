# -*- coding: utf-8 -*-
"""探测 NVIDIA NIM 免费端点上可用的模型 ID（key 从环境变量读，不落盘）。"""
import json
import os
import urllib.request
import urllib.error

KEY = os.environ.get("NVIDIA_API_KEY", "")
if not KEY:
    print("NO KEY: set NVIDIA_API_KEY env var")
    raise SystemExit(2)

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

# 1) 列出模型目录
try:
    data = get("https://integrate.api.nvidia.com/v1/models")
    ids = [m.get("id", "") for m in data.get("data", [])]
    print("MODELS COUNT:", len(ids))
    for i in ids:
        print(" ", i)
except urllib.error.HTTPError as e:
    print("models endpoint HTTP", e.code, e.read()[:300])
except Exception as e:
    print("models endpoint error:", repr(e))

# 2) 候选模型逐个做最小 chat 探测（找免费可用且能响应的）
CANDIDATES = [
    "deepseek-v4.1-flash", "lm-5.3-flash", "kimi-k3", "nemotron-3-super-120b",
    "deepseek-ai/deepseek-v4.1-flash", "z-ai/glm-5.3-flash", "glm-5.3-flash",
    "zai-org/glm-5.3-flash", "moonshotai/kimi-k3", "nvidia/nemotron-3-super-120b",
    "nemotron-3-super-120b-a12b", "nvidia/nemotron-3-super-120b-a12b:free",
]
for mid in CANDIDATES:
    body = json.dumps({
        "model": mid,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.load(r)
            msg = out["choices"][0]["message"]["content"]
            print("OK  ", mid, "->", msg.strip()[:40])
    except urllib.error.HTTPError as e:
        print("FAIL", mid, "HTTP", e.code)
    except Exception as e:
        print("FAIL", mid, repr(e)[:100])
