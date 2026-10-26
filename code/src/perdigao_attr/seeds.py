"""Deterministic seed derivation (no builtin hash()).

v1.1: same contract as v1.0 (master 2026091501, SHA256(master/namespace/index),
first 64bit masked to 63bit, Generator(PCG64)). Namespaces frozen.
"""
from __future__ import annotations

import hashlib

MASTER_SEED = 2026091501

ALLOWED_NAMESPACES = frozenset(
    {
        "split",
        "rf",
        "sham_formula",
        "sham_statistical",
        "rff",
        "bootstrap",
        "semisynth_positive",
        "semisynth_negative",
    }
)


def derive_seed(master_seed: int, namespace: str, index: int) -> int:
    """Derive a 63-bit seed from SHA256(master_seed + namespace + index)."""
    if namespace not in ALLOWED_NAMESPACES:
        raise ValueError(f"unknown namespace: {namespace}")
    if not isinstance(index, int) or index < 0:
        raise ValueError("index must be a non-negative int")
    payload = f"{int(master_seed)}/{namespace}/{int(index)}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    value = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return value


def derive_generator(master_seed: int, namespace: str, index: int):
    """Return numpy Generator(PCG64) for the derived seed."""
    import numpy as np

    return np.random.Generator(np.random.PCG64(derive_seed(master_seed, namespace, index)))
