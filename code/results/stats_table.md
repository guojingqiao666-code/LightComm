| Task | Strategy | Success (completed) | 95% CI | Success (all) | Tokens | Latency (s) |
|---|---|---|---|---|---|---|
| Multi-hop QA | Single-Agent | 7/7 (100%) | 65–100% | 7/9 (78%) | 575.9 ± 380.8 | 9.8 ± 7.0 |
| Multi-hop QA | Full-Context | 8/8 (100%) | 68–100% | 8/9 (89%) | 1,344.1 ± 538.0 | 12.5 ± 5.2 |
| Multi-hop QA | Summary | 9/9 (100%) | 70–100% | 9/9 (100%) | 1,286.8 ± 478.2 | 14.6 ± 7.4 |
| Multi-hop QA | Action-State | 8/9 (89%) | 56–98% | 8/9 (89%) | 1,295.6 ± 467.9 | 14.8 ± 8.2 |
| Multi-hop QA | LightComm | 8/8 (100%) | 68–100% | 8/9 (89%) | 1,522.2 ± 260.8 | 71.3 ± 19.5 |
| Bug Triage | Single-Agent | 5/9 (56%) | 27–81% | 5/9 (56%) | 569.4 ± 174.1 | 8.1 ± 3.7 |
| Bug Triage | Full-Context | 5/9 (56%) | 27–81% | 5/9 (56%) | 953.0 ± 45.9 | 11.4 ± 3.8 |
| Bug Triage | Summary | 5/6 (83%) | 44–97% | 5/9 (56%) | 954.2 ± 53.5 | 13.2 ± 6.5 |
| Bug Triage | Action-State | 5/8 (62%) | 31–86% | 5/9 (56%) | 977.6 ± 53.6 | 10.5 ± 4.8 |
| Bug Triage | LightComm | 3/7 (43%) | 16–75% | 3/9 (33%) | 987.9 ± 58.0 | 103.2 ± 69.7 |
| Doc Edit | Single-Agent | 8/8 (100%) | 68–100% | 8/9 (89%) | 364.4 ± 114.7 | 5.3 ± 4.7 |
| Doc Edit | Full-Context | 6/6 (100%) | 61–100% | 6/9 (67%) | 2,287.7 ± 351.6 | 21.1 ± 5.1 |
| Doc Edit | Summary | 4/4 (100%) | 51–100% | 4/9 (44%) | 2,054.5 ± 487.5 | 21.6 ± 7.5 |
| Doc Edit | Action-State | 5/5 (100%) | 57–100% | 5/9 (56%) | 2,263.4 ± 347.5 | 27.6 ± 11.0 |
| Doc Edit | LightComm | 6/6 (100%) | 61–100% | 6/9 (67%) | 2,811.5 ± 249.4 | 62.2 ± 50.7 |

## Timeouts / infrastructure errors
By strategy: {'single_agent': 3, 'full_context': 4, 'lightcomm': 6, 'summary': 8, 'action_state': 5}
By task: {'multihop': 4, 'bug_triage': 6, 'doc_edit': 16}

## Tests (LightComm vs each baseline)
| Task | Baseline | Fisher p (success) | Mann-Whitney p (tokens) | Mann-Whitney p (latency) |
|---|---|---|---|---|
| Multi-hop QA | Single-Agent | 1.00 | 0.0001 | 0.0002 |
| Multi-hop QA | Full-Context | 1.00 | 0.7794 | 0.0000 |
| Multi-hop QA | Summary | 1.00 | 0.4381 | 0.0000 |
| Multi-hop QA | Action-State | 1.00 | 0.4626 | 0.0002 |
| Bug Triage | Single-Agent | 1.00 | 0.0003 | 0.0002 |
| Bug Triage | Full-Context | 1.00 | 0.1617 | 0.0002 |
| Bug Triage | Summary | 0.27 | 0.2190 | 0.0013 |
| Bug Triage | Action-State | 0.62 | 0.2658 | 0.0005 |
| Doc Edit | Single-Agent | 1.00 | 0.0006 | 0.0008 |
| Doc Edit | Full-Context | 1.00 | 0.0253 | 0.0013 |
| Doc Edit | Summary | 1.00 | 0.0358 | 0.0199 |
| Doc Edit | Action-State | 1.00 | 0.0556 | 0.0854 |

## Step latency by model tier (completed runs)
| Strategy | Model | n steps | mean (s) | median (s) |
|---|---|---|---|---|
| Action-State | nvidia/nemotron-3-super-120b-a12b | 71 | 6.6 | 5.0 |
| Full-Context | nvidia/nemotron-3-super-120b-a12b | 75 | 5.7 | 4.5 |
| LightComm | nvidia/nemotron-3-super-120b-a12b | 21 | 10.4 | 7.6 |
| LightComm | nvidia/nemotron-3.5-lightning-30b-a3b | 48 | 50.0 | 38.3 |
| Summary | nvidia/nemotron-3-super-120b-a12b | 61 | 6.0 | 4.8 |
