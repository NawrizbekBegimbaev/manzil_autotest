# CODEX_COMMIT_2.md — 5-6й коммиты (mobile W1+W2 + audit results)

> **Когда брать:** прямо сейчас. Накопились правки после initial 4 коммитов:
> mobile W1+W2 реализация (untracked) + bug audit results + BACKEND_ASKS +
> NOW/CLAUDE updates.
>
> **Цель:** 2 атомарных коммита. Mobile-код отдельно, docs отдельно.

## Pre-check

```bash
git log --oneline           # должно быть 4 коммита (initial scaffolding chain)
git status --short          # ~22 path'а: 10 M + 1 D + 11 untracked

ruff check .                # ожидается All checks passed!
mypy --strict .             # ожидается Success: no issues found in N source files
pytest --collect-only -q 2>&1 | tail -1   # ожидается 420+ tests (378 api + 42 mobile + web_ui)
```

Если ruff/mypy не зелёные — **остановиться**, доложить.

---

## Коммит 5 — `test(mobile): driver login + order/offer flows (Wave 1 + 2)`

Файлы для стейджинга:

**Новые:**
```
mobile/flows/driver/_common/         (login_as_driver.yaml, login_and_open_first_order.yaml)
mobile/flows/driver/feed/
mobile/flows/driver/login/
mobile/flows/driver/navigation/
mobile/flows/driver/offers/
mobile/flows/driver/orders/
mobile/flows/driver/profile/
mobile/flows/driver/registration/register_step1_opens_telegram.yaml
mobile/tests/driver/                 (вся подпапка с подпапками orders/, offers/)
```

**Модифицированные:**
```
mobile/conftest.py                   (load_dotenv + driver env injection)
mobile/flows/smoke/app_launches.yaml (расширен)
mobile/seed/api_seed.py              (seed_active_order_for_driver_feed)
pyproject.toml                       (mobile.tests.driver.orders/offers пакеты)
pytest.ini                           (mutation marker)
.env.example                         (DRIVER_REAL_* + ANDROID_APP_ID добавки)
```

Команда:
```bash
git add mobile/flows/driver mobile/tests/driver \
        mobile/conftest.py mobile/flows/smoke/app_launches.yaml mobile/seed/api_seed.py \
        pyproject.toml pytest.ini .env.example

git status   # сверить — только перечисленные пути

git commit -m "$(cat <<'EOF'
test(mobile): driver login + order/offer flows (Wave 1 + 2)

42 Maestro flows / pytest tests for the Manzil driver mobile app
(Android + iOS parametrized via mobile/conftest.py).

Wave 1 — login, navigation, profile read:
- smoke: app launches + login screen renders all elements
- login: positive (with real driver account), wrong-password, disabled-empty
- navigation: login ↔ register, login → forgot password
- post-login: bottom tabs (Lenta / Takliflarim / Profil) navigation
- profile: shows driver name, phone, license info
- language toggle entry point
- takliflarim status tabs render
- feed renders order cards
- register step 1 → Telegram bot deeplink hand-off

Wave 2 — order detail + submit offer + my-offer detail:
- order detail: route, cargo, weight/volume render
- back navigation order detail → feed
- submit-offer form: opens, fields visible, disabled-empty, cancel closes
- submit valid offer (mutation marker, requires real driver account)
- comment 250-char limit
- my-offer detail opens from Takliflarim
- Takliflarim "Yangi" status filter

Infra additions:
- mobile/seed/api_seed.py: seed_active_order_for_driver_feed —
  registers supplier admin, invites dispatcher, creates active order
  visible in driver feed (via API, faster than UI)
- mobile/conftest.py: load_dotenv + per-platform env (DRIVER_PHONE,
  DRIVER_PASSWORD, APP_ID, APP_PATH)
- pyproject.toml: added mobile.tests.driver.{orders,offers} packages
- pytest.ini: added `mutation` marker for tests that create real
  backend data
- .env.example: documented driver test account vars and
  ANDROID_APP_ID=uz.greatmall.manzil.dev

Coverage: ~20% of senior manual QA work (5-10% after W1, ~20% after W2).
Real-device runs require ANDROID_APP_PATH / IOS_APP_PATH + emulator
+ driver test account in .env.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

После коммита проверить:
```bash
git status   # должны остаться: BACKEND_ASKS.md (untracked), bug.txt + CLAUDE.md + NOW.md (modified), D CODEX_COMMIT.md
git log --oneline -1   # последний коммит — этот
```

---

## Коммит 6 — `docs: bug audit results, backend asks, workflow updates`

Файлы для стейджинга:

**Новые:**
```
BACKEND_ASKS.md
```

**Модифицированные:**
```
bug.txt    (closed BUG-004/008/009/010, BUG-003 переписан, audit results)
CLAUDE.md  (mobile commands, два слоя tests + web_ui + mobile)
NOW.md     (после всех аудитов, мобильные волны, текущее состояние)
```

**Удалённый:**
```
CODEX_COMMIT.md   (выполнен в initial commit batch, удалён из working tree)
```

Команда:
```bash
git add BACKEND_ASKS.md bug.txt CLAUDE.md NOW.md
git add -u CODEX_COMMIT.md   # стейдж удаления

git status   # должно быть чисто после этого

git commit -m "$(cat <<'EOF'
docs: bug audit results + backend asks + workflow updates

bug.txt:
- BUG-004 (admin 403 on selectWinner): CLOSED, verified by E2E §4 step 12
- BUG-008 (TK_ADMIN JWT 401): CLOSED, verified by E2E §4 step 8 (2/2 retries)
- BUG-009 (cross-flow phone duplicate): CLOSED, backend returns 409
- BUG-010 (TK OTP IMAP timeout): CLOSED as non-reproducible single flake
- BUG-003 (TIN UI/API drift): description rewritten — direction reversed,
  API now requires exactly 12 digits while UI still accepts 8-18
- BUG-001 / BUG-002 / BUG-005: re-verified open 2026-05-13
- Re-verified date updated to 2026-05-13
- Summary table reflects current state; new Q7 added for cancel RBAC

BACKEND_ASKS.md (new):
- Frontend: add testTag / accessibilityIdentifier to mobile UI for
  stable locators (mobile tests currently rely on brittle text matching)

CLAUDE.md:
- Project description updated to reflect two parallel test layers
  (API + UI + mobile) instead of "API only, no UI"
- Coverage section rewritten to match actual implementation (orders,
  offers, warehouses, vehicles, feed, security, RBAC etc. — not just
  Auth+Employees+/me)
- Run commands added for mobile track
- NOW.md pointer at top for session-start orientation

NOW.md:
- Captures current dynamic state after all audits and waves
- Mobile W1 + W2 statuses, bug audit results, BACKEND_ASKS reference

CODEX_COMMIT.md: deleted from working tree (completed in commit
chain 5a22626..31a0e42, kept in history)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Финальная проверка

```bash
git log --oneline                  # 6 коммитов
git status                          # должен быть полностью чистым
ruff check .                        # All checks passed!
mypy --strict .                     # Success
pytest --collect-only -q 2>&1 | tail -1   # 420+ tests
```

Если всё зелёное — закончили. `git push` **НЕ делать** без явной команды.

---

## Чего НЕ делать

- НЕ амендить предыдущие 4 коммита. Только новые на HEAD.
- НЕ ставить `git commit -a` или `git add .`. Стейджить только перечисленные пути.
- НЕ коммитить `.env` (без .example). Проверить `git status` после каждого add.
- НЕ объединять оба коммита в один — разделение mobile-code / docs-audit умышленно.
- НЕ делать `git push` без явной команды пользователя.
- НЕ создавать tags / branches.
