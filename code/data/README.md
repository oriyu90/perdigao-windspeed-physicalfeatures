# データの取得（非同梱）— Perdigão observation data

> 本リポジトリには観測データ **を含めません**（NCAR EOL のデータ規約による）。
> 本人が NCAR EOL に注文して取得したファイルを検証済みハッシュで用いるのが前提です。

## 取得手順（v1.1 凍結時の実行記録・手順書 07 と同一）

1. **注文フォーム**: <https://data.eol.ucar.edu/cgi-bin/codiac/fgr_form/id=536.011>
   - Dataset: **Perdigão field campaign, dataset 536.011、DOI: 10.26023/ZDMJ-D1TY-FG14**
   - **Version は必ず 1.2 を選択**（1.2 以外になった場合は INFEASIBLE で停止する規約）
   - 時刻範囲: Begin `20161129 00:00:00` / End `20170701 23:59:59`
   - 形式: NetCDF / 圧縮 None
   - 送信先メールは注文者本人
2. **ダウンロードした全ファイル**を `data/raw/` 直下に置く
   （zip/tar は**展開しない**）。想定: **175 ファイル / 計 527,015,036 bytes**。
3. 検証:

```bash
uv run python scripts/p1_audit.py
```

   - ファイル単位の SHA-256 と件数・合計バイトを記録（`manifests/raw_files.jsonl`）
   - magic bytes・`xarray` で open 可能・時刻契約・タワー選定（tse13）を audit
   - 設定の期待値は `configs/data_contract.yaml`（tower: tse13、変数マッピング・QC 列）参照
4. EOL の注文リンクが失効している等で新規取得できない場合は、
   同一 Version の既存ファイルを **ハッシュ検証付きで**流用する規約です
   （流用の記録を audit/events.jsonl と manifest に残す。実装は `scripts/p1_audit.py` の
   `LOCAL_COPY_FROM` フォールバック参照）。

## 変数と時刻契約（抜粋）

- 主契約: 1 時間先平均風速 `U100 = spd_100m_tse13`（canonical U100）
- 22 親 → 44 列（`@0`, `@-1`）の R に展開（`configs/feature_dag.yaml`）
- 時刻: 稼働窓 `2016-11-29T00:00Z` 以降、開発窓 `< 2017-03-10T00:00Z`、
  確認窓 `2017-03-10T00:00Z … 2017-06-17`（v1.1 では未開封のまま提出）
- QC 後の開発窓 issue 行は 1,133 行 / 11 日（参照測定 `extras/dev_reference/` で使用した規模）

## 引用義務

データを取得して用いる場合は NCAR EOL データセット
（536.011、DOI `10.26023/ZDMJ-D1TY-FG14`）の引用をお願いします（`CITATION.cff` 参照）。
