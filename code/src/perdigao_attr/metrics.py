"""Metric definitions with a single source of truth.

RMSE = sqrt(mean(error^2)); MAE = mean(abs(error)).
Legacy-labelled sample-code value mean(sqrt(error^2)) is mathematically MAE
and must never be reported as RMSE.
"""
from __future__ import annotations

import numpy as np


def rmse(errors) -> float:
    e = np.asarray(errors, dtype=float).ravel()
    if e.size == 0:
        raise ValueError("empty error vector")
    return float(np.sqrt(np.mean(e**2)))


def mae(errors) -> float:
    e = np.asarray(errors, dtype=float).ravel()
    if e.size == 0:
        raise ValueError("empty error vector")
    return float(np.mean(np.abs(e)))


def legacy_labelled_rmse(errors) -> float:
    """Reproduce sample-code misnomer: mean(sqrt(error^2)) == MAE. For audit only."""
    e = np.asarray(errors, dtype=float).ravel()
    return float(np.mean(np.sqrt(e**2)))
