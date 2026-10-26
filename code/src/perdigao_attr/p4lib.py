"""P3 shared library: leak-free design matrices (R/P/sham/G), calibration + primary helpers.

Design use only; confirm-interval TARGET values must never be read here.
Confirm schema/masks (no target summaries) are handled by p1-style audit code,
and confirm targets are unsealed only in p3_primary.py after the calibration gate.

Conventions (frozen, from configs/protocol.yaml + feature_dag.yaml):
- 5-min issue grid, W=12 right-aligned input means, Y(T)=mean U100 over (T,T+1h].
- X = [F(T), F(T-5min)] lags (same alignment convention as P2 R0/R1).
- P bundle = all 12 AVAILABLE DAG features as one bundle (no reselection).
- R = all P parents / sufficient statistics + time + past target history.
- 100 shams: 34 formula-shuffle / 33 dimensional / 33 statistical, same added
  column count as P, generated from fixed seeds without reading confirm targets.
- G = Random Fourier Features, same added column count, bandwidth from dev-only
  median heuristic, fixed seed.
- Scaling: fold-train median/IQR; identical preprocessing for every group.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from netCDF4 import Dataset

from perdigao_attr.seeds import MASTER_SEED, derive_generator

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "configs"

G = 9.81
GAMMA_D = 0.0098
DZ = 80.0
W_PRIMARY = 12  # 1h in 5-min steps
PURGE = pd.Timedelta(hours=3)

# Frozen RF grid-center default used for calibration reps (member of frozen grid).
CAL_RF_PARAMS = {
    "n_estimators": 500,
    "max_features": 0.7,
    "min_samples_leaf": 20,
    "max_depth": None,
}

# P3 R base columns on the 5-min grid (canonical names; must all be P parents
# or sufficient statistics, time, or past-target carriers -- no new obs source).
R_BASE_5MIN = [
    "U100", "u100", "v100", "w100", "dir100",
    "U20", "u20", "v20",
    "T100", "T20", "tc100", "tc20",
    "var_u100", "var_v100", "var_w100",
    "cov_uw20", "cov_vw20", "cov_wT100",
    "theta_v100", "theta_v20",
    "sin_t", "cos_t",
]

P_FEATURES = [
    "tke", "sigma_u", "TI", "u_star20", "u_star_norm", "dtheta_v_dz",
    "N2", "dT_dz", "du_dz", "dv_dz", "Ri_g", "Ri_f",
]

# v1.1 bundles (frozen in configs/p_subset.yaml; mirrored here for slicing).
# core4x1 primary: (TI,N2,Ri_g,tke x @0) = 4 added / 48 total.
# top6x2 secondary: 6 feats x @0,@-1 = 12 added / 56 total.
# full24 secondary: all12 x @0,@-1 = 24 added / 68 total.
CORE4_FEATURES = ["TI", "N2", "Ri_g", "tke"]
TOP6_FEATURES = ["TI", "N2", "Ri_g", "Ri_f", "tke", "u_star_norm"]
BUNDLES = {
    "core4x1": {"features": list(CORE4_FEATURES), "lags": ["@0"], "added": 4, "total": 48},
    "top6x2": {"features": list(TOP6_FEATURES), "lags": ["@0", "@-1"], "added": 12, "total": 56},
    "full24": {"features": list(P_FEATURES), "lags": ["@0", "@-1"], "added": 24, "total": 68},
}


def bundle_indices(pnames: list[str], bundle: str = "core4x1") -> list[int]:
    """Column indices of the lagged P matrix belonging to a v1.1 bundle.

    pnames are like 'P_TI@0'/'P_TI@-1' (see add_lags). Sham lagged matrices
    use 'S_<feat>@lag' with the same feature order, so the same positional
    mapping applies after replacing the prefix.
    """
    if bundle not in BUNDLES:
        raise ValueError(f"unknown bundle: {bundle}")
    b = BUNDLES[bundle]
    want = {(f, lag) for f in b["features"] for lag in b["lags"]}
    idx = []
    for i, nm in enumerate(pnames):
        # nm like 'P_TI@0' -> feat 'TI', lag '@0'
        body = nm.split("_", 1)[1] if "_" in nm else nm
        if "@" in body:
            feat, lag = body.rsplit("@", 1)
            lag = "@" + lag
        else:
            feat, lag = body, "@0"
        if (feat, lag) in want:
            idx.append(i)
    if len(idx) != b["added"]:
        raise ValueError(f"bundle {bundle}: want {b['added']} cols, found {len(idx)} in {pnames}")
    return idx


def sham_bundle_indices(sham_names: list[str], bundle: str = "core4x1") -> list[int]:
    """Same as bundle_indices but for sham lagged names ('S_<feat>@lag')."""
    if bundle not in BUNDLES:
        raise ValueError(f"unknown bundle: {bundle}")
    b = BUNDLES[bundle]
    want = {(f, lag) for f in b["features"] for lag in b["lags"]}
    idx = []
    for i, nm in enumerate(sham_names):
        body = nm.split("_", 1)[1] if "_" in nm else nm
        if "@" in body:
            feat, lag = body.rsplit("@", 1)
            lag = "@" + lag
        else:
            feat, lag = body, "@0"
        if (feat, lag) in want:
            idx.append(i)
    if len(idx) != b["added"]:
        raise ValueError(f"sham bundle {bundle}: want {b['added']}, found {len(idx)}")
    return idx


# ---------------------------------------------------------------- loaders ---
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


def load_mapping() -> dict:
    contract = yaml.safe_load((CFG / "data_contract.yaml").read_text())
    assert contract["tower"] == "tse13", contract["tower"]
    return dict(contract["mapping"])


def load_5min(t0: np.datetime64, t1: np.datetime64, tower: str = "tse13") -> pd.DataFrame:
    """Load 5-min base series for [t0, t1). Values (design use must be justified by caller)."""
    mapping = load_mapping()
    nc_files = sorted((REPO / "data" / "raw").glob("isfs_qc_tiltcor_*.nc"))
    series: dict[str, list] = {}
    times_all: list = []
    for f in nc_files:
        ds = Dataset(str(f), "r")
        t = file_times(ds)
        keep = (t >= t0) & (t < t1)
        if not keep.any():
            ds.close()
            continue
        sites = ["".join(r.astype(str)).strip() for r in np.asarray(ds.variables["sites"][:])]
        ti = sites.index(tower)
        idx = np.where(keep)[0]
        times_all.append(t[idx])
        for canon, vname in mapping.items():
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


def qc_keep_mask(df: pd.DataFrame) -> np.ndarray:
    """Primary QC exclusions (ldiag + tower-shadow sector). No target readout."""
    l20 = df["qc_ldiag20"].values
    l100 = df["qc_ldiag100"].values
    qc_bad = (l20 != 0) | (l100 != 0) | np.isnan(l20) | np.isnan(l100)
    dd = df["dir100"].values
    wake = (dd >= 310) & (dd <= 340) & ~np.isnan(dd)
    return ~(qc_bad | wake)


# ------------------------------------------------------- 5-min transforms ---
def add_r_derived(df5: pd.DataFrame) -> pd.DataFrame:
    """Add theta_v parents + periodic time to the 5-min frame."""
    d = df5.copy()
    d["theta_v100"] = d["tc100"].values + 273.15
    d["theta_v20"] = d["tc20"].values + 273.15
    hod = pd.to_datetime(d["time"]).dt.hour + pd.to_datetime(d["time"]).dt.minute / 60.0
    d["sin_t"] = np.sin(2 * np.pi * hod.values / 24.0)
    d["cos_t"] = np.cos(2 * np.pi * hod.values / 24.0)
    return d


def compute_p5(df5: pd.DataFrame, dev_stats: dict | None = None, for_calibration: bool = False) -> pd.DataFrame:
    """12 physics features on the 5-min grid (P1-frozen DAG expressions).

    dev_stats: clip/denom thresholds estimated on DEV-train only. When None,
    thresholds are estimated from the input frame (DEV design use only; the
    caller must pass DEV-derived stats when transforming confirm data).
    """
    d = df5
    thv100 = d["theta_v100"].values
    thv20 = d["theta_v20"].values
    dtheta = (thv100 - thv20) / DZ + GAMMA_D
    thref = (thv100 + thv20) / 2.0
    Tref = (d["T100"].values + d["T20"].values) / 2.0 + 273.15
    du = (d["u100"].values - d["u20"].values) / DZ
    dv = (d["v100"].values - d["v20"].values) / DZ
    var_u = d["var_u100"].values
    U = d["U100"].values
    sig_u = np.sqrt(np.maximum(var_u, 0.0))
    tke = 0.5 * (var_u + d["var_v100"].values + d["var_w100"].values)
    u_star = (d["cov_uw20"].values ** 2 + d["cov_vw20"].values ** 2) ** 0.25
    N2raw = (G / thref) * dtheta
    denom_g = du ** 2 + dv ** 2
    shear = d["cov_uw20"].values * du + d["cov_vw20"].values * dv
    Ri_g_raw = np.where(denom_g > 1e-12, N2raw / np.maximum(denom_g, 1e-12), np.nan)
    Ri_f_raw = np.where(
        np.abs(shear) > 1e-12,
        ((G / Tref) * d["cov_wT100"].values) / np.where(np.abs(shear) > 1e-12, shear, 1.0),
        np.nan,
    )
    if dev_stats is None:
        ok_u = U[U > 0.1]
        pTI = np.nanpercentile(np.where(U > 0.1, sig_u / np.maximum(U, 1e-9), np.nan), [0.5, 99.5])
        pUs = np.nanpercentile(np.where(U > 0.1, u_star / np.maximum(U, 1e-9), np.nan), [0.5, 99.5])
        dev_stats = {
            "TI_clip": [float(pTI[0]), float(pTI[1])],
            "ustar_clip": [float(pUs[0]), float(pUs[1])],
            "N2_neg": "clip-to-0",
            "Ri_g_max": 5.0,
            "Ri_f_clip": [-5.0, 5.0],
            "denom_floor": 1e-12,
            "U_floor": 0.1,
        }
    Uf = np.maximum(U, dev_stats["U_floor"])
    TI = np.clip(sig_u / Uf, *dev_stats["TI_clip"])
    TI = np.where(U > dev_stats["U_floor"], TI, np.nan)
    usn = np.clip(u_star / Uf, *dev_stats["ustar_clip"])
    usn = np.where(U > dev_stats["U_floor"], usn, np.nan)
    N2 = np.clip(N2raw, 0, None)
    Ri_g = np.minimum(np.where(np.isfinite(Ri_g_raw), Ri_g_raw, np.nan), dev_stats["Ri_g_max"])
    Ri_f = np.clip(Ri_f_raw, *dev_stats["Ri_f_clip"])
    out = pd.DataFrame({
        "time": d["time"],
        "tke": tke,
        "sigma_u": sig_u,
        "TI": TI,
        "u_star20": u_star,
        "u_star_norm": usn,
        "dtheta_v_dz": dtheta,
        "N2": N2,
        "dT_dz": (d["T100"].values - d["T20"].values) / DZ,
        "du_dz": du,
        "dv_dz": dv,
        "Ri_g": Ri_g,
        "Ri_f": Ri_f,
    })
    return out, dev_stats


# ------------------------------------------------------------- aggregation ---
def aggregate_issues(r5: pd.DataFrame, p5: pd.DataFrame, W: int = W_PRIMARY) -> pd.DataFrame:
    """Right-aligned input means Z(T) + future target means Y(T); full windows only.

    Contract: max_input_time (== issue T) <= issue_time < target_start (T+eps).
    """
    rnum = r5.drop(columns=["time"])
    pnum = p5.drop(columns=["time"])
    Zr = rnum.rolling(W, min_periods=W).mean()
    Zp = pnum.rolling(W, min_periods=W).mean()
    Y = r5["U100"].shift(-W).rolling(W, min_periods=W).mean()
    out = pd.DataFrame({"time": r5["time"], "Y": Y.values})
    for c in rnum.columns:
        out[f"R_{c}"] = Zr[c].values
    for c in pnum.columns:
        out[f"P_{c}"] = Zp[c].values
    out["issue_time"] = out["time"]
    out["max_input_time"] = out["time"]
    out["target_start"] = out["time"] + pd.to_timedelta(1, unit="s")
    out["target_end"] = out["time"] + pd.to_timedelta(W * 5, unit="min")
    out["day"] = pd.to_datetime(out["time"]).dt.strftime("%Y-%m-%d")
    out = out.dropna().reset_index(drop=True)
    assert ((out["max_input_time"] <= out["issue_time"]) & (out["issue_time"] < out["target_start"])).all()
    return out


def add_lags(agg: pd.DataFrame, prefix: str) -> tuple[np.ndarray, list[str]]:
    """X = [F(T), F(T-5min)] for columns starting with prefix."""
    cols = [c for c in agg.columns if c.startswith(prefix)]
    F = agg[cols].values
    X = np.concatenate([F[1:], F[:-1]], axis=1)
    names = [f"{c}@0" for c in cols] + [f"{c}@-1" for c in cols]
    return X, names


def common_mask(agg: pd.DataFrame) -> np.ndarray:
    """Complete-case over target + R parents (identical mask for all groups)."""
    need = [c for c in agg.columns if c.startswith("R_")] + ["Y"]
    return (~agg[need].isna().any(axis=1)).values


# ------------------------------------------------------------------ scaling ---
def fit_scaler(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(X, axis=0)
    q75, q25 = np.nanpercentile(X, [75, 25], axis=0)
    iqr = q75 - q25
    iqr[~np.isfinite(iqr) | (iqr < 1e-12)] = 1.0
    med[~np.isfinite(med)] = 0.0
    return med, iqr


def apply_scaler(X: np.ndarray, med: np.ndarray, iqr: np.ndarray) -> np.ndarray:
    return (X - med) / iqr


# -------------------------------------------------------------------- shams ---
def _p_parent_pool() -> list[str]:
    return [
        "U100", "u100", "v100", "w100", "U20", "u20", "v20",
        "T100", "T20", "tc100", "tc20", "var_u100", "var_v100", "var_w100",
        "cov_uw20", "cov_vw20", "cov_wT100", "theta_v100", "theta_v20",
    ]


def build_formula_shams(r5: pd.DataFrame, n: int, seed_index: int = 0) -> dict[str, pd.DataFrame]:
    """Formula-shuffle: same parent count / op count / diff order / added cols;
    only sign, height order, and parent mapping are broken. Confirm-blind."""
    rng = derive_generator(MASTER_SEED, "sham_formula", seed_index)
    pool = _p_parent_pool()
    avail = {c: r5[c].values.astype(float) for c in pool if c in r5.columns}
    keys = list(avail.keys())
    # Fixed broken mapping: random permutation of the pool (derangement-ish).
    perm = rng.permutation(len(keys))
    broken = {keys[i]: avail[keys[perm[i]]] for i in range(len(keys))}
    # height-swap pairs
    swaps = [("u100", "u20"), ("v100", "v20"), ("T100", "T20"), ("tc100", "tc20"),
             ("theta_v100", "theta_v20")]
    out: dict[str, pd.DataFrame] = {}
    for j in range(n):
        g = derive_generator(MASTER_SEED, "sham_formula", 1000 + j)
        use_swap = g.random(len(swaps)) < 0.5
        local = dict(broken)
        for (a, b), s in zip(swaps, use_swap):
            if s and a in local and b in local:
                local[a], local[b] = local[b], local[a]
        sgn = g.choice([-1.0, 1.0], size=12)
        U = local["U100"]
        Uf = np.maximum(np.abs(U), 0.1)
        su = np.sqrt(np.maximum(local["var_u100"], 0.0))
        us = (local["cov_uw20"] ** 2 + local["cov_vw20"] ** 2) ** 0.25
        dth = (local["theta_v100"] - local["theta_v20"]) / DZ + GAMMA_D
        thref = (local["theta_v100"] + local["theta_v20"]) / 2.0
        Tref = (local["T100"] + local["T20"]) / 2.0 + 273.15
        du = (local["u100"] - local["u20"]) / DZ
        dv = (local["v100"] - local["v20"]) / DZ
        N2r = (G / thref) * dth
        dg = du ** 2 + dv ** 2
        sh = local["cov_uw20"] * du + local["cov_vw20"] * dv
        feats = [
            0.5 * (local["var_u100"] + local["var_v100"] + local["var_w100"]),
            su,
            np.clip(su / Uf, 0, 5),
            us,
            np.clip(us / Uf, 0, 5),
            dth,
            np.clip(N2r, 0, None),
            (local["T100"] - local["T20"]) / DZ,
            du,
            dv,
            np.minimum(np.where(dg > 1e-12, np.clip(N2r, 0, None) / np.maximum(dg, 1e-12), 0.0), 5.0),
            np.clip(np.where(np.abs(sh) > 1e-12, ((G / Tref) * local["cov_wT100"]) / np.where(np.abs(sh) > 1e-12, sh, 1.0), 0.0), -5, 5),
        ]
        arr = np.column_stack([sgn[k] * np.nan_to_num(np.asarray(f, dtype=float), nan=0.0) for k, f in enumerate(feats)])
        out[f"FS{j:02d}"] = pd.DataFrame(arr, columns=[f"S_{c}" for c in P_FEATURES])
    out["__time__"] = r5[["time"]].reset_index(drop=True)
    return out


_DIM_VEC = {  # (length, time, temperature)
    "U100": (1, -1, 0), "u100": (1, -1, 0), "v100": (1, -1, 0), "w100": (1, -1, 0),
    "U20": (1, -1, 0), "u20": (1, -1, 0), "v20": (1, -1, 0),
    "T100": (0, 0, 1), "T20": (0, 0, 1), "tc100": (0, 0, 1), "tc20": (0, 0, 1),
    "theta_v100": (0, 0, 1), "theta_v20": (0, 0, 1),
    "var_u100": (2, -2, 0), "var_v100": (2, -2, 0), "var_w100": (2, -2, 0),
    "cov_uw20": (2, -2, 0), "cov_vw20": (2, -2, 0),
    "cov_wT100": (1, -1, 1),
}
_P_DIM = {  # target dimensions of the 12 P features
    "tke": (2, -2, 0), "sigma_u": (1, -1, 0), "TI": (0, 0, 0),
    "u_star20": (1, -1, 0), "u_star_norm": (0, 0, 0), "dtheta_v_dz": (-1, 0, 1),
    "N2": (0, -2, 0), "dT_dz": (-1, 0, 1), "du_dz": (0, -1, 0),
    "dv_dz": (0, -1, 0), "Ri_g": (0, 0, 0), "Ri_f": (0, 0, 0),
}
_EXP_GRID = [-2, -1, -0.5, 0.5, 1, 2]


def build_dimensional_shams(r5: pd.DataFrame, n: int, seed_index: int = 0) -> dict[str, pd.DataFrame]:
    """Dimension-matched shams: unit dimensions equal P's, but exponents and
    parent combos are fixed random (dev-data independent). Same extreme-value
    rules as P. Confirm-blind."""
    rng = derive_generator(MASTER_SEED, "sham_formula", seed_index)
    std = {}
    for c in _p_parent_pool():
        if c in r5.columns:
            v = r5[c].values.astype(float)
            m, s = np.nanmedian(v), np.nanstd(v)
            std[c] = (v - m) / (s if np.isfinite(s) and s > 1e-12 else 1.0)
    pool = list(std.keys())
    dims = np.array([_DIM_VEC[c] for c in pool], dtype=float)
    out: dict[str, pd.DataFrame] = {}
    for j in range(n):
        # NOTE: contract namespace set has no sham_dimensional; dimensional
        # shams reuse the sham_formula namespace with a disjoint index block.
        g = derive_generator(MASTER_SEED, "sham_formula", 2000 + j)
        cols = []
        for feat in P_FEATURES:
            target = np.array(_P_DIM[feat], dtype=float)
            exp = np.zeros(len(pool))
            # greedy random search for an exponent combo matching target dim
            found = None
            for _ in range(2000):
                k = int(g.integers(2, 5))
                idx = g.choice(len(pool), size=k, replace=False)
                e = np.array([_EXP_GRID[int(g.integers(len(_EXP_GRID)))] for _ in range(k)])
                if np.allclose(e @ dims[idx], target, atol=1e-9):
                    found = (idx, e)
                    break
            if found is None:  # fallback: dimensionless random combo
                idx = g.choice(len(pool), size=2, replace=False)
                e = np.array([1.0, -1.0])
                # force dimensionless by pairing same-dim parents
                d0 = dims[idx[0]]
                same = [i for i in range(len(pool)) if np.allclose(dims[i], d0)]
                idx = np.array([idx[0], same[int(g.integers(len(same)))]])
            else:
                idx, e = found
            mat = np.column_stack([np.nan_to_num(std[pool[i]], nan=0.0) for i in idx])
            # monomial on shifted-positive values to keep finite
            mat = np.sign(mat) * np.log1p(np.abs(mat))
            colv = np.exp(np.clip(mat @ e, -5, 5))
            colv = (colv - np.median(colv)) / (np.std(colv) + 1e-9)
            if _P_DIM[feat] == (0, 0, 0):
                pass
            elif feat in ("Ri_g",):
                colv = np.minimum(colv, 5.0)
            elif feat in ("Ri_f",):
                colv = np.clip(colv, -5, 5)
            elif feat in ("N2",):
                colv = np.clip(colv, 0, None)
            cols.append(np.nan_to_num(colv, nan=0.0))
        out[f"DM{j:02d}"] = pd.DataFrame(np.column_stack(cols), columns=[f"S_{c}" for c in P_FEATURES])
    out["__time__"] = r5[["time"]].reset_index(drop=True)
    return out


def iaaft_surrogate(x: np.ndarray, rng, iters: int = 20) -> np.ndarray:
    """Iterative AAFT surrogate: preserves marginal dist + approx autospectrum."""
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x)
    vals = x[ok]
    n = vals.size
    if n < 100:
        return x.copy()
    sorted_vals = np.sort(vals)
    # initial random shuffle
    r = vals[rng.permutation(n)]
    amp = np.abs(np.fft.rfft(vals))
    for _ in range(iters):
        f = np.fft.rfft(r)
        r = np.fft.irfft(amp * np.exp(1j * np.angle(f)), n=n)
        # rank remap to original marginal
        order = np.argsort(r)
        r[order] = sorted_vals
    out = np.full_like(x, np.nan)
    out[ok] = r
    return out


def build_statistical_shams(p5: pd.DataFrame, dev_mask_5min: np.ndarray, n: int,
                             seed_index: int = 0) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Statistical shams: dev-only IAAFT surrogates of each P column (marginal
    dist + missing rate + autocorr matched). Confirm-blind (dev only).

    Returns (shams, validity_report). Validity per sham: |skew|,|kurt|,lag1
    autocorrelation and missing-rate closeness. Failures are recorded as
    INVALID_CONTROL (whole sham), never partially kept.
    """
    from scipy import stats as _st

    reports = []
    out: dict[str, pd.DataFrame] = {}
    for j in range(n):
        cols = []
        for k, feat in enumerate(P_FEATURES):
            g = derive_generator(MASTER_SEED, "sham_statistical", 3000 + j * 13 + k)
            v = p5[feat].values.astype(float)
            miss = ~np.isfinite(v) | (~dev_mask_5min)
            surr = iaaft_surrogate(np.where(miss, np.nan, v), g)
            surr[miss] = np.nan
            cols.append(surr)
        arr = np.column_stack(cols)
        # validity on dev-valid entries
        flags = []
        for k, feat in enumerate(P_FEATURES):
            v = p5[feat].values.astype(float)
            s = arr[:, k]
            ok = np.isfinite(v) & np.isfinite(s) & dev_mask_5min
            if ok.sum() < 500:
                flags.append("too-few-valid")
                continue
            sk = abs(float(_st.skew(v[ok])) - float(_st.skew(s[ok])))
            ku = abs(float(_st.kurtosis(v[ok])) - float(_st.kurtosis(s[ok])))
            a1 = abs(float(pd.Series(v[ok]).autocorr(1) or 0.0) - float(pd.Series(s[ok]).autocorr(1) or 0.0))
            mr = abs(float((~np.isfinite(v)).mean()) - float((~np.isfinite(s)).mean()))
            passed = (sk < 0.5) and (ku < 1.0) and (a1 < 0.15) and (mr < 0.02)
            flags.append("PASS" if passed else "INVALID_CONTROL")
        status = "PASS" if all(f == "PASS" for f in flags) else "INVALID_CONTROL"
        out[f"ST{j:02d}"] = pd.DataFrame(np.where(np.isfinite(arr), arr, 0.0),
                                         columns=[f"S_{c}" for c in P_FEATURES])
        reports.append({"sham": f"ST{j:02d}", "status": status,
                        "detail": ";".join(f"{f}={fl}" for f, fl in zip(P_FEATURES, flags))})
    out["__time__"] = p5[["time"]].reset_index(drop=True)
    return out, pd.DataFrame(reports)


# ------------------------------------------------------------------------ G ---
def build_grff(Zr_train: np.ndarray, Zr_full: np.ndarray, n_components: int,
               seed_index: int = 0) -> tuple[np.ndarray, dict]:
    """Restricted generic representation: Random Fourier Features.

    Bandwidth from dev-train median heuristic; fixed seed. Same added column
    count as P-after-lags.
    """
    rng = derive_generator(MASTER_SEED, "rff", seed_index)
    med, iqr = fit_scaler(Zr_train)
    Zt = apply_scaler(Zr_train, med, iqr)
    Zf = apply_scaler(Zr_full, med, iqr)
    sub = Zt[rng.choice(Zt.shape[0], size=min(2000, Zt.shape[0]), replace=False)]
    from scipy.spatial.distance import pdist

    d = pdist(sub, metric="euclidean")
    sigma = float(np.median(d)) if d.size else 1.0
    sigma = max(sigma, 1e-6)
    gamma = 1.0 / (2 * sigma ** 2)
    d_in = Zt.shape[1]
    W = rng.normal(scale=np.sqrt(2 * gamma), size=(d_in, n_components))
    b = rng.uniform(0, 2 * np.pi, size=n_components)
    feat = np.sqrt(2.0 / n_components) * np.cos(Zf @ W + b)
    return feat, {"sigma": sigma, "gamma": gamma, "n_components": n_components}


def sham_lag_matrix(sham5: pd.DataFrame, grid_time: np.ndarray,
                    Tarr: np.ndarray, TprevArr: np.ndarray,
                    W: int = W_PRIMARY, prefix: str = "S_") -> tuple[np.ndarray, list[str]]:
    """Lagged sham issue matrix aligned to main rows WITHOUT re-dropna.

    Rolling means are positional on the shared 5-min grid; rows are picked by
    (T, Tprev) issue times supplied by the main pipeline, so alignment holds
    even where the main common mask (not applied here) removes rows.
    All sham 5-min frames are finite-filled by construction; issues always
    have full input windows, hence the output must be fully finite.
    """
    cols = [c for c in sham5.columns if c.startswith(prefix)]
    assert len(cols) == len(P_FEATURES), (len(cols), sham5.columns.tolist()[:3])
    Z = np.asarray(sham5[cols].rolling(W, min_periods=W).mean().values, dtype=float)
    t2row = {np.datetime64(t): i for i, t in enumerate(np.asarray(grid_time))}
    r0 = np.array([Z[t2row[np.datetime64(t)]] for t in np.asarray(Tarr)])
    r1 = np.array([Z[t2row[np.datetime64(t)]] for t in np.asarray(TprevArr)])
    X = np.concatenate([r0, r1], axis=1)
    if not np.isfinite(X).all():
        bad = int((~np.isfinite(X)).sum())
        raise ValueError(f"sham lagged matrix has {bad} non-finite entries")
    names = [f"{c}@0" for c in cols] + [f"{c}@-1" for c in cols]
    return X, names


# ------------------------------------------------------------------ RF/stats ---
def fit_rf(Xtr: np.ndarray, ytr: np.ndarray, params: dict, seed: int, n_jobs: int = 8):
    from sklearn.ensemble import RandomForestRegressor

    rf = RandomForestRegressor(
        n_estimators=int(params["n_estimators"]),
        max_features=params["max_features"],
        min_samples_leaf=int(params["min_samples_leaf"]),
        max_depth=params["max_depth"],
        random_state=int(seed % (2 ** 31 - 1)),
        n_jobs=n_jobs,
    )
    rf.fit(Xtr, ytr)
    return rf


def daily_rmse(y: np.ndarray, pred: np.ndarray, days: np.ndarray) -> pd.DataFrame:
    e = y - pred
    df = pd.DataFrame({"day": days, "se": e ** 2})
    g = df.groupby("day")["se"].mean()
    return pd.DataFrame({"day": g.index, "rmse": np.sqrt(g.values), "n": df.groupby("day").size().values})


def moving_block_bootstrap_ci(diff: np.ndarray, n_block: int = 7, reps: int = 10000,
                              seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    """Paired day-level mean-diff CI via moving (circular) block bootstrap."""
    rng = derive_generator(MASTER_SEED, "bootstrap", seed)
    d = np.asarray(diff, dtype=float)
    n = d.size
    if n < n_block:
        raise ValueError("too few days for block bootstrap")
    est = float(np.mean(d))
    n_blocks = int(np.ceil(n / n_block))
    starts = rng.integers(0, n, size=(reps, n_blocks))
    idx = (starts[:, :, None] + np.arange(n_block)[None, None, :]) % n
    samp = d[idx.reshape(reps, -1)[:, :n]]
    means = samp.mean(axis=1)
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return est, lo, hi


def ar1_noise(n: int, rho: float, rng) -> np.ndarray:
    w = rng.normal(size=n)
    x = np.empty(n)
    x[0] = w[0]
    for i in range(1, n):
        x[i] = rho * x[i - 1] + np.sqrt(1 - rho ** 2) * w[i]
    return (x - x.mean()) / (x.std() + 1e-12)


def sha256_of_array(a: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(a, dtype=np.float64).tobytes())
    return h.hexdigest()
