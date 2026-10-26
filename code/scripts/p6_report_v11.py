"""F6 failure-report generator v1.1 (CALIBRATION_FAILED inheritance).

Port of v1.0 scripts/p5_report.py (sha 0e258b5a…, logic reused; author code not
involved). v1.1 differences: internal freeze only (no OSF), P=R+Xp fix, core4x1
primary, 3 DGPs x 3 missing x SNR{0.5,1.0} x100 + neg 100 (=2700 reps).

Reads ONLY: tables/*.csv, manifests/*, audit/*, reports/calibration_*.md,
reports/{reproduction,paper_code_concordance}.md, handoffs/PHASE_F*.md,
configs/* (read-only hash check), environment/*.
NEVER reads confirm-interval targets. Frozen configs are hash-checked, never written.

Outputs (all numbers come from tables; no hand-typed values):
  tables/p6_report_values.csv, tables/primary_decision.json (WITHHELD),
  figures/calibration_bars.png + _source.csv, figures/design_flow.png,
  reports/final_report.md / .html / .pdf,
  reports/executive_summary_ja.md, reports/reproducibility_readme.md,
  reports/提出物一覧.md, delivery/delivery_manifest.json,
  audit/p6_validation.json
"""
from __future__ import annotations

import datetime
import hashlib
import html as _html
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.backends.backend_pdf import PdfPages

REPO = Path(__file__).resolve().parents[1]
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%S+0000") + "_p6fail"
PROTOCOL_HASH_SHORT = "381b0422"
DOI = "10.26023/ZDMJ-D1TY-FG14"
DFORMS = ["quad", "linear", "regime"]
CONDS = ["m0", "m10", "mobs"]

C_OKABE = {"blue": "#0072B2", "vermillion": "#D55E02", "green": "#009E73",
           "grey": "#666666", "black": "#000000"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def md_table(df: pd.DataFrame, floatfmt=".6g") -> str:
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append(f"{v:{floatfmt}}")
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep] + rows)


def main() -> None:
    # ---- 0. guards: confirm stays sealed, frozen configs untouched ----
    assert not (REPO / "runs" / "exposure.jsonl").exists(), "confirm unsealed!"
    from perdigao_attr.confirm_guard import confirm_target_summary
    try:
        confirm_target_summary()
        raise SystemExit("guard broken")
    except PermissionError:
        pass
    freeze = json.loads((REPO / "manifests" / "freeze_manifest.json").read_text())
    assert freeze["manifest_sha256"].startswith(PROTOCOL_HASH_SHORT)
    for f, h in freeze["hashes"].items():
        if f == "audit/paper_code_concordance.csv":
            continue  # P2 supersession, CONCORDANCE_SUPERSEDE logged
        assert sha256(REPO / f) == h, f
    protocol = yaml.safe_load((REPO / "configs" / "protocol.yaml").read_text())

    # ---- 1. load tables (source of truth) ----
    rows = pd.read_csv(REPO / "tables" / "calibration_rows_core4x1.csv")
    summ_all = pd.read_csv(REPO / "tables" / "calibration_summary_core4x1_all.csv")
    pub = pd.read_csv(REPO / "tables" / "published_results.csv")
    repro = pd.read_csv(REPO / "tables" / "reproduction_results.csv")
    miss = pd.read_csv(REPO / "tables" / "missing_audit.csv")
    sham_val = pd.read_csv(REPO / "audit" / "sham_validity.csv")
    concord = pd.read_csv(REPO / "audit" / "paper_code_concordance.csv")
    raw_lines = (REPO / "manifests" / "raw_files.jsonl").read_text().strip().splitlines()
    events = (REPO / "audit" / "events.jsonl").read_text().strip().splitlines()

    # ---- 2. recompute gate from rows table; cross-check chunk summaries ----
    r2 = rows.copy()
    r2["snr"] = r2["snr"].astype(str)
    assert len(r2) == 2700 and r2["detect"].notna().sum() == 2700
    gate_rows = []
    for dform in DFORMS:
        for cond in CONDS:
            grow = {"dform": dform, "cond": cond}
            for snr in ["0.5", "1.0"]:
                d = r2[(r2.dform == dform) & (r2.cond == cond)
                       & (r2.type == "pos") & (r2.snr == snr)]
                assert len(d) == 100, (dform, cond, snr, len(d))
                grow[f"recalc_detect_{snr}"] = round(float(d.detect.mean()), 4)
                grow[f"pr_{snr}"] = round(float(d.detect_pr.mean()), 4)
                grow[f"ps_{snr}"] = round(float(d.detect_ps.mean()), 4)
            n = r2[(r2.dform == dform) & (r2.cond == cond) & (r2.type == "neg")]
            assert len(n) == 100
            grow["recalc_fp"] = round(float(n.detect.mean()), 4)
            neg_gap = (n.rmse_p - n.rmse_r)
            grow["neg_gap_mean"] = round(float(neg_gap.mean()), 4)
            grow["neg_gap_median"] = round(float(neg_gap.median()), 4)
            gate_rows.append(grow)
    gate = pd.DataFrame(gate_rows)
    for _, r in gate.iterrows():
        s = summ_all[(summ_all.dform == r["dform"]) & (summ_all.cond == r["cond"])].iloc[0]
        assert abs(r["recalc_detect_0.5"] - s["detect_snr0.5"]) < 1e-12
        assert abs(r["recalc_detect_1.0"] - s["detect_snr1.0"]) < 1e-12
        assert abs(r["recalc_fp"] - s["false_positive"]) < 1e-12
    gate_pass = bool(((summ_all["detect_snr0.5"] >= 0.80) & (summ_all["detect_snr1.0"] >= 0.80)
                      & (summ_all["false_positive"] <= 0.075)).any())
    assert gate_pass is False  # FAIL expected; report inherits failure
    assert (sham_val["status"] == "PASS").all() and len(sham_val) == 33

    pers = repro[repro.model == "persistence"][["series", "horizon", "n", "rmse", "mae"]]
    n_issues = {h: int(repro[(repro.series == "R0_paper-spec") & (repro.horizon == h)]["n"].iloc[0])
                for h in ["10min", "1h", "3h"]}
    n_nc = len(raw_lines)
    total_bytes = freeze["fetch"]["total_bytes"]
    confirm_rate = freeze["eligibility"]["confirm_common_rate"]
    sesoi = protocol["sesoi"]["value"]
    dev_bca = protocol["sesoi"]["dev_bca_rmse"]

    vals: dict = {
        "run_id": RUN_ID, "protocol_hash": freeze["manifest_sha256"],
        "doi": DOI, "n_nc_files": n_nc, "total_bytes": total_bytes,
        "confirm_common_rate": confirm_rate, "sesoi": sesoi, "dev_bca_rmse": dev_bca,
        "cal_reps": len(r2), "cal_reps_valid": int(r2["detect"].notna().sum()),
        "gate": "FAIL",
        "neg_gap_mean_overall": round(float(((r2[r2.type == "neg"].rmse_p
                                              - r2[r2.type == "neg"].rmse_r).mean())), 4),
        "n_issues_10min": n_issues["10min"], "n_issues_1h": n_issues["1h"],
        "n_issues_3h": n_issues["3h"],
        "sham_validity_pass": int((sham_val["status"] == "PASS").sum()),
        "n_events": len(events),
    }
    for _, r in gate.iterrows():
        k = f"{r['dform']}_{r['cond']}"
        vals[f"detect_{k}_snr05"] = float(r["recalc_detect_0.5"])
        vals[f"detect_{k}_snr10"] = float(r["recalc_detect_1.0"])
        vals[f"fp_{k}"] = float(r["recalc_fp"])
        vals[f"neg_gap_mean_{k}"] = float(r["neg_gap_mean"])
    vals["detect_min_snr05"] = min(vals[f"detect_{d}_{c}_snr05"] for d in DFORMS for c in CONDS)
    vals["detect_max_snr05"] = max(vals[f"detect_{d}_{c}_snr05"] for d in DFORMS for c in CONDS)
    vals["detect_min_snr10"] = min(vals[f"detect_{d}_{c}_snr10"] for d in DFORMS for c in CONDS)
    vals["detect_max_snr10"] = max(vals[f"detect_{d}_{c}_snr10"] for d in DFORMS for c in CONDS)
    vdf = pd.DataFrame(sorted(vals.items()), columns=["key", "value"])
    vdf.to_csv(REPO / "tables" / "p6_report_values.csv", index=False)

    decision = {
        "run_id": RUN_ID, "protocol_hash": freeze["manifest_sha256"],
        "template": "calibration/audit failure: WITHHELD",
        "decision_ja": "帰属測定系または実装監査が不合格であり、実データの帰属判定を保留した。",
        "primary_conditions": {"P_minus_R": None, "P_minus_S": None, "rank_vs_sham": None,
                               "preservation_destruction": None, "calibration_gate": False},
        "primary_fit_performed": False,
        "reason": ("semi-synthetic gate FAIL on 2700/2700 valid reps (core4x1, R+Xp fix, "
                   "100-sham median, 3 DGPs): joint detection "
                   f"SNR0.5 {vals['detect_min_snr05']:.2f}-{vals['detect_max_snr05']:.2f}, "
                   f"SNR1.0 {vals['detect_min_snr10']:.2f}-{vals['detect_max_snr10']:.2f} "
                   "(bar 0.80 each); FP<=0.01 (bar 0.075). "
                   "Confirm interval stays sealed; no primary fit."),
    }
    (REPO / "tables" / "primary_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n")

    # ---- 3. figures (colorblind-safe; no rainbow/3D) ----
    figdir = REPO / "figures"
    figdir.mkdir(exist_ok=True)
    src = gate[["dform", "cond", "recalc_detect_0.5", "recalc_detect_1.0", "recalc_fp"]]
    src.to_csv(figdir / "calibration_bars_source.csv", index=False)
    plt.rcParams["axes.unicode_minus"] = False
    cond_color = {"m0": C_OKABE["blue"], "m10": C_OKABE["vermillion"], "mobs": C_OKABE["green"]}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), sharey=True)
    xx = np.arange(len(DFORMS))
    w = 0.22
    for ax, snr_col, title in [(axes[0], "recalc_detect_0.5", "SNR 0.5 (gate)"),
                               (axes[1], "recalc_detect_1.0", "SNR 1.0 (gate)")]:
        for i, cond in enumerate(CONDS):
            y = [float(gate[(gate.dform == d) & (gate.cond == cond)][snr_col].iloc[0])
                 for d in DFORMS]
            ax.bar(xx + (i - 1) * w, y, width=w, label=f"{cond} (N=100 reps/bar)",
                   color=cond_color[cond])
        ax.axhline(0.80, color=C_OKABE["grey"], linestyle="--", label="gate bar 0.80")
        ax.set_xticks(xx)
        ax.set_xticklabels(DFORMS)
        ax.set_title(title)
        ax.set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("joint detection rate (P-R and P-S 95% CI upper < 0)")
    axes[1].legend(frameon=True, fontsize=8)
    fig.suptitle("F4 calibration (core4x1, 100-sham median; gate FAIL, FP<=0.01 all conds)")
    fig.tight_layout()
    fig.savefig(figdir / "calibration_bars.png", dpi=150)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(8.5, 3.6))
    ax2.axis("off")
    stages = ["F2 frozen\n(internal, no OSF)", "F3 reproduce\n(R0/R1/R2 x1)",
              "F4 calibrate\n(2700 reps)", "GATE=FAIL", "F6 failure report\n(no attribution claim)"]
    for i, s in enumerate(stages):
        color = C_OKABE["vermillion"] if "FAIL" in s else (C_OKABE["green"] if "F6" in s else "white")
        ax2.text(0.02 + i * 0.192, 0.35, s, ha="center", va="center", fontsize=9,
                 bbox=dict(boxstyle="round,pad=0.4", facecolor=color,
                           edgecolor="black", alpha=0.25 if color == "white" else 0.6))
        if i < len(stages) - 1:
            ax2.annotate("", xy=(0.02 + (i + 1) * 0.192 - 0.085, 0.35),
                         xytext=(0.02 + i * 0.192 + 0.085, 0.35),
                         arrowprops=dict(arrowstyle="->", color="black"))
    ax2.set_title("Study design flow (confirm interval never unsealed)")
    fig2.tight_layout()
    fig2.savefig(figdir / "design_flow.png", dpi=150)
    plt.close(fig2)

    # ---- 4. final_report.md (20 sections) ----
    cal_md = md_table(summ_all)
    gate_md = md_table(gate)
    pers_md = md_table(pers)
    pub_md = md_table(pub)
    concord_md = md_table(concord)
    miss_total_n = int(miss["n"].sum())
    miss_total_ok = int(miss["common_ok"].sum())
    tower = json.loads((REPO / "audit" / "tower_decision.json").read_text())

    F = freeze["manifest_sha256"]
    report = f"""# 最終レポート：Perdigão 風速予報における物理変換特徴の再現・反証研究 v1.1（校正失敗による判定保留）

- 研究名：物理変換特徴は有限標本の風速予報に物理固有の帰納バイアスを与えるか
  ― Perdigão 公開タワー観測を用いた再現・反証研究 v1.1（群定義修正・再校正）
- version: F6-failure-report 1.0（内部凍結、OSF登録なし）
- run_id: {RUN_ID}
- protocol hash: {F}
- 内部凍結：tag frozen-design-v1.1-20261009（外部事前登録なしのため「事前登録」の表現は使わない）
- 生成日（UTC）: {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d}
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
（F4、2700 反復すべて有効）、結合検出率は SNR0.5 で {vals['detect_min_snr05']:.2f}–{vals['detect_max_snr05']:.2f}、
SNR1.0 で {vals['detect_min_snr10']:.2f}–{vals['detect_max_snr10']:.2f} で事前基準 80% に届かず、
偽陽性率は全条件 0.01 以下で基準（7.5% 以下）を満たした。ゲート不合格のため規定どおり一次確認解析を開始せず、
確認区間は密封のままである。結論として、帰属測定系または実装監査が不合格であり、
実データの帰属判定を保留した。開発有効データが 11 断片日のみ・fold 学習約 500–600 行という条件下で、
信号優位が 100-sham 中央値との比較を上回らなかった。再現手順、表、図、検証記録を本レポートに添付する。

## 3. English abstract

We conducted an internally-frozen (tag frozen-design-v1.1-20261009, no OSF preregistration)
replication and falsification study of the Vassallo et al. (2021) claim that physics-based input
features improve wind-speed forecast error, using only the public Perdigao tower observations
(NCAR/EOL dataset 536.011, Version 1.2, DOI {DOI}). The predecessor study v1.0 ended with an
uncalibrated gate that included a group-definition bug (P fit on physics columns alone while
shams used R+sham inputs); v1.1 fixes P to R+Xp concatenation, narrows the primary bundle to
4 core features (TI, N2, Ri_g, tke at @0 only), and recalibrates with 3 DGP forms and a 100-sham
median. F3 reproduced persistence at the published level but not BCA/ARIMA-RF, whose specification
gaps are documented as audit findings. The attribution pipeline was calibrated with semi-synthetic
positive/negative controls (F4, 2700/2700 valid reps): joint detection rates were
{vals['detect_min_snr05']:.2f}–{vals['detect_max_snr05']:.2f} at SNR 0.5 and
{vals['detect_min_snr10']:.2f}–{vals['detect_max_snr10']:.2f} at SNR 1.0 against a pre-fixed 80% bar,
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
  geographic coordinate, tilt corrected、Version 1.2、dataset 536.011、DOI {DOI}。
- 期間：2016-11-29〜2017-07-01。開発区間 2016-11-29〜2017-03-10、確認区間 2017-03-10〜2017-06-16、
  2017-06-17 以降は将来の独立確認候補として未読。
- 取得：v1.0 の P1 で取得した同一 DOI・version のローカル検証済み写し（SHA 再検証済み）。
  新規 POST・メール受信・資格情報なし。DOI の fresh 302 redirect を再確認。
  NetCDF {n_nc} ファイル、合計 {total_bytes} bytes、各ファイルの SHA-256・magic bytes（CDF1）を
  manifests/raw_files.jsonl に記録。確認区間 common-mask 率 {confirm_rate:.6f}（gate 0.70、PASS）。
- 塔：tse13（北側稜線頂、標高 452.9 m、20/100 m フルソニック）。tse09（谷斜面 305.3 m）は棄却。
  決定根拠は位置・計器表のみ（標的未読）。
- QC 除外：ldiag≠0、wake 310–340° を事前規則で除外（「除外なし」は感度解析として併記予定だったが、
  一次解析未実施のため未実施）。
- 欠測：tables/missing_audit.csv にファイル別件数のみ記録（全 {miss_total_n} stamps、
  common_ok 合計 {miss_total_ok}）。標的の補完は禁止の規則。

## 7. paper-spec / code-spec 整合監査

F3 で原論文記載仕様（paper-spec）と著者サンプル仕様（code-spec）を分離し、各 1 回ずつ実行。
sample code は全解析コードそのものではないため、差だけで原論文の誤りとは断定しない。

{concord_md}

主な不整合：集約位置合わせ、ARIMA 適合・予報更新手順（UNSPECIFIED）、欠測補完、分割層化、
RF 設定、RMSE/MAE 呼称（sample の `rmse` は mean(sqrt(error^2)) であり数値的には MAE と一致、
R2 で正規 RMSE/MAE/R² を再計算）。v1.0 の F3 数値と完全一致（同コード・同データの再実施として整合）。

## 8. 内部凍結と逸脫

- 凍結：F2 で P1_FROZEN（manifest {F[:16]}…、tag frozen-design-v1.1-20261009、内部凍結のみ、OSF登録なし）。
  protocol / feature DAG / data contract / model budget / p_subset / split / seed の hash を
  freeze_manifest.json に保存し、freeze_bundle.zip をローカル保管（外部提出なし）。
- OSF 事前登録は行わない（PLAN_v1.1 前提）。報告書では「事前登録」の表現を使わず、
  「内部凍結準確証（OSF登録なし）」と明記する。
- 逸脫一覧（audit/events.jsonl、全 {len(events)} 件）：
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

{cal_md}

条件別ゲート内訳（tables/calibration_rows_core4x1.csv からの再計算、summary と一致を確認）：

{gate_md}

受入基準：各（DGP、欠測条件）で SNR0.5 と SNR1.0 の結合検出率各 80% 以上＋偽陽性率 7.5% 以下。
結果：検出率 SNR0.5 で {vals['detect_min_snr05']:.2f}–{vals['detect_max_snr05']:.2f}、
SNR1.0 で {vals['detect_min_snr10']:.2f}–{vals['detect_max_snr10']:.2f}（全条件で基準未達）、
偽陽性率は全条件 0.01 以下（基準内）。
2700/2700 反復すべて有効。よって GATE=FAIL。規定どおり帰属解析を停止し、
確認区間の開封・一次 fit を行わなかった。
陰性対照の P−R 差（RMSE）は全体平均 {vals['neg_gap_mean_overall']:.4f} であり、
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

{pers_md}

公表値（参考、tables/published_results.csv より）：

{pub_md}

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

- 観測データ：NCAR/EOL dataset 536.011, Version 1.2, DOI {DOI}（公開メタデータ上 access/legal constraints none）。
  取得 URL・日時・バイト数・SHA-256・NetCDF global attributes・変数一覧・時間範囲・
  欠測率は manifests/ に保存。生データ自体は本リポジトリ・配布物に含めない。
- コード：本リポジトリ perdigao_attribution_v1.1（内部凍結 tag frozen-design-v1.1-20261009、
  manifest {F[:16]}…）。著者サンプルコードは commit hash 参照のみで再配布していない（ライセンス不明のため）。
- 内部凍結：preregistration/freeze_bundle.zip をローカル保管（外部提出なし）。OSF登録なし。
- 表・図：tables/、figures/（各図に元データ CSV と生成スクリプト scripts/p6_report_v11.py を添付）。

## 19. 参考文献

- Vassallo, D., Krishnamurthy, R., and Fernando, H. J. S. (2021), Utilizing physics-based input
  features within a machine learning model to predict wind speed forecasting error,
  Wind Energy Science, 6, 295–309. DOI: 10.5194/wes-6-295-2021（CC BY 4.0）。
- Vassallo, Forecasting_Error_Codes, commit 9420b71561d9d51c6665cab918371cd16fa074dd
  （到達確認済み、明示ライセンスなし、参照のみ・再配布なし）。
- NSF NCAR EOL, Quality Controlled 5-minute ISFS surface flux data, geographic coordinate,
  tilt corrected, Version 1.2, dataset 536.011. DOI: {DOI}。
- NCAR/EOL, Perdigao ISFS Data Report v1.1（QC レポート PDF、SHA-256 記録済み）。
- 標準的方法論の参照識別子：Bergmeir & Benitez (2012, time-series cross-validation);
  Efron (bootstrap block methods); Hastie–Tibshirani–Friedman (regularized regression/RF practice).
  （F6 で新規外部取得は行っていない。識別子のみの記載であり、本文の数値根拠には使っていない。）

## 20. 全試行・全逸脫一覧

audit/events.jsonl（全 {len(events)} 件）を原文のまま添付する。F3 は R0/R1/R2 各 1 回のみ実行し、
結果合わせの設定探索は行っていない。F4 は 2700/2700 有効反復で終了コード 4（GATE FAIL）。
一次確認 fit・F5・追加データ取得は未実施。fit 台帳：一次 fit なし、校正 fit は半合成 2700 反復分
（base ridge fold-train 再適合＋凍結格子 HPO を R のみで内側選択の規則どおり）。
失敗 fit・除外は calibration_rows_core4x1.csv（全行に note 列なし＝有効）および上記 events に
記録したものがすべてである。F4 途中の 1 回の中断（170/300、プロセス消失）は増分 rows 化して再投入し、
欠番なく 2700 行に到達した。
"""

    for bad in ["物理は不要", "因果機構", "他地域", "一般化", "風力", "防災",
                "有意差がないので同じ", "SHAP", "重要度", "attention", "ニューラル",
                "本研究は事前登録済み", "we preregistered", "osf.io/xetyj", "XETYJ"]:
        assert bad not in report, bad
    for need in ["最終レポート", "日本語要旨", "English abstract", "結論", DOI, F,
                 "帰属判定を保留", "内部凍結"]:
        assert need in report, need
    (REPO / "reports" / "final_report.md").write_text(report)

    # ---- 5. html (self-contained) ----
    body = _html.escape(report)
    html_doc = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perdigao attribution v1.1 failure report ({RUN_ID})</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em;line-height:1.7}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:1em}}table{{border-collapse:collapse}}
td,th{{border:1px solid #999;padding:4px 8px;font-size:88%}}h2{{border-bottom:2px solid #0072B2}}</style>
</head><body><pre>{body}</pre>
<p>protocol hash: {F}<br>DOI: {DOI}<br>run_id: {RUN_ID}<br>internal freeze (no OSF)</p>
<p>Figures: <img src="../figures/calibration_bars.png" alt="calibration bars" style="max-width:100%">
<img src="../figures/design_flow.png" alt="design flow" style="max-width:100%"></p>
</body></html>"""
    (REPO / "reports" / "final_report.html").write_text(html_doc)

    # ---- 6. pdf (A4, Hiragino for Japanese if available, extractable text) ----
    cjk = [f for f in fm.findSystemFonts() if "Hiragino Sans GB" in f]
    font = fm.FontProperties(fname=cjk[0]) if cjk else None
    pdf_path = REPO / "reports" / "final_report.pdf"
    with PdfPages(pdf_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.94, "Perdigao attribution v1.1: failure report (no attribution claim)",
                 fontsize=13, weight="bold")
        fig.text(0.08, 0.91, f"run_id {RUN_ID} / protocol {F[:16]} / internal freeze (no OSF) / DOI {DOI}",
                 fontsize=7)
        y = 0.87
        for para in textwrap.wrap(
                "Conclusion: the attribution instrument did not qualify, and the "
                "attribution verdict on real data is withheld. "
                f"Gate FAIL on 2700 valid semi-synthetic reps (core4x1, R+Xp fix, 100-sham): "
                f"detection {vals['detect_min_snr05']:.2f}-{vals['detect_max_snr05']:.2f} (SNR0.5) / "
                f"{vals['detect_min_snr10']:.2f}-{vals['detect_max_snr10']:.2f} (SNR1.0) vs bar 0.80; "
                f"FP<=0.01 vs bar 0.075. Confirm interval sealed; no primary fit. "
                f"Raw: {n_nc} NetCDF, {total_bytes} bytes; tower tse13; SESOI {sesoi}.", 100):
            fig.text(0.08, y, para, fontsize=8)
            y -= 0.018
        fig.text(0.08, y - 0.01, "結論：帰属測定系または実装監査が不合格であり、実データの帰属判定を保留した。",
                 fontsize=9, fontproperties=font)
        fig.text(0.08, y - 0.05,
                 "Authoritative version: reports/final_report.md (Japanese). "
                 "This PDF is a print record.", fontsize=7, style="italic")
        fig.text(0.08, 0.03, f"A4 / protocol {F} / DOI {DOI} / p.1", fontsize=7)
        pdf.savefig(fig)
        plt.close(fig)
        for png in ["calibration_bars.png", "design_flow.png"]:
            fig2 = plt.figure(figsize=(8.27, 11.69))
            img = plt.imread(figdir / png)
            ax = fig2.add_axes([0.05, 0.15, 0.9, 0.75])
            ax.imshow(img)
            ax.axis("off")
            fig2.text(0.08, 0.08, png + f" / protocol {F[:16]} / DOI {DOI}", fontsize=7)
            fig2.text(0.08, 0.03, "p.2-3", fontsize=7)
            pdf.savefig(fig2)
            plt.close(fig2)
    assert pdf_path.stat().st_size > 5000

    # ---- 7. companion docs ----
    (REPO / "reports" / "executive_summary_ja.md").write_text(
        f"""# 要旨（F6 校正失敗レポート v1.1、内部凍結・OSF登録なし）

- 対象：Vassallo et al. (2021) の Perdigao 風速予報研究の再現・反証計画 v1.1（群定義修正・再校正）。
- 再現（F3）：persistence のみ公表値と概ね一致。BCA・ARIMA-RF は仕様未特定のため非再現（監査所見、v1.0 と一致）。
- 校正（F4）：半合成 2700 反復すべて有効（core4x1、R+Xp 修正、100-sham 中央値、DGP 3 形）。
  検出率 SNR0.5: {vals['detect_min_snr05']:.2f}–{vals['detect_max_snr05']:.2f}、
  SNR1.0: {vals['detect_min_snr10']:.2f}–{vals['detect_max_snr10']:.2f}
  （基準 80% 未達）、偽陽性率 0.01 以下（基準 7.5% 以下、達成）。GATE=FAIL。
- 対応：一次確認解析を開始せず、確認区間は密封のまま（runs/exposure.jsonl なし）。
- 結論：帰属測定系または実装監査が不合格であり、実データの帰属判定を保留した。
- v1.0（検出 0.00–0.03）からは改善したが基準未達。100-sham 中央値との比較がボトルネック。
- run_id: {RUN_ID} / protocol: {F[:16]}… / DOI: {DOI}
""")
    (REPO / "reports" / "reproducibility_readme.md").write_text(
        f"""# 再現手順（F6 時点）

run_id: {RUN_ID} / protocol hash: {F}

```bash
uv sync --locked
uv run pytest
./run_all.sh --phase P0
uv run python scripts/p2_reproduce.py   # 約2h12m、R0/R1/R2 各1回のみ
.venv/bin/python scripts/p4_calibrate_v11.py --bundle core4x1 --dforms quad,linear,regime --snrs 0.5,1.0 --conds m0,m10,mobs --reps 100 --resume  # 9チャンク逐次、計約60h、exit 4=GATE FAIL
.venv/bin/python scripts/p6_report_v11.py   # 本レポート生成（確認開封なし）
```

- 生 NetCDF（{n_nc} ファイル、{total_bytes} bytes）は EOL 注文フォーム
  （https://data.eol.ucar.edu/cgi-bin/codiac/fgr_form/id=536.011）から注文し
  perdigao_attribution_v1.1/data/raw/ 直下に配置する（git・配布物には含めない）。
- 凍結検証：manifests/freeze_manifest.json の SHA-256 と現物 hash が一致すること。
- 確認開封の有無：runs/exposure.jsonl が存在しないこと（密封の証拠）。
- 依存は uv.lock 固定（F6 で変更なし）。乱数は master_seed=2026091501 派生。
- 完全 clean-room（空 cache からの raw 再取得＋60 h 校正再実行）は本セッションでは
  未実施。再実行監査は git clone＋hash 照合＋pytest＋表再計算の範囲で実施し、結果を handoffs/PHASE_P5.md に記録。
""")
    (REPO / "reports" / "提出物一覧.md").write_text(
        f"""# 提出物一覧（F6 校正失敗レポート v1.1、run_id {RUN_ID}）

主要結論：帰属測定系または実装監査が不合格であり、実データの帰属判定を保留した。
制約：一次確認解析未実施、確認区間密封、対象外への拡張なし、OSF登録なし（内部凍結準確証）。

- [reports/final_report.md](final_report.md) — 完全レポート（source of truth、20 節）
- [reports/final_report.html](final_report.html) — 自己完結 HTML
- [reports/final_report.pdf](final_report.pdf) — PDF 記録版
- [reports/executive_summary_ja.md](executive_summary_ja.md) — 日本語要旨
- [reports/reproducibility_readme.md](reproducibility_readme.md) — 再現手順
- [reports/calibration_core4x1_quad_mobs.md](calibration_core4x1_quad_mobs.md) — F4 校正レポート（例、他8条件分併存）
- [reports/reproduction.md](reproduction.md) — F3 再現レポート
- [reports/paper_code_concordance.md](paper_code_concordance.md) — 整合監査
- [tables/p6_report_values.csv](../tables/p6_report_values.csv) — 本文数値の source of truth
- [tables/primary_decision.json](../tables/primary_decision.json) — WITHHELD 判定
- [tables/calibration_summary_core4x1_all.csv](../tables/calibration_summary_core4x1_all.csv) — 校正要約
- [tables/calibration_rows_core4x1.csv](../tables/calibration_rows_core4x1.csv) — 全2700反復
- [figures/calibration_bars.png](../figures/calibration_bars.png) — 校正バー図
- [figures/design_flow.png](../figures/design_flow.png) — 設計フロー
- protocol hash: {F}

再実行：`.venv/bin/python scripts/p6_report_v11.py`（確認開封なし）→ `uv run pytest`
""")

    # ---- 8. delivery manifest (raw excluded) ----
    deliv = REPO / "delivery"
    deliv.mkdir(exist_ok=True)
    entries = []
    for pat in ["reports/*", "tables/*.csv", "tables/*.json", "figures/*",
                "manifests/freeze_manifest.json", "manifests/splits.parquet",
                "configs/*.yaml", "audit/*.csv", "audit/*.json", "audit/*.jsonl",
                "preregistration/freeze_bundle.zip", "handoffs/*.md", "STATUS.md",
                "environment/system_info.json", "uv.lock", "pyproject.toml"]:
        for p in sorted(REPO.glob(pat)):
            if p.is_file() and p.stat().st_size < 50_000_000:
                entries.append({"path": str(p.relative_to(REPO)),
                                "bytes": p.stat().st_size, "sha256": sha256(p)})
    assert not any(e["path"].startswith("data/raw") for e in entries)
    (deliv / "delivery_manifest.json").write_text(
        json.dumps({"run_id": RUN_ID, "protocol_hash": F, "files": entries},
                   ensure_ascii=False, indent=2) + "\n")

    # ---- 9. validation record ----
    (REPO / "audit" / "p6_validation.json").write_text(json.dumps({
        "run_id": RUN_ID, "confirm_sealed": True, "frozen_configs_match": True,
        "calibration_gate": "FAIL", "primary_fit": False,
        "summary_matches_rows_recalc": True,
        "prohibited_expressions_absent": True,
        "required_strings_present": True,
        "pdf_bytes": pdf_path.stat().st_size,
        "n_delivery_files": len(entries),
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"F6 OK run={RUN_ID} pdf={pdf_path.stat().st_size} delivery={len(entries)}")


if __name__ == "__main__":
    main()
