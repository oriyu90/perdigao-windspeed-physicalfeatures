# 再現手順（F6 時点）

run_id: 2026-10-12T132705+0000_p6fail / protocol hash: 381b0422f96b7c6eda3270d843644d707701c8215bf9c061e575e87b250e952c

```bash
uv sync --locked
uv run pytest
./run_all.sh --phase P0
uv run python scripts/p2_reproduce.py   # 約2h12m、R0/R1/R2 各1回のみ
.venv/bin/python scripts/p4_calibrate_v11.py --bundle core4x1 --dforms quad,linear,regime --snrs 0.5,1.0 --conds m0,m10,mobs --reps 100 --resume  # 9チャンク逐次、計約60h、exit 4=GATE FAIL
.venv/bin/python scripts/p6_report_v11.py   # 本レポート生成（確認開封なし）
```

- 生 NetCDF（175 ファイル、527015036 bytes）は EOL 注文フォーム
  （https://data.eol.ucar.edu/cgi-bin/codiac/fgr_form/id=536.011）から注文し
  perdigao_attribution_v1.1/data/raw/ 直下に配置する（git・配布物には含めない）。
- 凍結検証：manifests/freeze_manifest.json の SHA-256 と現物 hash が一致すること。
- 確認開封の有無：runs/exposure.jsonl が存在しないこと（密封の証拠）。
- 依存は uv.lock 固定（F6 で変更なし）。乱数は master_seed=2026091501 派生。
- 完全 clean-room（空 cache からの raw 再取得＋60 h 校正再実行）は本セッションでは
  未実施。再実行監査は git clone＋hash 照合＋pytest＋表再計算の範囲で実施し、結果を handoffs/PHASE_P5.md に記録。
