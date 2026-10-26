"""Throwaway probe: import frozen code, build dev matrices, time fits. READ-ONLY on repo."""
from __future__ import annotations

import importlib.util
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("<PC>/研究/広大シンポジウム/新研究 v1.1/perdigao_attribution_v1.1").resolve()
OUT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("p4cal", REPO / "scripts" / "p4_calibrate_v11.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["p4cal"] = mod
spec.loader.exec_module(mod)

t0 = time.time()
M = mod.build_dev_matrices()
print(f"build_dev_matrices: {time.time() - t0:.1f}s")
print("n_issues:", len(M["Y"]), "n_days:", len(pd.unique(M["days"])))
print("days:", sorted(pd.unique(M["days"])))
print("qc_rate:", M["qc_rate"], "n_5min:", M["n_5min"])
Xr, Xp_full = M["Xr"], M["Xp_lag"]
print("Xr", Xr.shape, "Xp_full", Xp_full.shape)

folds_a = mod.day_folds(M["days"])
print("folds_a:", [(int(a.sum()), int(b.sum())) for a, b in folds_a])

# dev-mirror 14d forward-chaining blocks
d0, d1 = np.datetime64("2016-11-29T00:00:00"), np.datetime64("2017-03-10T00:00:00")
starts = pd.date_range(pd.Timestamp(d0), pd.Timestamp(d1), freq="14D")
print("block starts:", [s.strftime("%Y-%m-%d") for s in starts])
times = pd.DatetimeIndex(M["times"])
folds_b = []
for s in starts[1:]:
    e = min(s + pd.Timedelta(days=14), pd.Timestamp(d1))
    tr = (np.asarray(times) < np.datetime64(s.to_pydatetime() - pd.Timedelta(hours=3)))
    te = ((np.asarray(times) >= np.datetime64(s.to_pydatetime())) & (np.asarray(times) < np.datetime64(e.to_pydatetime())))
    folds_b.append((s, e, int(tr.sum()), int(te.sum())))
for f in folds_b:
    print("fold", f)

# timing: HPO-ish single fit
warnings.filterwarnings("ignore", category=UserWarning)
from perdigao_attr.p4lib import apply_scaler, fit_rf, fit_scaler  # noqa: E402

ftr = folds_a[0][0]
med, iqr = fit_scaler(Xr[ftr])
Z = apply_scaler(Xr[ftr], med, iqr)
y = M["Y"][ftr]
hp = {"n_estimators": 500, "max_features": 0.7, "min_samples_leaf": 20, "max_depth": None}
t1 = time.time()
rf = fit_rf(Z, y, hp, 12345)
print(f"RF 500-tree fit (R, 44 cols): {time.time() - t1:.2f}s, n_train={len(y)}")
Xrp = np.concatenate([Xr, Xp_full[:, mod.bundle_indices(M["pnames"], "core4x1")]], axis=1)
med2, iqr2 = fit_scaler(Xrp[ftr])
Z2 = apply_scaler(Xrp[ftr], med2, iqr2)
t2 = time.time()
rf = fit_rf(Z2, y, hp, 12345)
print(f"RF 500-tree fit (core4 P 48 cols): {time.time() - t2:.2f}s, n_train={len(y)}")
te_days = M["days"][folds_a[0][1]]
print("test rows fold1:", int(folds_a[0][1].sum()), "days:", sorted(pd.unique(te_days)))
print("SESOI:", 0.008862, "Y range:", float(np.min(M["Y"])), float(np.max(M["Y"])), "mean:", float(np.mean(M["Y"])))
