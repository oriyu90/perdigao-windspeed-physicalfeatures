#!/usr/bin/env python
"""参考実測 (reference measurement): P4-style primary statistics with the REAL
development-window target. Exploratory; the v1.1 frozen study is untouched.

Scope:
- v1.1 = CALIBRATION_FAILED / DELIVERED (gate 80% not reached; best detect 0.73).
  Frozen protocol: gate FAIL -> no primary fit; confirm window (2017-03-10 ..
  2017-06-17) sealed. This script measures on DEVELOPMENT data only (< 2017-03-10)
  with the real target Y = 1h-ahead mean U100, reusing v1.1 frozen code read-only.
- Never reads confirm data; never writes inside the repo; never creates exposure.jsonl.
- Output = exploratory reference values; does not unseal anything or change v1.1.

Measured (per bundle x foldset x fold x seed):
- R (44 cols), P = R + Xp_bundle (v1.1 fix), S = R + 100-sham per-issue median
  (34/33/33), G = R + Random-Fourier-Features (same added count), persistence
  context row (R_U100@0; no fit).
- HPO: F4 6-point R-only subgrid, winners reused for P/S/G (frozen rule).
- Foldsets:
  dayfolds : F4 day_folds (sorted-day halves, 2 folds) - identical to calibration.
  blocks14 : dev-mirror of the frozen outer design (14d forward-chaining eval
             blocks from DEV_START to DEV_END; train = issue_time < eval_start -
             3h purge; block at DEV_START skipped: no training data). Blocks with
             too few (train/test) rows are recorded with note and not fit.
- Pooled contrasts per seed: day-level mean diffs P-R, P-S, P-G, plus 7-day
  circular moving-block bootstrap (10000 reps) when pooled unique days >= 7
  (same estimator as F4); point mean otherwise.
- Detection is NOT defined for real y (no planted signal); CIs are descriptive.
- Rank of P among the 100 shams (fold-level %, and SE-weighted pooled %).

Safety rails asserted before/after:
- freeze manifest sha256 = 381b0422... with 13/14 files hash-checked
  (paper_code_concordance exempt per manifest rule; F3 seal intact);
- runs/exposure.jsonl absent; repo `git status --porcelain` empty (read-only use);
- max issue time < 2017-03-10T00:00Z (dev window only).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

SELF = Path(__file__).resolve().parents[1]
REPO = Path("<PC>/研究/広大シンポジウム/新研究 v1.1/perdigao_attribution_v1.1").resolve()

spec = importlib.util.spec_from_file_location("p4cal", REPO / "scripts" / "p4_calibrate_v11.py")
p4cal = importlib.util.module_from_spec(spec)
sys.modules["p4cal"] = p4cal
spec.loader.exec_module(p4cal)

from perdigao_attr.p4lib import (  # noqa: E402
    BUNDLES,
    apply_scaler,
    build_dimensional_shams,
    build_formula_shams,
    build_grff,
    build_statistical_shams,
    bundle_indices,
    daily_rmse,
    fit_rf,
    fit_scaler,
    moving_block_bootstrap_ci,
    sham_bundle_indices,
    sham_lag_matrix,
    sha256_of_array,
)
from perdigao_attr.seeds import MASTER_SEED, derive_seed  # noqa: E402

DEV_START = np.datetime64("2016-11-29T00:00:00")
DEV_END = np.datetime64("2017-03-10T00:00:00")
BLOCK_DAYS = 14
PURGE_HOURS = 3
MIN_TRAIN_ROWS = 200
MIN_TEST_ROWS = 40
BLOCK_BOOT_DAYS = 7
BOOT_REPS = 10000
FIT_SEED_OFFSET = 3000

BUNDLE_RANKS = {"core4x1": 0, "top6x2": 1, "full24": 2}
FOLDSET_RANKS = {"dayfolds": 0, "blocks14": 1}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[ref {datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def build_dev_mirror_blocks(times: np.ndarray) -> list[dict]:
    """Dev-mirror of the frozen outer eval design (14d forward chaining).

    Frozen confirm-split rule (p1_audit.py): eval = [start, min(start+14d, end));
    train = all issues with issue_time < eval_start - 3h purge.
    The block at DEV_START has no training data -> skip_first_block_no_train.
    """
    starts = pd.date_range(pd.Timestamp(DEV_START), pd.Timestamp(DEV_END), freq=f"{BLOCK_DAYS}D")
    t_arr = np.asarray(times, dtype="datetime64[ns]")
    info = []
    for k, s in enumerate(starts):
        e = min(s + pd.Timedelta(days=BLOCK_DAYS), pd.Timestamp(DEV_END))
        d_s, d_e = np.datetime64(s.to_pydatetime()), np.datetime64(e.to_pydatetime())
        d_p = np.datetime64(s.to_pydatetime() - pd.Timedelta(hours=PURGE_HOURS))
        tr_m, te_m = t_arr < d_p, (t_arr >= d_s) & (t_arr < d_e)
        n_tr, n_te = int(tr_m.sum()), int(te_m.sum())
        if k == 0:
            note = "skip_first_block_no_train"
        elif n_te == 0 and n_tr == 0:
            note = "empty_block_no_kept_rows"
        elif n_te == 0:
            note = "no_kept_issue_rows_in_eval_block"
        elif n_tr < MIN_TRAIN_ROWS:
            note = "too_few_train_rows"
        elif n_te < MIN_TEST_ROWS:
            note = "too_few_test_rows"
        else:
            note = ""
        info.append({"foldset": "blocks14", "fold": k, "eval_start": s.strftime("%Y-%m-%d"),
                     "eval_end": e.strftime("%Y-%m-%d"), "n_train": n_tr, "n_test": n_te,
                     "note": note, "tr_mask": tr_m, "te_mask": te_m})
    return info


def run_fold_real(Xr: np.ndarray, Y: np.ndarray, days: np.ndarray, rnames: list[str],
                  idx_tr: np.ndarray, idx_te: np.ndarray, rep_seed: int, bidx: list[int],
                  Xp_full: np.ndarray, daycode: np.ndarray,
                  sham_list_tr: list[np.ndarray], sham_list_te: list[np.ndarray]) -> dict:
    """One (fold, seed): R / P=R+Xp / 100-sham median S / G=R+RFF / persistence.

    Mirrors scripts/p4_calibrate_v11.py::run_rep_fold semantics: per-group
    fold-train median/IQR scaler; identical RF seed for R/P/shams; F4 6-point
    R-only HPO, winner reused for P/S/G."""
    Xr_tr, Xr_te = Xr[idx_tr], Xr[idx_te]
    y_tr, y_te = Y[idx_tr], Y[idx_te]
    days_te = days[idx_te]
    Xp_tr, Xp_te = Xp_full[idx_tr][:, bidx], Xp_full[idx_te][:, bidx]

    med_r, iqr_r = fit_scaler(Xr_tr)
    Ztr_r, Zte_r = apply_scaler(Xr_tr, med_r, iqr_r), apply_scaler(Xr_te, med_r, iqr_r)

    Xrp_tr = np.concatenate([Xr_tr, Xp_tr], axis=1)
    Xrp_te = np.concatenate([Xr_te, Xp_te], axis=1)
    assert Xrp_tr.shape[1] == Xr_tr.shape[1] + Xp_tr.shape[1], "P = R + Xp concat failed"
    med_p, iqr_p = fit_scaler(Xrp_tr)
    Ztr_p, Zte_p = apply_scaler(Xrp_tr, med_p, iqr_p), apply_scaler(Xrp_te, med_p, iqr_p)

    # G = R + RFF; RFF features from the FOLD-TRAIN R only (dev median heuristic);
    # group has its own fold-train scaler over the concatenated design (same rule).
    n_comp = Xp_tr.shape[1]
    # one call for train+te rows (median heuristic/W/b depend only on fold-train R
    # and the seed): identical math to the former two-call version, one RNG pass.
    gfeat_all, ginfo = build_grff(Xr_tr, np.vstack([Xr_tr, Xr_te]), n_comp)
    gfeat_tr, gfeat_te = gfeat_all[: Xr_tr.shape[0]], gfeat_all[Xr_tr.shape[0]:]
    Xrg_tr = np.concatenate([Xr_tr, gfeat_tr], axis=1)
    Xrg_te = np.concatenate([Xr_te, gfeat_te], axis=1)
    assert Xrg_tr.shape[1] == Xrp_tr.shape[1], "G added must equal P added"
    med_g, iqr_g = fit_scaler(Xrg_tr)
    Ztr_g, Zte_g = apply_scaler(Xrg_tr, med_g, iqr_g), apply_scaler(Xrg_te, med_g, iqr_g)

    hp = p4cal.inner_select(Xr_tr, y_tr, daycode[idx_tr], rep_seed)
    s_fit = derive_seed(MASTER_SEED, "rf", rep_seed)
    rf_r = fit_rf(Ztr_r, y_tr, hp, s_fit)
    rf_p = fit_rf(Ztr_p, y_tr, hp, s_fit)
    rf_g = fit_rf(Ztr_g, y_tr, hp, s_fit)
    pr_r, pr_p, pr_g = rf_r.predict(Zte_r), rf_p.predict(Zte_p), rf_g.predict(Zte_g)

    idx_b = rnames.index("R_U100@0")
    pr_b = Xr_te[:, idx_b]

    preds_s, rmse_shams = [], []
    for Xs_tr, Xs_te in zip(sham_list_tr, sham_list_te):
        Xrs_tr = np.concatenate([Xr_tr, Xs_tr], axis=1)
        Xrs_te = np.concatenate([Xr_te, Xs_te], axis=1)
        assert Xrs_tr.shape[1] == Xrp_tr.shape[1], "sham added must equal P added"
        med_s, iqr_s = fit_scaler(Xrs_tr)
        rf_s = fit_rf(apply_scaler(Xrs_tr, med_s, iqr_s), y_tr, hp, s_fit)
        p_s = rf_s.predict(apply_scaler(Xrs_te, med_s, iqr_s))
        preds_s.append(p_s)
        rmse_shams.append(float(np.sqrt(np.mean((y_te - p_s) ** 2))))
    pr_s = np.median(np.column_stack(preds_s), axis=1)

    dr = daily_rmse(y_te, pr_r, days_te).rename(columns={"rmse": "rmse_r", "n": "n_r"})
    dp = daily_rmse(y_te, pr_p, days_te).rename(columns={"rmse": "rmse_p", "n": "n_p"})
    ds = daily_rmse(y_te, pr_s, days_te).rename(columns={"rmse": "rmse_s", "n": "n_s"})
    dg = daily_rmse(y_te, pr_g, days_te).rename(columns={"rmse": "rmse_g", "n": "n_g"})
    db = daily_rmse(y_te, pr_b, days_te).rename(columns={"rmse": "rmse_b", "n": "n_b"})
    per_day = (dr.merge(dp, on="day").merge(ds, on="day")
               .merge(dg, on="day").merge(db, on="day"))
    num = per_day["n_r"].values
    assert num.min() > 0

    def sw(rmse: np.ndarray) -> float:
        return float(np.sqrt(np.sum(np.asarray(rmse, float) ** 2 * num) / np.sum(num)))

    pooled = {"rmse_r": sw(per_day["rmse_r"]), "rmse_p": sw(per_day["rmse_p"]),
              "rmse_s": sw(per_day["rmse_s"]), "rmse_g": sw(per_day["rmse_g"]),
              "rmse_b": sw(per_day["rmse_b"])}
    sham_rmses = np.asarray(rmse_shams, dtype=float)
    rank_pct = float(100.0 * np.mean(sham_rmses >= pooled["rmse_p"]))
    return {"per_day": per_day, "pooled": pooled, "sham_fold_rmses": sham_rmses,
            "rank_p_pct": rank_pct, "hp": f"{hp['max_features']}/{hp['min_samples_leaf']}",
            "n_train": int(len(idx_tr)), "n_test": int(len(idx_te)),
            "n_days": int(len(per_day)), "g_sigma": float(ginfo["sigma"])}


def se_weighted(rmse_all: np.ndarray, n_all: np.ndarray) -> float:
    return float(np.sqrt(np.sum(np.asarray(rmse_all, float) ** 2 * np.asarray(n_all))
                         / np.sum(n_all)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", type=str, default="core4x1,top6x2,full24")
    ap.add_argument("--foldsets", type=str, default="dayfolds,blocks14")
    ap.add_argument("--seeds", type=int, default=5,
                    help="paired seed count N; seed_i = 0..N-1 are used in order")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--tag", type=str, default="all")
    args = ap.parse_args()

    bundles = [b for b in args.bundles.split(",") if b]
    foldsets = [f for f in args.foldsets.split(",") if f]
    for b in bundles:
        if b not in BUNDLES:
            raise ValueError(f"unknown bundle {b}")
    for f in foldsets:
        if f not in ("dayfolds", "blocks14"):
            raise ValueError(f"unknown foldset {f}")
    n_seeds = int(args.seeds)
    assert 1 <= n_seeds <= 25

    out_tables, out_runs = SELF / "tables", SELF / "runs"
    out_tables.mkdir(exist_ok=True), out_runs.mkdir(exist_ok=True)

    # ---- pre-flight: frozen-code seal + repo cleanliness (read-only usage) ----
    fr = p4cal.verify_freeze()
    man_sha = fr["manifest"]
    assert man_sha.startswith("381b0422"), f"unexpected freeze manifest sha: {man_sha}"
    if fr["mismatch"]:
        print(json.dumps({"GATE": "ERROR", "reason": "freeze mismatch", "detail": fr}, indent=2))
        sys.exit(3)
    log(f"freeze verified: manifest {man_sha[:12]}..., 13-file hash check (concordance exempt)")
    exposure = REPO / "runs" / "exposure.jsonl"
    assert not exposure.exists(), "SEAL VIOLATION: exposure.jsonl exists"
    gs = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
    assert gs.returncode == 0 and gs.stdout.strip() == "", f"repo not clean:\n{gs.stdout}"

    run_id = f"{utcnow().replace(':', '').replace('+00:00', 'Z')}_{man_sha[:8]}_refrealdev_{args.tag}"
    rundir = out_runs / run_id
    rundir.mkdir(parents=True, exist_ok=True)

    log("building dev matrices (frozen builder; dev window only) ...")
    M = p4cal.build_dev_matrices()
    Xr, Xp_full, Y, days = M["Xr"], M["Xp_lag"], M["Y"], M["days"]
    rnames = M["rnames"]
    n = len(Y)
    udays = sorted(pd.unique(days).tolist())
    daycode = pd.Series(days).map({d: i for i, d in enumerate(udays)}).values
    log(f"issues n={n} over {len(udays)} days; Xr{Xr.shape}; Xp_full{Xp_full.shape}")
    assert len(Xr) == n == len(Y) == len(days)
    assert np.max(np.asarray(M["times"], dtype="datetime64[ns]")) < DEV_END, "dev window violated"

    log("building 100-sham panel (dev only) ...")
    r5, p5 = M["r5"], M["p5_full"]
    fs_panels = build_formula_shams(r5, 34)
    dm_panels = build_dimensional_shams(r5, 33)
    dev_mask5 = np.isfinite(p5["TI"].values)
    st_panels, rep_valid = build_statistical_shams(p5, dev_mask5, 33)
    n_sham = sum(1 for k in list(fs_panels) + list(dm_panels) + list(st_panels) if not k.startswith("__"))
    assert n_sham == 100, n_sham
    rep_valid.to_csv(out_tables / "ref_sham_validity.csv", index=False)
    all_keys = ([f"FS{j:02d}" for j in range(34)] + [f"DM{j:02d}" for j in range(33)]
                + [f"ST{j:02d}" for j in range(33)])
    _src = {"FS": fs_panels, "DM": dm_panels, "ST": st_panels}
    grid_time = r5["time"].values
    Tarr = M["sub"]["issue_time"].values
    Tparr = M["tprev"]
    sham_full: dict[str, tuple[np.ndarray, list[str]]] = {}
    for key in all_keys:
        Xs_full, snames = sham_lag_matrix(_src[key[:2]][key], grid_time, Tarr, Tparr)
        assert Xs_full.shape == Xp_full.shape, (key, Xs_full.shape, Xp_full.shape)
        sham_full[key] = (Xs_full, snames)
    log("sham panel aligned to issue grid (100 shams)")

    folds_a = [(k, a, b) for k, (a, b) in enumerate(p4cal.day_folds(days))]
    blocks = build_dev_mirror_blocks(np.asarray(M["times"], dtype="datetime64[ns]"))

    rows_file = out_tables / "ref_contrasts.csv"
    fold_file = out_tables / "ref_fold_rows.csv"
    if not rows_file.exists() or not args.resume:
        pd.DataFrame(columns=["bundle", "foldset", "fold", "seed_i", "est_pr", "lo_pr",
                              "hi_pr", "est_ps", "lo_ps", "hi_ps", "est_pg", "lo_pg",
                              "hi_pg", "rmse_r", "rmse_p", "rmse_s", "rmse_g", "rmse_b",
                              "n_days", "rank_p_pooled_pct", "hp", "ci_ok", "note"]
                     ).to_csv(rows_file, index=False)
    if not fold_file.exists() or not args.resume:
        pd.DataFrame(columns=["bundle", "foldset", "fold", "eval_start", "eval_end",
                              "seed_i", "rmse_r", "rmse_p", "rmse_s", "rmse_g", "rmse_b",
                              "rank_p_pct", "n_train", "n_test", "n_days", "hp", "note"]
                     ).to_csv(fold_file, index=False)
    if not args.resume:
        # reset append-only tables so a fresh run never appends onto prior rows;
        # the sham table makes rank_p_pooled_pct independently recomputable.
        pd.DataFrame(columns=["bundle", "foldset", "seed_i", "day", "rmse_r", "n_r",
                              "rmse_p", "n_p", "rmse_s", "n_s", "rmse_g", "n_g",
                              "rmse_b", "n_b"]).to_csv(out_tables / "ref_days_rows.csv", index=False)
        pd.DataFrame(columns=["bundle", "foldset", "fold", "eval_start", "eval_end",
                              "seed_i", "sham_key", "rmse_sham"]).to_csv(
            out_tables / "ref_sham_fold_rmse.csv", index=False)
    done_keys: set[tuple] = set()
    if args.resume and rows_file.exists():
        try:
            prev = pd.read_csv(rows_file)
            pooled_prev = prev[prev["fold"] == "pooled"]
            for t in pooled_prev.itertuples(index=False):
                done_keys.add((t.bundle, t.foldset, int(t.seed_i)))
            log(f"resume: {len(done_keys)} pooled keys already done")
        except Exception as e:
            log(f"resume read failed ({e}); starting fresh")

    meta_day = [{"fold": k, "eval_start": "-", "eval_end": "-", "note": ""} for k, _, _ in folds_a]
    meta_blk = [{f: d[f] for f in ("fold", "eval_start", "eval_end", "note")} for d in blocks]
    fold_meta = {"dayfolds": meta_day, "blocks14": meta_blk}
    app_rows = []
    for b in bundles:
        for fs_name in foldsets:
            for d in fold_meta[fs_name]:
                nm = {"bundle": b, "foldset": fs_name, "fold": d["fold"],
                      "eval_start": d["eval_start"], "eval_end": d["eval_end"],
                      "n_train": 0, "n_test": 0, "note": d["note"]}
                if fs_name == "dayfolds":
                    _, a, bb = folds_a[d["fold"]]
                    nm["n_train"], nm["n_test"] = int(a.sum()), int(bb.sum())
                else:
                    dd = blocks[d["fold"]]
                    nm["n_train"], nm["n_test"] = dd["n_train"], dd["n_test"]
                app_rows.append(nm)
    pd.DataFrame(app_rows).to_csv(out_tables / "ref_fold_appearance.csv", index=False)

    ckpt = {"run_id": run_id, "started_at_utc": utcnow(), "freeze_manifest": man_sha,
            "confirm_seal": "confirm window NOT read; exposure.jsonl NOT created (still absent)",
            "dev_window": ["2016-11-29T00:00Z", "2017-03-10T00:00Z"],
            "n_issues": int(n), "n_days": int(len(udays)),
            "bundles": bundles, "foldsets": foldsets, "n_seeds": n_seeds,
            "panel": {"dev_stats": {k: (list(map(float, v)) if isinstance(v, (list, tuple, np.ndarray)) else v)
                                    for k, v in M["dev_stats"].items()},
                      "qc_rate": M["qc_rate"], "n_5min": M["n_5min"], "build_s": M["build_s"],
                      "sham_validity": rep_valid["status"].value_counts().to_dict(),
                      "Xr_sha256": sha256_of_array(Xr), "Xp_full_sha256": sha256_of_array(Xp_full),
                      "Y_sha256": sha256_of_array(Y)},
            "done": 0}
    usable_counts = {}
    for fs_name in foldsets:
        if fs_name == "dayfolds":
            usable_counts[fs_name] = [f for f in fold_meta["dayfolds"] if not f["note"]]
        else:
            usable_counts[fs_name] = [f for f in fold_meta["blocks14"] if not f["note"]]
    ckpt["total"] = sum(len(usable_counts[f]) for f in foldsets) * n_seeds * len(bundles)
    log(f"tasks: {ckpt['total']}")

    t00 = time.time()
    contrast_rows: list[dict] = []
    for bundle in bundles:
        binfo = BUNDLES[bundle]
        bidx = bundle_indices(M["pnames"], bundle)
        assert Xp_full[:, bidx].shape[1] == binfo["added"]
        log(f"bundle {bundle}: added={binfo['added']} total={binfo['total']}")
        for fs_name in foldsets:
            if fs_name == "dayfolds":
                usable = [(k, a, bb) for k, a, bb in folds_a
                          if int(a.sum()) >= MIN_TRAIN_ROWS and int(bb.sum()) >= MIN_TEST_ROWS]
            else:
                usable = [(d["fold"], d["tr_mask"], d["te_mask"]) for d in blocks if not d["note"]]
            pooled_valid: list[dict] = []
            for k, ftr, fte in usable:
                idx_tr, idx_te = np.where(ftr)[0], np.where(fte)[0]
                sham_list_tr, sham_list_te = [], []
                sham_sn_ref = None
                for key in all_keys:
                    Xs_full, snames = sham_full[key]
                    sidx = sham_bundle_indices(snames, bundle)
                    assert sidx == bidx, f"sham slice must mirror P slice ({bundle})"
                    if sham_sn_ref is None:
                        sham_sn_ref = [snames[i] for i in sidx]
                    sham_list_tr.append(Xs_full[idx_tr][:, sidx])
                    sham_list_te.append(Xs_full[idx_te][:, sidx])
                dmeta = fold_meta[fs_name][k]
                for seed_i in range(n_seeds):
                    if args.resume and (bundle, fs_name, seed_i) in done_keys:
                        continue
                    idx = (BUNDLE_RANKS[bundle] * 10 + FOLDSET_RANKS[fs_name]) * 20 + k
                    rep_seed = FIT_SEED_OFFSET + idx * 100 + seed_i
                    try:
                        t1 = time.time()
                        res = run_fold_real(Xr, Y, days, rnames, idx_tr, idx_te, rep_seed,
                                            bidx, Xp_full, daycode, sham_list_tr, sham_list_te)
                    except Exception as e:
                        log(f"ERROR b={bundle} fs={fs_name} fold={k} seed={seed_i}: "
                            f"{type(e).__name__}: {str(e)[:120]}")
                        continue
                    res.update({"bundle": bundle, "foldset": fs_name, "fold": k, "seed_i": seed_i})
                    pooled_valid.append(res)
                    log(f"  {fs_name}/fold{k} ({dmeta['eval_start']}..{dmeta['eval_end']}) "
                        f"seed {seed_i}: rmse_r={res['pooled']['rmse_r']:.4f} "
                        f"rmse_p={res['pooled']['rmse_p']:.4f} rmse_s={res['pooled']['rmse_s']:.4f} "
                        f"rmse_g={res['pooled']['rmse_g']:.4f} rmse_b={res['pooled']['rmse_b']:.4f} "
                        f"rank={res['rank_p_pct']:.0f}% hp={res['hp']} ({time.time() - t1:.1f}s)")
            # ---- pooled contrasts per seed (disjoint day union across folds) ----
            for seed_i in range(n_seeds):
                rows = [r for r in pooled_valid if r["seed_i"] == seed_i]
                if not rows:
                    continue
                day_all = pd.concat([r["per_day"] for r in rows], ignore_index=True)
                assert not day_all["day"].duplicated().any(), "folds share a day - pooling rule violated"
                day_all = day_all.sort_values("day").reset_index(drop=True)
                d_pr = (day_all["rmse_p"] - day_all["rmse_r"]).values
                d_ps = (day_all["rmse_p"] - day_all["rmse_s"]).values
                d_pg = (day_all["rmse_p"] - day_all["rmse_g"]).values
                ci_ok = len(d_pr) >= BLOCK_BOOT_DAYS
                bseed = derive_seed(MASTER_SEED, "bootstrap",
                                    ((BUNDLE_RANKS[bundle] * 10 + FOLDSET_RANKS[fs_name]) * 20) * 1000 + seed_i)
                if ci_ok:
                    est_pr, lo_pr, hi_pr = moving_block_bootstrap_ci(
                        d_pr, BLOCK_BOOT_DAYS, BOOT_REPS, seed=bseed)
                    est_ps, lo_ps, hi_ps = moving_block_bootstrap_ci(
                        d_ps, BLOCK_BOOT_DAYS, BOOT_REPS, seed=bseed + 77)
                    est_pg, lo_pg, hi_pg = moving_block_bootstrap_ci(
                        d_pg, BLOCK_BOOT_DAYS, BOOT_REPS, seed=bseed + 154)
                else:
                    est_pr, lo_pr, hi_pr = float(np.mean(d_pr)), None, None
                    est_ps, lo_ps, hi_ps = float(np.mean(d_ps)), None, None
                    est_pg, lo_pg, hi_pg = float(np.mean(d_pg)), None, None

                def pool(col: str) -> float:
                    return se_weighted(np.concatenate([r["per_day"][col].values for r in rows]),
                                       np.concatenate([r["per_day"]["n_r"].values for r in rows]))
                # pooled sham rank: SE-weighted pooled per-sham RMSE across folds
                acc = np.zeros(next(iter(rows))["sham_fold_rmses"].shape, dtype=float)
                tot = 0.0
                for r in rows:
                    n_f = r["n_test"]
                    acc += r["sham_fold_rmses"] ** 2 * n_f
                    tot += n_f
                sham_pool_rmse = np.sqrt(acc / tot)
                rank_pool = float(100.0 * np.mean(sham_pool_rmse >= pool("rmse_p"))) if tot else None
                # persist per-sham RMSEs (pooled + fold-level) so every pooled rank
                # can be recomputed from tables alone
                sham_rows = [{"bundle": bundle, "foldset": fs_name, "fold": "pooled",
                              "eval_start": "-", "eval_end": "-", "seed_i": seed_i,
                              "sham_key": key, "rmse_sham": float(rm)}
                             for key, rm in zip(all_keys, sham_pool_rmse)]
                for r in rows:
                    dm_r = fold_meta[fs_name][r["fold"]]
                    sham_rows.extend({"bundle": bundle, "foldset": fs_name,
                                      "fold": r["fold"], "eval_start": dm_r["eval_start"],
                                      "eval_end": dm_r["eval_end"], "seed_i": seed_i,
                                      "sham_key": key, "rmse_sham": float(rm)}
                                     for key, rm in zip(all_keys, r["sham_fold_rmses"]))
                sham_file = out_tables / "ref_sham_fold_rmse.csv"
                pd.DataFrame(sham_rows).to_csv(sham_file, mode="a",
                                               header=not sham_file.exists(), index=False)

                crow = {"bundle": bundle, "foldset": fs_name, "fold": "pooled", "seed_i": seed_i,
                        "est_pr": est_pr, "lo_pr": lo_pr, "hi_pr": hi_pr,
                        "est_ps": est_ps, "lo_ps": lo_ps, "hi_ps": hi_ps,
                        "est_pg": est_pg, "lo_pg": lo_pg, "hi_pg": hi_pg,
                        "rmse_r": pool("rmse_r"), "rmse_p": pool("rmse_p"),
                        "rmse_s": pool("rmse_s"), "rmse_g": pool("rmse_g"),
                        "rmse_b": pool("rmse_b"),
                        "n_days": int(len(day_all)),
                        "rank_p_pooled_pct": rank_pool,
                        "hp": ";".join(sorted({r["hp"] for r in rows})),
                        "ci_ok": bool(ci_ok),
                        "note": "" if ci_ok else "too_few_days_for_7d_block_ci"}
                contrast_rows.append(crow)
                pd.DataFrame([crow]).to_csv(rows_file, mode="a", header=False, index=False)
                for r in rows:
                    pd.DataFrame([{"bundle": bundle, "foldset": fs_name, "fold": r["fold"],
                                   "eval_start": fold_meta[fs_name][r["fold"]]["eval_start"],
                                   "eval_end": fold_meta[fs_name][r["fold"]]["eval_end"],
                                   "seed_i": seed_i, **r["pooled"], "rank_p_pct": r["rank_p_pct"],
                                   "n_train": r["n_train"], "n_test": r["n_test"],
                                   "n_days": r["n_days"], "hp": r["hp"], "note": ""}]
                                 ).to_csv(fold_file, mode="a", header=False, index=False)
                day_long = day_all.copy()
                day_long.insert(0, "seed_i", seed_i)
                day_long.insert(0, "foldset", fs_name)
                day_long.insert(0, "bundle", bundle)
                dayfile = out_tables / "ref_days_rows.csv"
                day_long.to_csv(dayfile, mode="a", header=not dayfile.exists(), index=False)
            ckpt["done"] += len(pooled_valid)
            ckpt["elapsed_s"] = round(time.time() - t00, 1)
            (rundir / "checkpoint.json").write_text(json.dumps(ckpt, indent=2))

    if contrast_rows:
        sr = pd.DataFrame(contrast_rows)
        summ = []
        for (b, fs_name), sub in sr.groupby(["bundle", "foldset"]):
            r = {"bundle": b, "foldset": fs_name, "n_seeds": int(len(sub)),
                 "n_days_max": int(sub["n_days"].max())}
            for cname, pref in (("P_minus_R", "pr"), ("P_minus_S", "ps"), ("P_minus_G", "pg")):
                v = sub[f"est_{pref}"].astype(float).dropna().values
                r[f"med_est_{cname}"] = float(np.median(v)) if len(v) else None
                r[f"min_est_{cname}"] = float(np.min(v)) if len(v) else None
                r[f"max_est_{cname}"] = float(np.max(v)) if len(v) else None
                his = sub[f"hi_{pref}"].dropna().astype(float)
                r[f"ci_all_hi_lt0_{cname}"] = bool(np.all(his < 0)) if len(his) else None
                r[f"ci_any_hi_lt0_{cname}"] = bool(np.any(his < 0)) if len(his) else None
            for c in ("rmse_r", "rmse_p", "rmse_s", "rmse_g", "rmse_b", "rank_p_pooled_pct"):
                v = sub[c].astype(float).dropna().values
                r[f"med_{c}"] = float(np.median(v)) if len(v) else None
            summ.append(r)
        pd.DataFrame(summ).to_csv(out_tables / "ref_summary.csv", index=False)
        ckpt["summary"] = summ

    ckpt["finished_at_utc"] = utcnow()
    ckpt["elapsed_s"] = round(time.time() - t00, 1)
    (rundir / "checkpoint.json").write_text(json.dumps(ckpt, indent=2))

    fr2 = p4cal.verify_freeze()
    assert fr2["manifest"] == man_sha and not fr2["mismatch"], "freeze changed during run"
    assert not exposure.exists(), "SEAL VIOLATION at finish"
    gs2 = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
    assert gs2.returncode == 0 and gs2.stdout.strip() == "", f"repo dirty after run:\n{gs2.stdout}"
    log(f"DONE run_id={run_id} contrast_rows={len(contrast_rows)} elapsed={ckpt['elapsed_s']}s")


if __name__ == "__main__":
    main()
