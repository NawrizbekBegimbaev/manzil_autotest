# Manzil — QA-автоматизация

## Что это за репозиторий

Набор QA-автоматизации для платформы грузоперевозок **Manzil**. Три слоя проверок:
- **Web** — pytest + Playwright (sync, POM в `pages/`)
- **Mobile (Android)** — Maestro-флоу (`mobile/`, обёртка `utils/maestro.py`)
- **API (backend)** — requests-клиент (`utils/api_client.py`)

Плюс — **библиотека из 1497 ручных тест-кейсов** (`docs/testcases/`) и **баг-трекинг** (`docs/BUG_*.md`).

## Стек и структура

| Папка | Назначение |
|---|---|
| `tests/uat/` | Суточный UAT-набор (маркер `-m uat`): web-сценарии + API auth/RBAC |
| `tests/sanity/` | UI sanity-набор |
| `pages/` | Page Object Model (Playwright) |
| `mobile/` | Maestro-флоу (Android) |
| `utils/` | `api_client.py` (ApiClient), `maestro.py` (обёртка + APP_ID) |
| `scripts/` | Запуск прогонов, сборка книг, отчёт в Telegram |
| `docs/testcases/` | Библиотека кейсов: JSON-источник + 4 xlsx-книги |
| `docs/` | `BUG_REPRO.md`, `BUG_TRACKER.md`, `DRIFT-AUDIT.md`, `PROJECT_REFERENCE.md` |
| `reports/` | Отчёты прогонов (`uat-report-YYYY-MM-DD.xlsx`) |
| `.venv/` | Виртуальное окружение (все скрипты запускать через `.venv/bin/python`; в системном python3 нет openpyxl/playwright) |

## Команды

```bash
# Суточный UAT (100 кейсов): прогон → отчёт → отправка директору в Telegram
scripts/run_uat.sh
scripts/run_uat.sh --no-send      # без отправки (отчёт только локально)

# Пересобрать/переотправить отчёт из готовых allure-results
.venv/bin/python scripts/uat_report.py

# Пересборка книг тест-кейсов из JSON (после правок в docs/testcases/{api,web,mobile}/*.json)
.venv/bin/python scripts/build_full_book.py     # сводная manzil-testcases-full.xlsx (1497)
.venv/bin/python scripts/build_layer_books.py   # 3 послойные книги (api/web/mobile)
```

Прогон UAT требует запущенного Android-эмулятора (`avd manzil`, `emulator-5554`) и `.env`.

## Окружения

- **staging** — `https://staging-manzil.greatmall.uz` (суточный UAT идёт сюда; `BASE_URL` в `.env`)
- **dev** — `https://dev-manzil.greatmall.uz` (изолированное, свои аккаунты; здесь проверяются фиксы багов)
- Дефолтный язык интерфейса — **китайский** (China-first); тесты форсируют язык через `localStorage['__tolgee_currentLanguage']='ru'`.

## Библиотека тест-кейсов (1497)

Источник истины — **JSON** в `docs/testcases/{api,web,mobile}/*.json`. Из них собираются 4 книги:
- `manzil-testcases-full.xlsx` — 1497 (все слои + лист «Сводка»)
- `manzil-api-testcases.xlsx` — 1008 · `manzil-web-testcases.xlsx` — 370 · `manzil-mobile-testcases.xlsx` — 119

Схема кейса (9 полей): `id · razdel · screen · scenario · precond · steps · expected · priority · comment`.
Кейсы переписаны под **ручное выполнение** (человекочитаемые шаги, наблюдаемый результат, без код-жаргона). Книги xlsx **не редактировать руками** — только JSON, затем пересборка.

---

# Правила написания автотестов

Эти правила обязательны для любого нового и переписываемого тестового кода (все три слоя).
Автотесты пишутся **по кейсам из `docs/testcases/`**: один тест ↔ один ID кейса.

## Главный принцип: тесты ловят реальные баги

- Assertion = точное сравнение поля `expected` кейса с фактическим поведением.
  Для API проверяем ВСЁ, что описано: HTTP-статус, `code`, `detail` (включая локализацию),
  конкретные поля тела, содержимое `errors[]` (field + message) — а не только статус-код.
- НИКОГДА не ослаблять проверку, чтобы тест «прошёл». Расхождение с `expected` — это найденный
  баг, тест ДОЛЖЕН упасть. Запрещены: `assert status in (200, 400)`, try/except вокруг assert,
  `pytest.skip` при расхождении, пустые проверки вида `assert response is not None`.
- Каждый тест в докстринге содержит ID кейса и краткий ожидаемый результат.
- Сообщение при падении диагностичное:
  `assert r.status_code == 403, f"[API-AUTH-009] ожидали 403 wrong-app, получили {r.status_code}: {r.text}"`.
- Известные баги (открытые в `docs/BUG_TRACKER.md`, ссылки `(→ BUG-0XX)` в кейсах) — помечать
  `@pytest.mark.xfail(reason="BUG-028: ...", strict=True)`. `strict=True` обязателен: после фикса
  тест сам сообщит об этом (XPASS → fail), тогда убираем xfail и чистим баг-файлы по баг-флоу.
- Кейсы, требующие подготовки стенда с разработчиком (пометка в precond), — оформлять тестом с
  маркером `@pytest.mark.manual_setup` и `pytest.skip("<ID>: требуется подготовка стенда")` —
  они видны в отчёте, но не имитируют проверку.

## API-слой (`utils/api_client.py`)

- **Кэш токенов — один логин на роль за весь прогон.** В `ApiClient` держим модульный
  словарь `{role: tokens}` под `threading.Lock` (безопасно при xdist внутри воркера);
  сессионная фикстура `api(role)` отдаёт клиент с уже подставленным Bearer.
- Транспорт — `requests.Session` (keep-alive), общий на роль, таймауты явные (≤10 с).
- Тесты на login/refresh/logout/rate-limit кэш НЕ используют — им нужны собственные входы.
- **Rate-limit кейсы (429: 5 неудач/телефон, 30/IP за 10 мин)** — маркер `@pytest.mark.ratelimit`,
  запуск серийно (отдельно от `-n auto`) и только на ВЫДЕЛЕННЫХ телефонах — никогда не жечь
  попытки на учётках основных прогонов (UAT/sanity).
- Однотипные кейсы (матрица роль×clientType, i18n-языки, boundary длин) — через
  `@pytest.mark.parametrize` с `ids=[...]` = ID кейсов.
- Тестовые данные создавать через API в фикстурах (контракты provisioning — см. «Важные грабли»),
  имена уникальные (`f"AT-{uuid4().hex[:8]}"`), teardown — удаление через API.
  Тесты независимы от порядка запуска и друг от друга.

## Web-слой (Playwright + POM в `pages/`)

- **Один UI-логин на роль за прогон → `storage_state`**: сессионная фикстура кэширует state-файл
  по роли, тесты получают уже авторизованный контекст через `page_as(role)`. Сразу после создания
  контекста форсировать язык (`localStorage['__tolgee_currentLanguage']='ru'` через
  `add_init_script`) — до первой навигации.
- Кейсы самой формы входа (WEB-AUTH-*) — единственные, кто логинится через UI руками; им
  storage_state не нужен.
- POM: страница — класс, локаторы — атрибуты, действия — методы, **без assert внутри
  page-объектов** (проверки только в тестах). Локаторы: `get_by_role` / `get_by_test_id` /
  `get_by_label`; XPath запрещён.
- Ожидания: только web-first assertions (`expect(locator).to_have_text(...)`) с auto-wait.
  **Запрещены `time.sleep` и `wait_for_timeout`** — медленно и флаки.
- RBAC проверять в обе стороны: у роли с правом элемент есть, у роли без права —
  `expect(...).to_have_count(0)`.
- Viewport всегда **1920×1080** (иначе DataGrid прячет колонку действий — см. грабли).

## Mobile (Maestro, `mobile/`)

- Общий вход — `subflows/login.yaml` с условным логином: `clearState: false` + `runFlow when:
  visible "Hisobingizga kiring"` — вход выполняется один раз на пачку флоу, дальше сессия живёт.
- Флоу экрана входа (MOB-WH-001…010 и аналоги carrier) — наоборот `clearState: true`.
- Один флоу = один кейс, имя файла `<ID>_<slug>.yaml`.
- Assertions строгие: `assertVisible` с точными текстами из `expected` (узбекские строки как в
  кейсе), `assertNotVisible` для негативных. Запрещён безусловный `optional: true` на проверках
  из `expected` — optional скрывает баги.
- Ожидания — `extendedWaitUntil` с таймаутом, не фиксированные задержки.
- Флоу по открытым багам (BUG-028…034): проверяем текущее фактическое поведение с комментарием
  `# XFAIL BUG-0XX`, «правильный» assert держим рядом закомментированным — включается при фиксе.

## Скорость прогона

1. Токен-кэш (API) + storage_state (Web): вход выполняется ~по разу на роль, а не в каждом тесте.
2. `pytest-xdist -n auto --dist loadgroup`; зависимые цепочки (lifecycle заказа) —
   `@pytest.mark.xdist_group("...")`; `ratelimit` — отдельной серийной группой.
3. Подготовка данных для Web-тестов — через API, не через UI.
4. Headless по умолчанию; артефакты только при падении
   (`--tracing retain-on-failure --screenshot only-on-failure`).
5. Быстрые срезы: `-m uat` (суточный), `-m high` (смоук по приоритету), `-m "api and not ratelimit"`.

## Маркеры (pytest.ini)

Наборы: `uat`, `sanity`. Слои: `api`, `web`. Приоритет: `high`, `medium`, `low`.
Теги из кейсов: `positive, negative, validation, boundary, security, rbac, tenancy, idempotency,
i18n, pagination, conflict, session, lifecycle, state`. Служебные: `ratelimit, manual_setup, slow`.
Каждый тест несёт маркеры своего кейса.

## Что запрещено всегда

- Ослаблять или удалять проверки ради зелёного прогона.
- `sleep` в любом виде; ретраи assert'ов циклом. Единственное исключение — тесты
  реального времени (скользящие окна, TTL) с маркером `slow`, запускаемые отдельно
  (напр. API-AUTH-042 — окно rate-limit 10 мин); в основном прогоне и в web-тестах
  `sleep` запрещён без исключений.
- Хардкод учёток/паролей/URL в тестах — только `.env` (репозиторий публичный!).
- Зависимость теста от данных другого теста (кроме явных xdist_group-цепочек).
- Менять `expected` кейса под фактическое поведение без разбора: расхождение = баг →
  запись в `docs/BUG_TRACKER.md` + xfail(strict=True). `expected` переписывается только
  когда поведение признано корректным (и тогда — правка JSON + пересборка книг).
- **Правка теста «под реальность» без синхронной правки JSON.** Как только тест поправлен
  под фактический контракт (поведение признано корректным, не баг) — в ТОМ ЖЕ заходе:
  обновить `expected` соответствующего кейса в JSON, добавить в `comment` пометку
  «уточнено по фактическому контракту + дата», пересобрать книги. Тест и книга не должны
  расходиться — это не опционально.
- Оставлять недостижимые сейчас кейсы «висящими». Если кейс нельзя автоматизировать в
  текущей фазе (нужны кросс-доменные хелперы) — `automation: pending` в JSON с причиной;
  `coverage_map` показывает pending отдельной строкой и НЕ засчитывает как покрытые.

---

## Баг-флоу

- Найденные баги — в `docs/BUG_REPRO.md` (детальное репро) и `docs/BUG_TRACKER.md` (формат issue).
- Тест-кейсы ссылаются на баги строкой `(→ BUG-0XX)`; при фиксе `expected` переписывается на корректное поведение.
- Автотест на баг: до фикса — `xfail(strict=True)`; после фикса — убрать xfail, прогнать на dev, затем чистить баг-файлы.
- Проверенные-исправленными баги убираются из файлов (история — в git). Открытые сейчас: мобильные **BUG-028…034**.
- `docs/testcases/DRIFT-AUDIT.md` — категоризация расхождений «код vs BRD».

## Важные грабли (проверено на практике)

- **DataGrid (MUI) в headless**: inline-иконки действий не кликаются напрямую — нужен `focus()` + `press("Enter")` (паттерн «activate»), НЕ `click()`. Колонка «Действия»/⋮ виртуализируется за экраном — ставить viewport **1920×1080**.
- **Поле телефона**: MUI-инпуты с лейблами (не placeholder) → искать через `get_by_label`; ввод — `press_sequentially(delay=25)`.
- **Provisioning на dev/staging** (контракты): shipper-company POST требует `{name, tin(9 цифр), prefix(4 заглавные латиницы), address(мин ~2 симв — "a" даёт 400!), admin:{fullName, phone, password}}`; transport-company — то же без prefix; staff — `POST /shipper/staff {fullName, phone, password, role}`.
- **Выдать capability** (напр. `SEE_PRICES`): `PATCH /shipper/staff/{id}` с ПОЛНЫМ телом `{fullName, phone, role, capabilities:[...]}` (частичное тело → 400).
- **Order-lifecycle провизининг** (`tests/regression/order_lifecycle.py::OrderFactory`, честная цепочка через API): **order id — числовой (Long)**, не UUID. Деталь заказа `GET /shipper/orders/{id}` обёрнута в `{order, winningOffer, history}` — читать `["order"]`. Привязка водителя `POST /transport/orders/{id}/drivers` требует **`cardId`** у каждого водителя (иначе 400 `error.driver.card-id-required`); `POST /transport/orders/{id}/start` требует полного комплекта водителей (`driversCount`). Переходы: create(warehouse)→bid(carrier)→select(admin)→drivers+start(carrier)→communication CONFIRMED+goods-sent(warehouse)→complete(admin); cancel(admin) — только из SELECTED/IN_WORK/IN_TRANSIT.
- **Эмулятор**: на длинных сессиях деградирует — перед важным прогоном делать холодный рестарт (`adb emu kill` → перезапуск с `-no-snapshot -dns-server 8.8.8.8,1.1.1.1`).

## Безопасность (репозиторий ПУБЛИЧНЫЙ)

- `.env` — в `.gitignore`, никогда не коммитить. Реальные пароли/токены/JWT в git попадать не должны.
- В тест-кейсах/доках пароли маскировать (`<staging-password>`), телефоны — плейсхолдеры (`+998900000000`).
- Перед `git push` — скан диапазона на секреты; коммитить/пушить только по явной просьбе пользователя.
- Git co-author для коммитов: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Доменная модель

Полный справочник (роли, state-машины заказа/оффера, RBAC, capability) — `docs/PROJECT_REFERENCE.md`.
Кратко: роли SUPER_ADMIN / SHIPPER_* / TRANSPORT_ADMIN / DRIVER + capabilities (SMS_BLAST, ORDER_ENTRY, SEE_PRICES, REPORTS, BLACKLIST…). Жизненный цикл заказа: PUBLISHED → QUOTED → SELECTED → IN_WORK → IN_TRANSIT → COMPLETED/CANCELLED.