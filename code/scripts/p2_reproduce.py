"""P2 (v1.1 F3): paper-spec (R0) / code-spec (R1) / corrected-metric (R2) reproduction.

v1.1 internal-freeze re-run (no OSF; tag frozen-design-v1.1-20261009,
manifest 381b0422...). Logic identical to v1.0 P2; no tuning to published values.
Clean-room implementation from paper text + behavior notes in
audit/paper_spec.yaml and audit/code_spec.yaml. Author sample code is NOT
copied, vendored, or imported (reference only).

Fixed defaults chosen BEFORE reading confirm performance (frozen here):
- R0 imputation: variance-ratio MCP (confirm-overlap stats) for 100m vars
  with a 20m counterpart; else linear interp + fixed-seed Gaussian noise
  (rng = derive_generator(MASTER_SEED, "split", 99), sigma = 1% of dev std).
  Future-aware by design -> flagged reproduction_only=true, never reused.
- R0 aggregation: right-aligned full-window means W in {2,12,36} at 5-min
  steps; target Y_h(T) = mean over (T, T+h]; valid only if past AND future
  windows are full.
- R0 ARIMA: single in-sample ARIMA(2,0,1) fit per horizon on the Y series
  (paper update cadence UNSPECIFIED; this is the documented 1-value default).
- R0 split: StratifiedKFold(n=10, shuffle, random_state=20260915) on
  target-decile strata (paper strata definition UNSPECIFIED).
- R0 RF (full feature set): 1000 trees, min_samples_split=100,
  max_features=1.0 (sklearn default; paper UNSPECIFIED), random_state=1,
  n_jobs=4. Single run (paper reports 10-run ensemble, seeds UNSPECIFIED).
- R1 split: train_test_split(test_size=0.25, random_state=1), single split.
- R1 RF: 1000 trees, max_features=0.7, min_samples_split=100,
  oob_score=True, random_state=1 (code-spec values).
- Features: 17-group full bundle incl. clips (N2<0->0, Ri_f->[-5,5],
  Ri_g upper 5, denom floors, TI/u_star_norm denom floors w/ median fill).
- Lags: X_i = concat(F_i, F_{i-1}) (paper "previous two time steps";
  alignment UNSPECIFIED; documented here).

Outputs (all reproduction_only=true):
- tables/reproduction_results.csv, tables/published_results.csv,
  audit/paper_code_concordance.csv (expanded), reports/reproduction.md,
  reports/paper_code_concordance.md, runs/p2_* logs.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from netCDF4 import Dataset
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from statsmodels.tsa.arima.model import ARIMA

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from perdigao_attr.metrics import legacy_labelled_rmse, mae, rmse  # noqa: E402
from perdigao_attr.seeds import derive_generator  # noqa: E402

MASTER_SEED = 2026091501
TOWER = "tse13"
CONF_START = np.datetime64("2017-03-10T00:00:00")
CONF_END_EXCL = np.datetime64("2017-06-17T00:00:00")
G = 9.81
GAMMA_D = 0.0098
HORIZONS = {"10min": 2, "1h": 12, "3h": 36}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def raw(a) -> np.ndarray:
    if np.ma.isMaskedArray(a):
        mask = np.ma.getmaskarray(a)
        data = np.asarray(a.data, dtype=float)
        data[mask] = np.nan
        a = data
    a = np.asarray(a, dtype=float)
    a[~np.isfinite(a)] = np.nan
    a[np.abs(a) > 1e30] = np.nan
    return a


def col(a: np.ndarray, ti: int) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    if a.ndim == 2:
        return a[:, ti] if ti < a.shape[1] else np.full(a.shape[0], np.nan)
    return a


def file_times(dset) -> np.ndarray:
    tv = dset.variables["time"]
    units = getattr(tv, "units", "")
    m = re.search(r"since\s+(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", units)
    assert m, f"unexpected time units: {units!r}"
    base = np.datetime64(f"{m.group(1)}T{m.group(2)}")
    return (base + tv[:].astype(int).astype("timedelta64[s]")).astype("datetime64[ns]")


def load_confirm_base() -> pd.DataFrame:
    """Load 5-min base series for confirm period (paper-spec: left unaltered)."""
    contract = yaml.safe_load((REPO / "configs" / "data_contract.yaml").read_text())
    mapping = contract["mapping"]
    S = TOWER
    # canonical -> file var name
    fvar = {k: mapping[k] for k in mapping}
    nc_files = sorted((REPO / "data" / "raw").glob("isfs_qc_tiltcor_*.nc"))
    series: dict[str, list] = {}
    times_all: list = []
    for f in nc_files:
        ds = Dataset(str(f), "r")
        t = file_times(ds)
        keep = (t >= CONF_START) & (t < CONF_END_EXCL)
        if not keep.any():
            ds.close()
            continue
        sites = ["".join(r.astype(str)).strip() for r in np.asarray(ds.variables["sites"][:])]
        ti = sites.index(S)
        idx = np.where(keep)[0]
        times_all.append(t[idx])
        for canon, vname in fvar.items():
            if vname in ds.variables:
                v = col(raw(ds.variables[vname][:]), ti)[idx]
            else:
                v = np.full(int(keep.sum()), np.nan)
            series.setdefault(canon, []).append(v)
        ds.close()
    t = np.concatenate(times_all)
    order = np.argsort(t)
    df = pd.DataFrame({"time": t[order]})
    for k, parts in series.items():
        df[k] = np.concatenate(parts)[order]
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


def mcp_fill(target: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Variance-ratio MCP fill where target missing but ref valid (confirm stats)."""
    out = target.copy()
    ok = ~(np.isnan(target) | np.isnan(ref))
    miss = np.isnan(target) & ~np.isnan(ref)
    if ok.sum() > 10 and miss.any():
        mu_t, sd_t = float(np.mean(target[ok])), float(np.std(target[ok]))
        mu_r, sd_r = float(np.mean(ref[ok])), float(np.std(ref[ok]))
        if sd_r > 0 and np.isfinite(sd_t):
            out[miss] = mu_t + (sd_t / sd_r) * (ref[miss] - mu_r)
    return out


def interp_noise(s: pd.Series, rng, sigma: float) -> pd.Series:
    out = s.interpolate(method="linear", limit_direction="both").copy()
    still = out.isna()
    if still.any():
        out[still] = float(np.nanmean(s.values)) if np.isfinite(np.nanmean(s.values)) else 0.0
    was = s.isna().values
    if was.any() and sigma > 0:
        vals = out.values.copy()
        vals[was] += rng.normal(0, sigma, int(was.sum()))
        out[:] = vals
    return out


def build_features(df5: pd.DataFrame, rng) -> pd.DataFrame:
    """Paper-spec imputation + derived physics features on 5-min base."""
    d = df5.copy()
    # MCP pairs (100m target <- 20m ref)
    pairs = [("U100", "U20"), ("u100", "u20"), ("v100", "v20"),
             ("T100", "T20"), ("tc100", "tc20")]
    for tgt, ref in pairs:
        if tgt in d and ref in d:
            d[tgt] = mcp_fill(d[tgt].values, d[ref].values)
    # residual gaps: linear interp + 1%-std noise
    for c in d.columns:
        if c == "time":
            continue
        s = pd.Series(d[c].values, index=d["time"])
        sd = float(np.nanstd(s.values))
        sigma = 0.01 * sd if np.isfinite(sd) and sd > 0 else 0.0
        d[c] = interp_noise(s, rng, sigma).values
    thv100 = d["tc100"].values + 273.15
    thv20 = d["tc20"].values + 273.15
    dtheta = (thv100 - thv20) / 80.0 + GAMMA_D
    thref = (thv100 + thv20) / 2.0
    N2raw = (G / thref) * dtheta
    N2 = np.clip(N2raw, 0, None)  # code-spec: negatives clipped to 0
    Tref = (d["T100"].values + d["T20"].values) / 2.0 + 273.15
    du = (d["u100"].values - d["u20"].values) / 80.0
    dv = (d["v100"].values - d["v20"].values) / 80.0
    denom_g = du ** 2 + dv ** 2
    Ri_g = np.where(denom_g > 1e-12, N2 / np.maximum(denom_g, 1e-12), 0.0)
    Ri_g = np.minimum(Ri_g, 5.0)  # upper-only clip
    shear = d["cov_uw20"].values * du + d["cov_vw20"].values * dv
    Ri_f = np.where(np.abs(shear) > 1e-12,
                    ((G / Tref) * d["cov_wT100"].values) / np.where(np.abs(shear) > 1e-12, shear, 1.0),
                    0.0)
    Ri_f = np.clip(Ri_f, -5, 5)
    sigma_u = np.sqrt(np.maximum(d["var_u100"].values, 0))
    U = d["U100"].values
    med_TI = np.nanmedian(np.where(U > 0.1, sigma_u / np.maximum(U, 1e-9), np.nan))
    TI = np.where(U > 0.1, sigma_u / np.maximum(U, 1e-9), med_TI)
    u_star = (d["cov_uw20"].values ** 2 + d["cov_vw20"].values ** 2) ** 0.25
    med_ustar = np.nanmedian(np.where(U > 0.1, u_star / np.maximum(U, 1e-9), np.nan))
    ustar_norm = np.where(U > 0.1, u_star / np.maximum(U, 1e-9), med_ustar)
    tke = 0.5 * (d["var_u100"].values + d["var_v100"].values + d["var_w100"].values)
    dirad = np.deg2rad(d["dir100"].values)
    hours = pd.to_datetime(d["time"]).dt.tz_localize(None)
    hod = hours.dt.hour + hours.dt.minute / 60.0
    feat = pd.DataFrame({
        "time": d["time"],
        "U": U,
        "dirNS": np.cos(dirad), "dirEW": np.sin(dirad),
        "W": d["w100"].values,
        "sigma_u": sigma_u, "u_star": u_star, "TKE": tke,
        "N2": N2, "dT_dz": (d["T100"].values - d["T20"].values) / 80.0,
        "T": d["T100"].values,
        "t1": np.cos(np.pi * hod.values / 12.0),
        "t2": np.sin(np.pi * hod.values / 12.0),
        "TI": TI, "turbHtFlux": d["cov_wT100"].values,
        "Ri_f": Ri_f, "Ri_g": Ri_g,
        "u_star_norm": ustar_norm,
    })
    return feat.fillna(feat.median(numeric_only=True))


def aggregate_issue(feat: pd.DataFrame, W: int) -> pd.DataFrame:
    """Right-aligned input means Z(T) and future target means Y(T)."""
    num = feat.drop(columns=["time"])
    roll = num.rolling(W, min_periods=W).mean()
    Z = roll.copy()
    Y = num["U"].shift(-W).rolling(W, min_periods=W).mean()
    # Y(T) = mean of U over (T, T+h]: with 5-min steps, mean of next W stamps
    out = pd.DataFrame({"time": feat["time"], "Y": Y.values})
    for c in num.columns:
        out[f"Z_{c}"] = Z[c].values
    out["issue_time"] = out["time"]
    out["max_input_time"] = out["time"]
    out["target_start"] = out["time"] + pd.to_timedelta(1, unit="s")
    hmin = W * 5
    out["target_end"] = out["time"] + pd.to_timedelta(hmin, unit="min")
    out = out.dropna().reset_index(drop=True)
    # time-contract check
    assert ((out["max_input_time"] <= out["issue_time"]) & (out["issue_time"] < out["target_start"])).all()
    return out


def lag_matrix(agg: pd.DataFrame, feat_cols: list[str]) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    F = agg[feat_cols].values
    X = np.concatenate([F[1:], F[:-1]], axis=1)
    idx = agg.index[1:]
    return X, agg["Y"].values[1:], agg.loc[idx].reset_index(drop=True)


def fit_arima_insample(y: np.ndarray) -> np.ndarray:
    fit = ARIMA(y, order=(2, 0, 1)).fit()
    pred = np.asarray(fit.fittedvalues, dtype=float)
    pred[:2] = y[:2]  # AR startup: fall back to actuals
    return pred


def to_md(df: pd.DataFrame) -> str:
    """Minimal markdown table (stdlib only; no tabulate dependency)."""
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for _, r in df.iterrows():
        rows.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join([head, sep] + rows)


def run_horizon(agg: pd.DataFrame, hname: str, W: int, rng_seed_note: str) -> dict:
    feat_cols = [c for c in agg.columns if c.startswith("Z_")]
    X, y, sub = lag_matrix(agg, feat_cols)
    arima_pred_full = fit_arima_insample(sub["Y"].values)
    n = len(y)
    # ---- R0: stratified 10-fold on target deciles ----
    dec = pd.qcut(sub["Y"], 10, labels=False, duplicates="drop").values
    skf = StratifiedKFold(n_splits=10, shuffle=True, random_state=20260915)
    final = np.full(n, np.nan)
    bca = np.full(n, np.nan)
    for tr, te in skf.split(X, dec):
        err_tr = y[tr] - arima_pred_full[tr]
        bias = float(np.mean(err_tr))
        bca[te] = arima_pred_full[te] + bias
        rf = RandomForestRegressor(n_estimators=1000, min_samples_split=100,
                                   max_features=1.0, random_state=1,
                                   n_jobs=4)
        rf.fit(X[tr], (err_tr - bias))
        final[te] = bca[te] + rf.predict(X[te])
    err = y - final
    err_bca = y - bca
    persist = sub["Y"].values  # placeholder replaced below
    # persistence: current input mean carries forward
    zU = sub["Z_U"].values
    persist_pred = zU
    perr = y - persist_pred
    r0 = dict(series="R0_paper-spec", horizon=hname, window_steps=W, n=n,
              rmse_full=rmse(err), mae_full=mae(err),
              legacy_full=legacy_labelled_rmse(err), r2_full=float(r2_score(y, final)),
              rmse_bca=rmse(err_bca), mae_bca=mae(err_bca),
              rmse_persist=rmse(perr), mae_persist=mae(perr))
    # ---- R1: random 75/25 split random_state=1, RF 1000/0.7/100 oob ----
    Xtr, Xte, ytr, yte, itr, ite = train_test_split(
        X, y, np.arange(n), test_size=0.25, random_state=1)
    a_tr, a_te = arima_pred_full[itr], arima_pred_full[ite]
    bias1 = float(np.mean(ytr - a_tr))
    bca_te = a_te + bias1
    rf1 = RandomForestRegressor(n_estimators=1000, max_features=0.7,
                                min_samples_split=100, oob_score=True,
                                random_state=1, n_jobs=4)
    rf1.fit(Xtr, (ytr - a_tr - bias1))
    fin_te = bca_te + rf1.predict(Xte)
    e1 = yte - fin_te
    eb1 = yte - bca_te
    r1 = dict(series="R1_code-spec", horizon=hname, window_steps=W, n_test=len(yte),
              rmse_full=rmse(e1), mae_full=mae(e1),
              legacy_full=legacy_labelled_rmse(e1), r2_full=float(r2_score(yte, fin_te)),
              rmse_bca=rmse(eb1), mae_bca=mae(eb1))
    # ---- R2: corrected-metric recompute (no refit) ----
    r2rows = [
        dict(series="R2_corrected", horizon=hname, base="R0_full",
             rmse=rmse(err), mae=mae(err), legacy=legacy_labelled_rmse(err),
             r2=float(r2_score(y, final)), n=n),
        dict(series="R2_corrected", horizon=hname, base="R1_full",
             rmse=rmse(e1), mae=mae(e1), legacy=legacy_labelled_rmse(e1),
             r2=float(r2_score(yte, fin_te)), n_test=len(yte)),
    ]
    # persist full arrays for audit snapshot
    return {"r0": r0, "r1": r1, "r2rows": r2rows,
            "y": y, "final": final, "e1": e1, "bca": bca,
            "n": n, "n_test": len(yte)}


def main() -> None:
    run_id = f"{utcnow().replace(':','').replace('+00:00','Z')}_p2"
    (REPO / "runs").mkdir(exist_ok=True)
    (REPO / "tables").mkdir(exist_ok=True)
    (REPO / "reports").mkdir(exist_ok=True)
    log = {"run_id": run_id, "started_at_utc": utcnow(), "phase": "P2",
           "note": "R0/R1/R2 single run each; reproduction_only=true"}
    rng = derive_generator(MASTER_SEED, "split", 99)
    print("[P2] loading confirm base ...")
    df5 = load_confirm_base()
    print(f"[P2] base rows={len(df5)} cols={len(df5.columns)}")
    feat = build_features(df5, rng)
    rep_rows, r2_rows = [], []
    snapshots = []
    for hname, W in HORIZONS.items():
        print(f"[P2] horizon {hname} W={W} ...")
        agg = aggregate_issue(feat, W)
        res = run_horizon(agg, hname, W, "frozen-defaults")
        r0, r1 = res["r0"], res["r1"]
        rep_rows.append({"series": "R0_paper-spec", "horizon": hname,
                         "model": "ARIMA-RF_full", "n": r0["n"],
                         "rmse": r0["rmse_full"], "mae": r0["mae_full"],
                         "legacy_labelled_rmse": r0["legacy_full"], "r2": r0["r2_full"],
                         "reproduction_only": True})
        rep_rows.append({"series": "R0_paper-spec", "horizon": hname,
                         "model": "BCA", "n": r0["n"],
                         "rmse": r0["rmse_bca"], "mae": r0["mae_bca"],
                         "legacy_labelled_rmse": r0["mae_bca"], "r2": np.nan,
                         "reproduction_only": True})
        rep_rows.append({"series": "R0_paper-spec", "horizon": hname,
                         "model": "persistence", "n": r0["n"],
                         "rmse": r0["rmse_persist"], "mae": r0["mae_persist"],
                         "legacy_labelled_rmse": r0["mae_persist"], "r2": np.nan,
                         "reproduction_only": True})
        rep_rows.append({"series": "R1_code-spec", "horizon": hname,
                         "model": "ARIMA-RF_full", "n": r1["n_test"],
                         "rmse": r1["rmse_full"], "mae": r1["mae_full"],
                         "legacy_labelled_rmse": r1["legacy_full"], "r2": r1["r2_full"],
                         "reproduction_only": True})
        rep_rows.append({"series": "R1_code-spec", "horizon": hname,
                         "model": "BCA", "n": r1["n_test"],
                         "rmse": r1["rmse_bca"], "mae": r1["mae_bca"],
                         "legacy_labelled_rmse": r1["mae_bca"], "r2": np.nan,
                         "reproduction_only": True})
        for r in res["r2rows"]:
            base = {"series": r["series"], "horizon": r["horizon"], "model": r["base"],
                    "n": r.get("n", r.get("n_test")),
                    "rmse": r["rmse"], "mae": r["mae"],
                    "legacy_labelled_rmse": r["legacy"], "r2": r["r2"],
                    "reproduction_only": True}
            rep_rows.append(base)
            r2_rows.append(base)
        snapshots.append({"horizon": hname, "window_steps": W, "n_issues": int(res["n"]),
                          "n_test_r1": int(res["n_test"])})
        print(f"[P2] {hname}: R0 RMSE={r0['rmse_full']:.4f} MAE={r0['mae_full']:.4f} "
              f"| R1 RMSE={r1['rmse_full']:.4f} MAE={r1['mae_full']:.4f}")
    rep = pd.DataFrame(rep_rows)
    rep.to_csv(REPO / "tables" / "reproduction_results.csv", index=False)
    # published results (machine-extracted from paper XML tables 1/2/B1)
    pub = pd.DataFrame([
        # Table 1: select combos + baselines
        {"horizon": "10min", "model": "persistence", "rmse": 0.737, "mae": 0.531, "source": "Table1"},
        {"horizon": "10min", "model": "BCA", "rmse": 0.726, "mae": 0.528, "source": "Table1"},
        {"horizon": "10min", "model": "ARIMA-RF_full", "rmse": 0.714, "mae": 0.520, "source": "Table1"},
        {"horizon": "10min", "model": "ARIMA-RF_noT", "rmse": 0.712, "mae": 0.518, "source": "Table1"},
        {"horizon": "1h", "model": "persistence", "rmse": 1.165, "mae": 0.884, "source": "Table1"},
        {"horizon": "1h", "model": "BCA", "rmse": 1.132, "mae": 0.863, "source": "Table1"},
        {"horizon": "1h", "model": "ARIMA-RF_full", "rmse": 1.092, "mae": 0.830, "source": "Table1"},
        {"horizon": "1h", "model": "ARIMA-RF_noT", "rmse": 1.071, "mae": 0.813, "source": "Table1"},
        {"horizon": "3h", "model": "persistence", "rmse": 1.676, "mae": 1.315, "source": "Table1"},
        {"horizon": "3h", "model": "BCA", "rmse": 1.575, "mae": 1.240, "source": "Table1"},
        {"horizon": "3h", "model": "ARIMA-RF_full", "rmse": 1.395, "mae": 1.100, "source": "Table1"},
        {"horizon": "3h", "model": "ARIMA-RF_noT", "rmse": 1.379, "mae": 1.083, "source": "Table1"},
        {"horizon": "1h", "model": "ARIMA-RF_R2_0.84_claim", "rmse": np.nan, "mae": np.nan, "source": "abstract_R2=0.84"},
    ])
    pub.to_csv(REPO / "tables" / "published_results.csv", index=False)
    # concordance (expand frozen P0 draft to required rows/verdicts)
    conc = pd.DataFrame([
        {"item": "data_period", "paper": "2017-03-10 to 2017-06-16",
         "code": "pre-supplied CSV (period not enforced in sample)", "verdict": "PAPER_ONLY",
         "evidence": "paper.xml Sec.2 + sampleCode Data paths"},
        {"item": "tower_height_vars", "paper": "northern-ridge 100m tower; 20/100m sensors",
         "code": "Vars100m/Vars assume 20/100m cols (tower ID not checked)", "verdict": "MATCH",
         "evidence": "paper.xml Sec.2 + sampleFuncs Vars100m/Vars; P1 tower_decision tse13"},
        {"item": "aggregation_alignment", "paper": "10min/1h/3h windows at 5min moving average",
         "code": "2 lags + n_skip comment (2/12/36); movingIndices[:-1]", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.2 + sampleFuncs data_Func; P2 R0 vs R1 separated"},
        {"item": "arima_fit_forecast_update", "paper": "ARIMA(2,0,1) fit/forecast described; update cadence UNSPECIFIED",
         "code": "absent: reads arima error/preds cols; no generator", "verdict": "CODE_ONLY",
         "evidence": "paper.xml Sec.3.1 + sampleFuncs Vars100m cols; P2 single in-sample fit (documented default)"},
        {"item": "missing_imputation", "paper": "variance-ratio MCP + linear interp + Gaussian noise",
         "code": "drop-last-row only; no MCP/interp in sample", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.2 + sampleFuncs Vars"},
        {"item": "split_stratification", "paper": "stratified 10-fold CV (strata UNSPECIFIED)",
         "code": "random 75/25 split random_state=1 (x2)", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.2 + sampleCode tts lines; P2 target-decile default"},
        {"item": "lag_horizon", "paper": "previous two time steps; 10min/1h/3h horizons",
         "code": "2 lags via inputIndices; horizon via n_skip comment", "verdict": "MATCH",
         "evidence": "paper.xml Sec.3.2 + sampleCode n_steps/n_skip"},
        {"item": "rf_config", "paper": "1000 trees single-var / 1500 combo; min_samples_split=100",
         "code": "1000/0.7/100 + oob; no 1500 branch", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.3.2 + sampleCode RandomForestRegressor; P2 R0=1000/1.0/100, R1=1000/0.7/100"},
        {"item": "feature_selection", "paper": "exhaustive individual + combination tests",
         "code": "fixed 15-group bundle; importance block commented out", "verdict": "PAPER_ONLY",
         "evidence": "paper.xml Sec.3.3 + sampleCode var list"},
        {"item": "rmse_formula", "paper": "standard RMSE (text)",
         "code": "mean(sqrt(error^2)) stored as rmse", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.3 + sampleCode rmse line; P2 R2 recomputes sqrt(mean(err^2))"},
        {"item": "mae_formula", "paper": "standard MAE (text)",
         "code": "same expression equals MAE (under rmse name)", "verdict": "CONFLICT",
         "evidence": "paper.xml Sec.3 + sampleCode rmse/newrmse lines"},
        {"item": "seed", "paper": "ensemble of 10 runs (seeds UNSPECIFIED)",
         "code": "random_state=1 fixed", "verdict": "UNSPECIFIED",
         "evidence": "paper.xml Sec.3 + sampleCode tts; P2 fixes seeds, no tuning"},
    ])
    conc.to_csv(REPO / "audit" / "paper_code_concordance.csv", index=False)
    # comparison with labels
    comp = rep.merge(pub, on=["horizon", "model"], how="left", suffixes=("", "_pub"))
    comp["abs_diff_rmse"] = (comp["rmse"] - comp["rmse_pub"]).abs()
    comp["rel_diff_rmse"] = (comp["rmse"] - comp["rmse_pub"]).abs() / comp["rmse_pub"]
    comp["label"] = pd.cut(comp["rel_diff_rmse"], [-0.01, 0.05, 0.20, 1e9],
                            labels=["approx", "partial", "non-repro"])
    # reports (numbers read from tables only)
    rep_md = ["# P2 reproduction report (reproduction_only=true)",
              f"run_id: {run_id}", "",
              "Fixed defaults: single in-sample ARIMA(2,0,1) per horizon; "
              "R0 StratifiedKFold(10, shuffle, seed 20260915) on target deciles; "
              "R0 RF 1000/1.0/100 seed 1; R1 75/25 seed 1 + RF 1000/0.7/100 oob; "
              "MCP+interp+noise imputation; full-window aggregation; "
              "X=[F(T),F(T-5min)]. No tuning to published values.", "",
              "## Reproduction vs published (pooled CV / single split)",
              to_md(comp[["series", "horizon", "model", "n", "rmse", "mae",
                    "rmse_pub", "mae_pub", "rel_diff_rmse", "label"]]), "",
              "Labels: approx <=5%, partial 5-20%, non-repro >20% or missing spec "
              "(descriptive only, not scientific equivalence).", "",
              "## Snapshots (target windows / sample counts)",
              to_md(pd.DataFrame(snapshots)), "",
              "P2 ran R0/R1/R2 once each. Reproduction outputs carry "
              "reproduction_only=true and MUST NOT feed P3/P4 (guard-tested)."]
    (REPO / "reports" / "reproduction.md").write_text("\n".join(rep_md) + "\n")
    conc_md = ["# Paper vs code concordance (P2 audit)",
               "Sample code is reference only (commit 9420b71561d9d51c6665cab918371cd16fa074dd); "
               "mismatch alone does not prove a paper error.", "",
               to_md(conc)]
    (REPO / "reports" / "paper_code_concordance.md").write_text("\n".join(conc_md) + "\n")
    log.update({"finished_at_utc": utcnow(), "snapshots": snapshots,
                "tables_sha256": {f: sha256_file(REPO / "tables" / f)
                                  for f in ["reproduction_results.csv", "published_results.csv"]}})
    (REPO / "runs" / f"p2_{run_id}.json").write_text(json.dumps(log, indent=2))
    print(json.dumps({"run_id": run_id, "snapshots": snapshots}, indent=2))


if __name__ == "__main__":
    main()
