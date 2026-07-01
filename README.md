# Manzil — UI Sanity Suite

Daily UI sanity for **Manzil** (SaaS грузоперевозок UZ↔CN), STAGING. Playwright
(sync) + pytest, Page Object Model, **UI-only** — никаких HTTP/API-вызовов из
тестов. Архитектура повторяет образец MyXodim.

## Принципы

- **POM**: класс на страницу, локаторы в `__init__`, методы — действия/геттеры
  **без ассертов**. Ассерты только в тестах через `expect(...).to_*` (auto-retry).
- **Без хардкода**: URL, телефоны, пароли, таймауты, Telegram — только из `.env`
  (`config/settings.py`, pydantic-settings).
- **Без `networkidle`**: SPA держит живые соединения. Навигация ждёт
  `domcontentloaded`, готовность проверяем `expect()` по стабильному элементу.
- **Логин**: телефон + пароль, без OTP. Каждая роль логинится **один раз за
  прогон** (session-фикстура); контекст переиспользуется. Смена пользователя =
  смена контекста, не logout через UI.
- **Локаторы**: `data-testid` почти нет → по `name`/роли/лейблу/плейсхолдеру;
  списки матчим по URL.

## Структура

```
config/settings.py          — URL/доступы/TG из .env
conftest.py                 — cfg, browser_context_args, session-логины по ролям
pages/base_page.py          — goto, heading
pages/auth/login_page.py    — форма логина
pages/super_admin/          — Page Objects по областям
pages/common/nav_page.py    — обобщённый page-load
tests/sanity/               — кейсы (по файлу на логическую группу)
scripts/run_sanity.sh       — ежедневный прогон + сборка XLSX (без отправки)
scripts/report_telegram.py  — XLSX-отчёт + ручная отправка в Telegram
```

## Установка

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium
cp .env.example .env   # заполнить BASE_URL и доступы
```

## Запуск

```bash
pytest -m sanity                       # весь набор
pytest -m "sanity and smoke"           # только page-load смоки
pytest tests/sanity/test_auth.py       # отдельный файл
scripts/run_sanity.sh                  # ежедневный прогон + локальный XLSX
allure serve allure-results            # просмотр отчёта
```

## Отчёт в Telegram (ручная отправка)

`run_sanity.sh` отчёт **не отправляет** — только собирает `reports/sanity-report.xlsx`.
После разбора падений (реальные баги, а не косяки тестов) отправляем вручную:

```bash
.venv/bin/python scripts/report_telegram.py
```

Если `TG_BOT_TOKEN`/`TG_CHAT_ID` пусты — отправка молча пропускается, XLSX
всё равно пишется.

## Роли и self-provisioning

`SUPER_ADMIN` → `/super-admin/...`, `ADMIN` → `/dashboard`,
`MANAGER` → `/shipper/storeroom`, `CARRIER` → `/transport/orders`.

В `.env` нужен **только SUPER_ADMIN** (телефон+пароль) и `NEW_ACCOUNT_PASSWORD`.
Остальные роли набор **создаёт сам** в session-фикстуре `provisioned`:
SUPER_ADMIN создаёт грузоотправителя (→ ADMIN-логин) и транспортную компанию
(→ CARRIER-логин), а ADMIN создаёт сотрудника-«Менеджера» (→ MANAGER-логин).
Под каждым логинимся в отдельном контексте; в конце прогона арендаторы удаляются
(каскадом со своими сотрудниками). Все созданные сущности помечены `SANITY`.

## Покрытие (21 кейс)

1–4 логины ролей · 5–9 страницы SUPER_ADMIN · 10–11 создание грузоотправителя/
трак-компании (с очисткой) · 12–17 страницы ADMIN · 18–19 MANAGER · 20–21 CARRIER.
Создание заявки — только в мобильном приложении (`mobile/`, Maestro/Android).

## Сквозной тендер (mobile → web)

`scripts/run_tender_e2e.sh` — оркестратор: SUPER_ADMIN провижит грузоотправителя
(+ склад-сотрудника для мобайла) и перевозчика → **мобайл публикует заявку**
(Maestro) → **веб-перевозчик** находит её в ленте и предлагает цену → **веб-
грузоотправитель** принимает (выбор победителя) → арендаторы удаляются. Нужен
запущенный эмулятор с APK. См. `mobile/README.md`.

## Язык интерфейса

Staging может отдавать дефолт zh/uz. Ассерты — на русском, поэтому контекст
принудительно ставит `localStorage['__tolgee_currentLanguage']='ru'` (init-script
в `conftest.py`) — UI всегда русский, детерминированно.
