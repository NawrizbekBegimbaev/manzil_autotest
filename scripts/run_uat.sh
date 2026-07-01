#!/usr/bin/env bash
# Ежедневный прогон UAT-автотестов + директорский отчёт.
#
#   scripts/run_uat.sh            # прогнать, собрать отчёт, отправить в Telegram (если настроен)
#   scripts/run_uat.sh --no-send  # без отправки (отчёт только локально)
#
# Требуется: .env с BASE_URL + SUPER_ADMIN creds + NEW_ACCOUNT_PASSWORD.
# Для отправки директору: TG_BOT_TOKEN + TG_CHAT_ID (чат/канал директора) в .env.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
PY="$VENV/bin/python"
PYTEST="$VENV/bin/pytest"
[[ -x "$PY" ]] || { echo "venv не найден: $VENV" >&2; exit 1; }

SEND_FLAG=""
[[ "${1:-}" == "--no-send" ]] && SEND_FLAG="--build-only"

rm -rf allure-results reports/junit.xml
mkdir -p reports

# Прогон только UAT-набора (web). Падения тестов не должны прерывать сборку отчёта.
set +e
"$PYTEST" -m uat
RC=$?
set -e

# Директорский отчёт: все 71 кейса со статусом последнего прогона.
"$PY" scripts/uat_report.py $SEND_FLAG || true

echo "UAT прогон завершён (pytest rc=$RC). Отчёт: reports/uat-report-$(date +%F).xlsx"
exit $RC
