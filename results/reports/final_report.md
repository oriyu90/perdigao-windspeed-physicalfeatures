# 最終レポート：Perdigão 風速予報における物理変換特徴の再現・反証研究 v1.1（校正失敗による判定保留）

- 研究名：物理変換特徴は有限標本の風速予報に物理固有の帰納バイアスを与えるか
  ― Perdigão 公開タワー観測を用いた再現・反証研究 v1.1（群定義修正・再校正）
- version: F6-failure-report 1.0（内部凍結、OSF登録なし）
- run_id: 2026-10-12T132705+0000_p6fail
- protocol hash: 381b0422f96b7c6eda3270d843644d707701c8215bf9c061e575e87b250e952c
- 内部凍結：tag frozen-design-v1.1-20261009（外部事前登録なしのため「事前登録」の表現は使わない）
- 生成日（UTC）: 2026-10-12
- source of truth: tables/*.csv（本文数値は tables/p6_report_values.csv からのみ転記）

## 1. 表紙

上記のとおり。本レポートは校正失敗時の失敗レポートであり、帰属判定を含まない。
確認区間の標的は開封しておらず、一次確認解析は未実施である（runs/exposure.jsonl なし）。
本研究は事前登録を欠くため、確証的強度は外部登録済みの現行研究より一段低い
「内部凍結準確証・探索的確証」に留まる。

## 2. 日本語要旨

Vassallo et al. (2021) が報告した「物理ベース入力特徴による風速予報誤差の改善」という主張を、
Perdigão 公開タワー観測（NCAR/EOL dataset 536.011, Version 1.2）のみを用いて追試する計画を立て、
内部凍結した（tag frozen-design-v1.1-20261009、OSF登録なし）。現行研究 v1.0 は校正プログラムの
群定義欠落（P を物理列のみで fit し sham 側は R＋sham で fit する非対称）を含む状態でゲート不合格となり
確定したため、本研究では P＝R＋Xp の修正を核とし、一次束を核心 4 種（TI・N2・Ri_g・tke×@0、追加 4 列）に縮小し、
DGP 3 形・100-sham 中央値で校正を再実施した。原研究再現（F3）では persistence のみが公表値と概ね一致し、
BCA と ARIMA-RF は仕様の未特定部分のため再現しなかった。帰属判定パイプラインの妥当性を半合成対照で校正したところ
（F4、2700 反復すべて有効）、結合検出率は SNR0.5 で 0.09–0.41、
SNR1.0 で 0.11–0.73 で事前基準 80% に届かず、
偽陽性率は全条件 0.01 以下で基準（7.5% 以下）を満たした。ゲート不合格のため規定どおり一次確認解析を開始せず、
確認区間は密封のままである。結論として、帰属測定系または実装監査が不合格であり、
実データの帰属判定を保留した。開発有効データが 11 断片日のみ・fold 学習約 500–600 行という条件下で、
信号優位が 100-sham 中央値との比較を上回らなかった。再現手順、表、図、検証記録を本レポートに添付する。

## 3. English abstract

We conducted an internally-frozen (tag frozen-design-v1.1-20261009, no OSF preregistration)
replication and falsification study of the Vassallo et al. (2021) claim that physics-based input
features improve wind-speed forecast error, using only the public Perdigao tower observations
(NCAR/EOL dataset 536.011, Version 1.2, DOI 10.26023/ZDMJ-D1TY-FG14). The predecessor study v1.0 ended with an
uncalibrated gate that included a group-definition bug (P fit on physics columns alone while
shams used R+sham inputs); v1.1 fixes P to R+Xp concatenation, narrows the primary bundle to
4 core features (TI, N2, Ri_g, tke at @0 only), and recalibrates with 3 DGP forms and a 100-sham
median. F3 reproduced persistence at the published level but not BCA/ARIMA-RF, whose specification
gaps are documented as audit findings. The attribution pipeline was calibrated with semi-synthetic
positive/negative controls (F4, 2700/2700 valid reps): joint detection rates were
0.09–0.41 at SNR 0.5 and
0.11–0.73 at SNR 1.0 against a pre-fixed 80% bar,
with false positive rates at or below 0.01 (bar 0.075). The gate failed, so per protocol no primary
confirm-interval analysis was started and the confirm interval remains sealed
(no runs/exposure.jsonl). Conclusion: the attribution instrument did not qualify, and the
attribution verdict on real data is withheld. Reproduction steps, tables, figures, and validation
records are attached. This study is exploratory-confirmatory under internal freeze only and makes no external-registration claim.

## 4. 研究質問と主張範囲

主研究質問（PLAN_v1.1.md §1.1）：同一の観測情報から決定論的に作られる安定度・乱流の物理変換特徴は、
同じ情報・次元・欠測構造・概ね同じ非線形性を持つ非物理変換より、Perdigao の 100 m 風速 1 時間先予報の
時間外汎化誤差を小さくするか。推定対象は現実の物理過程の効果ではなく、限られたデータとモデルの下での
物理固有の有限標本帰納バイアスである。主張範囲は Perdigao・1 時間先・指定特徴束（一次 core4x1）・
指定モデル族に限定する。一次束を core4 に縮小したため、原論文の 12 特徴束そのものの主張を直接反証・支持しない。
対象外への拡張は行わない。本レポートではこの問いへの回答を出さない（判定保留）。

## 5. 先行研究と再現対象

- Vassallo, D., Krishnamurthy, R., and Fernando, H. J. S. (2021),
  Utilizing physics-based input features within a machine learning model to predict wind speed
  forecasting error, Wind Energy Science, 6, 295–309. DOI: 10.5194/wes-6-295-2021
  （CC BY 4.0）。
- 著者参考コード dvassall/Forecasting_Error_Codes（commit 9420b71561d9d51c6665cab918371cd16fa074dd、
  到達確認済み、明示ライセンスなしのため参照のみ、コピー・再配布なし）。
- 現行研究 v1.0（CALIBRATION_FAILED で確定、確認密封維持）は読出し専用。本研究はその再実施である。

## 6. データ入手性、version、期間、QC、欠測

- 提供元：NSF NCAR Earth Observing Laboratory、Quality Controlled 5-minute ISFS surface flux data、
  geographic coordinate, tilt corrected、Version 1.2、dataset 536.011、DOI 10.26023/ZDMJ-D1TY-FG14。
- 期間：2016-11-29〜2017-07-01。開発区間 2016-11-29〜2017-03-10、確認区間 2017-03-10〜2017-06-16、
  2017-06-17 以降は将来の独立確認候補として未読。
- 取得：v1.0 の P1 で取得した同一 DOI・version のローカル検証済み写し（SHA 再検証済み）。
  新規 POST・メール受信・資格情報なし。DOI の fresh 302 redirect を再確認。
  NetCDF 175 ファイル、合計 527015036 bytes、各ファイルの SHA-256・magic bytes（CDF1）を
  manifests/raw_files.jsonl に記録。確認区間 common-mask 率 0.852623（gate 0.70、PASS）。
- 塔：tse13（北側稜線頂、標高 452.9 m、20/100 m フルソニック）。tse09（谷斜面 305.3 m）は棄却。
  決定根拠は位置・計器表のみ（標的未読）。
- QC 除外：ldiag≠0、wake 310–340° を事前規則で除外（「除外なし」は感度解析として併記予定だったが、
  一次解析未実施のため未実施）。
- 欠測：tables/missing_audit.csv にファイル別件数のみ記録（全 45112 stamps、
  common_ok 合計 25706）。標的の補完は禁止の規則。

## 7. paper-spec / code-spec 整合監査

F3 で原論文記載仕様（paper-spec）と著者サンプル仕様（code-spec）を分離し、各 1 回ずつ実行。
sample code は全解析コードそのものではないため、差だけで原論文の誤りとは断定しない。

| item | paper | code | verdict | evidence |
| --- | --- | --- | --- | --- |
| data_period | 2017-03-10 to 2017-06-16 | pre-supplied CSV (period not enforced in sample) | PAPER_ONLY | paper.xml Sec.2 + sampleCode Data paths |
| tower_height_vars | northern-ridge 100m tower; 20/100m sensors | Vars100m/Vars assume 20/100m cols (tower ID not checked) | MATCH | paper.xml Sec.2 + sampleFuncs Vars100m/Vars; P1 tower_decision tse13 |
| aggregation_alignment | 10min/1h/3h windows at 5min moving average | 2 lags + n_skip comment (2/12/36); movingIndices[:-1] | CONFLICT | paper.xml Sec.2 + sampleFuncs data_Func; P2 R0 vs R1 separated |
| arima_fit_forecast_update | ARIMA(2,0,1) fit/forecast described; update cadence UNSPECIFIED | absent: reads arima error/preds cols; no generator | CODE_ONLY | paper.xml Sec.3.1 + sampleFuncs Vars100m cols; P2 single in-sample fit (documented default) |
| missing_imputation | variance-ratio MCP + linear interp + Gaussian noise | drop-last-row only; no MCP/interp in sample | CONFLICT | paper.xml Sec.2 + sampleFuncs Vars |
| split_stratification | stratified 10-fold CV (strata UNSPECIFIED) | random 75/25 split random_state=1 (x2) | CONFLICT | paper.xml Sec.2 + sampleCode tts lines; P2 target-decile default |
| lag_horizon | previous two time steps; 10min/1h/3h horizons | 2 lags via inputIndices; horizon via n_skip comment | MATCH | paper.xml Sec.3.2 + sampleCode n_steps/n_skip |
| rf_config | 1000 trees single-var / 1500 combo; min_samples_split=100 | 1000/0.7/100 + oob; no 1500 branch | CONFLICT | paper.xml Sec.3.2 + sampleCode RandomForestRegressor; P2 R0=1000/1.0/100, R1=1000/0.7/100 |
| feature_selection | exhaustive individual + combination tests | fixed 15-group bundle; importance block commented out | PAPER_ONLY | paper.xml Sec.3.3 + sampleCode var list |
| rmse_formula | standard RMSE (text) | mean(sqrt(error^2)) stored as rmse | CONFLICT | paper.xml Sec.3 + sampleCode rmse line; P2 R2 recomputes sqrt(mean(err^2)) |
| mae_formula | standard MAE (text) | same expression equals MAE (under rmse name) | CONFLICT | paper.xml Sec.3 + sampleCode rmse/newrmse lines |
| seed | ensemble of 10 runs (seeds UNSPECIFIED) | random_state=1 fixed | UNSPECIFIED | paper.xml Sec.3 + sampleCode tts; P2 fixes seeds, no tuning |

主な不整合：集約位置合わせ、ARIMA 適合・予報更新手順（UNSPECIFIED）、欠測補完、分割層化、
RF 設定、RMSE/MAE 呼称（sample の `rmse` は mean(sqrt(error^2)) であり数値的には MAE と一致、
R2 で正規 RMSE/MAE/R² を再計算）。v1.0 の F3 数値と完全一致（同コード・同データの再実施として整合）。

## 8. 内部凍結と逸脫

- 凍結：F2 で P1_FROZEN（manifest 381b0422f96b7c6e…、tag frozen-design-v1.1-20261009、内部凍結のみ、OSF登録なし）。
  protocol / feature DAG / data contract / model budget / p_subset / split / seed の hash を
  freeze_manifest.json に保存し、freeze_bundle.zip をローカル保管（外部提出なし）。
- OSF 事前登録は行わない（PLAN_v1.1 前提）。報告書では「事前登録」の表現を使わず、
  「内部凍結準確証（OSF登録なし）」と明記する。
- 逸脫一覧（audit/events.jsonl、全 4 件）：
  - CONCORDANCE_SUPERSEDE：P0 draft の concordance を F3 完全版（12 行）へ置換
    （freeze_manifest.json は不変）。
  - CALIBRATION_FAILED：ゲート不合格のため一次 fit を開始せず停止（規定どおり）。
  - F6（本レポート）：凍結設定の変更なし、確認開封なし。

## 9. 時刻契約、分割、特徴 DAG、対照群

- 時刻契約：UTC 正規化、右端揃え入力 Z_h(T)=mean(Z in (T-h,T])、標的 Y_h(T)=mean(U100 in (T,T+h])、
  全入力の最大 source time ≤ T、purge 3 時間、前処理・補完・HPO は fold 学習側のみ。
- 分割：開発 2016-11-29〜2017-03-10、確認 2017-03-10〜2017-06-16 を 14 日連続ブロック
  （8 outer folds、manifests/splits.parquet、purge 3 h）。確認性能を見た後の境界変更なし。
- 特徴 DAG：configs/feature_dag.yaml に数式・単位・親変数・時刻・塔・高度・QC を固定（12 特徴、
  すべて AVAILABLE、hash 凍結済み）。P＝R＋Xp の群定義を明記（v1.0 の P_only バグの修正）。
- 対照群：B（persistence 等予報基準）、R（全親情報 44 列）、P_core4（R＋核心 4 種×@0＝48 次元、一次）、
  P_top12／P_full24（二次、未実行）、S（100 sham：式シャッフル 34／次元整合 33／統計整合 33、
  各々対応する P と同追加列数）、G（R＋ランダム Fourier 同追加列数、帯域は開発 median heuristic）。
  全群で追加列数・common mask・fit 予算一致。scaler（median/IQR）は各群・各 fold 学習側で別 fit。
  sham 妥当性 33/33 PASS（audit/sham_validity.csv、INVALID_CONTROL なし）。

## 10. 半合成校正結果

実観測 X と欠測構造を保ち、確認標的を使わず陽性対照（予測可能基礎項＋既知 P 依存項＋ブロック相関ノイズ）と
陰性対照（基礎項＋P 独立ノイズ）を生成。DGP 3 形（quad／linear／regime、いずれも tanh(/2) 有界、
開発全体で標準化）、SNR 6 水準（ゲート判定は 0.5／1.0 のみ、他は未実行の報告のみ対象）、
AR1 rho=0.5、base ridge（alpha=1.0）は fold-train 再適合、
HPO は凍結格子 6 点部分格子を R のみで内側選択→P・100 sham へ勝者共通適用、開発 11 日の 2 日プール評価。
検出/rep は P-R と P-S の両 95% CI 上限<0（一次条件 1・2 に対応）。校正の検出判定に G は使わない。
最小必須（core4×3DGP×SNR0.5/1.0×3 欠測×100＋陰性 100/条件＝2700 反復相当）を checkpoint 分割で完走。

| bundle | dform | cond | detect_snr0.5 | n_valid_snr0.5 | pr_snr0.5 | ps_snr0.5 | detect_snr1.0 | n_valid_snr1.0 | pr_snr1.0 | ps_snr1.0 | false_positive | n_valid_neg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core4x1 | linear | m0 | 0.15 | 100 | 0.26 | 0.2 | 0.45 | 100 | 0.59 | 0.54 | 0.01 | 100 |
| core4x1 | linear | m10 | 0.15 | 100 | 0.26 | 0.21 | 0.45 | 100 | 0.57 | 0.54 | 0.01 | 100 |
| core4x1 | linear | mobs | 0.19 | 100 | 0.32 | 0.27 | 0.4 | 100 | 0.55 | 0.47 | 0 | 100 |
| core4x1 | quad | m0 | 0.28 | 100 | 0.42 | 0.4 | 0.52 | 100 | 0.62 | 0.68 | 0.01 | 100 |
| core4x1 | quad | m10 | 0.41 | 100 | 0.61 | 0.51 | 0.71 | 100 | 0.83 | 0.78 | 0.01 | 100 |
| core4x1 | quad | mobs | 0.37 | 100 | 0.62 | 0.48 | 0.73 | 100 | 0.85 | 0.81 | 0 | 100 |
| core4x1 | regime | m0 | 0.09 | 100 | 0.25 | 0.13 | 0.24 | 100 | 0.31 | 0.32 | 0.01 | 100 |
| core4x1 | regime | m10 | 0.1 | 100 | 0.27 | 0.18 | 0.11 | 100 | 0.3 | 0.2 | 0.01 | 100 |
| core4x1 | regime | mobs | 0.1 | 100 | 0.24 | 0.16 | 0.15 | 100 | 0.33 | 0.25 | 0 | 100 |

条件別ゲート内訳（tables/calibration_rows_core4x1.csv からの再計算、summary と一致を確認）：

| dform | cond | recalc_detect_0.5 | pr_0.5 | ps_0.5 | recalc_detect_1.0 | pr_1.0 | ps_1.0 | recalc_fp | neg_gap_mean | neg_gap_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quad | m0 | 0.28 | 0.42 | 0.4 | 0.52 | 0.62 | 0.68 | 0.01 | 0.0103 | 0.0105 |
| quad | m10 | 0.41 | 0.61 | 0.51 | 0.71 | 0.83 | 0.78 | 0.01 | 0.0065 | 0.003 |
| quad | mobs | 0.37 | 0.62 | 0.48 | 0.73 | 0.85 | 0.81 | 0 | 0.0118 | 0.0069 |
| linear | m0 | 0.15 | 0.26 | 0.2 | 0.45 | 0.59 | 0.54 | 0.01 | 0.0103 | 0.0105 |
| linear | m10 | 0.15 | 0.26 | 0.21 | 0.45 | 0.57 | 0.54 | 0.01 | 0.0065 | 0.003 |
| linear | mobs | 0.19 | 0.32 | 0.27 | 0.4 | 0.55 | 0.47 | 0 | 0.0118 | 0.0069 |
| regime | m0 | 0.09 | 0.25 | 0.13 | 0.24 | 0.31 | 0.32 | 0.01 | 0.0103 | 0.0105 |
| regime | m10 | 0.1 | 0.27 | 0.18 | 0.11 | 0.3 | 0.2 | 0.01 | 0.0065 | 0.003 |
| regime | mobs | 0.1 | 0.24 | 0.16 | 0.15 | 0.33 | 0.25 | 0 | 0.0118 | 0.0069 |

受入基準：各（DGP、欠測条件）で SNR0.5 と SNR1.0 の結合検出率各 80% 以上＋偽陽性率 7.5% 以下。
結果：検出率 SNR0.5 で 0.09–0.41、
SNR1.0 で 0.11–0.73（全条件で基準未達）、
偽陽性率は全条件 0.01 以下（基準内）。
2700/2700 反復すべて有効。よって GATE=FAIL。規定どおり帰属解析を停止し、
確認区間の開封・一次 fit を行わなかった。
陰性対照の P−R 差（RMSE）は全体平均 0.0095 であり、
修正後のハンディは v1.0（+0.5044）の約 1/25 以下に縮小したが、100-sham 中央値との比較（P-S 側）が
ボトルネックとなった（例：quad×mobs で P-R 検出 0.62/0.85 に対し P-S 検出 0.48/0.81）。

図：figures/calibration_bars.png（元データ figures/calibration_bars_source.csv）、
figures/design_flow.png。

## 11. 一次結果

未実施。校正ゲート不合格のため一次確認解析（CONFIRM）は開始していない。
Δ_PR、Δ_PS、sham rank、95% CI、SESOI 判定のいずれも実データについては存在しない。
tables/primary_decision.json に WITHHELD（判定保留）を記録した。
一次 5 条件の AND 判定は適用対象がないため実施していない。

## 12. 物理保存・破壊試験

未実施（一次解析未実施のため）。保存試験（水平回転の共変性）・破壊試験（鉛直順序・符号破壊）・
レジーム試験（開発区間固定閾値の強安定／中立／強不安定）は凍結設計に残るが実行していない。

## 13. 二次・感度解析

未実施。top12／full24 束、10 分先・3 時間先、Elastic Net・HistGradientBoosting、レジーム別効果、
拡張 SNR（0.25／0.75／1.5／2.0）はいずれも実行していない。
二次 family への Holm 補正の適用機会は発生していない。

## 14. 査読で想定される反論への回答

- 「検出力不足は設計不良ではないか」：ゲート仕様・DGP・HPO 規則・sham 構成・評価単位は確認性能を見る前に
  固定した。検出力不足は事後調整ではなく事前固定ゲートが検出した事実であり、失敗を隠さず報告する。
- 「束を広げれば通るのではないか」：確認性能を見た後の束・DGP・SNR・seed・探索範囲の変更は禁止規則により行わない。
  変更は新規凍結＋再実行の対象であり、本レポートでは行わない。
- 「v1.0 のバグ修正で通ると思ったのではないか」：修正により検出率は v1.0（0.00–0.03）から
  最大 0.73 まで改善したが、事前基準には届かなかった。改善の事実とゲート不合格の事実をともに報告する。
- 「再現の不一致は実装誤りではないか」：persistence が全 horizon で概ね一致（下表）し集約パイプラインは妥当。
  BCA・ARIMA-RF の差は ARIMA 更新手順の未特定に起因する監査所見であり、調整対象にしないと事前に固定した。

| series | horizon | n | rmse | mae |
| --- | --- | --- | --- | --- |
| R0_paper-spec | 10min | 28508 | 0.732085 | 0.525842 |
| R0_paper-spec | 1h | 28488 | 1.1639 | 0.882673 |
| R0_paper-spec | 3h | 28440 | 1.67417 | 1.31524 |

公表値（参考、tables/published_results.csv より）：

| horizon | model | rmse | mae | source |
| --- | --- | --- | --- | --- |
| 10min | persistence | 0.737 | 0.531 | Table1 |
| 10min | BCA | 0.726 | 0.528 | Table1 |
| 10min | ARIMA-RF_full | 0.714 | 0.52 | Table1 |
| 10min | ARIMA-RF_noT | 0.712 | 0.518 | Table1 |
| 1h | persistence | 1.165 | 0.884 | Table1 |
| 1h | BCA | 1.132 | 0.863 | Table1 |
| 1h | ARIMA-RF_full | 1.092 | 0.83 | Table1 |
| 1h | ARIMA-RF_noT | 1.071 | 0.813 | Table1 |
| 3h | persistence | 1.676 | 1.315 | Table1 |
| 3h | BCA | 1.575 | 1.24 | Table1 |
| 3h | ARIMA-RF_full | 1.395 | 1.1 | Table1 |
| 3h | ARIMA-RF_noT | 1.379 | 1.083 | Table1 |
| 1h | ARIMA-RF_R2_0.84_claim | nan | nan | abstract_R2=0.84 |

- 「確認区間を見れば何か言えるのではないか」：ゲート不合格後の確認開封は規則で禁止されている。
  見ていないデータで結論を補うことはしない。

## 15. 限界

- 本レポートは帰属判定を含まない。物理変換の効果の有無・大小・実用価値について何も主張しない。
- 再現は固定 default の 1 回実行であり、原論文の未特定部分の別解釈を尽くしたものではない。
- 半合成 DGP は事前固定の 3 設定（quad／linear／regime＋tanh、AR1 rho=0.5）であり、現実の物理過程の
  代替物ではない。校正失敗は「今回の判定パイプラインが今回の条件下で感度不足」という測定器評価であり、
  物理一般の評価ではない。
- 開発有効データは 11 断片日（1133 issues、fold 学習 625/508 行）に限られ、長期・多季節の代表性はない。
- OSF 事前登録がないため確証的強度は一段低く、探索的確証として扱う。
- 対象外への拡張は行わない。

## 16. 再現方法

```bash
uv sync --locked
uv run pytest
./run_all.sh --phase P0   # 環境・契約試験のみ（実データ取得は EOL 注文が前提）
```

- Python 3.12（uv 固定）、OS・wheel 情報は environment/system_info.json、依存固定は uv.lock
  （hash 凍結済み、F6 で変更なし）。
- 乱数は NumPy Generator(PCG64) に統一、master_seed=2026091501、seed 派生は
  SHA256(master_seed＋namespace＋index) 先頭 64 bit（Python 組込み hash() 禁止）。
- F3 再現：`.venv/bin/python scripts/p2_reproduce.py`（約 2h12m、R0/R1/R2 各 1 回のみ）。
- F4 校正：`.venv/bin/python scripts/p4_calibrate_v11.py --bundle core4x1 --dforms <3形>
  --snrs 0.5,1.0 --conds <3水準> --reps 100 --resume` を 9 チャンク逐次実行（計約 60 h、
  終了コード 4=GATE FAIL、増分 rows＋checkpoint で crash-safe 化）。
- F6 本レポート：`.venv/bin/python scripts/p6_report_v11.py`（本ファイル生成、確認開封なし）。
- 第三者の完全再実行は、原データの再取得（EOL 注文フォーム、無償、メール受領方式）を前提とする。
  生 NetCDF は git・配布物に含めない（取得 URL・version・hash・スキーマ・処理コードを公開単位とする）。
- 完全 clean-room（空 cache からの raw 再取得＋60 h 校正再実行）は本セッションでは未実施。
  再実行監査は git clone＋hash 照合＋pytest＋表再計算の範囲で実施し、結果を handoffs/PHASE_P5.md に記録。

## 17. 結論

帰属測定系または実装監査が不合格であり、実データの帰属判定を保留した。

（一次 5 条件のすべてを満たさないため、結論テンプレートのうち校正失敗に対応する本テンプレートを
tables/primary_decision.json から自動選択した。自由な強調による格上げは行わない。）

## 18. データ・コード可用性

- 観測データ：NCAR/EOL dataset 536.011, Version 1.2, DOI 10.26023/ZDMJ-D1TY-FG14（公開メタデータ上 access/legal constraints none）。
  取得 URL・日時・バイト数・SHA-256・NetCDF global attributes・変数一覧・時間範囲・
  欠測率は manifests/ に保存。生データ自体は本リポジトリ・配布物に含めない。
- コード：本リポジトリ perdigao_attribution_v1.1（内部凍結 tag frozen-design-v1.1-20261009、
  manifest 381b0422f96b7c6e…）。著者サンプルコードは commit hash 参照のみで再配布していない（ライセンス不明のため）。
- 内部凍結：preregistration/freeze_bundle.zip をローカル保管（外部提出なし）。OSF登録なし。
- 表・図：tables/、figures/（各図に元データ CSV と生成スクリプト scripts/p6_report_v11.py を添付）。

## 19. 参考文献

- Vassallo, D., Krishnamurthy, R., and Fernando, H. J. S. (2021), Utilizing physics-based input
  features within a machine learning model to predict wind speed forecasting error,
  Wind Energy Science, 6, 295–309. DOI: 10.5194/wes-6-295-2021（CC BY 4.0）。
- Vassallo, Forecasting_Error_Codes, commit 9420b71561d9d51c6665cab918371cd16fa074dd
  （到達確認済み、明示ライセンスなし、参照のみ・再配布なし）。
- NSF NCAR EOL, Quality Controlled 5-minute ISFS surface flux data, geographic coordinate,
  tilt corrected, Version 1.2, dataset 536.011. DOI: 10.26023/ZDMJ-D1TY-FG14。
- NCAR/EOL, Perdigao ISFS Data Report v1.1（QC レポート PDF、SHA-256 記録済み）。
- 標準的方法論の参照識別子：Bergmeir & Benitez (2012, time-series cross-validation);
  Efron (bootstrap block methods); Hastie–Tibshirani–Friedman (regularized regression/RF practice).
  （F6 で新規外部取得は行っていない。識別子のみの記載であり、本文の数値根拠には使っていない。）

## 20. 全試行・全逸脫一覧

audit/events.jsonl（全 4 件）を原文のまま添付する。F3 は R0/R1/R2 各 1 回のみ実行し、
結果合わせの設定探索は行っていない。F4 は 2700/2700 有効反復で終了コード 4（GATE FAIL）。
一次確認 fit・F5・追加データ取得は未実施。fit 台帳：一次 fit なし、校正 fit は半合成 2700 反復分
（base ridge fold-train 再適合＋凍結格子 HPO を R のみで内側選択の規則どおり）。
失敗 fit・除外は calibration_rows_core4x1.csv（全行に note 列なし＝有効）および上記 events に
記録したものがすべてである。F4 途中の 1 回の中断（170/300、プロセス消失）は増分 rows 化して再投入し、
欠番なく 2700 行に到達した。
