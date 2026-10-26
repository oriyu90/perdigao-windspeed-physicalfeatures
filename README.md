# Perdigão 物理特徴帰属研究 v1.1 — コード・成果物の公開コピー（匿名化）

> 状態: **CALIBRATION_FAILED**（校正ゲート未達・最高検出 0.73）→ 主解析 P4 **不実施（WITHHELD）**。
> 本フォルダは、内部凍結済みリポジトリ `perdigao_attribution_v1.1`（HEAD `e2e3563`、
> manifest `381b0422…`）の**読み出し専用コピー**に、匿名化・データ非同梱の整理をしたものです。
> 凍結本体は一切変更していません（`docs/provenance/provenance.md` 参照）。

## 何の研究か（3 行）

- **問い**: Vassallo et al. (2021, Wind Energy Science) が主張する「物理ベース入力特徴を
  機械学習に入れると風速予報誤差が改善する」を、Perdigão 観測キャンペーンの tse13 塔データで
  **再現・反証する**計画 v1.1（v1.0 の群定義バグ `P=Xp24` を `P=R+Xp` 修正した再実施）。
- **方法**: 合成 DGP による帰属測定（group-attribution 設計: 完全合成群・部分合成群の比較）
  をプロトコル凍結・プログラム指名・二重実装整合（concordance）付きで運用。
- **結果**: 校正ゲート（検出率 80% + FP 7.5%）は **全 9 条件で不達（最高 0.73）** → 主統計
  （確認データでの P4）は実施されず、確認データも未開封のまま **DELIVERED (WITHHELD)**。

## リポジトリ構成

```
public_release/
├── README.md / README.en.md      ← 本書（日本語版 / 英語版）
├── LICENSE (MIT) / LICENSE-DOCS.md (CC BY 4.0)
├── CITATION.cff                  ← 引用情報（原著論文・データセット含む）
├── code/                         ← 実行リポジトリ（凍結本体と同一構造・パス除去版）
│   ├── src/perdigao_attr/  scripts/  tests/  configs/  environment/
│   ├── pyproject.toml  uv.lock  run_all.sh
│   └── data/README.md            ← データの取得手順（データ本体は非同梱）
├── docs/
│   ├── guides/00–05・07–08        ← 実行手順書 8 編（06・09 は内部セッション文書のため非公開）
│   ├── plan_v1.1.md              ← 研究計画書（スクラブ済み）
│   └── provenance/               ← 凍結情報・整合記録・スクラブ記録
├── results/
│   ├── tables/                   ← 校正結果・再現結果の表 28 件（全 9 条件の gate・summary・rows ほか補助表）
│   ├── figures/                  ← 校正ゲートの図 2 枚 + 図源 CSV
│   └── reports/                  ← final_report.md/html/pdf、executive_summary、limitations ほか
└── extras/
    └── dev_reference/            ← F6 後の探索的参考測定（開発期間のみ・実Y・合成なし）
```

## セットアップ

```bash
cd code
uv sync --locked          # Python 3.12 (uv)。versions: numpy 2.5.3 / pandas 3.0.6 / sklearn 1.9.1
uv run python -m pytest tests/ -q    # 18/18 PASS（環境・群・指標・時間契約・guard の自己検証＋同梱成果物の照合）
```

> 注: `run_all.sh` は F1 時点の fail-closed 雛形です。`./run_all.sh --frozen --from-raw` は
> **仕様どおり終了コード 3 で停止します**（凍結設計の維持が目的で、全フェーズ実装は `scripts/` 側にあります）。
> 公開コピーでの実行は下記の段階実行で行ってください。

データ取得後の段階実行（各フェーズの詳細は `docs/guides/` 参照）:

```bash
uv run python scripts/p1_audit.py     # F2: データ検証・凍結（data/raw 構築と SHA 台帳作成）
uv run python scripts/p2_reproduce.py # F3: 原研究再現（約 2h12m）
uv run python scripts/p4_calibrate_v11.py --bundle core4x1 --dforms quad,linear,regime --snrs 0.5,1.0 --reps 100 --resume  # F4: 校正ゲート（結果 → code/tables/）
```

`scripts/p6_report_v11.py`（F6 最終報告の再生成）は凍結レイアウトの
`code/manifests/freeze_manifest.json` を要求します。本コピーには含まれないため、
詳細は `docs/provenance/provenance.md` の errata 節を参照してください。

## データ（非同梱）

Perdigão 観測データ（NCAR EOL dataset 536.011、DOI `10.26023/ZDMJ-D1TY-FG14`、**Version 1.2**）は
ライセンス上ここには含めません。取得手順・時刻範囲・検証（175 ファイル / 527,015,036 bytes /
SHA-256 記録）は **`code/data/README.md`** にまとめてあります。

## 結果（results/ の見どころ）

| 項目 | 内容 | 主なファイル |
|---|---|---|
| 校正ゲート | 全 9 条件 FAIL（検出最高 0.73 < 0.80。FP 条件は pass） | `tables/calibration_summary_core4x1_all.csv`, `figures/calibration_bars.png` |
| 2700 行の生行 | 9 条件 × 300 行の校正行 | `tables/calibration_rows_core4x1.csv` |
| 最終報告 | WITHHELD、18/18 tests、提出物一式 | `reports/final_report.md`（本文の正は md。html は同内容・pdf は表紙＋図版の 3 ページ印刷記録） |
| 前提・局所判断 | 実装コードと論文章の対応 | `docs/provenance/paper_code_concordance.md`（＋同内容 CSV） |

※ 無接尾辞の `tables/calibration_results_core4x1.csv`・`tables/calibration_summary_core4x1.csv`・
`reports/calibration_core4x1.md` は **5 反復パイロット（smoke）実行**（run_id `2026-10-10T002428`、
n_valid=5）の成果物です。正式な 100 反復の値は `calibration_summary_core4x1_all.csv` と
`calibration_*_{dform}_{m}.*` を参照してください（smoke の quad/mobs SNR1.0 検出 0.8 はパイロット値。
正式値は 0.73）。`reports/calibration_core4x1.md` 冒頭にも同様の追記注記があります。

## ライセンス・引用

- **コード（code/ 以下）**: [MIT](LICENSE)
- **文書・図・テーブル（docs/, results/, extras/, README）**: [CC BY 4.0](LICENSE-DOCS.md)
  （ただし `extras/dev_reference/scripts/*.py` はコードのため MIT）
- 引用する場合は `CITATION.cff` 参照。特に原著論文
  **Vassallo, D., Krishnamurthy, R., and Fernando, H. J. S. (2021), Wind Energy Science 6, 295–309,
  DOI: 10.5194/wes-6-295-2021** とデータセット **NCAR EOL 536.011（DOI: 10.26023/ZDMJ-D1TY-FG14）**
  の引用が必須です。原著著者の参考コード (`dvassall/Forecasting_Error_Codes`) は
  ライセンス未明示のため参照のみ（コピー・再配布はしない）。

## 解釈の限定（禁止表現）

`docs/plan_v1.1.md` §F6 の禁止表現規約に従い、本研究の測定は
「物理固有の有限標本帰納バイアス」への限定された質問です。因果効果の主張、
「物理が効く／不要」型の表現、運用有用性・一般化の主張は行いません。
報告書類はこの規約で書かれています。

## 匿名化・改変について

- ユーザー名・絶対パス・内部セッション記録を除去しています（一覧は
  `docs/provenance/provenance.md`）。凍結マニフェスト対象の 14 ファイルのうち
  `audit/paper_code_concordance.csv` は manifest 凍結規程により照合免除。残る 13 件のうち
  **12 件は本コピーに同梱され、凍結本体と byte 一致**（`code/configs/` 5 件 + `code/uv.lock`、
  `results/tables/` の sites.csv・missing_audit.csv、`freeze_bundle_public.zip` 内の
  audit 3 件 + splits.parquet）。最後の 1 件 `manifests/raw_files.jsonl`（生データ 175 ファイルの
  SHA 台帳）は内部記録のため本コピーには含めず、凍結本体側で照合する。
  また `scripts/p1_audit.py` の定数、`code/tests/` 2 件の成果物参照パス（公開レイアウト
  `results/` への適応・provenance.md 追補参照）、`plan_v1.1.md` 等の文中パスは改変済みのため、
  本コピー単体でのマニフェスト再検証は意味を持ちません（凍結本体側での検証方法は
  provenance.md に記載）。
- 探索的付録 `extras/dev_reference/` は非事前登録の参考測定であり、
  上記の CALIBRATION_FAILED / DELIVERED / WITHHELD の判定を変えるものではありません。
- `docs/plan_v1.1.md` 内には非公開の内部文書（実装手順書 06・09）への参照が残っていますが、
  当該文書自体は本公開に含まれません。
