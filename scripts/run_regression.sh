#!/usr/bin/env bash
# Полный DEV-регресс API-слоя (tests/regression/api).
#
#   scripts/run_regression.sh            # весь API-регресс
#   scripts/run_regression.sh <путь/-k>  # срез (доп. аргументы уходят в pytest)
#
# КОНФИГ: -n 4 (НЕ -n auto). -n auto = 16 воркеров перегружают dev-стенд →
# транзиентные 503 + гонки провизининга (409 name-already-used, таймауты) →
# падает РАЗНЫЙ набор каждый прогон. -n 4 стабилен и не медленнее (узкое место —
# стенд, а не CPU). См. CLAUDE.md → «Скорость прогона».
#
# ЭТАЛОН (2026-07-24, dev): 986 passed · 16 xfailed · 0 failed · ~2:06.
#   16 xfailed = 15 известных багов (BUG-035 ×5, BUG-038, BUG-039, BUG-040 ×6)
#              + сторож DRIFT-001 (/countries|/cities 200 анонимно, ждём ответа).
# Любое расхождение (не 0 failed / внезапный XPASS) — разбирать, не игнорировать.
#
# Требуется: .env с DEV_* учётками (+ ONEC_WEBHOOK_SECRET для 1С happy-path).
# ratelimit/iplimit/slow — вне основного прогона (свои серийные группы).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTEST="${VENV:-.venv}/bin/pytest"
[[ -x "$PYTEST" ]] || { echo "venv не найден: ${VENV:-.venv}" >&2; exit 1; }

exec "$PYTEST" tests/regression/api/ \
  -m "not ratelimit and not iplimit and not slow" \
  -n 4 --dist loadgroup -p no:randomly "$@"
