"""CLI entry: python -m perdigao_attr.cli --phase P0 (fail-closed stubs for later phases)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def cmd_preflight() -> int:
    import platform
    import shutil

    print(f"python={sys.version.split()[0]} platform={platform.platform()}")
    print(f"disk_free_GB={shutil.disk_usage(str(REPO_ROOT)).free / 1e9:.1f}")
    for name in ("configs/protocol.yaml", "configs/feature_dag.yaml", "configs/p_subset.yaml"):
        p = REPO_ROOT / name
        print(f"{name}: {'OK' if p.exists() else 'MISSING'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["P0", "P1", "P2", "P3", "P4", "P5"])
    ap.add_argument("--frozen", action="store_true")
    args = ap.parse_args(argv)
    if args.phase == "P0":
        return cmd_preflight()
    # Later phases are sealed in P0: refuse to run without a frozen bundle.
    blocked = {
        "phase": args.phase,
        "error": "BLOCKED: phase not available in P0 scaffold (no freeze bundle yet)",
        "resume": "complete P0, then P1 freeze before P2+",
    }
    print(json.dumps(blocked, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
