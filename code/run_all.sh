#!/usr/bin/env bash
# perdigao_attribution_v1.1 entry point (F1 P0).
# F6 / clean-room target interface: ./run_all.sh --frozen --from-raw
# F1時点ではP0のみ実装、以降は fail-closed で停止する。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/logs" "$ROOT/runs" "$ROOT/audit"

FROZEN=""
FROM_RAW=""
PHASE=""

for arg in "$@"; do
  case "$arg" in
    --frozen) FROZEN="--frozen" ;;
    --from-raw) FROM_RAW="--from-raw" ;;
    F0|F1|F2|F3|F4|F5|F6|P0|P1|P2|P3|P4|P5) PHASE="$arg" ;;
    *) echo "[run_all] unknown arg: $arg" >&2; exit 2 ;;
  esac
done

echo "[run_all] v1.1 F1 P0 at $(date -u +%Y-%m-%dT%H:%M:%SZ) phase=${PHASE:-unset} frozen=${FROZEN:-no} from_raw=${FROM_RAW:-no}"

if [[ "$FROZEN" == "--frozen" && "$FROM_RAW" == "--from-raw" ]]; then
  echo "[run_all] full reproduction requested, but pipeline is F1 (P0 only). Stopping fail-closed." >&2
  exit 3
fi

if [[ -z "$PHASE" ]]; then
  echo "[run_all] usage: ./run_all.sh --frozen --from-raw | ./run_all.sh <PHASE>" >&2
  exit 2
fi

if [[ "$PHASE" == "P0" || "$PHASE" == "F1" ]]; then
  exec "$ROOT/.venv/bin/python" -m perdigao_attr.cli --phase P0
fi

echo "[run_all] phase $PHASE not implemented yet (F1 P0 only). Stopping fail-closed." >&2
exit 3
