#!/usr/bin/env bash
# Phase runner wrapper for long jobs (see 00 rule).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PHASE="${1:-P0}"
mkdir -p "$ROOT/logs" "$ROOT/runs"
LOG="$ROOT/logs/${PHASE}.console.log"
echo "[run_phase] $PHASE -> $LOG"
if [[ "$PHASE" == "P0" ]]; then
  "$ROOT/.venv/bin/python" -m perdigao_attr.cli --phase P0 2>&1 | tee "$LOG"
else
  echo "[run_phase] $PHASE not available in F1 (no freeze bundle yet). Stopping fail-closed." | tee "$LOG"
  exit 3
fi
