"""F4 P3 calibration gate v1.1 (P=R+Xp fix, core4 primary, 100-sham median).

Reads: dev 5-min observations (design data) + frozen configs.
Never reads: confirm-interval TARGET values (guard-tested).

Fixes vs v1.0 p3_calibrate.py:284-290 (P_only bug):
- v1.0: rf_p fit on Xp (24 cols) alone; sham on R+sham -> P disadvantaged.
- v1.1: Xrp=[Xr,Xp_bundle] concatenated, separate scaler per group per fold-train,
  single-Xp path removed (groups.fit_p_only banned, regression-tested).

Gate (frozen, PLAN_v1.1 sec.3-4):
- Bundles: core4x1 primary (TI,N2,Ri_g,tke x @0, added 4, total 48);
  top6x2/full24 secondary (added 12/24).
- DGP 3 forms (tanh(/2)-bounded): quad (z1*z2+0.5*z1^2-0.5*z2^2),
  linear (z1+z2), regime (z1 4-class slopes 0.15/0.6/1.0/1.5 + 0.3*z1).
- SNR 0.25/0.5/0.75/1.0/1.5/2.0 (gate on 0.5/1.0 only, rest reported).
- rho 0.5 fixed, base ridge(alpha=1.0) per fold-train, HPO 6-pt R-only reuse.
- Missing m0 0%/m10 10%/mobs observed; pool2 two day-block folds.
- Sham: full 100 (34/33/33) median (9-panel proxy abolished).
- Detection per rep = BOTH 95% CIs (P-R and P-S) upper < 0.
- Gate per (dform, missing): detect SNR0.5 & SNR1.0 each >=80% + FP <=7.5%.
  FAIL -> do NOT unseal confirm.

Staged execution: --bundle/--dforms/--snrs/--conds filter the task grid;
each invocation writes its own run dir + checkpoint every 10 reps.
Minimum gate = core4 x 3 DGP x SNR{0.5,1.0} x 3 missing x100 + neg 100/cond.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from perdigao_attr.p4lib import (  # noqa: E402
    BUNDLES,
    CAL_RF_PARAMS,
    P_FEATURES,
    R_BASE_5MIN,
    W_PRIMARY,
    add_lags,
    add_r_derived,
    aggregate_issues,
    apply_scaler,
    ar1_noise,
    build_dimensional_shams,
    build_formula_shams,
    build_grff,
    build_statistical_shams,
    bundle_indices,
    common_mask,
    compute_p5,
    daily_rmse,
    fit_rf,
    fit_scaler,
    load_5min,
    moving_block_bootstrap_ci,
    qc_keep_mask,
    sham_bundle_indices,
    sham_lag_matrix,
    sha256_of_array,
)
from perdigao_attr.seeds import MASTER_SEED, derive_seed  # noqa: E402

DEV_START = np.datetime64("2016-11-29T00:00:00")
DEV_END = np.datetime64("2017-03-10T00:00:00")
RHO_AR1 = 0.5
ALL_DFORMS = ["quad", "linear", "regime"]
ALL_SNRS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
GATE_SNRS = [0.5, 1.0]
ALL_CONDS = {"m0": 0.0, "m10": 0.10, "mobs": round(1 - 0.852623, 6)}
OBSERVED_RATE = round(1 - 0.852623, 6)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_S(z1: np.ndarray, z2: np.ndarray, form: str) -> np.ndarray:
    if form == "quad":
        return np.tanh((z1 * z2 + 0.5 * z1 ** 2 - 0.5 * z2 ** 2) / 2.0)
    if form == "linear":
        return np.tanh((z1 + z2) / 2.0)
    if form == "regime":
        cls = np.digitize(z1, [-1.0, 0.0, 1.0])
        slopes = np.array([0.15, 0.6, 1.0, 1.5])[cls]
        return np.tanh((slopes * z2 + 0.3 * z1) / 2.0)
    raise ValueError(f"unknown S form: {form}")


def to_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join([head, sep] + rows)


def verify_freeze() -> dict:
    man = json.loads((REPO / "manifests" / "freeze_manifest.json").read_text())
    bad = []
    for f, h in man["hashes"].items():
        if f == "audit/paper_code_concordance.csv":
            continue
        p = REPO / f
        if not p.exists():
            bad.append(f"{f}:MISSING")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
            bad.append(f"{f}:MISMATCH")
    return {"mismatch": bad, "manifest": man["manifest_sha256"]}


def build_dev_matrices() -> dict:
    t0 = time.time()
    df5 = load_5min(DEV_START, DEV_END)
    qc_ok = qc_keep_mask(df5)
    r5 = add_r_derived(df5)
    tt = pd.to_datetime(r5["time"])
    cut = tt.quantile(2 / 3)
    tr5 = (tt <= cut).values
    p5_all, dev_stats = compute_p5(r5[tr5].reset_index(drop=True))
    p5_full, _ = compute_p5(r5, dev_stats=dev_stats)
    agg = aggregate_issues(r5[["time"] + R_BASE_5MIN], p5_full, W=W_PRIMARY)
    q = pd.Series(qc_ok.astype(float))
    qwin = q.rolling(W_PRIMARY, min_periods=W_PRIMARY).min().values
    base_times = r5["time"].values
    agg_qc = []
    tmap = {t: i for i, t in enumerate(base_times)}
    for t in agg["time"].values:
        i = tmap[np.datetime64(t)]
        agg_qc.append(qwin[i] if i < len(qwin) and np.isfinite(qwin[i]) else 0.0)
    agg["qc_win_ok"] = np.array(agg_qc)
    agg = agg[agg["qc_win_ok"] == 1.0].reset_index(drop=True)
    filt_times = agg["time"].values
    Xr, rnames = add_lags(agg, "R_")
    Xp0, pnames = add_lags(agg, "P_")
    mask = common_mask(agg)
    kprime = np.where(mask[1:])[0] + 1
    tprev = filt_times[kprime - 1]
    Xr, Xp1 = Xr[mask[1:]], Xp0[mask[1:]]
    sub = agg.loc[agg.index[1:]].reset_index(drop=True).loc[pd.Series(mask[1:]).values]
    sub = sub.reset_index(drop=True)
    Y = sub["Y"].values.astype(float)
    days = sub["day"].values
    times = pd.to_datetime(sub["issue_time"])
    assert len(tprev) == len(sub) == len(Y)
    return {
        "Xr": Xr, "Xp_lag": Xp1, "rnames": rnames, "pnames": pnames,
        "Y": Y, "days": days, "times": times, "sub": sub,
        "tprev": tprev, "dev_stats": dev_stats, "r5": r5, "p5_full": p5_full,
        "qc_rate": float(np.mean(qc_ok)), "n_5min": len(df5),
        "build_s": round(time.time() - t0, 1),
    }


def day_folds(days: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    uniq = sorted(pd.unique(days).tolist())
    assert len(uniq) >= 7, f"need >=7 dev days, got {len(uniq)}"
    cut = len(uniq) // 2
    folds = []
    for tr_days, te_days in ((uniq[:cut], uniq[cut:]), (uniq[cut:], uniq[:cut])):
        tr = np.isin(days, tr_days)
        te = np.isin(days, te_days)
        folds.append((tr, te))
    return folds


CAL_HPO_GRID = [
    {"n_estimators": 500, "max_features": mf, "min_samples_leaf": ml, "max_depth": None}
    for mf in (0.3, 0.7) for ml in (5, 20, 100)
]


def inner_select(Xr_tr, y_tr, pday_tr, rep_seed: int) -> dict:
    pday_tr = np.asarray(pday_tr)
    umax = int(pday_tr.max())
    te_in = pday_tr > umax - 7
    tr_in = pday_tr <= umax - 8
    if tr_in.sum() < 100 or te_in.sum() < 30:
        cut = int(len(pday_tr) * 2 / 3)
        order = np.argsort(pday_tr, kind="stable")
        tr_in = np.zeros(len(pday_tr), bool)
        te_in = np.zeros(len(pday_tr), bool)
        tr_in[order[:cut]], te_in[order[cut:]] = True, True
    med, iqr = fit_scaler(Xr_tr[tr_in])
    Ztr, Zva = apply_scaler(Xr_tr[tr_in], med, iqr), apply_scaler(Xr_tr[te_in], med, iqr)
    best, best_mse = None, np.inf
    for hp in CAL_HPO_GRID:
        rf = fit_rf(Ztr, y_tr[tr_in], hp, derive_seed(MASTER_SEED, "rf", rep_seed))
        mse = float(np.mean((y_tr[te_in] - rf.predict(Zva)) ** 2))
        if mse < best_mse:
            best, best_mse = hp, mse
    return best


def run_rep_fold(Xr_tr, Xp_tr, y_tr, Xr_te, Xp_te, y_te, days_te, rep_seed: int,
                 pday_tr=None, use_hpo: bool = True, fixed_hp: dict | None = None,
                 sham_trs: list | None = None, sham_tes: list | None = None) -> pd.DataFrame:
    """v1.1 fixed evaluation: P = [Xr, Xp_bundle] concatenated (never Xp alone).

    Each group gets its own fold-train scaler (no cross-group sharing).
    S estimator = per-issue median of the full 100-sham panel.
    """
    if fixed_hp is not None:
        hp = fixed_hp
    else:
        hp = (inner_select(Xr_tr, y_tr, pday_tr, rep_seed)
              if (pday_tr is not None and use_hpo) else CAL_RF_PARAMS)
    # R
    med_r, iqr_r = fit_scaler(Xr_tr)
    Ztr_r, Zte_r = apply_scaler(Xr_tr, med_r, iqr_r), apply_scaler(Xr_te, med_r, iqr_r)
    # P = R + Xp (v1.1 fix)
    Xrp_tr = np.concatenate([Xr_tr, Xp_tr], axis=1)
    Xrp_te = np.concatenate([Xr_te, Xp_te], axis=1)
    assert Xrp_tr.shape[1] == Xr_tr.shape[1] + Xp_tr.shape[1]
    med_p, iqr_p = fit_scaler(Xrp_tr)
    Ztr_p, Zte_p = apply_scaler(Xrp_tr, med_p, iqr_p), apply_scaler(Xrp_te, med_p, iqr_p)
    s = derive_seed(MASTER_SEED, "rf", rep_seed)
    rf_r = fit_rf(Ztr_r, y_tr, hp, s)
    rf_p = fit_rf(Ztr_p, y_tr, hp, s)
    pr_r, pr_p = rf_r.predict(Zte_r), rf_p.predict(Zte_p)
    dr = daily_rmse(y_te, pr_r, days_te)
    dp = daily_rmse(y_te, pr_p, days_te)
    tab = dr.merge(dp, on="day", suffixes=("_r", "_p"))
    if sham_trs:
        preds = []
        for Xs_tr, Xs_te in zip(sham_trs, sham_tes):
            Xrs_tr = np.concatenate([Xr_tr, Xs_tr], axis=1)
            Xrs_te = np.concatenate([Xr_te, Xs_te], axis=1)
            assert Xrs_tr.shape[1] == Xrp_tr.shape[1], "sham added must equal P added"
            med_s, iqr_s = fit_scaler(Xrs_tr)
            rf_s = fit_rf(apply_scaler(Xrs_tr, med_s, iqr_s), y_tr, hp, s)
            preds.append(rf_s.predict(apply_scaler(Xrs_te, med_s, iqr_s)))
        pr_s = np.median(np.column_stack(preds), axis=1)
        ds = daily_rmse(y_te, pr_s, days_te).rename(columns={"rmse": "rmse_s", "n": "n_s"})
        tab = tab.merge(ds, on="day")
    tab["hp_mf"] = hp["max_features"]
    tab["hp_ml"] = hp["min_samples_leaf"]
    return tab


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--pilot", action="store_true",
                    help="5 reps x 1 missing(mobs) x SNR{0.5,1.0}+neg, core4/quad only")
    ap.add_argument("--bundle", type=str, default="core4x1",
                    choices=["core4x1", "top6x2", "full24"])
    ap.add_argument("--dforms", type=str, default="quad,linear,regime",
                    help="comma list among quad,linear,regime")
    ap.add_argument("--snrs", type=str, default="",
                    help="comma SNR list override, e.g. '0.5,1.0'")
    ap.add_argument("--conds", type=str, default="",
                    help="comma cond list override, e.g. 'mobs' or 'm0,m10,mobs'")
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--rho", type=float, default=RHO_AR1)
    ap.add_argument("--resume", action="store_true",
                    help="resume: skip (dform,cond,type,snr,rep) already in rows file")
    args = ap.parse_args()
    bundle = args.bundle
    dforms = [x for x in args.dforms.split(",") if x]
    for d in dforms:
        if d not in ALL_DFORMS:
            raise ValueError(f"unknown dform: {d}")
    snr_levels = [float(x) for x in args.snrs.split(",")] if args.snrs else list(ALL_SNRS)
    cond_names = [x for x in args.conds.split(",") if x] if args.conds else list(ALL_CONDS.keys())
    for c in cond_names:
        if c not in ALL_CONDS:
            raise ValueError(f"unknown cond: {c}")
    conds = [(c, ALL_CONDS[c]) for c in cond_names]
    rho = float(args.rho)
    binfo = BUNDLES[bundle]

    log = {"started_at_utc": utcnow(), "phase": "F4-calibration-v1.1", "bundle": bundle}
    fr = verify_freeze()
    log["freeze_check"] = fr
    run_id = (f"{utcnow().replace(':','').replace('+00:00','Z')}"
              f"_{fr['manifest'][:8]}_f4cal_{bundle}")
    log["run_id"] = run_id
    rundir = REPO / "runs" / run_id
    rundir.mkdir(parents=True, exist_ok=True)
    (REPO / "tables").mkdir(exist_ok=True)
    (REPO / "reports").mkdir(exist_ok=True)
    (REPO / "audit").mkdir(exist_ok=True)
    if fr["mismatch"]:
        print(json.dumps({"GATE": "ERROR", "reason": "freeze mismatch", "detail": fr}, indent=2))
        (rundir / "checkpoint.json").write_text(json.dumps(log, indent=2))
        sys.exit(3)

    print(f"[F4-cal] building dev matrices (bundle={bundle}) ...", flush=True)
    M = build_dev_matrices()
    Xr, Xp_full, Y, days, times = M["Xr"], M["Xp_lag"], M["Y"], M["days"], M["times"]
    pnames = M["pnames"]
    bidx = bundle_indices(pnames, bundle)
    Xp = Xp_full[:, bidx]
    assert Xp.shape[1] == binfo["added"], (Xp.shape, binfo)
    assert Xr.shape[1] + Xp.shape[1] == binfo["total"]
    folds = day_folds(days)
    udays = sorted(pd.unique(days).tolist())
    n = len(Y)
    log.update({k: M[k] for k in ("n_5min", "qc_rate", "build_s")})
    log.update({"n_issues": int(n), "n_days": int(len(udays)),
                "folds": [{"n_train": int(a.sum()), "n_test": int(b.sum())}
                          for a, b in folds],
                "r_dim": int(Xr.shape[1]), "p_added": int(Xp.shape[1]),
                "p_total": int(Xr.shape[1] + Xp.shape[1]),
                "bundle": bundle, "bundle_info": binfo,
                "cal_rf": CAL_RF_PARAMS, "hpo_subgrid": CAL_HPO_GRID})

    print("[F4-cal] building 100 shams (dev only) ...", flush=True)
    r5, p5 = M["r5"], M["p5_full"]
    fs = build_formula_shams(r5, 34)
    dm = build_dimensional_shams(r5, 33)
    dev_mask5 = np.isfinite(p5["TI"].values)
    st, rep_valid = build_statistical_shams(p5, dev_mask5, 33)
    n_sham = sum(1 for k in list(fs) + list(dm) + list(st) if not k.startswith("__"))
    rep_valid.to_csv(REPO / "audit" / "sham_validity.csv", index=False)
    assert n_sham == 100, n_sham
    log["sham_parity_12cols"] = True
    Gfeat, ginfo = build_grff(Xr[folds[0][0]], Xr, Xp.shape[1])
    log["sham"] = {"n": int(n_sham), "validity": rep_valid["status"].value_counts().to_dict(),
                   "g": ginfo}

    print("[F4-cal] aligning 100-sham panel to issue rows ...", flush=True)
    _src = {"FS": fs, "DM": dm, "ST": st}
    all_keys = ([f"FS{j:02d}" for j in range(34)] + [f"DM{j:02d}" for j in range(33)]
                + [f"ST{j:02d}" for j in range(33)])
    grid_time = M["r5"]["time"].values
    Tarr = M["sub"]["issue_time"].values
    Tparr = M["tprev"]
    sham_mats: dict[str, np.ndarray] = {}
    sham_names_ref = None
    for key in all_keys:
        Xs_full, snames = sham_lag_matrix(_src[key[:2]][key], grid_time, Tarr, Tparr)
        assert Xs_full.shape == Xp_full.shape, (key, Xs_full.shape, Xp_full.shape)
        sidx = sham_bundle_indices(snames, bundle)
        assert sidx == bidx, "sham slice must mirror P slice positionally"
        sham_mats[key] = Xs_full[:, sidx]
        if sham_names_ref is None:
            sham_names_ref = snames
    assert all(v.shape == Xp.shape for v in sham_mats.values())
    log["panel"] = {"keys": len(all_keys), "bundle": bundle,
                    "hash": sha256_of_array(np.column_stack([sham_mats[k][:, 0] for k in all_keys[:9]]))}

    from sklearn.linear_model import Ridge
    ri = Xp_full[:, pnames.index("P_Ri_g@0")]
    ti_ = Xp_full[:, pnames.index("P_TI@0")]
    mu1, sd1 = float(np.mean(ri)), float(np.std(ri)) + 1e-12
    mu2, sd2 = float(np.mean(ti_)), float(np.std(ti_)) + 1e-12
    z1, z2 = (ri - mu1) / sd1, (ti_ - mu2) / sd2
    S_by_form = {}
    for dform in dforms:
        s = build_S(z1, z2, dform)
        s = (s - float(np.mean(s))) / (float(np.std(s)) + 1e-12)
        S_by_form[dform] = s
    var_s = {k: float(np.var(v)) for k, v in S_by_form.items()}
    fold_ops = []
    for ftr, _fte in folds:
        med0, iqr0 = fit_scaler(Xr[ftr])
        rg = Ridge(alpha=1.0).fit(apply_scaler(Xr[ftr], med0, iqr0), Y[ftr])
        base = rg.predict(apply_scaler(Xr, med0, iqr0))
        fold_ops.append({"base": base,
                         "base_rmse_tr": float(np.sqrt(np.mean((Y[ftr] - base[ftr]) ** 2)))})
    day_code = pd.Series(days).map({d: i for i, d in enumerate(udays)}).values
    log["synth"] = {"ridge_alpha": 1.0, "rho_ar1": rho, "var_S": var_s,
                    "dforms": dforms,
                    "folds": [{"base_rmse_train": o["base_rmse_tr"]} for o in fold_ops]}

    if args.pilot:
        dforms_run = ["quad"]
        conds_run = [("mobs", OBSERVED_RATE)]
        tasks = [("pos", 0.5), ("pos", 1.0), ("neg", None)]
        reps = 5
    else:
        dforms_run = dforms
        conds_run = conds
        tasks = [("pos", s) for s in snr_levels] + [("neg", None)]
        reps = int(args.reps)
    log["grid"] = {"dforms": dforms_run, "snrs": snr_levels,
                   "conds": [c for c, _ in conds_run], "reps": reps, "rho": rho}

    rows = []
    ckpt = {"run_id": run_id, "done": 0,
            "total": len(dforms_run) * len(conds_run) * len(tasks) * reps}
    # Incremental rows file (crash-safe): one append per rep, resume by key.
    rows_file = REPO / "tables" / f"calibration_rows_{bundle}.csv"
    done_keys: set[tuple] = set()
    if not args.pilot and rows_file.exists():
        try:
            prev = pd.read_csv(rows_file)
            for t in prev.itertuples(index=False):
                done_keys.add((t.bundle, t.dform, t.cond, t.type, str(t.snr), int(t.rep)))
            print(f"[F4-cal] resume: {len(done_keys)} rows already in {rows_file.name}", flush=True)
        except Exception as e:
            print(f"[F4-cal] resume read failed ({e}); starting fresh", flush=True)
    if not args.pilot and not rows_file.exists():
        pd.DataFrame(columns=["bundle", "dform", "cond", "type", "snr", "rep", "detect",
                              "detect_pr", "detect_ps", "est", "lo", "hi", "est_ps",
                              "lo_ps", "hi_ps", "rmse_r", "rmse_p", "rmse_s",
                              "n_days", "hp", "note"]).to_csv(rows_file, index=False)

    def flush_row(row: dict) -> None:
        pd.DataFrame([row]).to_csv(rows_file, mode="a", header=False, index=False)

    t00 = time.time()
    skipped = 0
    for dform in dforms_run:
        S = S_by_form[dform]
        vs = var_s[dform]
        for cname, rate in conds_run:
            for typ, snr in tasks:
                for r in range(reps):
                    key = (bundle, dform, cname, typ, str(snr if snr else "neg"), r)
                    if not args.pilot and key in done_keys:
                        skipped += 1
                        ckpt["done"] += 1
                        continue
                    seed = derive_seed(MASTER_SEED,
                                       "semisynth_positive" if typ == "pos" else "semisynth_negative",
                                       {"m0": 0, "m10": 10_000, "mobs": 20_000}[cname] + r)
                    rng = np.random.Generator(np.random.PCG64(seed))
                    w = ar1_noise(n, rho, rng)
                    keep = rng.random(n) >= rate
                    row_base = {"bundle": bundle, "dform": dform, "cond": cname,
                                "type": typ, "snr": snr if snr else "neg", "rep": r}
                    pool = []
                    rep_ok, rep_note = True, ""
                    for (ftr, fte), ops in zip(folds, fold_ops):
                        c = float(np.sqrt(snr / vs)) if typ == "pos" else 0.0
                        tgt = ops["base"] + (c * S if typ == "pos" else 0.0) + w
                        idx_tr = np.where(ftr & keep)[0]
                        idx_te = np.where(fte & keep)[0]
                        if len(idx_tr) < 200 or len(idx_te) < 40:
                            rep_ok, rep_note = False, "too-few-rows"
                            break
                        try:
                            pool.append(run_rep_fold(
                                Xr[idx_tr], Xp[idx_tr], tgt[idx_tr],
                                Xr[idx_te], Xp[idx_te], tgt[idx_te],
                                days[idx_te], rep_seed=(seed % 1_000_000) + len(pool),
                                pday_tr=day_code[idx_tr], use_hpo=True,
                                sham_trs=[sham_mats[k][idx_tr] for k in all_keys],
                                sham_tes=[sham_mats[k][idx_te] for k in all_keys]))
                        except Exception as e:
                            rep_ok, rep_note = False, f"rep-error:{type(e).__name__}"
                            break
                    if not rep_ok:
                        new_row = {**row_base, "detect": None, "note": rep_note}
                        rows.append(new_row)
                        if not args.pilot:
                            flush_row(new_row)
                        ckpt["done"] += 1
                        continue
                    m = pd.concat(pool, ignore_index=True).drop_duplicates("day")
                    if len(m) < 7 or "rmse_s" not in m.columns:
                        new_row = {**row_base, "detect": None, "note": "too-few-days"}
                        rows.append(new_row)
                        if not args.pilot:
                            flush_row(new_row)
                        ckpt["done"] += 1
                        continue
                    d_pr = (m["rmse_p"] - m["rmse_r"]).values
                    d_ps = (m["rmse_p"] - m["rmse_s"]).values
                    try:
                        est, lo, hi = moving_block_bootstrap_ci(d_pr, 7, 10000,
                                                                seed=seed % 1_000_000)
                        est_s, lo_s, hi_s = moving_block_bootstrap_ci(
                            d_ps, 7, 10000, seed=(seed % 1_000_000) + 77)
                    except Exception as e:
                        new_row = {**row_base, "detect": None,
                                     "note": f"rep-error:{type(e).__name__}"}
                        rows.append(new_row)
                        if not args.pilot:
                            flush_row(new_row)
                        ckpt["done"] += 1
                        continue
                    det_pr, det_ps = bool(hi < 0), bool(hi_s < 0)
                    rmse_r = float(np.sqrt(np.sum(m["rmse_r"].values ** 2 * m["n_r"].values)
                                           / np.sum(m["n_r"].values)))
                    rmse_p = float(np.sqrt(np.sum(m["rmse_p"].values ** 2 * m["n_p"].values)
                                           / np.sum(m["n_p"].values)))
                    rmse_s = float(np.sqrt(np.sum(m["rmse_s"].values ** 2 * m["n_s"].values)
                                           / np.sum(m["n_s"].values)))
                    new_row = {**row_base, "detect": bool(det_pr and det_ps),
                                 "detect_pr": det_pr, "detect_ps": det_ps,
                                 "est": est, "lo": lo, "hi": hi,
                                 "est_ps": est_s, "lo_ps": lo_s, "hi_ps": hi_s,
                                 "rmse_r": rmse_r, "rmse_p": rmse_p, "rmse_s": rmse_s,
                                 "n_days": int(len(m)),
                                 "hp": f"{m['hp_mf'].iloc[0]}/{m['hp_ml'].iloc[0]}"}
                    rows.append(new_row)
                    if not args.pilot:
                        flush_row(new_row)
                    ckpt["done"] += 1
                    if ckpt["done"] % 10 == 0:
                        ckpt["elapsed_s"] = round(time.time() - t00, 1)
                        ckpt["rows_file"] = str(rows_file)
                        ckpt["skipped"] = skipped
                        (rundir / "checkpoint.json").write_text(json.dumps(ckpt, indent=2))
                        print(f"[F4-cal] {ckpt['done']}/{ckpt['total']} "
                              f"elapsed={ckpt['elapsed_s']}s", flush=True)
    if args.pilot:
        df = pd.DataFrame(rows)
    else:
        # Cumulative rows file is the truth (crash-safe); filter to this grid.
        full = pd.read_csv(rows_file)
        df = full[(full.bundle == bundle) & (full.dform.isin(dforms_run))
                  & (full.cond.isin([c for c, _ in conds_run]))]
    grid_tag = f"{bundle}_{'+'.join(dforms_run)}_{'+'.join(c for c, _ in conds_run)}"
    out_csv = REPO / "tables" / f"calibration_results_{grid_tag}.csv"
    df.to_csv(out_csv, index=False)
    summ = []
    gate_ok = True
    for dform in dforms_run:
        for cname, _ in conds_run:
            d = {"bundle": bundle, "dform": dform, "cond": cname}
            for s in snr_levels:
                qs = df[df.type == "pos"].copy()
                qs = qs[(qs.dform == dform) & (qs.cond == cname) & (qs.snr.astype(str) == str(s))]
                qv = qs[qs["detect"].notna()]
                rate = float(qv["detect"].mean()) if len(qv) else float("nan")
                d[f"detect_snr{s}"] = round(rate, 4)
                d[f"n_valid_snr{s}"] = int(len(qv))
                for col, tag in (("detect_pr", "pr"), ("detect_ps", "ps")):
                    if col in qv.columns and len(qv):
                        d[f"{tag}_snr{s}"] = round(float(qv[col].mean()), 4)
                if s in GATE_SNRS and not (len(qv) >= 50 and rate >= 0.80):
                    gate_ok = False
            qn = df[(df.dform == dform) & (df.cond == cname) & (df.type == "neg")]
            qnv = qn[qn["detect"].notna()]
            fp = float(qnv["detect"].mean()) if len(qnv) else float("nan")
            d["false_positive"] = round(fp, 4)
            d["n_valid_neg"] = int(len(qnv))
            if not (len(qnv) >= 50 and fp <= 0.075):
                gate_ok = False
            summ.append(d)
    # pilot gate rule: too few reps -> report only, gate FAIL by n_valid rule
    sds = pd.DataFrame(summ)
    sds.to_csv(REPO / "tables" / f"calibration_summary_{grid_tag}.csv", index=False)
    log.update({"summary": summ, "gate": "PASS" if gate_ok else "FAIL",
                "finished_at_utc": utcnow(), "elapsed_s": round(time.time() - t00, 1)})
    (rundir / "checkpoint.json").write_text(json.dumps({**ckpt, **log}, indent=2))
    md = ["# F4 calibration report v1.1 (confirm targets never read)",
          f"run_id: {run_id}", "",
          f"freeze: {fr['manifest'][:12]}... verified (concordance amendment excluded)",
          f"bundle: {bundle} {binfo}; dforms: {dforms_run}",
          f"dev issues: {n} over {len(udays)} days; "
          f"folds (n_train, n_test): {[(int(a.sum()), int(b.sum())) for a, b in folds]}; "
          f"AR1 rho={rho}; "
          f"R dim {Xr.shape[1]}, P added {Xp.shape[1]} (R+Xp fix); HPO {len(CAL_HPO_GRID)}-point subgrid",
          f"shams: {n_sham} (34/33/33) median; validity: "
          f"{rep_valid['status'].value_counts().to_dict()}; G-RFF sigma={ginfo['sigma']:.3f}", "",
          "## Gate summary (detection >= .80 at SNR .5/1.0 per (dform,cond); FP <= .075)",
          to_md(sds),
          "",
          f"GATE={'PASS' if gate_ok else 'FAIL'}",
          "FAIL -> do NOT unseal confirm; write CALIBRATION_FAILED handoff (F6 inherits report)."]
    (REPO / "reports" / f"calibration_{grid_tag}.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"GATE": "PASS" if gate_ok else "FAIL", "summary": summ}, indent=2))
    if args.out:
        Path(args.out).write_text("PASS" if gate_ok else "FAIL")
    sys.exit(0 if gate_ok else 4)


if __name__ == "__main__":
    main()
