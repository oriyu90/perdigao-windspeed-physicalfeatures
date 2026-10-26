# F4 calibration report v1.1 (confirm targets never read)
run_id: 2026-10-11T110001+0000_381b0422_f4cal_core4x1

freeze: 381b0422f96b... verified (concordance amendment excluded)
bundle: core4x1 {'features': ['TI', 'N2', 'Ri_g', 'tke'], 'lags': ['@0'], 'added': 4, 'total': 48}; dforms: ['linear']
dev issues: 1133 over 11 days; folds (n_train, n_test): [(625, 508), (508, 625)]; AR1 rho=0.5; R dim 44, P added 4 (R+Xp fix); HPO 6-point subgrid
shams: 100 (34/33/33) median; validity: {'PASS': 33}; G-RFF sigma=6.539

## Gate summary (detection >= .80 at SNR .5/1.0 per (dform,cond); FP <= .075)
| bundle | dform | cond | detect_snr0.5 | n_valid_snr0.5 | pr_snr0.5 | ps_snr0.5 | detect_snr1.0 | n_valid_snr1.0 | pr_snr1.0 | ps_snr1.0 | false_positive | n_valid_neg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core4x1 | linear | mobs | 0.19 | 100 | 0.32 | 0.27 | 0.4 | 100 | 0.55 | 0.47 | 0.0 | 100 |

GATE=FAIL
FAIL -> do NOT unseal confirm; write CALIBRATION_FAILED handoff (F6 inherits report).
