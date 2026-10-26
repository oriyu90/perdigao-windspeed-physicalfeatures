"""P2 reproduction tests (03 mandatory). Single-run outputs, no tuning."""
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]


# Public-release copy: run artifacts live under ../results and the revised
# concordance CSV under ../docs/provenance (frozen-repo layout keeps them in
# REPO/tables|reports|audit). The frozen layout wins when it exists (e.g. after
# running the pipeline inside this copy).
def _first_exists(*candidates: Path) -> Path:
    for p in candidates:
        if p.exists():
            return p
    return candidates[-1]


TABLES = _first_exists(REPO / "tables", REPO.parent / "results" / "tables")
REPORTS = _first_exists(REPO / "reports", REPO.parent / "results" / "reports")
AUDIT = _first_exists(REPO / "audit", REPO.parent / "docs" / "provenance")


def test_metric_recompute_consistent():
    from perdigao_attr.metrics import legacy_labelled_rmse, mae, rmse

    rep = pd.read_csv(TABLES / "reproduction_results.csv")
    # R2 rows must match the corresponding R0/R1 full rows (same predictions)
    for h in ["10min", "1h", "3h"]:
        r0 = rep[(rep.series == "R0_paper-spec") & (rep.horizon == h) & (rep.model == "ARIMA-RF_full")].iloc[0]
        r2 = rep[(rep.series == "R2_corrected") & (rep.horizon == h) & (rep.model == "R0_full")].iloc[0]
        assert r0.rmse == r2.rmse and r0.mae == r2.mae
        r1 = rep[(rep.series == "R1_code-spec") & (rep.horizon == h) & (rep.model == "ARIMA-RF_full")].iloc[0]
        r2b = rep[(rep.series == "R2_corrected") & (rep.horizon == h) & (rep.model == "R1_full")].iloc[0]
        assert r1.rmse == r2b.rmse and r1.mae == r2b.mae
    # metric definitions hold on a fixture vector
    assert rmse([0, 3, 4]) != mae([0, 3, 4])
    assert legacy_labelled_rmse([0, 3, 4]) == mae([0, 3, 4])


def test_legacy_mislabel_detected():
    rep = pd.read_csv(TABLES / "reproduction_results.csv")
    # legacy-labelled column equals true MAE for BCA rows by construction
    bca = rep[rep.model == "BCA"]
    assert (bca["legacy_labelled_rmse"] == bca["mae"]).all()
    # and for full rows legacy != rmse in general (misnomer would misreport)
    full = rep[rep.model == "ARIMA-RF_full"]
    assert (full["legacy_labelled_rmse"] != full["rmse"]).all()


def test_reproduction_blocked_from_confirm():
    from perdigao_attr import confirm_guard

    rep = pd.read_csv(TABLES / "reproduction_results.csv")
    assert bool(rep["reproduction_only"].all())
    # confirm interval stays sealed for primary analysis
    assert not confirm_guard.is_unsealed()
    try:
        confirm_guard.require_unsealed()
    except PermissionError:
        return
    raise AssertionError("confirm guard must stay sealed after P2")


def test_future_aware_columns_excluded_from_main():
    # reproduction imputation is future-aware; main pipeline must not exist yet
    assert not list((REPO / "data" / "processed").glob("*.parquet"))
    assert not list((REPO / "data" / "interim").glob("*.parquet"))
    md = (REPORTS / "reproduction.md").read_text()
    assert "reproduction_only=true" in md
    assert "MUST NOT feed P3/P4" in md


def test_horizon_snapshot_counts():
    rep = pd.read_csv(TABLES / "reproduction_results.csv")
    r0 = rep[(rep.series == "R0_paper-spec") & (rep.model == "ARIMA-RF_full")]
    assert set(r0.horizon) == {"10min", "1h", "3h"}
    for _, row in r0.iterrows():
        # >28000-paper-scale minus window edges; 3h loses most
        assert 27000 < int(row.n) <= 28512, row.to_dict()
    pub = pd.read_csv(TABLES / "published_results.csv")
    assert set(pub.horizon) >= {"10min", "1h", "3h"}
    conc = pd.read_csv(AUDIT / "paper_code_concordance.csv")
    required = {"data_period", "tower_height_vars", "aggregation_alignment",
                "arima_fit_forecast_update", "missing_imputation",
                "split_stratification", "lag_horizon", "rf_config",
                "feature_selection", "rmse_formula", "mae_formula", "seed"}
    assert required <= set(conc.item)
    assert set(conc.verdict) <= {"MATCH", "CONFLICT", "PAPER_ONLY", "CODE_ONLY", "UNSPECIFIED"}
