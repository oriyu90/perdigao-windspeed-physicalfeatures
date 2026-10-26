project: perdigao_attribution_v1.1
state: DELIVERED
phase: F6
protocol_hash: 381b0422f96b7c6eda3270d843644d707701c8215bf9c061e575e87b250e952c
git_commit: dc70ed6 F6 failure report delivered (DELIVERED)
dirty: false
started_at_utc: 2026-10-07T15:23:00Z
updated_at_utc: 2026-10-10T00:18:57Z
completed:
  - DOI 10.26023/ZDMJ-D1TY-FG14 fresh 302 redirect verified (EOL landing 1453B SPA); dataset v1.2 local verified copy from v1.0 data/raw (175 nc, 527015036 bytes, SHA re-verified)
  - raw audit: 175/175 CDF1 magic, nsites 41, coverage 2016-11-29T00:02:30 to 2017-07-01T09:32:30, grid 0 off-300s/0 dups/monotonic
  - tower tse13 three-way match finalized (tse13 452.9m ridge crest vs tse09 305.3m valley-slope; full 20/100m sonic suites)
  - canonical mapping 22 vars + spd identity (dev file, max hypot-spd diff recorded) + QC exclusions (ldiag/wake 310-340)
  - eligibility gate 85.2623% (24310/28512, threshold 70%) PASS; paper claim 100m-without-20m 0/28295
  - dev BCA RMSE 0.886165 recomputed (rolling 24h ARIMA(2,0,1), 100 origins) -> SESOI 0.008862 (v1.0 value reference only, not reused)
  - splits 14d x 8 frozen (purge 3h, 2017-03-10 to 2017-06-17); content identical to v1.0 (parquet hash differs only by writer metadata)
  - configs frozen FROZEN-P1: protocol (core4x1 primary, top6x2/full24 secondary, P=R+Xp, SNR 6 levels, DGP quad/linear/regime, 100-sham median) + feature_dag + data_contract + model_budget + p_subset
  - freeze_manifest.json sha 381b0422... (14 files, all hashes verified at F3 start) + freeze_bundle.zip local only sha 07c7bb60... (15 files, gitignored, no OSF)
  - raw_files.jsonl sha 479e7805... identical to v1.0 (same bytes); sites/missing_audit identical to v1.0
  - F3 freeze re-verification PASS (manifest recalc 381b0422 match, 14 files OK, tag frozen-design-v1.1-20261009 annotated, git clean, seal SEALED, v1.0 untouched)
  - F3 P2 R0/R1/R2 each once done (run_id 2026-10-09T220255+0000_p2, 2026-10-09T22:02:55Z to 2026-10-10T00:14:28Z, no tuning): 10min n28508/7127, 1h n28488/7122, 3h n28440/7110
  - persistence approx on all horizons (10min 0.7321 vs 0.737, 1h 1.1639 vs 1.165, 3h 1.6742 vs 1.676); BCA/ARIMA-RF non-repro (e.g. 1h BCA 0.0778 vs 1.132, ARIMA-RF 0.0777 vs 1.092); R2 recompute consistent; legacy==MAE detected
  - outputs: tables/reproduction_results.csv sha 09e104df..., published_results.csv 6d27c579..., audit/paper_code_concordance.csv 51dea741... (12 rows, P2/P1 labels, CONCORDANCE_SUPERSEDE logged, manifest immutable), reports/reproduction.md + paper_code_concordance.md
  - pytest 16/16 pass (11 existing + 5 P2); confirm sealed (no runs/exposure.jsonl, guard PermissionError); no data/processed|interim parquet;現行本体無変更
completed:
  - F6 P5 failure report delivered (run 2026-10-12T132705+0000_p6fail; 20-section md/html/pdf, WITHHELD decision, 71-file delivery)
pending:
  - none (study stopped at DELIVERED)
blocked: false
blocker_code: null
next_command: none (DELIVERED; further conditions require a new freeze and new study)
next_instruction: none (DELIVERED)
