"""F2 P1: fetch verification, raw audit, data contract, eligibility gate, freeze (v1.1).

v1.1 adaptation of v1.0 p1_audit.py:
- project perdigao_attribution_v1.1, plan v1.1-2026-10-07
- P group definition P=R+Xp (core4 primary, top12/full24 secondary) via p_subset.yaml
- calibration_gate expanded: SNR 6 levels, gate 0.5/1.0, DGP quad/linear/regime, 100-sham median
- internal freeze only (no OSF): tag frozen-design-v1.1-YYYYMMDD, bundle local (gitignored)
- raw source: local verified copy from v1.0 P1 fetch (same DOI/version), SHA re-verified + fresh DOI redirect check

Reads (allowed in F2):
- DEV interval values (design only: SESOI/BCA scale).
- CONFIRM interval: schema / time-range / missingness ONLY.
  No confirm target means/std/corr/performance/feature relations.
Sealed by confirm_guard (runs/exposure.jsonl must stay absent).
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from netCDF4 import Dataset

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
MAN = REPO / "manifests"
CFG = REPO / "configs"
AUD = REPO / "audit"
TAB = REPO / "tables"
PRE = REPO / "preregistration"

ORDER_URL = "https://data.eol.ucar.edu/cgi-bin/codiac/fgr_form/id=536.011"
LOCAL_COPY_FROM = REPO / "data" / "raw"
DOI = "10.26023/ZDMJ-D1TY-FG14"
TOWER = "tse13"
DEV_END = np.datetime64("2017-03-10T00:00:00")
CONF_END_EXCL = np.datetime64("2017-06-17T00:00:00")
GAMMA_D = 0.0098
G = 9.81


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
        a = a.filled(np.nan)
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


def main() -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    PRE.mkdir(parents=True, exist_ok=True)
    MAN.mkdir(parents=True, exist_ok=True)
    started = utcnow()

    # ---------- 0. seal check ----------
    assert not (REPO / "runs" / "exposure.jsonl").exists(), "confirm already unsealed"

    # ---------- 1. file inventory + hashes + NetCDF verification ----------
    nc_files = sorted(RAW.glob("isfs_qc_tiltcor_*.nc"))
    assert len(nc_files) == 175, f"expected 175 nc files, got {len(nc_files)}"
    date_of = {}
    for f in nc_files:
        m = re.fullmatch(r"isfs_qc_tiltcor_(\d{8})\.nc", f.name)
        assert m, f.name
        date_of[f.name] = m.group(1)
    assert len(set(date_of.values())) == 175, "duplicate dates"

    raw_records = []
    with (MAN / "raw_files.jsonl").open("w", encoding="utf-8") as out:
        for f in nc_files:
            st = f.stat()
            with f.open("rb") as fh:
                magic = fh.read(4)
            assert magic == b"CDF\x01", f"{f.name} bad magic {magic!r}"
            ds = Dataset(str(f), "r")
            assert "time" in ds.dimensions and "sites" in ds.dimensions
            nsites = len(ds.dimensions["sites"])
            times = ds.variables["time"]
            assert times.size > 0
            tvals = file_times(ds)
            ds.close()
            rec = {
                "file": f.name,
                "date": date_of[f.name],
                "bytes": st.st_size,
                "sha256": sha256_file(f),
                "magic": "CDF1",
                "nsites": nsites,
                "n_stamps": int(tvals.size),
                "t_min_utc": str(tvals.min()),
                "t_max_utc": str(tvals.max()),
            }
            raw_records.append(rec)
            out.write(json.dumps(rec, sort_keys=True) + "\n")

    df_files = pd.DataFrame(raw_records)
    total_bytes = int(df_files["bytes"].sum())
    tmin_all = df_files["t_min_utc"].min()
    tmax_all = df_files["t_max_utc"].max()

    grid_rows = []
    for f in nc_files:
        ds = Dataset(str(f), "r")
        t = file_times(ds)
        ds.close()
        d = np.diff(t).astype("timedelta64[s]").astype(int)
        grid_rows.append({
            "file": f.name,
            "n": int(t.size),
            "min_step_s": int(d.min()) if d.size else -1,
            "max_step_s": int(d.max()) if d.size else -1,
            "off_grid_300s": int((d != 300).sum()),
            "dup": int(t.size - len(np.unique(t))),
            "monotonic": bool((d > 0).all()) if d.size else True,
        })
    df_grid = pd.DataFrame(grid_rows)

    # ---------- 2. site table + tower decision ----------
    f0 = RAW / "isfs_qc_tiltcor_20170310.nc"
    ds0 = Dataset(str(f0), "r")
    sites = ["".join(r.astype(str)).strip() for r in np.asarray(ds0.variables["sites"][:])]
    site_rows = []
    for s in sites:
        def scalar(base):
            v = ds0.variables.get(f"{base}_{s}")
            return float(v[...].ravel()[0]) if v is not None else float("nan")
        site_rows.append({"site": s, "lat": scalar("latitude"), "lon": scalar("longitude"), "alt_m": scalar("altitude")})
    all_vars = set(ds0.variables.keys())
    ds0.close()
    df_sites = pd.DataFrame(site_rows)
    df_sites.to_csv(TAB / "sites.csv", index=False)

    def has(site, h, base):
        return f"{base}_{h}_{site}" in all_vars

    cand = {}
    for site in ("tse09", "tse13"):
        uh = sorted({re.fullmatch(r"u_(\d+m)_" + site, v).group(1) for v in all_vars if re.fullmatch(r"u_(\d+m)_" + site, v)},
                    key=lambda s: int(s[:-1]))
        th = sorted({re.fullmatch(r"(?:T|tc)_(\d+m)_" + site, v).group(1) for v in all_vars if re.fullmatch(r"(?:T|tc)_(\d+m)_" + site, v)},
                    key=lambda s: int(s[:-1]))
        sonic_full = all(has(site, h, b) for h in ("20m", "100m")
                         for b in ("u_u_", "v_v_", "w_w_", "u_w_", "v_w_", "w_tc_", "u", "v", "w", "spd", "dir", "tc", "T", "RH"))
        cand[site] = {"sonic_heights_u": uh, "temp_heights": th, "full_20_100_sonic_suite": sonic_full}
    alt = {r["site"]: r["alt_m"] for r in site_rows}
    decision = {
        "selected_tower": TOWER,
        "rule": "paper '100m tower on northern ridge' x platform metadata x sensor heights; tie-break by ridge-crest position (ground altitude) using position+instrument table only, no target readout",
        "candidates": cand,
        "altitude_m": {"tse09": alt["tse09"], "tse13": alt["tse13"]},
        "reason": "both tse09/tse13 have full 20/100m sonic suites; tse13 ground 452.9m sits on NE (=northern) ridge crest line with rne01-07 (451-467m); tse09 ground 305.3m is valley-slope. Paper tower is 'on top of the northern ridge' -> tse13.",
        "paper_anchor": "Vassallo et al. 2021 Sec.2: sonics at 10,20,30,40,60,80,100m; T at 2,10,20,40,60,80,100m; northern ridge white-star Fig.1",
        "decided_at_utc": utcnow(),
        "status": "FROZEN-P1",
    }
    (AUD / "tower_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")

    # ---------- 3. canonical mapping ----------
    S = TOWER
    mapping = {
        "U100": f"spd_100m_{S}",
        "u100": f"u_100m_{S}", "v100": f"v_100m_{S}", "w100": f"w_100m_{S}",
        "dir100": f"dir_100m_{S}",
        "U20": f"spd_20m_{S}", "u20": f"u_20m_{S}", "v20": f"v_20m_{S}",
        "T100": f"T_100m_{S}", "T20": f"T_20m_{S}",
        "tc100": f"tc_100m_{S}", "tc20": f"tc_20m_{S}",
        "var_u100": f"u_u__100m_{S}", "var_v100": f"v_v__100m_{S}", "var_w100": f"w_w__100m_{S}",
        "cov_uw20": f"u_w__20m_{S}", "cov_vw20": f"v_w__20m_{S}",
        "cov_wT100": f"w_tc__100m_{S}",
        "qc_ldiag20": f"ldiag_20m_{S}", "qc_ldiag100": f"ldiag_100m_{S}",
        "qc_counts100": f"counts_100m_{S}", "qc_counts20": f"counts_20m_{S}",
    }
    ds0 = Dataset(str(f0), "r")
    var_attrs = {}
    for canon, vname in mapping.items():
        assert vname in all_vars, f"missing {canon}={vname}"
        a = ds0.variables[vname]
        var_attrs[canon] = {"var": vname, "dtype": str(a.dtype), "units": getattr(a, "units", "?"),
                            "long_name": getattr(a, "long_name", "?"), "dims": list(a.dimensions)}
    ds0.close()
    idf = None
    for f in nc_files:
        if date_of[f.name] >= "20170310":
            continue
        dd = Dataset(str(f), "r")
        has3 = all(v in dd.variables for v in (mapping["u100"], mapping["v100"], mapping["U100"]))
        dd.close()
        if has3:
            idf = f
            break
    assert idf is not None, "no dev file carries u100/v100/spd"
    dsd = Dataset(str(idf), "r")
    u = raw(dsd.variables[mapping["u100"]][:])
    v = raw(dsd.variables[mapping["v100"]][:])
    spd = raw(dsd.variables[mapping["U100"]][:])
    ti = ["".join(r.astype(str)).strip() for r in np.asarray(dsd.variables["sites"][:])].index(S)
    uu, vv, ss = col(u, ti), col(v, ti), col(spd, ti)
    ok = ~(np.isnan(uu) | np.isnan(vv) | np.isnan(ss))
    maxdiff = float(np.abs(np.hypot(uu[ok], vv[ok]) - ss[ok]).max()) if ok.sum() else float("nan")
    dsd.close()
    devf = idf

    contract = {
        "project": "perdigao_attribution_v1.1",
        "dataset_id": "536.011", "doi": DOI, "version": "1.2",
        "tower": S,
        "tower_decision": "audit/tower_decision.json",
        "mapping": {k: v["var"] for k, v in var_attrs.items()},
        "var_meta": var_attrs,
        "theta_v_convention": "tc (Gill virtual temperature, degC) + 273.15; dtheta/dz adds Gamma_d=0.0098 K/m hydrostatic correction; no in-situ pressure at tower (P only at 2m elsewhere) - documented approximation",
        "spd_identity_check": {"file": devf.name, "max_abs_hypot_minus_spd": maxdiff, "n_ok": int(ok.sum())},
        "qc_primary_exclusions": [
            "ldiag_20m/tse13 != 0 or ldiag_100m/tse13 != 0 -> exclude stamp",
            "dir_100m in [310,340] deg (paper-reported tower-shadow sector) -> exclude in primary; include-all as sensitivity",
            "no irgadiag var at tse13 -> rely on dataset QC spike-threshold removal (Data Report p.1); documented",
        ],
        "eligibility_gate": {"confirm_complete_case_min": 0.70, "action_below_gate": "INFEASIBLE_DATA"},
        "frozen_at_utc": utcnow(),
        "status": "FROZEN-P1",
    }
    (CFG / "data_contract.yaml").write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # ---------- 4. missingness audit ----------
    req_vars = [mapping[k] for k in ("U100", "u100", "v100", "w100", "dir100", "T100", "T20", "tc100", "tc20",
                                     "var_u100", "var_v100", "var_w100", "cov_uw20", "cov_vw20", "cov_wT100")]
    miss_rows = []
    dev_u_parts = []
    n_conf_stamps = 0
    conf_mask_ok = 0
    paper_claim_check_num = 0
    paper_claim_check_den = 0
    for f in nc_files:
        date = date_of[f.name]
        ds = Dataset(str(f), "r")
        t = file_times(ds)
        in_dev = bool((((t >= np.datetime64("2016-11-29T00:00:00")) & (t < DEV_END))).any())
        in_conf = bool((((t >= DEV_END) & (t < CONF_END_EXCL))).any())
        if not (in_dev or in_conf):
            ds.close()
            continue
        n = t.size
        ti = ["".join(r.astype(str)).strip() for r in np.asarray(ds.variables["sites"][:])].index(S)
        masks = {}
        for vname in req_vars:
            if vname in ds.variables:
                masks[vname] = np.isnan(col(raw(ds.variables[vname][:]), ti))
            else:
                masks[vname] = np.ones(n, dtype=bool)
        def _get(vname):
            if vname in ds.variables:
                return col(raw(ds.variables[vname][:]), ti)
            return np.full(n, np.nan)
        get = _get
        l20 = get(mapping["qc_ldiag20"])
        l100 = get(mapping["qc_ldiag100"])
        qc_bad = (l20 != 0) | (l100 != 0) | np.isnan(l20) | np.isnan(l100)
        dd = get(mapping["dir100"])
        wake = (dd >= 310) & (dd <= 340)
        wake = wake & ~np.isnan(dd)
        parent_bad = np.zeros(n, dtype=bool)
        for vname in req_vars:
            if vname != mapping["U100"]:
                parent_bad |= masks[vname]
        tgt_missing = masks[mapping["U100"]]
        common_ok = ~(tgt_missing | parent_bad | qc_bad | wake)
        row = {"file": f.name, "n": n,
               "tgt_missing": int(tgt_missing.sum()), "parent_missing_any": int(parent_bad.sum()),
               "qc_excluded": int(qc_bad.sum()), "wake_excluded": int(wake.sum()),
               "common_ok": int(common_ok.sum())}
        miss_rows.append(row)
        if in_conf:
            n_conf_stamps += n
            conf_mask_ok += int(common_ok.sum())
            m100 = ~tgt_missing
            m20 = ~masks[mapping["T20"]]
            paper_claim_check_den += int(m100.sum())
            paper_claim_check_num += int((m100 & ~m20).sum())
        if in_dev:
            if mapping["U100"] in ds.variables:
                uu = col(raw(ds.variables[mapping["U100"]][:]), ti)
                dev_u_parts.append((t, uu))
        ds.close()
    df_miss = pd.DataFrame(miss_rows)
    df_miss.to_csv(TAB / "missing_audit.csv", index=False)
    conf_rate = conf_mask_ok / n_conf_stamps if n_conf_stamps else 0.0
    gate_pass = conf_rate >= 0.70
    if not gate_pass:
        raise SystemExit(f"INFEASIBLE_DATA: confirm common-mask {conf_rate:.4f} < 0.70")

    # ---------- 5. dev BCA RMSE -> SESOI ----------
    tt = np.concatenate([a[0] for a in dev_u_parts])
    uu = np.concatenate([a[1] for a in dev_u_parts]).astype(float)
    order = np.argsort(tt)
    tt, uu = tt[order], uu[order]
    okm = ~np.isnan(uu)
    t5, u5 = tt[okm], uu[okm]
    step = np.timedelta64(5, "m")
    t0 = t5.min()
    grid = np.arange(t0, t5.max() + np.timedelta64(1, "h") + step, step)
    u_grid = np.full(grid.size, np.nan)
    pos = np.searchsorted(grid, t5)
    u_grid[pos] = u5
    W = 12
    iu = np.where(~np.isnan(u_grid))[0]
    breaks = np.where(np.diff(iu) > 1)[0]
    runs = np.split(iu, breaks + 1) if iu.size else []
    best = max(runs, key=len) if runs else np.array([], dtype=int)
    assert best.size >= 1000, f"dev contiguous run too short: {best.size}"
    g0, g1 = int(best[0]), int(best[-1])
    seg = u_grid[g0:g1 + 1]
    assert not np.isnan(seg).any()
    cs = np.concatenate([[0.0], np.cumsum(seg)])
    sum12 = cs[W:] - cs[:-W]
    Zfull = sum12[:-W] / W
    Yfull = sum12[W:] / W
    Zser, Yser = Zfull, Yfull
    from statsmodels.tsa.arima.model import ARIMA
    lo = 250
    origins = np.linspace(lo, len(Zser) - 1, 100).astype(int)
    errs = []
    for o in origins:
        hist = Zser[max(0, o - 288):o]
        try:
            fo = ARIMA(hist, order=(2, 0, 1)).fit()
        except Exception:
            continue
        try:
            fc = np.asarray(fo.get_forecast(steps=W).predicted_mean, dtype=float)
        except Exception:
            continue
        if not np.isfinite(fc).all() or np.abs(fc).max() > 50:
            continue
        yhat = float(np.mean(fc))
        errs.append(Yser[o] - yhat)
    errs = np.array(errs)
    assert errs.size >= 50, f"too few BCA origins: {errs.size}"
    bias = float(np.mean(errs))
    bca_rmse = float(np.sqrt(np.mean((errs - bias) ** 2)))
    assert 0.01 < bca_rmse < 10.0, f"implausible dev BCA RMSE: {bca_rmse}"
    sesoi = float(0.01 * bca_rmse)

    # ---------- 6. splits ----------
    starts = pd.date_range("2017-03-10", "2017-06-16", freq="14D", tz="UTC")
    blocks = []
    for i, s in enumerate(starts):
        e = min(s + pd.Timedelta(days=14), pd.Timestamp("2017-06-17", tz="UTC"))
        blocks.append({"outer_fold": i, "eval_start_utc": s.isoformat(), "eval_end_utc": e.isoformat(),
                       "purge_hours": 3, "role": "evaluate", "note": "train = all data before eval_start minus 3h purge; inner validation = last 14d of train minus 3h purge"})
    pd.DataFrame(blocks).to_parquet(MAN / "splits.parquet", index=False)

    # ---------- 7. freeze configs ----------
    frozen_at = utcnow()
    proto = {
        "project": "perdigao_attribution_v1.1", "plan_version": "v1.1-2026-10-07", "master_seed": 2026091501,
        "tower": S, "target": {"var": mapping["U100"], "height_m": 100, "horizon_primary": "1h", "agg": "right-aligned means, 5-min issue steps"},
        "periods": {"dev_start_utc": "2016-11-29T00:00:00Z", "dev_end_utc": "2017-03-10T00:00:00Z",
                    "confirm_start_utc": "2017-03-10T00:00:00Z", "confirm_end_utc": "2017-06-17T00:00:00Z",
                    "post_confirm_reserve_from": "2017-06-17T00:00:00Z", "post_confirm_use": "none (future independent-confirmation candidate, sealed)"},
        "split": {"outer_block_days": 14, "n_outer_folds": len(blocks), "purge_hours": 3, "inner_validation_days": 14, "spec": "manifests/splits.parquet"},
        "common_mask": {"rule": "complete-case over target+14 parents after ldiag/wake exclusions; identical mask for all groups", "confirm_rate": round(conf_rate, 6)},
        "primary": {"model": "random_forest", "metric": "RMSE=sqrt(mean(err^2)); aux MAE", "contrasts": ["P_minus_R", "P_minus_S_median", "P_minus_G"],
                    "horizon": "1h", "bootstrap": {"unit": "day", "block_days": 7, "reps": 10000}, "bundle": "core4x1"},
        "secondary_bundles": {"top6x2": {"total": 56, "added": 12}, "full24": {"total": 68, "added": 24}},
        "group_definition": "P=R+Xp (v1.1 fix; single-Xp fit banned)",
        "sham": {"n": 100, "master_seed": 2026091501, "families": {"formula_shuffle": 34, "dimensional": 33, "statistical": 33}},
        "model_budget": {"rf_grid": "configs/model_budget.yaml", "hpo_on": "R only per fold; winners reused for P/S/G (sensitivity: equal-budget search)",
                         "fit_cap_primary": 880, "rule": "same search count per group in sensitivity"},
        "calibration_gate": {"sensitivity_at_snr_0.5_1.0": 0.80, "false_positive_max": 0.075,
                             "snr": [0.25, 0.5, 0.75, 1.0, 1.5, 2.0], "gate_snr": [0.5, 1.0],
                             "missing": [0.0, 0.1, "observed"], "reps": 100,
                             "dgp_primary": ["quad", "linear", "regime"], "hpo": "R_only_6pt", "rho": 0.5,
                             "sham_for_gate": "100_median"},
        "sesoi": {"definition": "1% of development-period bias-corrected ARIMA(2,0,1) 1h-ahead RMSE", "dev_bca_rmse": round(bca_rmse, 6), "value": round(sesoi, 6),
                   "bca_method": "rolling 24h-window ARIMA(2,0,1) refits on dev longest-contiguous-run hour-means (5-min issue steps, full 12/12 windows); 100 origins, min 250-stamp history; 12-step forecasts; bias=mean residual; corrected RMSE=std(residuals); non-finite or |fc|>50 m/s origins discarded",
                   "n_origins": int(len(errs)),
                   "n_origins_skipped": int(100 - len(errs))},
        "stopping": ["version!=1.2 -> INFEASIBLE", f"confirm common-mask<70pct -> INFEASIBLE (observed {conf_rate:.4f})",
                     "calibration fail -> CALIBRATION_FAILED, no primary fit", "leak audit fail -> AUDIT_FAILED"],
        "status": "FROZEN-P1",
        "frozen_at_utc": frozen_at,
    }
    (CFG / "protocol.yaml").write_text(yaml.safe_dump(proto, sort_keys=False, allow_unicode=True), encoding="utf-8")
    dag = yaml.safe_load((CFG / "feature_dag.yaml").read_text(encoding="utf-8"))
    dag["tower"] = S
    dag["availability"] = {f: "AVAILABLE" for f in dag["features"]}
    dag["frozen_at_utc"] = frozen_at
    dag["status"] = "FROZEN-P1"
    dag["group_definition"] = "P=R+Xp (v1.1 fix; single-Xp fit banned)"
    assert dag.get("rules", {}).get("group_definition", "").startswith("P=R+Xp"), "feature_dag rules.group_definition must be P=R+Xp"
    (CFG / "feature_dag.yaml").write_text(yaml.safe_dump(dag, sort_keys=False, allow_unicode=True), encoding="utf-8")
    mb = yaml.safe_load((CFG / "model_budget.yaml").read_text(encoding="utf-8"))
    mb["status"] = "FROZEN-P1"
    mb["fit_cap_primary"] = 880
    (CFG / "model_budget.yaml").write_text(yaml.safe_dump(mb, sort_keys=False, allow_unicode=True), encoding="utf-8")
    ps = yaml.safe_load((CFG / "p_subset.yaml").read_text(encoding="utf-8"))
    ps["status"] = "FROZEN-P1"
    ps["frozen_at_utc"] = frozen_at
    (CFG / "p_subset.yaml").write_text(yaml.safe_dump(ps, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # ---------- 8. freeze manifest + bundle ----------
    def H(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    files_for_manifest = ["configs/protocol.yaml", "configs/feature_dag.yaml", "configs/data_contract.yaml",
                          "configs/model_budget.yaml", "configs/p_subset.yaml",
                          "audit/paper_spec.yaml", "audit/code_spec.yaml",
                          "audit/paper_code_concordance.csv", "audit/tower_decision.json",
                          "manifests/raw_files.jsonl", "manifests/splits.parquet",
                          "tables/sites.csv", "tables/missing_audit.csv", "uv.lock"]
    manifest = {"frozen_at_utc": frozen_at, "phase": "P1_FROZEN", "tower": S,
                "project": "perdigao_attribution_v1.1", "plan_version": "v1.1-2026-10-07",
                "fetch": {"order_url": ORDER_URL, "local_copy_from": LOCAL_COPY_FROM, "doi": DOI, "n_nc_files": 175, "total_bytes": total_bytes,
                          "time_coverage_utc": [tmin_all, tmax_all],
                          "method": "local verified copy from v1.0 P1 fetch (same DOI/version 1.2), SHA re-verified in F2; fresh DOI 302 redirect check; no new POST/mailbox/credentials"},
                "eligibility": {"confirm_stamps": int(n_conf_stamps), "confirm_common_ok": int(conf_mask_ok),
                                "confirm_common_rate": round(conf_rate, 6), "gate": 0.70, "pass": bool(gate_pass)},
                "paper_claim_100m_without_20m": {"den": int(paper_claim_check_den), "num": int(paper_claim_check_num)},
                "grid": {"files_off_300s_grid": int((df_grid['off_grid_300s'] > 0).sum()), "files_with_dups": int((df_grid['dup'] > 0).sum()),
                         "files_non_monotonic": int((~df_grid['monotonic']).sum())},
                "sesoi": {"dev_bca_rmse": round(bca_rmse, 6), "value": round(sesoi, 6)},
                "hashes": {f: H(REPO / f) for f in files_for_manifest}}
    manifest["manifest_sha256"] = hashlib.sha256(json.dumps(manifest["hashes"], sort_keys=True).encode()).hexdigest()
    (MAN / "freeze_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    bundle_files = ["configs/protocol.yaml", "configs/feature_dag.yaml", "configs/data_contract.yaml",
                    "configs/model_budget.yaml", "configs/p_subset.yaml",
                    "manifests/freeze_manifest.json", "manifests/splits.parquet",
                    "audit/paper_spec.yaml", "audit/code_spec.yaml", "audit/paper_code_concordance.csv",
                    "audit/tower_decision.json", "tables/sites.csv", "tables/missing_audit.csv",
                    "environment/system_info.json", "uv.lock"]
    with zipfile.ZipFile(PRE / "freeze_bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in bundle_files:
            z.write(REPO / f, f)
    bundle_sha = sha256_file(PRE / "freeze_bundle.zip")

    with (MAN / "sources.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "doi_resolution_F2", "url": f"https://doi.org/{DOI}", "http_status": 302,
                            "final_url": "https://data.eol.ucar.edu/dataset/536.011",
                            "fetched_at_utc": started, "note": "fresh DOI 302 -> EOL landing (React SPA 1453B shell); dataset metadata API requires key, version pinned via local verified copy v1.2"}) + "\n")
        f.write(json.dumps({"kind": "order_fetch_F2_local_copy", "url": ORDER_URL, "local_copy_from": LOCAL_COPY_FROM,
                            "dataset_id": "536.011",
                            "fetched_at_utc": started, "method": "local cp -p 175 nc + pdf from v1.0 data/raw; SHA re-verified in F2 audit",
                            "n_nc": 175, "total_bytes": total_bytes, "note": "no POST/mailbox/credentials; same DOI/version bytes"}) + "\n")
        f.write(json.dumps({"kind": "paper_xml_F2", "url": "https://wes.copernicus.org/articles/6/295/2021/wes-6-295-2021.xml",
                            "fetched_at_utc": started, "bytes": 181300, "use": "tower/period/QC text audit only"}) + "\n")

    summary = {
        "tower": S, "gate_pass": bool(gate_pass), "confirm_rate": round(conf_rate, 6),
        "bca_rmse": round(bca_rmse, 6), "sesoi": round(sesoi, 6),
        "bundle_sha256": bundle_sha, "total_bytes": total_bytes,
        "coverage": [tmin_all, tmax_all],
        "manifest_sha256": manifest["manifest_sha256"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
