# CODEX_COMMIT.md — Initial git commit для Manzil

> Эту задачу можно делать **параллельно** с `CODEX_CI.md` (разные файлы).
> Зависимостей нет — API-сьют уже зелёный (352 passed после V1+V2 фиксов на 2026-05-12).

## Контекст

Репо инициализирован, **0 коммитов**. 18 top-level untracked путей.
`.gitignore` уже корректный (`.env`, `.venv`, `__pycache__`, `allure-results`,
`playwright-traces`, `.playwright-mcp` и т.п. — всё закрыто).

**Цель:** разбить весь untracked-контент на **4 атомарных коммита**, чтобы
history читалась, а не была монолитом. Каждый коммит — самостоятельный:
репо собирается / тесты запускаются на любом коммите.

## Перед началом — проверки

1. `git status --short` — никаких staged изменений. Если есть — разобраться.
2. `git log --oneline` — действительно 0 коммитов (`fatal: ... does not have any commits yet`).
3. `pytest tests/ --collect-only -q 2>&1 | tail -1` — суит собирается (число тестов ≥ 350).
4. `ruff check . 2>&1 | tail -5` и `mypy --strict . 2>&1 | tail -5` — оба без ошибок.

Если хоть один пункт не сходится — **остановиться и доложить**, не коммитить.

## План коммитов

### Коммит 1 — `chore: project scaffolding and tooling config`

Файлы:
```
.env.example
.gitignore
README.md
CLAUDE.md
pyproject.toml
pytest.ini
conftest.py        (root-level)
```
- `.env` (без .example) НЕ коммитить — он в .gitignore, проверить что не staged.
- Все `CODEX_*.md` / `NOW.md` / `bug.txt` — НЕ в этот коммит (см. коммит 4).

Команда:
```bash
git add .env.example .gitignore README.md CLAUDE.md pyproject.toml pytest.ini conftest.py
git status   # сверить — должно быть ровно 7 файлов
git commit -m "$(cat <<'EOF'
chore: project scaffolding and tooling config

- pyproject.toml: Python 3.13, httpx, pytest, pydantic v2, playwright, allure
- pytest.ini: testpaths tests + web_ui, marker registry, strict-config
- ruff/mypy strict
- .env.example documents all required dev/staging env vars
- README orients new contributors, CLAUDE.md is for Claude Code

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Коммит 2 — `feat(api): httpx client, pydantic schemas, endpoint wrappers, test data layer`

Файлы:
```
api/                  (client.py + schemas/ + endpoints/)
config/               (settings.py)
data/                 (builders, pools, constants)
utils/                (otp helpers, tin generator)
```
Команда:
```bash
git add api config data utils
git status
git commit -m "$(cat <<'EOF'
feat(api): httpx client, schemas, endpoint wrappers, test data layer

api/client.py — Bearer auth, ProblemDetail handling, expect_status helper.
api/schemas/  — pydantic v2 models for the entire Manzil surface:
                auth, employees, me, orders, offers, warehouses, vehicles,
                feed, pagination, registration, problem.
api/endpoints/— thin wrappers, one per area.
config/       — pydantic-settings (URLs, OTP modes, pool ranges).
data/         — phone/email pools with filelock for xdist safety,
                builders for request payloads (UPPERCASE roles/enums
                per 2026-05-04+ backend contract), constants.
utils/        — TIN generator (UZ 12-digit, per-process RNG seed for
                xdist), Gmail IMAP OTP fetcher with singleton connection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Коммит 3 — `test: API suite — auth, employees, me, orders, offers, warehouses, vehicles, feed`

Файлы:
```
tests/
```
Команда:
```bash
git add tests
git status   # проверить — только tests/...
git commit -m "$(cat <<'EOF'
test: API suite covering auth, employees, me, and full carrier flows

378 tests across 18 modules:
- auth (13): registration, login, refresh, OTP verify, password reset
- employees (4): list, invite, update, delete with RBAC and BOLA checks
- me (1), smoke (4)
- orders / offers / warehouses / vehicles / feed (5): carrier-side flows
  with dispatcher-fixture for order creation (SUPPLIER_ADMIN can't create
  orders per backend RBAC, must be SUPPLIER_DISPATCHER)
- security (5): BOLA, mass-assignment, JWT manipulation, injection, rate-limit
- rbac, contract, contract_validation, concurrency, edge_cases, property,
  timing, e2e: cross-cutting checks

State at this commit (dev backend 2026-05-13):
352 passed, 1 flaky failure (rate-limit ConnectTimeout under load),
4 IMAP setup timeouts, 13 xfailed (known backend gaps), 0 xpassed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Коммит 4 — `test(web_ui): Playwright suite + operational docs`

Файлы:
```
web_ui/
bug.txt
supplier-orders.yml
NOW.md
CODEX_NEXT.md
CODEX_MOBILE.md
CODEX_COMMIT.md      (этот файл)
CODEX_CI.md          (если уже создан другой агент сделавший N2)
```
Команда:
```bash
git add web_ui bug.txt supplier-orders.yml NOW.md CODEX_NEXT.md CODEX_MOBILE.md CODEX_COMMIT.md
# Если в рабочем дереве есть CODEX_CI.md — добавить и его:
[ -f CODEX_CI.md ] && git add CODEX_CI.md
git status   # должно быть чисто после этого
git commit -m "$(cat <<'EOF'
test(web_ui): Playwright UI suite + operational docs

web_ui/ — 162 Playwright tests over the same api/client.py infrastructure.
Shares real Keycloak accounts (supplier admin, TK admin) via cached
storage_state. Cleanup of created data goes through API for speed.

Covers supplier (orders, warehouses, inbox, profile, RBAC) and TK
(feed, fleet, offers, RBAC, account drawer) flows, plus cross-role e2e.

Docs:
- bug.txt: open bug log against dev backend (with closed-section
  for bugs verified fixed by V1/V2 test runs)
- NOW.md: project dynamic state, read at session start
- CODEX_NEXT.md / CODEX_MOBILE.md / CODEX_*.md: planned work specs

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Финальная проверка

```bash
git log --oneline           # 4 коммита, в указанном порядке
git status                  # должен быть clean
git ls-files | wc -l        # все ожидаемые файлы трекаются
pytest tests/ --collect-only -q 2>&1 | tail -1   # суит собирается на HEAD
```

## Чего НЕ делать

- НЕ делать `git push` без явной команды пользователя — origin может ещё
  отсутствовать или быть не настроен.
- НЕ ставить `git commit -a` или `git add .` — стейджить только указанные пути.
- НЕ амендить коммиты по ходу — если ошибся, делать новый или
  `git reset --mixed HEAD~1` и пересобрать (только если ничего не запушено).
- НЕ коммитить `.env` (проверять `git status` после каждого `git add`).
- НЕ коммитить `manzil_api_tests.egg-info/`, `.playwright-mcp/`, `playwright-traces/`,
  `allure-results/` — они в .gitignore. Проверить `git ls-files | grep -E "(egg-info|allure-results|playwright-traces)"` после — должно быть пусто.
