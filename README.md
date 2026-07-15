# Manzil — QA Automation Suite

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-9.x-0A9EDC?logo=pytest&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-web-2EAD33?logo=playwright&logoColor=white)
![Maestro](https://img.shields.io/badge/Maestro-mobile-FF5C5C)
![Allure](https://img.shields.io/badge/Allure-reporting-FF6C37)
![Tests](https://img.shields.io/badge/UAT-100%2F100_green-brightgreen)

End-to-end QA-автоматизация для **Manzil** — SaaS грузоперевозок по коридору
**Узбекистан ↔ Китай** (роли: супер-админ, грузоотправитель, склад, менеджер,
транспортная компания). Один репозиторий покрывает **три слоя продукта**: веб-UI,
мобильное Android-приложение и backend-API — с ежедневным прогоном, директорским
отчётом и трекингом дефектов.

> Демонстрационный репозиторий инженера по автоматизации тестирования. Реальные
> учётные данные и токены в репозиторий не попадают (`.env` в `.gitignore`,
> шаблон — `.env.example`).

---

## 📊 Покрытие

**100 автоматизированных UAT-кейсов**, ежедневный прогон — `100/100 green` (~14 мин).

| Слой | Роль / область | Кейсов | Инструмент |
|---|---|---:|---|
| Web UI | Супер-администратор | 18 | Playwright |
| Web UI | Администратор грузоотправителя | 19 | Playwright |
| Web UI | Менеджер | 9 | Playwright |
| Web UI | Транспортная компания | 14 | Playwright |
| Mobile | Сотрудник склада (Android) | 14 | Maestro |
| API | Аутентификация + RBAC | 26 | requests |
| | **Итого** | **100** | |

Помимо автоматизированного набора ведётся **библиотека ручных тест-кейсов** —
**1497 автоматизируемых** сценариев (API 1008 / Web 370 / Mobile 119), выверенных
по актуальному билду staging, плюс 41 вынесенный в архив как неавтоматизируемый
(чистый визуал, a11y, «проверить на устройстве»). Источник истины — JSON, из
которого собираются Excel-книги (`docs/testcases/`).

---

## 🧱 Стек и подход

- **Python 3.13 + pytest** — ядро, маркеры (`uat`, `sanity`, по ролям), фикстуры.
- **Playwright (sync)** — веб-UI, **Page Object Model**: класс на страницу,
  локаторы в `__init__`, методы — действия/геттеры **без ассертов**; ассерты
  только в тестах через `expect(...)` с авто-ретраем.
- **Maestro** — мобильное Android-приложение склада (YAML-флоу + pytest-обёртка,
  запуск на локальном эмуляторе).
- **requests** — backend-API как система-под-тестом (auth, RBAC, `/me`,
  ролевые 403-гейты); отдельный клиент, который не бросает на 4xx — ассертит тест.
- **Allure** — сбор результатов, из них строится директорский XLSX-отчёт.
- **pydantic-settings** — вся конфигурация из `.env`, **ноль хардкода** (URL,
  доступы, таймауты, Telegram).

### Инженерные принципы

- **Свежий tenant на прогон.** Компании грузоотправителя/ТК и их сотрудники
  создаются автоматически (session-фикстура `provisioned`) и удаляются в teardown —
  прогон изолирован и самоочищается, никакого «мусора» на staging.
- **API-seed для предусловий.** Заказы в нужном статусе (`published` → `quoted`
  → `selected` → `in_transit`) поднимаются через API, а не кликами по UI —
  быстро и детерминированно; ассерты остаются на UI-слое.
- **Без `networkidle`.** SPA держит живые соединения — готовность проверяется
  `expect()` по стабильному элементу, а не сетевым простоем.
- **Логин один раз за прогон** на роль (session-контекст), смена пользователя =
  смена контекста, а не logout через UI.
- **Локализация.** Продукт China-first (дефолтный язык интерфейса — китайский);
  тесты форсируют язык и ассертят по стабильным ключам (`code` в problem+json),
  а не по локализованному тексту.

---

## 🗂️ Структура репозитория

```
config/settings.py           — конфигурация из .env (pydantic-settings)
conftest.py                  — фикстуры: cfg, session-логины по ролям,
                               provisioned (свежий tenant), api-клиент
pages/                       — Page Objects (auth, super_admin, shipper, transport, common)
tests/uat/                   — UAT-набор (по файлу на роль)
  test_super_admin.py        — супер-админ (web)
  test_admin.py              — админ грузоотправителя (web)
  test_manager.py            — менеджер (web)
  test_tk.py                 — транспортная компания (web)
  test_warehouse_mobile.py   — склад (Android/Maestro)
  test_api_auth_rbac.py      — backend API: auth + RBAC
utils/
  api_client.py              — API-клиент (система-под-тестом)
  api_seed.py                — сидинг заказов для предусловий
  data.py                    — генераторы уникальных данных, dataclass-ы
mobile/                      — Maestro: flows/ (YAML), config, scripts
scripts/
  run_uat.sh                 — ежедневный прогон + сборка отчёта (--no-send)
  uat_report.py              — XLSX-отчёт по ролям + доставка в Telegram
docs/
  BUGS.md                    — журнал дефектов (причина, коммит-фикс, статус)
  BUG_REPRO.md               — репро-репорты для разработки
  PROJECT_REFERENCE.md       — доменная модель, роли, state-машины, RBAC
  testcases/                 — библиотека тест-кейсов (JSON → xlsx)
```

---

## 🚀 Запуск

```bash
# окружение
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium

# конфигурация
cp .env.example .env      # заполнить SUPER_ADMIN_* и NEW_ACCOUNT_PASSWORD

# весь UAT-набор (web + mobile + api), отчёт локально без отправки
scripts/run_uat.sh --no-send

# точечно
pytest -m uat                             # все 100 кейсов
pytest tests/uat/test_api_auth_rbac.py    # только API (быстро, ~15 c)
pytest -m tk                              # только транспортная компания
```

Мобильные кейсы требуют Android-эмулятора и Maestro CLI (см.
`mobile/` и `docs/PROJECT_REFERENCE.md`).

---

## 📈 Отчётность и трекинг дефектов

- **Директорский отчёт** (`scripts/uat_report.py`) — XLSX со сводкой по ролям и
  листом на каждую роль; статус каждого кейса берётся из последнего прогона
  (Allure). Опциональная доставка в Telegram.
- **Блокирующие баги** помечаются `xfail(run=False)` — прогон остаётся зелёным,
  а в отчёте кейс показан как «Заблокирован (баг)», а не «Провален».
- **Журнал дефектов** (`docs/BUGS.md`) ведётся как история: симптом → корень в
  коде → коммит-фикс → привязка к ID кейсов. Для разработки — отдельные
  репро-репорты (`docs/BUG_REPRO.md`) с шагами и доказательствами (ответы API, логи).

---

## 🎯 Что демонстрирует проект

- Автоматизацию **трёх разных слоёв** (web / mobile / API) в едином наборе.
- Проектирование поддерживаемой архитектуры (POM, фикстуры, изоляция данных).
- Работу с **RBAC и безопасностью** на уровне API (ролевые/capability 403-гейты,
  проверка контрактов, wrong-app, refresh-ротация).
- Полный QA-цикл: тест-дизайн (1497 кейсов) → автоматизация → прогон →
  отчётность для менеджмента → трекинг и верификация фиксов.
