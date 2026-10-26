"""Synthetic ISFS-like NetCDF fixture for P0 smoke tests (tiny, deterministic)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from perdigao_attr.seeds import derive_generator
from perdigao_attr.time_contract import validate_frame

MASTER_SEED = 2026091501


def make_fixture(path: Path, n_steps: int = 288, seed_index: int = 0) -> Path:
    """Create a tiny 5-min synthetic tower file. Deterministic for fixed seed_index."""
    rng = derive_generator(MASTER_SEED, "split", seed_index)
    times = pd.date_range("2016-12-01T00:00:00", periods=n_steps, freq="5min")  # naive UTC
    u100 = 6.0 + 2.0 * np.sin(np.arange(n_steps) / 48.0) + rng.normal(0, 0.5, n_steps)
    u20 = 0.8 * u100 + rng.normal(0, 0.3, n_steps)
    ds = xr.Dataset(
        {
            "U100": (("time",), u100, {"units": "m s-1", "height": "100 m"}),
            "U20": (("time",), u20, {"units": "m s-1", "height": "20 m"}),
        },
        coords={"time": times},
        attrs={"title": "P0 synthetic fixture (not observations)", "seed_index": seed_index,
               "time_zone": "UTC"},
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path, engine="netcdf4")
    return path


def build_issue_frame(n: int = 24, horizon_min: int = 60, step_min: int = 5) -> pd.DataFrame:
    """Build a valid issue/target frame satisfying the time contract."""
    base = pd.Timestamp("2017-03-10T00:00:00Z")
    issues = [base + pd.Timedelta(minutes=i * step_min) for i in range(n)]
    rows = [
        {
            "issue_time": t,
            "target_start": t + pd.Timedelta(seconds=1),
            "target_end": t + pd.Timedelta(minutes=horizon_min),
            "max_input_time": t,
        }
        for t in issues
    ]
    return validate_frame(pd.DataFrame(rows))
