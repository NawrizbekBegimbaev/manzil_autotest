# CLAUDE.md — Manzil API Tests (project-level)

> Этот файл — для Claude Code, работающего в этом проекте.
> **Динамическое состояние — в `./NOW.md`. Читать в начале каждой сессии.**

## Что это

Тест-сьют для **Manzil** (SaaS грузоперевозок UZ↔CN), два параллельных слоя в одном репо:

1. **API tests (`tests/`)** — REST API напрямую через httpx, основной слой.
2. **UI tests (`web_ui/`)** — Playwright, поверх того же `api/client.py`
   (cleanup и seeding идут через API, а не через UI — быстрее и надёжнее).
   UI-слой появился после 2026-05-01 когда frontend подъехал.

**Стек:** Python 3.13, httpx, pytest, pydantic v2, Playwright, allure.
**Auth:** Keycloak JWT (Bearer), realm `manzil-dev` (dev) / `manzil` (prod),
refresh-rotation включён.

**Прогоны раздельные** (см. секцию «Команды»):
- `pytest tests/` — API-петля, быстрая, 378 тестов, ~6 мин на n=6.
- `pytest web_ui/` — UI-петля, медленная, 162 теста, требует `playwright install`.

## Текущее покрытие swagger (по факту на 2026-05-12)

Backend dev-окружения экспонирует значительно больше, чем на старте проекта.
Реальное покрытие сьюита:

**Auth (13 тест-файлов)** — web/mobile login, refresh, logout, invitation accept,
web/mobile registration (supplier + TK + driver), email + Telegram OTP verify,
web/mobile password-reset, boundary/validation.

**User (1)** — GET/PATCH `/api/v1/me`, PATCH `/api/v1/me/driver`.

**Employees (4)** — list (paginated), invite, update, delete (supplier admin).

**Orders (1)** — `/api/v1/orders` CRUD, draft→active→cancelled lifecycle (US-6/7).

**Offers (1)** — `/api/v1/orders/{id}/offers` TK подаёт оффер, selectWinner, withdraw.

**Warehouses (1)** — `/api/v1/warehouses` supplier-склады.

**Vehicles (1)** — `/api/v1/vehicles` TK автопарк.

**Feed (1)** — `/api/v1/feed` TK видит активные заявки по body_type.

**Cross-cutting:**
- **Smoke (4)** — health, login, register, /me.
- **Security (5)** — BOLA, mass assignment, JWT manipulation, injection, rate-limiting.
- **RBAC (1)** — sweep protected routes без токена и с чужой ролью.
- **Contract (2)** — error consistency, HTTP-протокол (methods, content-type).
- **Concurrency (1)** — реальные race-conditions (parallel invite, parallel registration).
- **Edge cases (2)** — concurrent registration cross-flow.
- **Property (1)** — hypothesis-driven random payloads.
- **Timing (1)** — TTL и clock-зависимые (часть требует backend test-clock).
- **Contract validation (1)** — schemathesis по openapi.json (skip пока spec за oauth2-proxy).
- **E2E (1)** — full tender flow (parked в части шагов, см. ниже).

**Эндпойнты в `api/endpoints/`:** `auth`, `dev`, `employees`, `feed`, `me`, `offers`,
`orders`, `vehicles`, `warehouses`.

**Пустые placeholder-папки в `tests/`** (резерв под будущие модули, файлов нет):
`i18n/`, `maintenance/`, `provider/`, `tender/`, `tk/`. Не путать с `web_ui/tk/` —
это другой слой (Playwright).

**Не покрыто (бекенд ещё не отдаёт):** notifications, documents/files, analytics,
finance, reports. Главный E2E тендер из BRD §4 теперь технически собираем
(orders+offers+select+complete есть), но parked до закрытия BUG-008
(TK_ADMIN JWT 401 на `/me`/`/my-offers`/`/feed`).

## Команды

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
mypy --strict .

pytest --collect-only
pytest tests/ -n 6                              # API-петля (полная)
pytest tests/ -m smoke                          # smoke только
pytest tests/ -m "smoke and not requires_email_otp"

playwright install chromium                     # один раз на машину
pytest web_ui/                                  # UI-петля (медленная)

maestro --version                               # mobile требует Maestro CLI
pytest mobile/ -m mobile_smoke                  # быстрые W1 smoke + login
pytest mobile/ -m "mobile and not requires_real_account"  # без driver-аккаунта

allure serve allure-results
```

Mobile-прогоны требуют установленный APK/IPA и запущенный emulator/simulator
до старта pytest. Android dev app id: `uz.greatmall.manzil.dev`.

## Структура

```
api/
  client.py          — httpx.Client + Bearer auth + ProblemDetail handling
  schemas/           — pydantic модели request/response из swagger
  endpoints/         — auth.py, employees.py, me.py
config/settings.py   — pydantic-settings (URLs, OTP modes, pools)
data/                — phone_pool, email_pool с filelock, constants, i18n
utils/               — tin_generator (12-digit UZ TIN), otp_helpers
tests/
  conftest.py
  smoke/             — health, register, login, /me
  auth/              — все auth-флоу (positive + negative)
  employees/         — CRUD сотрудников
```

## Что НЕЛЬЗЯ

- Дёргать Keycloak напрямую (только через `/api/v1/auth/*`)
- Хардкодить URL/email/phone — всё через `settings` + пулы
- Парсить Telegram-сообщения для OTP (нужен dev-mode backend; см. .env.example)
- Писать тесты на эндпойнты, которых нет в swagger
- `try/except Exception` для "стабильности"
- Дублировать pydantic-схемы между client и tests — модели живут в `api/schemas/`
- Хитрые retry-обёртки в client.py — httpx даёт всё необходимое

## Открытые вопросы

В коде помечены `TODO(open-question-N)`:
1. **Base URL** dev API — пока заглушка в .env.example
2. **Email OTP** в dev — fixed/mailhog/endpoint?
3. **Telegram OTP** в dev (для drivers) — fixed/endpoint?
4. **TIN checksum** — нужен ли алгоритм или backend принимает любые 12 цифр?
5. **Password policy** — точные требования Keycloak
6. **Phone format** strict `+998` или E.164?

## Cleanup стратегия

Префикс `[E2E]` в названии компании и `e2e+{slot}@manzil.test` в email пуле.
Maintenance-тест чистит раз в неделю через DELETE /api/v1/employees + (когда
появится) DELETE /api/v1/companies. Soft-delete на стороне backend (см. swagger
`/api/v1/employees/{id}` DELETE 204).

## Многопоточность

`pytest -n` совместим со всеми тестами кроме `@pytest.mark.serial`. Конкуренция
за телефоны/email защищена filelock в `data/phone_pool.py`/`email_pool.py`.

JWT-токены — каждый тест получает свежий через `web_login` фикстуру или
`registered_supplier_admin`. Не шарить токены между тестами.
