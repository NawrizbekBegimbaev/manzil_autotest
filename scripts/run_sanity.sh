#!/usr/bin/env bash
# Daily sanity run. Executes the UI sanity suite, collects Allure results +
# JUnit XML, and builds the XLSX report LOCALLY. It does NOT send to Telegram —
# sending is a manual step done once a day after triaging failures:
#
#   .venv/bin/python scripts/report_telegram.py
#
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
PY="$VENV/bin/python"
PYTEST="$VENV/bin/pytest"

if [[ ! -x "$PY" ]]; then
  echo "venv not found at $VENV — create it: python3.13 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

rm -rf allure-results reports/junit.xml
mkdir -p reports

set +e
"$PYTEST" -m sanity
PYTEST_RC=$?
set -e

# Build the XLSX report locally regardless of pass/fail (no auto-send).
"$PY" scripts/report_telegram.py --build-only || true

echo "Sanity finished (pytest rc=$PYTEST_RC). Report: reports/sanity-report.xlsx"
echo "To send to Telegram after triage: $PY scripts/report_telegram.py"
exit $PYTEST_RC
