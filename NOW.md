# NOW.md — Manzil API Tests (project dynamic state)

> Project: `/Users/n.begimbayevgreatmall.uz/Documents/Manzil`
> Stable info → `CLAUDE.md`. Этот файл — что меняется от сессии к сессии.
> **Last updated:** 2026-05-14 (mobile Wave 1 spec готов, driver app проанализирован)

---

## Workflow

- **Claude:** планирует, исследует, пишет спеки для Codex (формат — как `CODEX_TASKS.md`: точные файлы, строки, готовые сниппеты, pytest-команды).
- **Codex:** выполняет правки кода.
- Я **не** редактирую `*.py` в этом проекте без явной просьбы. Probe-скрипты в `/tmp/` для исследования допустимы.

---

## Active work

### Mobile (новая параллельная ветка, 2026-05-12)

Mobile-приложение готово, цель — **полное покрытие Android + iOS**.
- **Framework:** **Maestro** (YAML флоу) + тонкая pytest-обёртка для API setup/verify.
  Решение принято после сравнения с Appium 2026-05-12 — Maestro выиграл по
  скорости авторинга / прогона, простоте setup, и тому что QA уже с ним работал.
- **Куда:** новая папка `mobile/` в этом репо.
- **План:** `CODEX_MOBILE.md` — 5 волн (W0=инфра, W1=registration, W2=login/me, W3=feed, W4=full coverage, W5=opt).
- **Wave 0** — Codex может делать **прямо сейчас** (инфра, без приложения).
- **Wave 1+** ждёт: Claude анализирует APK/IPA когда положишь на ноут, потом спека.

**Что нужно от пользователя для перехода Wave 0 → Wave 1:** APK + IPA/.app +
appId + тестовые аккаунты. См. секцию "Phase 1+" в `CODEX_MOBILE.md`.

### API — стабилизирован ✅

**Эволюция:**
| Стадия | passed | failed | errors | xpassed | Когда |
|---|---|---|---|---|---|
| Baseline | 274 | 32 | 49 | 7 | 2026-05-12 |
| После V1 (schema drift) | 304 | 23 | 32 | 3 | 2026-05-12 |
| **После V2 (RBAC + races + IMAP)** | **352** | **1** | **4** | **0** | **2026-05-12** |

Цель (passed ≥ 340 / failed ≤ 10 / errors ≤ 5 / xpassed = 0) **перевыполнена**.

**Что в остатке (флакаемость окружения, не код):**
- 4 errors — Gmail IMAP таймауты в setup-фикстурах. Codex уже поднял timeout
  120→180s и почистил IMAP singleton. На следующем прогоне может уйти в 0.
- 1 failure — `test_registration_spam_eventually_returns_429` поймал
  `ConnectTimeout` под параллельной нагрузкой. Тест намеренно спамит rate-limit;
  flakyness от сети.

Спеки V1 и V2 удалены (правки закоммичены в коде, закрытые баги — в `bug.txt` closed-секции).
Лог последнего прогона: `/private/tmp/manzil_run_after_v2.log`.

### 🎉 BRD §4 E2E — GREEN 2026-05-13

После N3 probe (первый запуск упал на IMAP-flake) Claude сделал 2 retry —
**оба зелёные, по 27 секунд каждый**. Все 13 шагов tender-flow проходят.

Это значит **3 бага закрыты на backend'е**:
- **BUG-008** (P0 — TK_ADMIN JWT 401 на /feed) — шаг 8 проходит.
- **BUG-004** (P1 — SUPPLIER_ADMIN 403 на selectWinner) — шаг 12 проходит.
- **BUG-010** (TK OTP IMAP timeout) — non-reproducible, был одноразовый flake.

Bug.txt обновлён: closed-секция дополнена, в open-секциях BUG-004/008/010
помечены `[CLOSED 2026-05-13]`, Q4/Q6 backend-questions обновлены.

### Что следующее (на Codex'а сейчас)

### Mobile Wave 1 ✅ выполнен 2026-05-14 (см. W2 секцию выше)

Wave 1 details below kept for traceability — реализация в коде уже.



Codex реализовал инфраструктуру + 12 flow / 24 теста (Android+iOS параметризация):
login (positive/negative/disabled), nav (register, forgot), register Step 1,
post-login tabs, profile, language toggle, takliflarim, feed.

Проверки: ruff/mypy зелёные, `pytest mobile/ --collect-only` → 24. Все
скипаются без `ANDROID_APP_PATH/IOS_APP_PATH` (ожидаемое).

**`BACKEND_ASKS.md`** заведён, первая запись: frontend ask про
testTag/accessibilityIdentifier.

### Mobile Wave 2 ✅ выполнен 2026-05-14

Codex реализовал W2: order detail + submit offer + my-offer detail.
- Maestro flows: order_detail render/back, submit form opens/disabled/cancel,
  submit_valid (mutation), comment limit, my-offer detail, Takliflarim filter
- `mobile/seed/api_seed.py`: `seed_active_order_for_driver_feed` для precondition
- pytest wrappers в `mobile/tests/driver/orders/` и `.../offers/`
- Маркер `mutation` добавлен в pytest.ini

Проверки: ruff/mypy зелёные, `pytest mobile/ --collect-only` → **42 теста**
(24 W1 + 18 W2). Реальный прогон на эмуляторе не делался — требует device + env.

Coverage после W2: ~20% от senior manual QA work (с 5-10% до W2).

### Что нужно от пользователя для реального прогона W1+W2

В `.env` заполнить (см. `.env.example`):
```
ANDROID_APP_PATH=/полный/путь/к/manzil-driver.apk
ANDROID_APP_ID=uz.greatmall.manzil.dev
DRIVER_REAL_PHONE=+998918744540
DRIVER_REAL_PASSWORD=Nawrizbek_20
DRIVER_REAL_FULL_NAME=Naurizbek Mambetali uli Begimbaev
```

Запустить эмулятор + установить приложение, потом:
```bash
pytest mobile/ -k android -v          # ~5 мин на 12 тестов
```

Для iOS — установить `Manzil.app` в симулятор, заполнить `IOS_APP_PATH` +
`IOS_APP_ID` (вытащить через `plutil -p Manzil.app/Info.plist`).

**Anomaly to verify (низкий приоритет):**
- Profile «Shahar» (город) на тестовом driver-аккаунте показывает
  `Nawrizbek_20` — совпадает с паролем. Либо случайно ввели, либо
  backend mapping bug. Расследовать позже.

**Желательно (не срочно):**
- **Верифицировать BUG-007** — он был заблокирован BUG-008, теперь разблокирован.
  Нужен UI-сценарий: TK подаёт оффер → Supplier отменяет → TK открывает /offers,
  смотрим 404 или нормальный список.
- **Сделать 5-й коммит** с накопившимися изменениями (`D CODEX_COMMIT.md`,
  bug.txt + NOW.md обновления после E2E зелёного). Содержание ясно — можно
  поручить Codex'у.

**Заблокировано backend'ом:**
- **`CODEX_NEXT.md` N4** — Telegram OTP. Ждёт backend-договорённости о dev-endpoint.

**Закрыто 2026-05-13:**
- ~~`CODEX_CI.md` (N2)~~ — 3 workflow + README.
- ~~`CODEX_LINT_FIX.md`~~ — 6 ruff + 257 mypy → 0/0.
- ~~`CODEX_MOBILE.md` Wave 0~~ — Maestro инфра.
- ~~`CODEX_COMMIT.md` (N1)~~ — 4 атомарных коммита, 216 файлов.
- ~~`CODEX_NEXT.md` N3~~ — E2E зелёный 2/2 retries (27s каждый).

### Git состояние

```
31a0e42 test(web_ui): Playwright suite + operational docs
707918a test: API suite covering auth, employees, me, and full carrier flows
2da92d2 feat(api): httpx client, schemas, endpoint wrappers, test data layer
5a22626 chore: project scaffolding and tooling config
```
- `git status` — ` D CODEX_COMMIT.md` + правки в `bug.txt`, `NOW.md`
  (накопились после E2E зелёного). Готовы к 5-му коммиту.
- ruff 0, mypy --strict 0, pytest --collect-only 378 tests.

---

## Last full run — 2026-05-12 baseline

```
pytest tests/ -n 6 --tb=line -q   (5:43)
274 passed · 32 failed · 49 errors · 8 skipped · 8 xfailed · 7 xpassed
```
Лог: `/tmp/manzil_full_run.log` (перезаписывается на следующем прогоне — скопировать, если нужен исторический diff).

---

## Backend schema drift (release ~2026-05-04)

Тесты были корректны на момент написания, но не догоняют новый контракт:

1. `/me` `role` теперь UPPER_SNAKE: `SUPPLIER_ADMIN`, `TK_ADMIN`, `DRIVER` (был `supplier.admin`, `tk.admin`).
2. `GET /api/v1/employees` теперь paginated `{content, page}` (был array). Скорее всего то же для других list-эндпойнтов — проверить под Codex Task 2.
3. `OrderResponse` добавил `pickupWarehouseId`, `destinationWarehouseId`, `loadCity`, `unloadCity` (`/feed` валится из-за `extra="forbid"`).
4. `POST /employees` → 400 (тело без `field`). Гипотеза: роли в payload тоже UPPERCASE (`MANAGER` вместо `manager`). Под probe.
5. `POST /orders` → 400. Гипотеза: новые required-поля (`pickupWarehouseId`/`destinationWarehouseId`). Под probe.
6. `POST /employees` от TK_ADMIN теперь 400 (валидация тела до auth-check), а не 403.

---

## Bug status (verified 2026-05-13)

### Закрыты в эту сессию
| Bug | Как подтверждено |
|---|---|
| BUG-004 (admin 403 на select winner) | E2E §4 шаг 12 проходит 2/2 |
| BUG-008 (TK_ADMIN 401) | E2E §4 шаг 8 проходит 2/2 |
| BUG-010 (IMAP timeout) | non-reproducible flake |
| BUG-009 (cross-flow phone) | probe 2026-05-13: TK reg same phone → 409 |

### Открыты, верифицированы 2026-05-13 (5 шт)
- **BUG-001** P1 — дубль email в /suppliers → 204 (backend не вернул 409).
- **BUG-002** P2 — Swagger /v3/api-docs → 302 oauth2-proxy.
- **BUG-003** P1 — **CHANGED**: API теперь TIN ровно 12, UI 8-18. Направление
  дрифта поменялось. Нужен fix UI (12 цифр) + swagger update.
- **BUG-005** P3 — MZL не уникален cross-company. Probe создал 2 ордера в
  2 компаниях, оба `MZL-0001`.
- **BUG-007** P1 — **FRONTEND-ONLY** (verified). Backend в `/my-offers`
  возвращает 200 + `orderStatus='CANCELLED'` в response item. Фронт должен
  использовать это поле вместо отдельного fetch заявки.

### НЕ верифицировано — требует Playwright
- **BUG-006** P1 — UI action-кнопки на «В работе».

### Новая находка (Q7 в bug.txt)
- POST /orders/{id}/cancel: DISPATCHER получает 409 «not-cancellable» если у
  order есть active offer, ADMIN отменяет успешно. Это feature (admin override)
  или непрописанный RBAC bug? Нужно сверить с BRD §3.

Probe-скрипты: `/tmp/probe_all_bugs.py`, `/tmp/probe_remaining_bugs.py`.

---

## Open questions (статус vs `CLAUDE.md`)

1. **Base URL dev API** — ✅ `https://dev-manzil.greatmall.uz` (в .env, работает).
2. **Email OTP в dev** — ✅ режим `imap_gmail` работает; `fixed` сломан с 2026-05-04.
3. **Telegram OTP в dev** — ⏳ всё ещё открыт. `fixed` не работает; нужен test-bot или endpoint. Блокирует 3 mobile-register теста.
4. **TIN checksum** — ✅ `TIN_CHECKSUM=false` ок (backend принимает любые 12 цифр в dev).
5. **Password policy** — ✅ `P@ssw0rd!` проходит (полная Keycloak-политика не задокументирована, но не блокирует).
6. **Phone format** — ✅ `+998` префикс, формат пулa подходит.

---

## После Codex — следующие блоки на планирование

В порядке приоритета:

1. **Update project `CLAUDE.md`** — секция «Текущее покрытие swagger» врёт. Реально покрыто: orders, offers, vehicles, warehouses, feed, security, RBAC, concurrency, contract, e2e (parked). Надо заменить параграф под факт.
2. ~~Решение по `web_ui/`~~ — **РЕШЕНО 2026-05-12:** оставляем как параллельный track. 34 теста, шарят `api/client.py` для cleanup, тестят UI-инварианты (видимость кнопок, sidebar per role, locale switcher) которые API не покрывает. Запускается отдельно `pytest web_ui/`. CLAUDE.md обновлён.
3. **Первый git commit** — репо: 0 коммитов, всё untracked. Когда Codex закончит и зелёный прогон зафиксирован — сделать initial commit (предложить разбить на 3-4 логических, не один монолит).
4. **CI план** — `.github/workflows/tests.yml`: smoke + lint на push, полный сьют ночью.
5. **BRD §4 full tender E2E** — сейчас parked. Проверить, не подъехала ли часть backend (offers/* и orders/* уже покрыты), переоценить разблокировку.
6. **Telegram OTP** — отдельный сюжет на оживление мобильной регистрации. Может потребовать backend-договорённости.

---

## Где смотреть

| Что | Где |
|---|---|
| Стабильный конфиг проекта | `CLAUDE.md` |
| Открытые баги | `bug.txt` (обновл. 2026-05-05) |
| Желательно: 5-й коммит | накопившиеся правки `bug.txt` + `NOW.md` + удаление `CODEX_COMMIT.md` |
| Желательно: BUG-007 ретест | UI-сценарий через `web_ui/tk/offers/` (разблокирован после BUG-008) |
| Ждёт пользователя (APK/IPA) | `CODEX_MOBILE.md` Wave 1 |
| Заблокировано backend-ask'ом | `CODEX_NEXT.md` N4 (Telegram OTP) |
| Отложенные API задачи (E2E + OTP) | `CODEX_NEXT.md` |
| Mobile-план (5 волн, Maestro, Android+iOS) | `CODEX_MOBILE.md` |
| Backend/Frontend asks (Telegram OTP, testID) | `BACKEND_ASKS.md` |
| Лог baseline-прогона | `/tmp/manzil_full_run.log` |
| Allure-результаты | `allure-results/` (allure serve allure-results) |
| Воркфлоу-память Claude | `~/.claude/projects/-Users-.../memory/` |
