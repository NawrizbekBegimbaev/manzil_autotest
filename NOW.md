# NOW.md — Manzil API Tests (project dynamic state)

> Project: `/Users/n.begimbayevgreatmall.uz/Documents/Manzil`
> Stable info → `CLAUDE.md`. Этот файл — что меняется от сессии к сессии.
> **Last updated:** 2026-05-13 (API-сьют стабилизирован, V2 закрыт)

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

### Что следующее (на Codex'а сейчас)

**Активное:**
- **`CODEX_COMMIT.md` (N1)** — initial git commit (4 атомарных). Precheck
  зелёный. Не зависит от mobile.

**Ждёт пользователя:**
- **`CODEX_MOBILE.md` Wave 1** — driver registration. Нужны APK/IPA на ноуте,
  потом Claude анализирует и пишет спеку.

**Закрыто 2026-05-13:**
- ~~`CODEX_CI.md` (N2)~~ — 3 workflow + README.
- ~~`CODEX_LINT_FIX.md`~~ — 6 ruff + 257 mypy → 0/0.
- ~~`CODEX_MOBILE.md` Wave 0~~ — Maestro инфра. `mobile/` структура,
  `runner`, `conftest`, smoke + README. 2 теста собираются, skip без env.

**После N1 — E2E:**
- **`CODEX_NEXT.md` N3** — BRD §4 E2E верификация (изолированный прогон).

**Заблокировано backend'ом:**
- **`CODEX_NEXT.md` N4** — Telegram OTP. Ждёт backend-договорённости о dev-endpoint.

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

## Bug status (vs `bug.txt` от 2026-05-05)

### Закрыты (XPASS в прогоне 2026-05-12)
| Bug | Подтверждающий тест |
|---|---|
| BUG-005 (дубль TIN в /suppliers) | `test_register_supplier_with_duplicate_tin_returns_409` |
| BUG-005 cross-flow TIN Supplier↔TK | `test_supplier_and_tk_cannot_share_tin` |
| BUG-003 cross-flow email Supplier↔TK | `test_email_taken_by_supplier_blocks_tk_registration` |
| BUG-007 или BUG-009 (дубль phone) | `test_same_phone_blocks_second_supplier_registration` — нумерация в xfail-сообщении расходится с bug.txt, нужна сверка (Codex Task 7) |

### Открыты (в bug.txt, в этом прогоне не верифицировались отдельно)
- **BUG-001** P1 — дубль email в /suppliers → 204 вместо 409
- **BUG-002** P2 — Swagger UI за oauth2-proxy
- **BUG-003** P1 — INN UI 8–18 vs API 1–18 (контракт-дрифт)
- **BUG-004** P1 — `/offers/{id}/select` → 403 для SUPPLIER_ADMIN
- **BUG-006** P1 — UI не показывает action-кнопки на «В работе»
- **BUG-007** P1 — TK `/offers` крашится 404 на оффер удалённой заявки (блокируется BUG-008)
- **BUG-008** **P0** — TK_ADMIN JWT → 401 на `/me`, `/my-offers`, `/feed`

### Возможные новые баги (вскроются после probe в Codex)
- Если `POST /employees` 400 не объясняется UPPERCASE-ролью → новый bug.
- Если `POST /orders` 400 не объясняется новыми required-полями → новый bug.

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
| Активное для Codex | `CODEX_COMMIT.md` (N1) |
| После N1 — E2E верификация | `CODEX_NEXT.md` N3 |
| Ждёт пользователя (APK/IPA) | `CODEX_MOBILE.md` Wave 1 |
| Заблокировано backend-ask'ом | `CODEX_NEXT.md` N4 (Telegram OTP) |
| Следующая волна (API: commit + CI + E2E + OTP) | `CODEX_NEXT.md` |
| Mobile-план (Appium, обе платформы) | `CODEX_MOBILE.md` |
| Лог baseline-прогона | `/tmp/manzil_full_run.log` |
| Allure-результаты | `allure-results/` (allure serve allure-results) |
| Воркфлоу-память Claude | `~/.claude/projects/-Users-.../memory/` |
