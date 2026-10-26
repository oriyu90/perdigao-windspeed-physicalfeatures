"""Time contract: max_input_time <= issue_time < target_start.

All inputs are right-aligned: Z_h(T) = mean(Z in (T-h, T]).
Target: Y_h(T) = mean(U100 in (T, T+h]).
Primary horizon h = 1h; issue grid 5 min; purge 3 h.
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ("issue_time", "target_start", "target_end", "max_input_time")


def validate_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out = df.copy()
    for c in REQUIRED_COLUMNS:
        out[c] = pd.to_datetime(out[c], utc=True)
    ok = (out["max_input_time"] <= out["issue_time"]) & (out["issue_time"] < out["target_start"])
    bad = out[~ok]
    if len(bad):
        raise ValueError(f"time-contract violated in {len(bad)} rows; e.g. {bad.head(3).to_dict('records')}")
    if not (out["target_start"] < out["target_end"]).all():
        raise ValueError("target_start must be < target_end")
    return out
