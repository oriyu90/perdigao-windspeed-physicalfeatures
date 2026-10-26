# Provenance — 公開コピーと内部凍結本体の対応記録

作成日: 2026-10-26。本公開コピーは**内部凍結リポジトリを一巡して read-only で読み出し、
凍結本体を一切変更せずに**作成した。

## 内部凍結本体の情報（値は凍結本体から取得）

| 項目 | 値 |
|---|---|
| リポジトリ HEAD | `e2e3563bf2aaa1806507d08ef28cd27ce2765ead`（`git status --porcelain` 空。デザイン凍結タグ `frozen-design-v1.1-20261009` 以降に F3〜F6・残作業の **7 コミット**が存在する — 初版の「凍結後 commit なし」は誤記、下記 errata 節参照） |
| verify_freeze の manifest 内容ハッシュ | `381b0422f96b7c6eda3270d843644d707701c8215bf9c061e575e87b250e952c`（各 run checkpoint に記録・全フェーズで共通） |
| `manifests/freeze_manifest.json` ファイル自体の SHA-256 | `451afa01882977614af3a6775daf80aef2fd7340cfcd78586d66ae6bc000c973` |
| manifest 14 ファイルの hash 照合 | **13/14 一致**（`audit/paper_code_concordance.csv` は manifest 凍結規程により照合免除） |
| 凍結時期 | F2: 2026-10-09（`internal freeze (no-OSF)`） |
| フェーズ完遂 | F3 再現 → F4 校正ゲート **CALIBRATION_FAILED**（2026-10-11/12）→ F5 skipped（主解析不実施）→ F6 最終報告 **DELIVERED (WITHHELD)**（2026-10-12） |
| テスト | 18/18 PASS（delivery 記録） |

`status_snapshot.md`（凍結本体 STATUS.md のコピー）にフェーズごとの詳細がある。

## 公開コピーで行った改変（スクラブ一覧）

| ファイル | 改変内容 |
|---|---|
| `code/scripts/p1_audit.py` | `ORDER_URL` を非公開ダウンロード URL から一般注文フォーム URL に変更。`LOCAL_COPY_FROM` をローカル絶対パスからリポジトリ内 `data/raw` 相対参照に変更 |
| `docs/plan_v1.1.md`, `docs/guides/00_…md` | 文中の絶対パス（ユーザーの PC 内パス）を `<PC>/…` 表記に置換 |
| `extras/dev_reference/scripts/ref_realdev.py`, `…/probe_env.py` | 文中の絶対パスを `<PC>/…` 表記に置換 |
| `docs/provenance/freeze_bundle_public.zip` | 内部 `freeze_bundle.zip` の再構成。`manifests/freeze_manifest.json` 内の `order_url` / `local_copy_from` の 2 フィールドを空欄化（それ以外・15ファイル構成・ハッシュ群は原版のまま） |

これにより**公開コピー単体では凍結マニフェストの再検証は意味を持たない**（原典調査用の
留意点）。凍結本体側での検証方法は次の通り:

```bash
# 内部凍結リポジトリ側（公開コピーとは別の場所）で:
cd <凍結本体の親>/perdigao_attribution_v1.1
git rev-parse HEAD                                # e2e3563… と出ることを確認
git status --porcelain                            # 空であることを確認
shasum -a 256 manifests/freeze_manifest.json      # 451afa01… と出ることを確認

# manifest 照合（13/14・concordance 免除）と内容ハッシュ（381b0422…）の再算出は
# 凍結本体の検証関数で一括確認できる:
.venv/bin/python -c "import scripts.p1_audit as p; print(p.verify_freeze())"
```

## 公開から除外した内容

| 除外 | 理由 |
|---|---|
| `data/`（生 NetCDF 等 503 MB） | NCAR EOL データ規約により再配布不可（取得手順は `code/data/README.md`） |
| `logs/`（12 GB） | 実行ログ。公開に不要 |
| `runs/`（各フェーズの checkpoint） | 内部実行メタ（絶対パス混入）。結果は `results/` で公開 |
| `.git/`, `.venv/`, `__pycache__/` | 内部履歴・環境。ユーザー情報を含むため |
| `handoffs/`, `NEXT_SESSION_PROMPT.md`, 手順書 06/09 | サブエージェント運用のための内部文書 |
| `audit/events.jsonl` | 内部セッション記録。provenance の要点は本書に集約 |
| `manifests/raw_files.jsonl` | 生データ 175 ファイルの SHA 台帳（内部実行記録）。照合は凍結本体側で実施 |
| `manifests/freeze_manifest.json` | `order_url` / `local_copy_from` を空欄化した版を `freeze_bundle_public.zip` 内に同梱 |
| `reports/検収チェックリスト_実測.md`, `提出物一覧.md` | 内部検収文書 |

補足: 整合記録（concordance）は 2 版が存在する。凍結時版 `audit/paper_code_concordance.csv`
（`freeze_bundle_public.zip` 内・F2/F3 時点の表記・manifest 記録ハッシュ一致）と、F3 以降に
改訂された `docs/provenance/paper_code_concordance.md`（P1/P2 表記）。改訂の経緯は
`status_snapshot.md` の CONCORDANCE_SUPERSEDE 欄を参照。

※ 確認期間（2017-03-10 以降）の観測データは研究全体を通じて開封・同梱ともに
行っておりません。`runs/exposure.jsonl` は不在のまま維持されています
（`extras/dev_reference/` の参考測定も同様）。

## extras/dev_reference について

F6 後（2026-10-25/26）に確認期間を開けずに行った開発期間のみの探索参考測定
（P4 型主統計・実 Y・合成 DGP なし）のコード・報告書・テーブル。**非事前登録の参考値で
あり、CALIBRATION_FAILED / WITHHELD の判定を変えるものではない**。
補足: fold-level sham RMSE 100 群（`ref_sham_fold_rmse.csv`）を成果物として永続化したため、
`ref_contrasts.csv` の pooled rank は成果物のみから独立再計算できる。

---

## errata と追補（2026-10-26 公開前精査対応）

第三者監査相当の精査（数値照合・テスト実行・ハッシュ検証）で判明した凍結文書の誤記・不整合と、
公開コピー側で行った対応の記録。**凍結本体・凍結成果物の数値・本文は一切変更していない**。
以下は本公開コピー（凍結本体とは別物）の文書側での正誤記録である。

### A. 本精査で公開コピーに行った変更

| ファイル | 変更 |
|---|---|
| `code/src/perdigao_attr/__pycache__/`（.pyc 2 件） | **削除**。バイトコードにユーザーのホームディレクトリを起点とする絶対パスが残存し、匿名化ポリシー（本書「公開コピーで行った改変」節）に反していた |
| `code/tests/test_p2_reproduction.py`, `code/tests/test_groups_v11.py` | 成果物参照パスの**解決方法のみ**公開レイアウトに適応（凍結レイアウト `code/tables\|reports\|audit` が存在すれば優先）。検証内容・期待値は無変更 |
| `docs/provenance/paper_code_concordance.csv` | **新規同梱**。凍結本体 `audit/paper_code_concordance.csv`（F3 改訂版・CONCORDANCE_SUPERSEDE 後・12 項目）の byte 等価コピー。SHA-256 `51dea7418193b9a1f9ae81446b9a4d2606a939eaf844dd1b8caec1ce80c48c9d`（STATUS.md F3 outputs 記録値と一致）。注意: zip 内の同名著は F2 凍結時版（manifest 記録ハッシュ `02f8c869…`）で別物 |
| `README.md` / `README.en.md` / `code/README.md` | 再現手順を実在コマンドに修正（`run_all.sh` が F1 雛形で全実行系 `--frozen --from-raw` は exit 3 と明記）＋ smoke 成果物の注記追加 |
| `docs/guides/05_フェーズF5-F6.md` | F4 実行例の CLI を実在フラグに修正（`--bundle core4` → `core4x1`、`--sform quad` → `--dforms quad`） |
| `results/reports/calibration_core4x1.md` | 冒頭に【公開コピー追記】注記を追加（5 反復 smoke である旨・正式値 0.73 への参照）。**数値・本文は一切変更していない** |
| `.gitignore` | **新規追加**。macOS の `.DS_Store`・`._*` と Python の `__pycache__/`・`*.pyc`・`.venv/`・`.pytest_cache_/` の除外設定のみ（追加時点で該当ファイルは本コピーに存在しない）。GitHub 公開（下記 D）に際して後日混入を防ぐためのもの。内容・コードへの影響なし |

対応後の公開コピーで `code/` にて `uv sync --locked && uv run python -m pytest tests/ -q` は
**18/18 PASS**（実測、Python 3.12 / uv.lock 準拠環境）。

### B. 凍結文書の誤記・不整合（errata。修正はしない）

| 件 | 詳細 |
|---|---|
| `status_snapshot.md`: `git_commit` | `git_commit: dc70ed6 F6 failure report delivered (DELIVERED)` は誤記。F6 delivery commit は `925a6d6`、`dc70ed6` は「残作業W1-W3」。HEAD は `e2e3563`（git log で確認済み） |
| `status_snapshot.md`: `updated_at_utc` | `2026-10-10T00:18:57Z` は F3 完了時刻で、F6（2026-10-12）内容に更新されていない |
| `status_snapshot.md`: YAML 重複キー | `completed:` が 9 行目と 25 行目に重複。厳密な YAML パーサでは前半 24 項目が消失する |
| `provenance.md` 本体（上の HEAD 表） | 初版の「凍結後 commit なし」は誤り。デザイン凍結タグ以降に 7 コミット（F3 / STATUS / F4 chunk1 / F4 complete / F6 / 残作業W1-W3 / 残作業W4）が存在。本表は修正済み |
| `configs/feature_dag.yaml`: `dtheta_v_dz` | 凍結式 `(theta_v100-theta_v20)/80` は乾燥断熱減率 `GAMMA_D = 0.0098 K/m` の項を欠く。実装（`p4lib.py` / `p2_reproduce.py` の `GAMMA_D`）と `data_contract.yaml`（`dtheta/dz adds Gamma_d=0.0098`）が正。凍結 config は修正しない |
| `configs/feature_dag.yaml`: `rules` | `denom_floor: abs_below_dev_p1pct_is_missing` の実装は固定値 1e-12 / U>0.1 ガードであり dev 下位 1% ではない。`reproduction_only_clip`（Ri_f∈[-5,5]・Ri_g≤5）が主解析パイプラインにも適用されており、guides/01「主解析 clip と再現専用 clip を区別」の前提と不整合。N2 の負値 0 クリップは rules に記載なし |
| `scripts/p4_calibrate_v11.py`: `mobs` | 欠測水準 `mobs = 1−0.852623 = 14.7377%` の導出源は**確認区間** common-mask 率（`protocol.yaml` `confirm_rate`）で、config 参照でなく定数埋め込み。guides/04 は「実測14.7377%」と表記するが導出区間を明記していない |
| `final_report.md` §16 | `./run_all.sh --phase P0` は誤記（`--phase` は未知引数で exit 2）。正しくは `./run_all.sh P0` |
| `final_report.md` §8・§20 | §8 は「逸脱一覧（全 4 件）」に対し本文列挙が 3 件。§20 は `audit/events.jsonl`（全 4 件）の「原文のまま添付」を述べるが、本公開では上記「公開から除外した内容」表のとおり非同梱（凍結本体側で参照） |
| `final_report.md` §16・§18 のパス | 本文の `tables/`・`figures/`・`audit/`・`manifests/`・`handoffs/` は凍結レイアウト基準。公開コピーでは `results/tables/`・`results/figures/` が対応 |
| `extras/dev_reference/reports/参考実測報告_実Y開発期間_20261025.md` §4.3 | 「CI 半幅は ±0.016〜0.054」は誤記。`ref_contrasts.csv`（dayfolds・ci_ok=True・15 行）の再計算では **P−R: 0.016–0.041、P−R と P−S の合算: 0.016–0.057** |
| 反復数の表記 | plan_v1.1.md「＋陰性100（=2100反復相当）」と final_report「2700 反復」は数え方が異なるだけ: 陰性行は DGP 間で同一（est 差 ≤2e-16・同一 seed・S 項なし）のため、固有計算は 2100（陽性 1800＋陰性 300）、CSV 行数は複製込みで 2700（陰性 900 行 = 300 × 3 DGP 複製） |
| `results/tables/` の無接尾辞 3 点 | `calibration_results_core4x1.csv`・`calibration_summary_core4x1.csv`・`reports/calibration_core4x1.md` は 5 反復 smoke 成果物（run_id `2026-10-10T002428`・n_valid=5）。正式値（`_all.csv`・per-condition 9 点）と併存するため参照時は注意（README にも注記済み） |
| `docs/guides/05` clean-room 手順 | `./run_all.sh --frozen --from-raw` は F6 目標インターフェースの記述だが、`run_all.sh` は F1 雛形のまま実装されず常に exit 3（README 側は実態どおりに修正済み） |

### C. 公開コピーでの pytest の位置づけ

凍結本体では 18/18 PASS（凍結本体レイアウトの成果物を参照）。公開コピーでは、上記 A の
パス適応により**同梱成果物**（`results/tables/`・`results/reports/`・`docs/provenance/paper_code_concordance.csv`）
を照合して 18/18 PASS となる。ユーザーが `scripts/p2_reproduce.py` 等を実行して
`code/tables\|reports\|audit` を生成した場合は生成物側が優先される（その場合の照合対象は再実行成果物）。

### D. GitHub 公開（2026-10-26）

本公開コピーを GitHub リポジトリ `oriyu90/perdigao-windspeed-physicalfeatures`
（**Private**、単一初期 commit）としてアップロードした。生データは引き続き同梱しない
（`code/data/README.md` の取得手順どおり取得後に `code/` 上で再現可能）。アップロード時点で
匿名化チェック（ローカル絶対パス・ユーザー名文字列・`.pyc` の残存ゼロ）を再確認済み。
