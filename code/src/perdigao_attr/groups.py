"""v1.1 group definitions: P = R + Xp (fix of v1.0 P_only bug).

- R: 44 cols (22 five-min parents x 2 lags @0/@-1 at issue time).
- P_core4 (primary): R + (TI, N2, Ri_g, tke x @0) = 48 total / +4 added.
- P_top12 (secondary): R + (TI, N2, Ri_g, Ri_f, tke, u_star_norm x @0,@-1) = 56 / +12.
- P_full24 (secondary): R + (12 features x @0,@-1) = 68 / +24.
- S_j: R + sham_j with the same added count as the corresponding P.
- G: R + RFF/spline with the same added count.

Preprocessing contract (F4 implementation): scaler (median/IQR) is fit
separately per group and per fold-train, never shared across groups.
All groups share the identical common mask and identical fit budget.

This module provides F1-level dimension/mask/ban contracts. Full P3
matrices (real physics/sham/RFF) are built in F4; here synthetic matrices
with the same shapes verify the contracts.
"""
from __future__ import annotations

import numpy as np

R_DIM = 44

P_FEATURES_ALL = [
    "tke", "sigma_u", "TI", "u_star20", "u_star_norm", "dtheta_v_dz",
    "N2", "dT_dz", "du_dz", "dv_dz", "Ri_g", "Ri_f",
]

CORE4_FEATURES = ["TI", "N2", "Ri_g", "tke"]
TOP6_FEATURES = ["TI", "N2", "Ri_g", "Ri_f", "tke", "u_star_norm"]

BUNDLES = {
    "core4x1": {"features": list(CORE4_FEATURES), "lags": ["@0"], "added": 4, "total": 48},
    "top6x2": {"features": list(TOP6_FEATURES), "lags": ["@0", "@-1"], "added": 12, "total": 56},
    "full24": {"features": list(P_FEATURES_ALL), "lags": ["@0", "@-1"], "added": 24, "total": 68},
}


def group_dims(bundle: str = "core4x1") -> tuple[int, int]:
    """Return (total, added) for a bundle name."""
    if bundle not in BUNDLES:
        raise ValueError(f"unknown bundle: {bundle}")
    b = BUNDLES[bundle]
    return int(b["total"]), int(b["added"])


def build_design_matrices(n_rows: int = 128, bundle: str = "core4x1", seed: int = 0):
    """Build synthetic R/Xp/Xs/Xg matrices with v1.1-correct shapes.

    Returns dict with Xr (n,44), Xp/Xs/Xg (n,added), Xrp/Xrs/Xrg (n,total),
    plus identical common_mask for all groups.
    """
    total, added = group_dims(bundle)
    rng = np.random.Generator(np.random.PCG64(seed))
    Xr = rng.normal(size=(n_rows, R_DIM))
    Xp = rng.normal(size=(n_rows, added))
    Xs = rng.normal(size=(n_rows, added))
    Xg = rng.normal(size=(n_rows, added))
    Xrp = np.concatenate([Xr, Xp], axis=1)
    Xrs = np.concatenate([Xr, Xs], axis=1)
    Xrg = np.concatenate([Xr, Xg], axis=1)
    assert Xrp.shape[1] == total == R_DIM + added
    assert Xrs.shape[1] == total
    assert Xrg.shape[1] == total
    mask = common_mask(Xrp, Xrs, Xrg)
    return {
        "Xr": Xr, "Xp": Xp, "Xs": Xs, "Xg": Xg,
        "Xrp": Xrp, "Xrs": Xrs, "Xrg": Xrg,
        "common_mask": mask, "total": total, "added": added,
    }


def common_mask(*mats: np.ndarray) -> np.ndarray:
    """Identical complete-case mask shared by all groups.

    F1 synthetic version: all-finite rows across every supplied matrix.
    F4 real version: complete-case over target+parents after QC exclusions,
    computed once and reused identically for R/P/S/G.
    """
    if not mats:
        raise ValueError("need at least one matrix")
    n = mats[0].shape[0]
    for m in mats:
        if m.shape[0] != n:
            raise ValueError("row count mismatch across groups")
    mask = np.ones(n, dtype=bool)
    for m in mats:
        mask &= np.isfinite(np.asarray(m, dtype=float)).all(axis=1)
    return mask


def fit_p_only(*args, **kwargs):
    """Banned legacy path: fitting on Xp alone (v1.0 bug). Always fails.

    v1.0 `p3_calibrate.py:284-290` fit rf_p on Xp (24 cols only) while sham
    used R+sham. v1.1 forbids this: P must be [Xr, Xp] concatenated.
    Any call to this function raises so regression tests FAIL if revived.
    """
    raise RuntimeError(
        "P_ONLY_BANNED: P must be R+Xp concatenated (v1.1 F1 fix). "
        "Single-Xp fit path was removed; use build_design_matrices()['Xrp']."
    )


def validate_group_contract(bundle: str = "core4x1", n_rows: int = 64) -> dict:
    """Assert total/added/common-mask contract for one bundle."""
    total, added = group_dims(bundle)
    d = build_design_matrices(n_rows=n_rows, bundle=bundle)
    assert d["Xrp"].shape == (n_rows, total)
    assert d["Xrs"].shape == (n_rows, total)
    assert d["Xrg"].shape == (n_rows, total)
    assert d["Xp"].shape[1] == added
    assert d["Xs"].shape[1] == added
    assert d["Xg"].shape[1] == added
    assert d["common_mask"].dtype == bool
    return {"bundle": bundle, "total": total, "added": added, "n": n_rows}
