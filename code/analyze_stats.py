"""Statistical analysis for the camera-ready version (Table II, Section IV-B, V).

Reads results/results.json and writes results/stats_table.md with:
  * success on completed runs with Wilson 95% CI,
  * success with infrastructure errors (timeouts) counted as failures,
  * tokens and latency as mean +/- sample s.d. over completed runs,
  * timeout counts per strategy and per task,
  * Fisher exact tests on success, Mann-Whitney U (permutation) tests on tokens/latency,
  * per-tier step latency.
Standard library only.
"""
import json, math, random, statistics as st
from collections import defaultdict, Counter
from itertools import combinations

STRATS = ["single_agent", "full_context", "summary", "action_state", "lightcomm"]
NAMES = {"single_agent": "Single-Agent", "full_context": "Full-Context", "summary": "Summary",
         "action_state": "Action-State", "lightcomm": "LightComm"}
TASKS = {"multihop": "Multi-hop QA", "bug_triage": "Bug Triage", "doc_edit": "Doc Edit"}

def completed(r): return "error" not in (r.get("verify_detail") or {})

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)

def fisher(a, b, c, d):
    """Two-sided Fisher exact test for [[a,b],[c,d]]."""
    n1, n2, k = a + b, c + d, a + c
    def p(x): return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n1 + n2, k)
    p0 = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, k - n2), min(k, n1) + 1) if p(x) <= p0 + 1e-12))

def _u(x, y):
    return sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in x for b in y)

def perm_test(x, y, iters=20000, seed=0):
    """Two-sided Mann-Whitney U test with a permutation null (exact enough for small n)."""
    rng = random.Random(seed); n, m = len(x), len(y); mid = n * m / 2
    obs = abs(_u(x, y) - mid); pool = list(x) + list(y); hit = 0
    for _ in range(iters):
        rng.shuffle(pool)
        if abs(_u(pool[:n], pool[n:]) - mid) >= obs - 1e-12: hit += 1
    return (hit + 1) / (iters + 1)

def msd(v): return f"{st.mean(v):,.1f} ± {st.stdev(v):,.1f}" if len(v) > 1 else "-"

def main():
    R = json.load(open("results/results.json"))["results"]
    g = defaultdict(list)
    for r in R: g[(r["task"], r["strategy"])].append(r)
    out = ["| Task | Strategy | Success (completed) | 95% CI | Success (all) | Tokens | Latency (s) |",
           "|---|---|---|---|---|---|---|"]
    for t in TASKS:
        for s in STRATS:
            runs = g[(t, s)]; c = [r for r in runs if completed(r)]; k = sum(r["success"] for r in c)
            lo, hi = wilson(k, len(c))
            out.append(f"| {TASKS[t]} | {NAMES[s]} | {k}/{len(c)} ({100*k/max(1,len(c)):.0f}%) | "
                       f"{100*lo:.0f}–{100*hi:.0f}% | {k}/{len(runs)} ({100*k/len(runs):.0f}%) | "
                       f"{msd([r['tokens'] for r in c])} | {msd([r['wall_time_s'] for r in c])} |")
    out += ["", "## Timeouts / infrastructure errors",
            "By strategy: " + str(dict(Counter(r["strategy"] for r in R if not completed(r)))),
            "By task: " + str(dict(Counter(r["task"] for r in R if not completed(r)))), "",
            "## Tests (LightComm vs each baseline)",
            "| Task | Baseline | Fisher p (success) | Mann-Whitney p (tokens) | Mann-Whitney p (latency) |", "|---|---|---|---|---|"]
    for t in TASKS:
        lc = [r for r in g[(t, "lightcomm")] if completed(r)]
        for s in STRATS[:-1]:
            b = [r for r in g[(t, s)] if completed(r)]
            a1 = sum(r["success"] for r in lc); b1 = sum(r["success"] for r in b)
            pf = fisher(a1, len(lc) - a1, b1, len(b) - b1)
            pt = perm_test([r["tokens"] for r in lc], [r["tokens"] for r in b])
            pl = perm_test([r["wall_time_s"] for r in lc], [r["wall_time_s"] for r in b])
            out.append(f"| {TASKS[t]} | {NAMES[s]} | {pf:.2f} | {pt:.4f} | {pl:.4f} |")
    out += ["", "## Step latency by model tier (completed runs)", "| Strategy | Model | n steps | mean (s) | median (s) |", "|---|---|---|---|---|"]
    sl = defaultdict(list)
    for r in R:
        if completed(r):
            for stp in r["steps"]: sl[(r["strategy"], stp["model"])].append(stp["wall_time"])
    for (s, m), v in sorted(sl.items()):
        out.append(f"| {NAMES[s]} | {m} | {len(v)} | {st.mean(v):.1f} | {st.median(v):.1f} |")
    open("results/stats_table.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))

if __name__ == "__main__":
    main()
