# Manzil API + Web-UI test suite

Automated tests for the Manzil platform (cargo logistics SaaS, UZ↔CN). Two
test layers in one repo:

- **API tests** (`tests/`) — direct httpx against the REST API. Cover
  auth, registrations, employees, orders, warehouses, vehicles, offers,
  feed, and security/property/contract layers.
- **Web-UI tests** (`web_ui/`) — Playwright against the live SPA. Cover
  pre-OTP forms, post-OTP authenticated flows for all 4 roles, and
  cross-role e2e scenarios.

Total: **~530 tests** against `https://dev-manzil.greatmall.uz`.

---

## CI

- `lint` — ruff + mypy --strict, on every push/PR. Blocks merge.
- `api-tests` — `pytest tests/` without OTP-dependent tests, on every PR. ~3-4 min.
- `nightly-full` — full API + UI with OTP, every night at 02:00 UTC.

Badges after the first green run:
[badges placeholders]

---

## Quick start

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

cp .env.example .env       # then fill secrets if needed

pytest -m smoke                 # ~10 tests, fastest sanity
pytest                          # full suite (~10 min on dev)
pytest web_ui                   # UI only (~4 min)
pytest tests                    # API only (~4 min)

UI_HEADED=true pytest web_ui/smoke -v   # watch the browser
allure serve allure-results              # view detailed report
```

### Targeting different environments

The suite supports three environments, switched via `MANZIL_ENV`:

| `MANZIL_ENV` | URL | Allowed |
|---|---|---|
| `dev` (default) | `https://dev-manzil.greatmall.uz` | everything |
| `staging` | `https://staging-manzil.greatmall.uz` | everything (data may be sensitive — coordinate) |
| `prod` | `https://manzil.greatmall.uz` | only anonymous read-only probes |

```bash
pytest -m smoke                                     # dev (default)
MANZIL_ENV=staging pytest -m smoke                  # staging
MANZIL_ENV=prod pytest -k anonymous_health -m smoke # prod (auto-skips destructive)
```

**Production safety**: a collection-hook in `conftest.py` automatically
skips any test marked `requires_real_account`, `requires_email_otp`,
`requires_telegram_otp`, or `maintenance` when `MANZIL_ENV=prod`. You
cannot accidentally hit prod with a destructive test — it just gets a
clear skip with the reason.

For prod-safe sanity checks see `web_ui/smoke/test_anonymous_health.py`
(no login, no forms, no mutation — just verifies the SPA shell loads).

---

## Setup

### CI Secrets

Configure these GitHub Actions secrets before enabling CI:

| Secret | Value | Source |
|---|---|---|
| `GMAIL_IMAP_USER` | `nbegimbaev2006@gmail.com` | Existing mailbox |
| `GMAIL_IMAP_APP_PASSWORD` | 16-char App Password | `myaccount.google.com/apppasswords` |
| `MANZIL_TEST_PASSWORD` | `P@ssw0rd!` or another Keycloak-policy password | Team agreement |
| `SUPPLIER_ADMIN_REAL_EMAIL` | `nbegimbaev2006@gmail.com` | Shared dev account |
| `SUPPLIER_DISPATCHER_REAL_EMAIL` | `nbegimbaev2020@gmail.com` | Shared dev account |
| `SUPPLIER_MANAGER_REAL_EMAIL` | `nbegimbaev56@gmail.com` | Shared dev account |
| `TK_REAL_EMAIL` | `202390415@ajou.uz` | Shared dev account |
| `REAL_ACCOUNT_PASSWORD` | `Nawrizbek_20` | Shared dev account |

Do not commit these values to workflow YAML files. Reference them only through
`${{ secrets.X }}`.

---

## Layer map

```
tests/                    # API layer (380 tests)
├── smoke/                # health + register + login + /me
├── auth/                 # login, refresh, logout, OTP, password reset
├── registration/         # supplier, TK, driver mobile
├── employees/            # CRUD + invite + RBAC
├── orders/               # CRUD + status transitions + filters
├── warehouses/           # CRUD + RBAC + cross-tenant
├── vehicles/             # CRUD + body types + RBAC
├── offers/               # submit, withdraw, note, select
├── feed/                 # filters + visibility invariants
├── me/                   # GET/PATCH /me + /me/driver
├── security/             # BOLA, mass assignment, JWT manipulation
├── contract/             # HTTP details — content-type, methods, errors
├── property/             # hypothesis fuzzing
├── contract_validation/  # schemathesis (gated by OpenAPI snapshot)
└── e2e/                  # full tender flow (parked — needs OTP capture)

web_ui/                   # UI layer (~150 tests)
├── conftest.py           # browser, contexts, role storage_state cache
├── pages/                # Page Object Model
│   ├── _base.py          # BasePage with goto/expect_loaded
│   ├── _common/          # Sidebar, AccountDrawer, native_confirm helper
│   ├── auth/             # Login, RegisterEntry, RegisterSupplier/TKForm,
│   │                     # ForgotPassword, VerifyOtp
│   ├── supplier/         # Dashboard, Orders, OrderDetail, OrderCreate,
│   │                     # Warehouses, Employees, Profile
│   └── tk/               # Feed, Fleet, Offers
├── seed/                 # cleanup helpers (wipe [E2E-UI] data via API)
├── smoke/                # 3 dual-account login bootstraps
├── auth_pages/           # /auth/forgot-password unauthenticated tests
├── supplier/             # Senior-QA layer for the Supplier side
│   ├── auth/             # pre-OTP register, account drawer, logout
│   ├── rbac/             # sidebar+create button per sub-role
│   ├── orders/           # list, detail, /orders/create form, draft edit
│   ├── warehouses/       # CRUD + delete-confirm + edit
│   ├── employees/        # view, invite, role+block, delete-confirm
│   ├── inbox/            # (placeholder — blocked on BUG-017)
│   ├── profile/          # /settings/profile read + edit
│   └── aux/              # locale switcher, notifications
├── tk/                   # Senior-QA layer for the TK side
│   ├── auth/             # pre-OTP register, drawer, logout
│   ├── rbac/             # sidebar + supplier-routes blocked
│   ├── feed/             # list, filters, submit-offer dialog
│   ├── fleet/            # CRUD + delete + edit
│   └── offers/           # my-offers list
├── e2e/                  # cross-role: visibility, tender flow
└── maintenance/          # weekly sweep of leaked test data
```

---

## Roles and accounts

UI tests use 4 pre-verified shared Keycloak accounts (do **not** delete
or change roles). All 3 supplier accounts are employees of the same
company «TeamQa».

| Role | Email | Landing | Sidebar |
|---|---|---|---|
| `SUPPLIER_ADMIN` | `nbegimbaev2006@gmail.com` | `/dashboard` | Аналитика, Заявки, Склады, Сотрудники |
| `SUPPLIER_DISPATCHER` | `nbegimbaev2020@gmail.com` | `/orders` | Заявки, Склады |
| `SUPPLIER_MANAGER` | `nbegimbaev56@gmail.com` | `/orders` | Заявки |
| `TK_ADMIN` | `202390415@ajou.uz` | `/feed` | Лента заявок, Автопарк, Отклики |

Password (all four): `Nawrizbek_20`

Driver (mobile-only) role is intentionally not tested — no dev mobile
environment yet.

---

## Markers

```
smoke        — fastest happy-path tests
positive     — positive UC coverage
negative     — negative paths + validation errors
rbac         — role-based access control
edge_case    — edge cases, races
serial       — must run sequentially (not xdist-safe)
property     — hypothesis fuzzing
schemathesis — OpenAPI-driven contract validation (gated)
security     — BOLA, mass assignment, JWT, injection
contract     — HTTP protocol details
concurrency  — real parallel-request invariants
slow         — many requests (rate-limit probes)

ui              — any UI test (Playwright)
ui_supplier     — Supplier role
ui_tk           — TK_Admin role
ui_cross        — two browser contexts in one scenario
requires_real_account — uses shared Keycloak accounts (xdist-unsafe)
requires_email_otp    — needs email-OTP capture (currently parked)
requires_telegram_otp — needs Telegram-OTP capture (driver, parked)
maintenance     — weekly cleanup tasks (NOT in default run)
```

Examples:
```bash
pytest -m "ui_supplier and not requires_real_account"  # local-CI safe
pytest -m "smoke or rbac"
pytest -m maintenance                                  # weekly sweep
```

---

## Test data and cleanup

Anything created during a test run is tagged with `[E2E-UI]` (warehouses,
order cargo) or plate prefix `UIT-` (vehicles), and wiped via the API in
autouse teardown fixtures.

If a test crashes mid-run, leftovers can pile up. Run the maintenance
sweep weekly (or on-demand):

```bash
pytest -m maintenance
```

It cancels open `[E2E-UI]`-tagged orders and deletes their warehouses,
plus removes `UIT-`-prefixed vehicles.

---

## Open questions and parked work

See `bug.txt` "Открытые вопросы" section. Highlights:
- **Q1** — email-OTP capture (mailhog/fixed/endpoint?). Without it,
  ~80 API tests for email-driven flows are skipped.
- **Q2** — Telegram-OTP capture for driver mobile (no driver tests
  until resolved AND mobile dev env exists).
- **Q12** — `/v3/api-docs` gated by oauth2-proxy — schemathesis fuzz
  blocked until either the route is opened or a snapshot is committed.

Parked test categories:
- `tests/e2e/test_full_tender_flow.py` — needs Q1.
- `tests/contract_validation/` — needs Q12.
- `web_ui/supplier/orders/test_draft_order_edit.py` — DRAFT edit URL
  not yet reconned (4 xfail tests).
- `web_ui/supplier/inbox/` — blocked on BUG-017 (UI doesn't render
  action buttons on «В работе» orders).

---

## Bug tracking

All findings live in `bug.txt` (BusinessHub format). Latest cards:
BUG-001..BUG-020. Sections:
- Critical/Major bugs in API or UI
- Sweep summary table
- Open questions to backend team

---

## Contributing

- ruff + mypy strict — must pass before merge:
  ```bash
  ruff check .
  mypy --strict .
  ```
- New POMs go into `web_ui/pages/` and follow `_base.BasePage`.
- New tests must clean up after themselves (autouse teardown ok).
- Use `[E2E-UI]` prefix for any UI-created data.
- Don't hardcode account credentials — read from `settings`.
- Don't test against shared accounts in destructive ways
  (delete/block/role-change of fixture users).

---

## Support

- Slack: `#manzil-qa` (when the channel exists)
- Issues: this repo
