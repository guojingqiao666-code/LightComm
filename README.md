# LightComm — Experiment Harness (IEEE ISPA 2026 / DAAA 2026, camera-ready)

Accompanying source for "LightComm: A Composable Orchestration Framework for
Distributed LLM-Based Multi-Agent Workflows with Empirical Cost-Latency Analysis".

## Files

- `llm_client.py` — OpenAI-compatible client wrapper (NVIDIA NIM endpoint).
- `lightcomm.py` — LightComm orchestrator: action-state communication (adaptive
  96-char skip rule), tiered routing, dependency-aware parallel scheduling.
- `tasks.py` — three task families (multi-hop QA, bug triage, doc edit) with
  rule-based, synonym-group semantic verifiers.
- `run_experiment.py` — runs 5 strategies x 3 task families x 3 instances x 3
  repeats (135 runs) and writes `results/results.json`.
- `analyze_results.py` — aggregates completed runs (infrastructure errors
  excluded from denominators), emits `results/summary_table.md` (Table I and the
  ablation figure data of the submitted version).
- `analyze_stats.py` — camera-ready statistics (standard library only): Wilson 95%
  CIs, success with timeouts counted as failures, mean ± s.d., timeout counts,
  Fisher exact and Mann–Whitney U permutation tests, per-tier step latency.
  Writes `results/stats_table.md` (Table II and Section IV-B of the paper).
- `generate_fig1_architecture.py` — Fig. 1 (architecture) of the camera-ready.
- `generate_figures.py` / `generate_composite.py` — Fig. 2 and Fig. 3.
- `probe_nvidia.py` / `bench_nvidia.py` — endpoint probe and per-model latency
  microbenchmark (paper Section IV: 8.8 s vs 3.5 s).
- `config.json` — endpoint config; API key is read from the environment
  variable named in `api_key_env` (never stored in this package).

## Reproduce

1. `pip install -r requirements.txt`
2. Export your NVIDIA NIM API key:
   - Windows PowerShell: `$env:NVIDIA_API_KEY = "<your-nvapi-key>"`
3. `python probe_nvidia.py`   # verify endpoint and model IDs
4. `python bench_nvidia.py`   # per-model latency microbenchmark
5. `python run_experiment.py` # full experiment (~1-2 h on the free tier)
6. `python analyze_results.py`# aggregate tables
7. `python analyze_stats.py`  # Table II, CIs and significance tests
8. `python generate_fig1_architecture.py && python generate_figures.py && python generate_composite.py`

## Notes

- Each (task, strategy) cell has 3 task instances x 3 repeated runs = 9 runs;
  `seed` in `config.json` (42) seeds Python's RNG, but the harness draws no random
  numbers; variation between repeats comes from LLM sampling (temperature 0.3 for
  agent steps, 0.0 for compression and merge) and from endpoint behavior.
- Experiment settings: concurrency limit K = `max_concurrency` = 2, per-call
  timeout 120 s, 3 retries; compression skip threshold 96 characters.
- `results/results.json` is the raw log of the 135 runs reported in the paper
  (26 runs ended in infrastructure errors after retries; they are kept in the log).

- Free-tier endpoints are noisy; the harness records every infrastructure
  error and excludes those runs from success-rate denominators (n = completed
  runs), keeping counts visible.
- Monetary cost is zero on the NVIDIA NIM free tier and is therefore omitted
  from the result tables.
