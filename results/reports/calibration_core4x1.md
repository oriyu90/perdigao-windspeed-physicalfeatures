# F4 calibration report v1.1 (confirm targets never read)

> 【公開コピー追記 2026-10-26】本ファイルは **5 反復のパイロット（smoke）実行**の成果物です
> （各 `n_valid` = 5、dform は quad/mobs のみ）。正式な 100 反復の結果は
> `calibration_core4x1_{dform}_{m}.md`（9 件）と `tables/calibration_summary_core4x1_all.csv`
> を参照してください（quad/mobs SNR1.0 の正式値: detect 0.73 / pr 0.85 / ps 0.81）。

run_id: 2026-10-10T002428+0000_381b0422_f4cal_core4x1

freeze: 381b0422f96b... verified (concordance amendment excluded)
bundle: core4x1 {'features': ['TI', 'N2', 'Ri_g', 'tke'], 'lags': ['@0'], 'added': 4, 'total': 48}; dforms: ['quad']
dev issues: 1133 over 11 days; folds (n_train, n_test): [(625, 508), (508, 625)]; AR1 rho=0.5; R dim 44, P added 4 (R+Xp fix); HPO 6-point subgrid
shams: 100 (34/33/33) median; validity: {'PASS': 33}; G-RFF sigma=6.539

## Gate summary (detection >= .80 at SNR .5/1.0 per (dform,cond); FP <= .075)
| bundle | dform | cond | detect_snr0.25 | n_valid_snr0.25 | detect_snr0.5 | n_valid_snr0.5 | pr_snr0.5 | ps_snr0.5 | detect_snr0.75 | n_valid_snr0.75 | detect_snr1.0 | n_valid_snr1.0 | pr_snr1.0 | ps_snr1.0 | detect_snr1.5 | n_valid_snr1.5 | detect_snr2.0 | n_valid_snr2.0 | false_positive | n_valid_neg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core4x1 | quad | mobs |  | 0 | 0.4 | 5 | 0.8 | 0.4 |  | 0 | 0.8 | 5 | 1.0 | 0.8 |  | 0 |  | 0 | 0.0 | 5 |

GATE=FAIL
FAIL -> do NOT unseal confirm; write CALIBRATION_FAILED handoff (F6 inherits report).
