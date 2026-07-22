#!/usr/bin/env bash
# Rate-limit / IP-bucket regression cases — run SEPARATELY from the main suite.
#
# These deliberately burn failed-login attempts (5/phone, 30/IP per 10 min), so they
# must run serially, on dedicated throwaway phones, and NOT under -n auto. The main
# run excludes them via `-m "not ratelimit and not iplimit"`.
#
#   scripts/run_ratelimit.sh            # ratelimit group (fits the IP budget)
#   scripts/run_ratelimit.sh --iplimit  # iplimit group ONLY (run isolated — nukes the IP)
#
# Requires DEV_* creds in .env (regression targets DEV).
set -euo pipefail
cd "$(dirname "$0")/.."

PYTEST="${VENV:-.venv}/bin/pytest"
[[ -x "$PYTEST" ]] || { echo "venv не найден: ${VENV:-.venv}" >&2; exit 1; }

if [[ "${1:-}" == "--iplimit" ]]; then
  # IP-bucket + slow cases: each nukes the shared IP budget (or waits >10 min) — run this
  # group ALONE, then wait ~10 min before anything else logs in.
  echo "[run_ratelimit] iplimit+slow group (isolated) — throttles the IP / waits >10 min"
  exec "$PYTEST" -m "iplimit or slow" -p no:randomly
fi

# Default: the ratelimit group. Serial (no xdist). Stays within the 30/10-min IP budget.
exec "$PYTEST" -m "ratelimit and not iplimit" -p no:randomly
