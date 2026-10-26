# perdigao_attribution_v1.1（公開コピー・匿名化版）

新研究 v1.1: 現行研究 v1.0 (`CALIBRATION_FAILED`、確認密封) の再実施 (re-run) + 内部凍結による修正再実行。

- 問い・データ・判定5条件は現行踏襲。P群定義バグ (`P=Xp24` 単独fit) を `P=R+Xp` に修正する (一次 core4 = R44+4 = 48 total)。
- OSF登録は行わない。内部凍結 (`frozen-design-v1.1-20261009` + `freeze_manifest.json` + freeze bundle ローカル保管) のみ。「内部凍結 (OSF登録なし)」と明記する。
- 現行研究 v1.0 リポジトリは本公開に含めない（読出し専用の契約は凍結本体側で維持）。
- 文書: 研究計画書 `../docs/plan_v1.1.md` + 実行手順 `../docs/guides/`（00–05・07–08 の 8 編。06・09 は非公開）。
- 実行状況の要点は `../docs/provenance/status_snapshot.md`（凍結本体 `STATUS.md` のコピー）。

## 再現

```bash
uv sync --locked
uv run python -m pytest tests/ -q      # 18/18 PASS（同梱成果物は ../results、整合CSVは ../docs/provenance から照合）
```

`run_all.sh` は F1 時点の fail-closed 雛形です。`./run_all.sh --frozen --from-raw` は
**仕様どおり終了コード 3 で停止します**（凍結設計の維持が目的。全フェーズ実装は `scripts/` 側）。

段階実行（data/raw を整えた後。データ取得は data/README.md）:
`scripts/p1_audit.py` (F2 データ検証・凍結) → `scripts/p2_reproduce.py` (F3 再現)
→ `scripts/p4_calibrate_v11.py` (F4 校正ゲート)。
`scripts/p6_report_v11.py` (F6 報告再生成) は凍結レイアウトの `manifests/freeze_manifest.json`
を要求します（本コピーには同梱しないため、詳細は `../docs/provenance/provenance.md` の errata 参照）。
凍結済み設計のまま動かすため `--frozen` を外すと abort する（仕様どおり）。

凍結マニフェスト・公開コピーでの改変内容は `../docs/provenance/provenance.md` を参照。
