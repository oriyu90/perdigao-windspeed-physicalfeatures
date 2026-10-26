# p4_realdev_reference (v1.1 F6後・参考実測)

## 位置づけ

`新研究 v1.1 / perdigao_attribution_v1.1`（DELIVERED、CALIBRATION_FAILED）の
**凍結研究本体には触れない** 場所に置く、探索的な**参考実測**フォルダである。

> ※ 公開コピーの注記: この README は内部作業時の記録のコピーのため、実行例に現れる
> 凍結本体側のパス（`perdigao_attribution_v1.1/.venv` 等）は本公開コピーには存在しない。
> 実行環境の構築は `code/`（同梱）の手順（`uv sync --locked` 等）に従うこと。

- 背景: v1.1 は校正ゲート（検出率 80% 以上 + FP 7.5% 以下）で**全 9 条件不達**（最高
  quad/mobs/SNR1.0 = 0.73）のため、凍結プロトコルの規定により P4 主解析
  （確認データを用いた一次測定）は**不実施**で停止した。
- 本フォルダは、ゲート合格なら実施されるはずだった「実際のモデル測定」のうち、
  **確認期間を開封することなく実行できる部分**（開発期間内のみ、実 Y を使う、
  合成 DGP を使わない）を、凍結コードを read-only で再利用して測定する。
- 非事前登録・探索。結果は参考値であり、v1.1 の結論
  （CALIBRATION_FAILED / DELIVERED / WITHHELD）を変えない。

## 絶対禁止事項

1. 確認期間 `2017-03-10T00:00Z` 以降のデータ（実 Y）は**読まない**。
   本フォルダの実行において `perdigao_attribution_v1.1/runs/exposure.jsonl` の
   **作成も禁止**（常時不在を assert する）。
2. 凍結リポジトリ本体への**書込み禁止**（byte 等価を assert）。
   `imports/scripts` は read-only 参照のみ。git 管理外の `__pycache__` 生成のみ例外。
3. 凍結設定（protocol/p_subset/feature_dag/data_contract/model_budget/splits）の変更禁止。
4. 本測定結果を「確認データでの検証」として報告・引用することは**禁止**。
   「開発期間内・探索的・参考」と明記すること。
5. 「物理が効く/不要」「因果」「一般化」「運用有用性」等の
   禁止表現（PLAN_v1.1 §F6 / v1.1 報告書の禁止表現）を使わない。

## 測定設計（v1.1 凍結機構の開発期間ミラー）

- 対象 Y: 実 1 時間先平均風速 `spd_100m_tse13`（canonical: U100）。
- 群: R（44 列）、P = R + Xp（バンドル追加、v1.1 の P=R+Xp 修正）、
  S = R + 100 sham（34/33/33、per-issue 中央値）、
  G = R + RFF（追加列数同一）、B = persistence（参考、fit なし `R_U100@0`）。
- バンドル: core4x1（primary, 追加 4/計 48）、top6x2（12/56）、full24（24/68）。
- HPO: F4 同型 R-only 6 点サブグリッド、勝者を P/S/G に流用（凍結ルール）。
- 分割（2 系統）:
  - `dayfolds`: F4 の `day_folds`（QC 後 11 日の半分 2 fold）— 校正と同型。
  - `blocks14`: 凍結外側設計（14 日 forward-chaining、purge 3h、
    train = issue_time < eval_start − 3h）を開発期間 2016-11-29〜2017-03-10 にミラー。
    先頭ブロック（訓練なし）は skip、評価側 40 行未満／訓練側 200 行未満の
    ブロックは note 付きで不実施。
- pool: fold 集合内で日が重ならないことを assert（pooled day-level 差分）。
- 推定: 日毎 RMSE 差分 P−R / P−S / P−G、7 日円環 moving-block bootstrap
  （10000 回、F4 同一推定量）、pooled 日数 ≥ 7 のときのみ CI（それ未満は点推定＋note）。
- 種 (seed): 群間ペアで 5 seeds（感度分析: 中央値/最小/最大）。
- 検出率(detection)は実 Y には**定義されない**（仕込信号がない）。CI は記述統計。
- SESOI 0.008862（dev BCA RMSE 0.886165 の 1%）は解釈の物差しとして提示。
- rank(P): 100 sham の RMSE が P の RMSE 以上の割合（＝P が勝てた sham の割合）。
  fold 単位は `ref_fold_rows.csv`、pooled は `ref_contrasts.csv`
  （per-sham RMSE は `ref_sham_fold_rmse.csv` に永続化・2026-10-26 精査で追加）。

## 実行

```
V="../perdigao_attribution_v1.1/.venv/bin/python"   # read-only venv（フォルダ外）
"$V" scripts/ref_realdev.py --bundles core4x1,top6x2,full24 --foldsets dayfolds,blocks14 --seeds 5 --tag full
"$V" scripts/ref_realdev.py --bundles core4x1 --foldsets dayfolds,blocks14 --seeds 1 --tag smoke
```

出力: `tables/ref_*.csv`、`runs/<run_id>/checkpoint.json`（メタ）、`reports/` 報告書。

## 安全レール（スクリプト内 assert）

- freeze manifest sha256 `381b0422…` かつ 14 ファイル中 13 の hash 一致
  （concordance 免除・F4 同方式。前後で確認）。
- `exposure.jsonl` 不在（前後確認）、リポジトリ `git status --porcelain` 空（前後確認）。
- issue 時刻最大値 < 2017-03-10T00:00Z（開発窓限定）の硬い assert。

## 制限

- 開発期間の QC 保持行は n=1133 / 11 日（2017-01-28〜02-03 + 02-15,16 + 03-08,09）、
  極端に断片化。CI は広く、外挿・一般化は不可。
- blocks14 は 8 ブロック中 2 ブロックのみ有効（データの断片化のため）。
  ブロック設計の主解析性はここでは示せない。
- G の推定量は F4 校正で未使用のため本参考測定で新規追加（凍結外の拡張、
  各群ごと fold-train scaler ルール準拠）。解釈は探索的。
- sklearn/pandas のバージョン依存性: `perdigao_attribution_v1.1/.venv` の
  sklearn 1.9.1 / pandas 3.0.6 / numpy 2.5.3 を使用（unlock 検証は v1.1 F3 相当）。
