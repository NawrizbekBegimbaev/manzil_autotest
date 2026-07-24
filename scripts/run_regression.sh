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
# ЭТАЛОН (2026-07-24, dev): 1014 passed · 15 xfailed · 0 failed · ~2–4 мин (стенд-зависимо).
#   15 xfailed = известные открытые баги (BUG-035, BUG-038, BUG-039, BUG-040).
#   Сдвиг с прежнего 986/16: +27 passed — регистрация MNZL-269 (осн. срез, API-REG класс A);
#   +1 passed / −1 xfailed — снят сторож DRIFT-001 (countries/cities публичны по дизайну, 3aba606).
# Любое расхождение (не 0 failed / внезапный XPASS) — разбирать, не игнорировать.
#
# Требуется: .env с DEV_* учётками (+ ONEC_WEBHOOK_SECRET для 1С happy-path).
# ratelimit/iplimit/slow/regotp — вне основного прогона (свои серийные группы):
#   regotp: scripts/run_registration_otp.sh — 14 passed (API-REG OTP-запросы, серийно).
#   iplimit: scripts/run_ratelimit.sh --iplimit — вкл. API-REG-011/068 (+2 к группе), изолированно.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTEST="${VENV:-.venv}/bin/pytest"
[[ -x "$PYTEST" ]] || { echo "venv не найден: ${VENV:-.venv}" >&2; exit 1; }

exec "$PYTEST" tests/regression/api/ \
  -m "not ratelimit and not iplimit and not slow and not regotp" \
  -n 4 --dist loadgroup -p no:randomly "$@"
