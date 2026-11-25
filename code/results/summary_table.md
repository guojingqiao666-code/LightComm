# 实验结果汇总

共 135 条记录；其中基础设施错误（端点超时/重试耗尽）26 条已排除，成功率按 completed runs 判定，Token/延迟/成本取均值。

### Task: bug_triage

| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) | Avg Cost (USD) |
|---|---|---|---|---|---|---|
| bug_triage | action_state | 62% | 8 | 978 | 10.47 | 0.00000 |
| bug_triage | full_context | 56% | 9 | 953 | 11.38 | 0.00000 |
| bug_triage | lightcomm | 43% | 7 | 988 | 103.15 | 0.00000 |
| bug_triage | single_agent | 56% | 9 | 569 | 8.08 | 0.00000 |
| bug_triage | summary | 83% | 6 | 954 | 13.21 | 0.00000 |


### Task: doc_edit

| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) | Avg Cost (USD) |
|---|---|---|---|---|---|---|
| doc_edit | action_state | 100% | 5 | 2263 | 27.56 | 0.00000 |
| doc_edit | full_context | 100% | 6 | 2288 | 21.13 | 0.00000 |
| doc_edit | lightcomm | 100% | 6 | 2812 | 62.17 | 0.00000 |
| doc_edit | single_agent | 100% | 8 | 364 | 5.25 | 0.00000 |
| doc_edit | summary | 100% | 4 | 2054 | 21.55 | 0.00000 |


### Task: multihop

| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) | Avg Cost (USD) |
|---|---|---|---|---|---|---|
| multihop | action_state | 89% | 9 | 1296 | 14.83 | 0.00000 |
| multihop | full_context | 100% | 8 | 1344 | 12.52 | 0.00000 |
| multihop | lightcomm | 100% | 8 | 1522 | 71.30 | 0.00000 |
| multihop | single_agent | 100% | 7 | 576 | 9.84 | 0.00000 |
| multihop | summary | 100% | 9 | 1287 | 14.64 | 0.00000 |


### 消融视角（lightcomm 与关闭部分机制的策略对比）

| Task | Strategy | Success | n | Avg Tokens | Avg Latency (s) |
|---|---|---|---|---|---|
| bug_triage | lightcomm | 43% | 7 | 988 | 103.15 |
| bug_triage | full_context (no comm) | 56% | 9 | 953 | 11.38 |
| bug_triage | action_state (no router/sched) | 62% | 8 | 978 | 10.47 |
| doc_edit | lightcomm | 100% | 6 | 2812 | 62.17 |
| doc_edit | full_context (no comm) | 100% | 6 | 2288 | 21.13 |
| doc_edit | action_state (no router/sched) | 100% | 5 | 2263 | 27.56 |
| multihop | lightcomm | 100% | 8 | 1522 | 71.30 |
| multihop | full_context (no comm) | 100% | 8 | 1344 | 12.52 |
| multihop | action_state (no router/sched) | 89% | 9 | 1296 | 14.83 |
