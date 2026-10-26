"""Confirm-interval guard: block target-summary readout before unseal.

P0/P1 may compute schema / time-range / missingness of the confirm interval,
but must not read target distributions, correlations, or predictive performance.
Unseal happens only in F4/P3 after calibration passes; the event is logged to
runs/exposure.jsonl. Until then any call to confirm_target_summary() raises.
"""
from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def unseal_marker() -> Path:
    return _repo_root() / "runs" / "exposure.jsonl"


def is_unsealed() -> bool:
    marker = unseal_marker()
    if not marker.exists():
        return False
    if os.environ.get("PERDIGAO_UNSEALED", "0") != "1":
        return False
    return True


def confirm_target_summary(*args, **kwargs):
    """Always blocked until unseal. Used by tests + P1 guard."""
    raise PermissionError(
        "CONFIRM_GUARD: confirm-interval target summary is sealed until P3 calibration passes. "
        "P1 may only read schema/time-range/missingness."
    )


def require_unsealed() -> None:
    if not is_unsealed():
        raise PermissionError("CONFIRM_GUARD: confirm interval is still sealed.")
