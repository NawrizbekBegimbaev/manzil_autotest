#!/usr/bin/env bash
# Registration / password-reset OTP-request cases (MNZL-269) — run SEPARATELY, SERIAL.
#
# Every case here calls POST /auth/register/otp or /auth/reset/otp with a VALID body, and
# those endpoints share ONE per-IP limiter: ~20 requests / 10 min / IP (measured on dev),
# across register AND reset. Under -n4 that budget is spent instantly → false 429s. So this
# group is `regotp`, runs serial (no xdist), and is excluded from the -n4 main run
# (run_regression.sh: `-m "... and not regotp"`).
#
# The serial group issues ~19 limiter-touching requests — just under the 20/10-min budget.
# If the tail 429s, the window is saturated: wait ~10 min and re-run. The hard IP-exhaustion
# cases (API-REG-011 register-otp 20/IP, API-REG-068 public-feed 60/IP) are `iplimit`, run
# ISOLATED via run_ratelimit.sh --iplimit — NOT here.
#
#   scripts/run_registration_otp.sh            # the regotp group (serial)
#   scripts/run_registration_otp.sh <-k expr>  # a slice (extra args go to pytest)
#
# Requires DEV_* creds in .env (regression targets DEV).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTEST="${VENV:-.venv}/bin/pytest"
[[ -x "$PYTEST" ]] || { echo "venv не найден: ${VENV:-.venv}" >&2; exit 1; }

exec "$PYTEST" tests/regression/api/test_registration.py \
  -m "regotp and not iplimit" -p no:randomly "$@"
