# P2 reproduction report (reproduction_only=true)
run_id: 2026-10-09T220255+0000_p2

Fixed defaults: single in-sample ARIMA(2,0,1) per horizon; R0 StratifiedKFold(10, shuffle, seed 20260915) on target deciles; R0 RF 1000/1.0/100 seed 1; R1 75/25 seed 1 + RF 1000/0.7/100 oob; MCP+interp+noise imputation; full-window aggregation; X=[F(T),F(T-5min)]. No tuning to published values.

## Reproduction vs published (pooled CV / single split)
| series | horizon | model | n | rmse | mae | rmse_pub | mae_pub | rel_diff_rmse | label |
|---|---|---|---|---|---|---|---|---|---|
| R0_paper-spec | 10min | ARIMA-RF_full | 28508 | 0.33861537990762686 | 0.23710256067380664 | 0.714 | 0.52 | 0.5257487676363769 | non-repro |
| R0_paper-spec | 10min | BCA | 28508 | 0.34123905625708895 | 0.23980719118599247 | 0.726 | 0.528 | 0.5299737517119987 | non-repro |
| R0_paper-spec | 10min | persistence | 28508 | 0.7320853517209909 | 0.5258416625821649 | 0.737 | 0.531 | 0.006668450853472341 | approx |
| R1_code-spec | 10min | ARIMA-RF_full | 7127 | 0.3421584648915313 | 0.23672413783292365 | 0.714 | 0.52 | 0.5207864637373512 | non-repro |
| R1_code-spec | 10min | BCA | 7127 | 0.3431672559463593 | 0.2392329938834221 | 0.726 | 0.528 | 0.5273178292749872 | non-repro |
| R2_corrected | 10min | R0_full | 28508 | 0.33861537990762686 | 0.23710256067380664 |  |  |  |  |
| R2_corrected | 10min | R1_full | 7127 | 0.3421584648915313 | 0.23672413783292365 |  |  |  |  |
| R0_paper-spec | 1h | ARIMA-RF_full | 28488 | 0.07774454162409028 | 0.0551109431189284 | 1.092 | 0.83 | 0.9288053648131042 | non-repro |
| R0_paper-spec | 1h | BCA | 28488 | 0.0778043749705684 | 0.055784692803604714 | 1.132 | 0.863 | 0.931268219990664 | non-repro |
| R0_paper-spec | 1h | persistence | 28488 | 1.1638998993967047 | 0.8826725425298795 | 1.165 | 0.884 | 0.0009442923633436488 | approx |
| R1_code-spec | 1h | ARIMA-RF_full | 7122 | 0.07919761340856495 | 0.056308389609123606 | 1.092 | 0.83 | 0.9274747129958196 | non-repro |
| R1_code-spec | 1h | BCA | 7122 | 0.07891692899651026 | 0.056638487662875145 | 1.132 | 0.863 | 0.9302853984129769 | non-repro |
| R2_corrected | 1h | R0_full | 28488 | 0.07774454162409028 | 0.0551109431189284 |  |  |  |  |
| R2_corrected | 1h | R1_full | 7122 | 0.07919761340856495 | 0.056308389609123606 |  |  |  |  |
| R0_paper-spec | 3h | ARIMA-RF_full | 28440 | 0.026874283220272317 | 0.019267097150546697 | 1.395 | 1.1 | 0.9807352808456828 | non-repro |
| R0_paper-spec | 3h | BCA | 28440 | 0.026473791593675557 | 0.01923187077828864 | 1.575 | 1.24 | 0.983191243432587 | non-repro |
| R0_paper-spec | 3h | persistence | 28440 | 1.6741656213016178 | 1.3152381647983975 | 1.676 | 1.315 | 0.0010944980300609188 | approx |
| R1_code-spec | 3h | ARIMA-RF_full | 7110 | 0.026776516900280663 | 0.019157208309702092 | 1.395 | 1.1 | 0.9808053642291894 | non-repro |
| R1_code-spec | 3h | BCA | 7110 | 0.026275309904848422 | 0.01906970254392645 | 1.575 | 1.24 | 0.9833172635524772 | non-repro |
| R2_corrected | 3h | R0_full | 28440 | 0.026874283220272317 | 0.019267097150546697 |  |  |  |  |
| R2_corrected | 3h | R1_full | 7110 | 0.026776516900280663 | 0.019157208309702092 |  |  |  |  |

Labels: approx <=5%, partial 5-20%, non-repro >20% or missing spec (descriptive only, not scientific equivalence).

## Snapshots (target windows / sample counts)
| horizon | window_steps | n_issues | n_test_r1 |
|---|---|---|---|
| 10min | 2 | 28508 | 7127 |
| 1h | 12 | 28488 | 7122 |
| 3h | 36 | 28440 | 7110 |

P2 ran R0/R1/R2 once each. Reproduction outputs carry reproduction_only=true and MUST NOT feed P3/P4 (guard-tested).
