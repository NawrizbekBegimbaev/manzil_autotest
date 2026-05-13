# CODEX_MOBILE.md — Mobile (Android + iOS) автотесты

> Цель: полное покрытие mobile-приложения Manzil (driver flow на Android и iOS).
>
> Stack: **Maestro** (YAML-флоу) + тонкий **pytest-wrapper** для интеграции
> с API (setup/cleanup/verify через существующий `api/client.py`).
>
> Этот файл подключается **после** того, как `CODEX_TASKS.md` и `CODEX_NEXT.md` пройдены.
>
> **Phase 0** (этот файл сейчас) — инфраструктура, можно делать **до** установки приложения.
> **Phase 1+** — спека по фактическим экранам, **появится после** того, как Claude
> проанализирует приложение (нужны APK/IPA на этом ноутбуке).

---

## Почему Maestro, а не Appium

| Фактор | Решающий вес |
|---|---|
| Скорость авторинга 300+ тестов | Maestro YAML в 5-10× короче |
| Скорость прогона | Maestro ~30 мин на 300 vs Appium ~90 мин |
| QA знает Maestro, не Appium | прямой match |
| Setup инфры | один бинарник vs Appium server + drivers + capabilities |
| Recording mode | YAML генерится тыканьем по экрану — буст на старте |
| API setup/verify через `api/client.py` | через pytest-wrapper, как web_ui делает с Playwright |

Решение принято 2026-05-12 после обсуждения. Гибрид не выбираем — один фреймворк.

---

## Roadmap (5 волн)

| Wave | Что | Когда стартует | Тестов (план) | Спека |
|---|---|---|---|---|
| **0** | Инфраструктура: Maestro CLI, mobile/ структура, pytest-wrapper, smoke-каркас | **СЕЙЧАС** (без приложения) | 0 | **детальная** |
| 1 | Driver registration (start → verify → complete) | После установки APK/IPA + анализа Claude | ~15 | placeholder |
| 2 | Login + /me + profile edit | После W1 | ~20 | placeholder |
| 3 | Feed + accept order | После W2 | ~30 | placeholder |
| 4 | Negative + RBAC + edge cases + iOS-specific | После W3 | ~100 | placeholder |
| 5 | Performance (cold start, memory) + accessibility | После W4 (опционально) | ~20 | placeholder |

---

## Wave 0 — инфраструктура (детальная спека)

### Шаг W0.1 — установить Maestro локально (один раз)

Это **руками** — пользователю, не Codex'у. Codex упомянет это в README, но не запускает (на CI-машинах Codex'а нет Maestro).

```bash
# macOS
curl -Ls "https://get.maestro.mobile.dev" | bash
# либо
brew tap mobile-dev-inc/tap && brew install maestro

# Проверка
maestro --version    # ожидается >=1.40
```

### Шаг W0.2 — обновить `pytest.ini`

Добавить маркеры:
```ini
mobile: mobile UI tests via Maestro (slow, requires device/emulator + maestro CLI)
mobile_android: subset that runs only on Android
mobile_ios: subset that runs only on iOS
mobile_smoke: fast mobile-smoke subset
requires_device: requires a running emulator or connected device
requires_maestro: requires `maestro` CLI in PATH
```
И `testpaths`:
```ini
testpaths = tests web_ui mobile
```

### Шаг W0.3 — `.env.example` дополнить

```bash
# ----- Mobile (Maestro) -----

# Android: либо путь к APK (для свежей установки), либо app_id уже установленного
ANDROID_APP_PATH=                       # /absolute/path/to/manzil-driver.apk
ANDROID_APP_ID=                         # e.g. uz.manzil.driver (TBD by Claude analysis)
ANDROID_DEVICE_ID=                      # `adb devices` — пусто = берёт первый

# iOS: либо путь к .app (simulator) / .ipa (real device), либо bundleId
IOS_APP_PATH=                           # /absolute/path/to/Manzil.app
IOS_APP_ID=                             # e.g. uz.manzil.driver (TBD)
IOS_DEVICE_NAME=iPhone 15
IOS_PLATFORM_VERSION=17.0

# Maestro
MAESTRO_DEFAULT_TIMEOUT_MS=10000
MAESTRO_FLOWS_DIR=mobile/flows
```

### Шаг W0.4 — создать `mobile/` структуру

```
mobile/
├── __init__.py
├── README.md                           # setup instructions
├── conftest.py                         # pytest fixtures: maestro runner, device, api seed
├── flows/                              # Maestro YAML (один файл = один флоу)
│   ├── _config.yaml                    # shared config (appId, env defaults)
│   ├── _common/                        # переиспользуемые суб-флоу (login_as, cleanup)
│   │   └── .gitkeep
│   ├── smoke/
│   │   └── app_launches.yaml
│   └── driver/
│       ├── registration/.gitkeep       # Wave 1 наполнит
│       ├── login/.gitkeep              # Wave 2
│       └── feed/.gitkeep               # Wave 3
├── runner/
│   ├── __init__.py
│   ├── maestro_runner.py               # subprocess wrapper для `maestro test`
│   └── locator_helpers.py              # helpers если понадобятся (Wave 1+)
├── seed/
│   ├── __init__.py
│   └── api_seed.py                     # переиспользует api/client.py для setup
└── tests/
    ├── __init__.py
    └── smoke/
        ├── __init__.py
        └── test_app_launches.py        # pytest, который вызывает maestro flow
```

### Шаг W0.5 — `mobile/runner/maestro_runner.py`

```python
"""Тонкая обёртка над `maestro test` CLI.

Зачем pytest-обёртка вокруг YAML:
- Setup пред-условий через api/client.py (зарегистрировать пользователя,
  засеять заказы) ДО запуска UI-флоу.
- Verify пост-условий через API ПОСЛЕ флоу (статус заказа изменился).
- Cleanup гарантирован даже если flow упал.
- Parametrize по платформе и роли через pytest fixtures.
- Allure-репорты в общем формате с остальным сьютом.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MaestroNotInstalled(RuntimeError):
    """Raised at session start if `maestro` is not in PATH."""


@dataclass
class MaestroResult:
    """Результат прогона одного флоу."""
    flow: Path
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def check_maestro_installed() -> str:
    """Проверка что maestro в PATH. Возвращает версию."""
    if shutil.which("maestro") is None:
        raise MaestroNotInstalled(
            "Maestro CLI не найден. Установи: "
            "`curl -Ls 'https://get.maestro.mobile.dev' | bash` "
            "или `brew install maestro`"
        )
    result = subprocess.run(
        ["maestro", "--version"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def run_flow(
    flow_path: Path,
    *,
    params: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    timeout_s: int = 600,
) -> MaestroResult:
    """Запустить один Maestro-флоу.

    Args:
        flow_path: путь к .yaml.
        params: значения для `${VAR}` подстановок в YAML (через --env флаг Maestro).
        env: дополнительные shell env vars (например `appId`).
        platform: "android" | "ios" — для логирования (Maestro сам выбирает по подключённому устройству).
        timeout_s: жёсткий timeout всего флоу.

    Returns:
        MaestroResult с returncode, stdout, stderr.
    """
    if not flow_path.exists():
        raise FileNotFoundError(flow_path)

    cmd = ["maestro", "test", str(flow_path)]
    if params:
        for k, v in params.items():
            cmd.extend(["--env", f"{k}={v}"])

    merged_env = {**os.environ}
    if env:
        merged_env.update(env)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=merged_env,
        check=False,
    )
    return MaestroResult(
        flow=flow_path,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
```

### Шаг W0.6 — `mobile/conftest.py`

```python
"""Mobile-тесты: pytest fixtures для Maestro-обёртки."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest

from config.settings import Settings
from mobile.runner.maestro_runner import (
    MaestroNotInstalled,
    check_maestro_installed,
    run_flow,
)

Platform = Literal["android", "ios"]

FLOWS_DIR = Path(__file__).parent / "flows"


@pytest.fixture(scope="session", autouse=True)
def _verify_maestro_installed() -> None:
    """Падает один раз в начале сессии если maestro не установлен."""
    try:
        version = check_maestro_installed()
        print(f"\n[maestro] using {version}")
    except MaestroNotInstalled as e:
        pytest.skip(str(e), allow_module_level=True)


@pytest.fixture(params=["android", "ios"], ids=["android", "ios"])
def platform(request: pytest.FixtureRequest) -> Platform:
    """Параметризация по платформе. Тест прогоняется на обеих.

    Auto-skip если для платформы не задан APP_PATH/APP_ID в env.
    """
    p: Platform = request.param
    if p == "android":
        if not os.environ.get("ANDROID_APP_ID") and not os.environ.get("ANDROID_APP_PATH"):
            pytest.skip("ANDROID_APP_ID/PATH не задан")
    if p == "ios":
        if not os.environ.get("IOS_APP_ID") and not os.environ.get("IOS_APP_PATH"):
            pytest.skip("IOS_APP_ID/PATH не задан")
    return p


@pytest.fixture
def maestro_env(platform: Platform) -> dict[str, str]:
    """env-параметры для Maestro YAML (доступны как ${APP_ID} и т.д. в флоу)."""
    if platform == "android":
        return {
            "APP_ID": os.environ.get("ANDROID_APP_ID", ""),
            "APP_PATH": os.environ.get("ANDROID_APP_PATH", ""),
        }
    return {
        "APP_ID": os.environ.get("IOS_APP_ID", ""),
        "APP_PATH": os.environ.get("IOS_APP_PATH", ""),
    }


@pytest.fixture
def maestro(maestro_env: dict[str, str], platform: Platform):
    """Удобный коллбек: maestro(flow_name, params=...) → MaestroResult.

    Использование:
        result = maestro("smoke/app_launches.yaml")
        assert result.passed, result.stderr
    """
    def _run(flow_rel_path: str, params: dict[str, str] | None = None):
        flow_path = FLOWS_DIR / flow_rel_path
        return run_flow(flow_path, params=params, env=maestro_env, platform=platform)
    return _run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Attach maestro stdout/stderr к Allure при падении."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call" or not rep.failed:
        return
    # Логи Maestro уже в captured stdout pytest'а — Allure их подцепит автоматом.
    # Скриншоты Maestro кладёт в ~/.maestro/tests/<timestamp>/ — путь
    # печатается в stderr; в Wave 1 можно подцеплять конкретные файлы.
```

### Шаг W0.7 — `mobile/flows/_config.yaml`

Shared config, переиспользуется из других YAML:
```yaml
# Маэстро config — берётся по умолчанию для всех флоу в этой папке
# (через include sub-flows). Здесь только дефолты которые имеет смысл
# вынести; конкретные appId задаются в каждом флоу через ${APP_ID}.

appId: ${APP_ID}
# Maestro >=1.40 поддерживает per-flow `env:` блок для inline defaults;
# реальные значения приходят из --env CLI флага (см. mobile/conftest.py).
```

### Шаг W0.8 — `mobile/flows/smoke/app_launches.yaml`

Минимальный smoke-флоу:
```yaml
appId: ${APP_ID}
tags:
  - smoke
---
- launchApp:
    clearState: true
- assertVisible:
    text: ".*"           # любой текст на стартовом экране
    timeout: 10000
# Конкретные ассерты добавим в Wave 1, когда Claude проанализирует
# real splash/initial screen.
```

### Шаг W0.9 — `mobile/tests/smoke/test_app_launches.py`

```python
"""Mobile smoke: приложение стартует и показывает initial-экран.

Wave 0 — каркас. Тест проходит mypy/ruff и `--collect-only`, но реально
запускается только если ANDROID_APP_ID / IOS_APP_ID задан и устройство
подключено. Без env → skip с понятной причиной.
"""

from __future__ import annotations

import pytest

from mobile.pages._base import Platform   # на случай если в Wave 1+ Locator helpers пригодятся


@pytest.mark.mobile
@pytest.mark.mobile_smoke
@pytest.mark.requires_device
@pytest.mark.requires_maestro
def test_app_launches_and_shows_initial_screen(
    maestro,
    platform: Platform,
) -> None:
    """Запускаем смоук-флоу и проверяем что Maestro отработал успешно."""
    result = maestro("smoke/app_launches.yaml")
    assert result.passed, f"smoke failed on {platform}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
```

> **Примечание:** в W0 в `mobile/pages/_base.py` пока ничего класть не нужно —
> Maestro работает с YAML-флоу, не Python page objects. Папку `mobile/pages/`
> вообще не создаём (в отличие от Appium-варианта). Если в Wave 1+ окажется,
> что нужны Python-хелперы (например для парсинга UI-дампа), добавим тогда.

### Шаг W0.10 — `mobile/seed/api_seed.py`

Тонкие функции для API setup до запуска флоу:
```python
"""API setup для mobile-тестов: регистрируем драйверов, заводим заказы и т.п.

Реюзает api/client.py — тот же паттерн что в web_ui/seed/.
В Wave 0 — пустые placeholder'ы. Конкретные сидеры появятся в Wave 1+
(например `seed_registered_driver(phone)` для login-сценариев).
"""

from __future__ import annotations

from api.client import ApiClient
from config.settings import Settings


def make_anonymous_client(settings: Settings) -> ApiClient:
    """Свежий клиент без токена — для регистраций."""
    return ApiClient(base_url=str(settings.api_base_url), verify=settings.http_verify_ssl)


# Wave 1 наполнит: seed_registered_driver, seed_order_visible_to_driver, и т.д.
```

### Шаг W0.11 — `mobile/README.md`

```markdown
# Mobile tests (Maestro)

## Setup (одноразово)

### macOS
```
# Maestro CLI
curl -Ls "https://get.maestro.mobile.dev" | bash
# или
brew tap mobile-dev-inc/tap && brew install maestro

# Android: Android Studio → SDK Manager → API 34 emulator
# iOS: Xcode + simctl iPhone 15
```

### Запуск устройств
```
# Android
emulator -avd Pixel_7_API_34
# iOS
xcrun simctl boot "iPhone 15"
open -a Simulator
```

### Установить приложение (один раз)
```
# Android
adb install /path/to/manzil-driver.apk

# iOS simulator
xcrun simctl install booted /path/to/Manzil.app
```

### Заполнить `.env`
```
ANDROID_APP_ID=uz.manzil.driver
IOS_APP_ID=uz.manzil.driver
# (см. .env.example)
```

## Прогон
```
pytest mobile/                            # все mobile-тесты на обеих платформах
pytest mobile/ -m mobile_smoke            # только smoke
pytest mobile/ -k android                 # только Android
maestro test mobile/flows/smoke/app_launches.yaml --env APP_ID=uz.manzil.driver   # напрямую без pytest
```

## Структура

- `flows/` — YAML флоу (Maestro-тесты)
- `flows/_common/` — sub-flows, подключаются через `runFlow:` в Maestro
- `runner/` — Python-обёртка над `maestro test` CLI
- `seed/` — API setup через `api/client.py`
- `tests/` — pytest-тесты, которые вызывают флоу через `maestro` fixture
```

### Финальная проверка Wave 0

```bash
pip install -e ".[dev]"
ruff check mobile/
mypy --strict mobile/
pytest mobile/ --collect-only -q                # 2 теста (android+ios)
pytest mobile/ -q 2>&1 | tail -5                # без maestro или env → skip с причиной
```

### Коммит после Wave 0

```
test(mobile): Maestro infrastructure (Wave 0)

- Maestro-Python pytest wrapper: subprocess wrapper around `maestro test`
  with per-platform env injection (APP_ID / APP_PATH).
- flows/ directory: YAML flows authored declaratively; _common/ for shared
  sub-flows via `runFlow:`.
- seed/ reuses api/client.py for pre-test API setup (driver registration,
  order seeding) — same pattern as web_ui/.
- Smoke skeleton auto-skips when ANDROID_APP_ID/IOS_APP_ID not set or
  maestro CLI not in PATH.
- README documents one-time Maestro install + emulator setup.

App-specific flows and tests come in Wave 1+ after Claude analyzes the
actual application screens via Maestro Inspector.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## Phase 1+ — нужно от пользователя (для анализа Claude)

Чтобы Claude мог начать анализ для Wave 1, нужно:

1. **APK файл** для Android — путь типа `/Users/.../manzil-driver-vX.Y.apk`.
2. **`.app` или `.ipa`** для iOS:
   - `.app` для simulator (из Xcode `Build → Show Build Folder`).
   - `.ipa` для real device.
   - Либо исходники Xcode — Claude соберёт через `xcodebuild`.
3. **`appId` / Bundle ID** — обычно совпадает на iOS и Android (например
   `uz.manzil.driver`). Если не знаешь — Claude вытащит из бандла
   (`aapt dump badging` для APK, `unzip -p Info.plist` для iOS).
4. **Backend URL** — приложение бьёт `https://dev-manzil.greatmall.uz` (как web)
   или отдельный mobile-backend? Уточнить в команде.
5. **Тестовые аккаунты** — для login-сценариев. Если только через регистрацию
   (Telegram deeplink) — упрёмся в OTP capture (см. `CODEX_NEXT.md` Task N4 —
   Telegram OTP пока broken).
6. **Дизайн / Figma** (опционально) — помогает писать негативные сценарии.

Когда это всё будет — **скажи Claude**, и я:
1. Открою `maestro studio` или `adb shell uiautomator dump` / `xcrun simctl io booted enumerate` — сканирую экраны и иерархии.
2. Использую `maestro record` (recording mode) для типичных пользовательских флоу — это даст готовый baseline YAML.
3. Зафиксирую все locator'ы (testID/accessibility label/text/ID) и где их **нет** — отметить как "нужно попросить разработчиков добавить".
4. Напишу детальную спеку Wave 1 (registration flow) с готовыми YAML и pytest-обёртками.

---

## Maestro-специфика, которую полезно знать заранее

- **Локаторы:** в YAML ссылаются через `text:`, `id:`, `point: x, y`. Лучшее —
  `id:` (accessibility identifier из app). Если разработчики не дали testID,
  идём через `text:` + `index:`.
- **Per-platform overrides:** один YAML работает на обеих, но можно так:
  ```yaml
  - tapOn:
      id: "login_button"
  - assertVisible:
      text: "Войти"          # один текст
  - runFlow:
      when:
        platform: iOS
      file: ios_specific.yaml
  ```
- **Параметризация:** `${VAR}` подставляется из `--env VAR=value`. У нас
  pytest-фикстура `maestro_env` уже это делает.
- **Sub-flows:** `runFlow: file: _common/login_as_driver.yaml` — переиспользуемые
  блоки, как функции.
- **runScript:** позволяет вызвать shell/JS внутри флоу. Удобно для API-вызовов
  на лету (`runScript: api_setup.js`), но мы обычно делаем это **до** запуска
  флоу из pytest — чище и быстрее дебажить.
- **Maestro Cloud:** платный CI runner от Mobile.dev. Альтернатива — self-hosted
  emulator на GitHub Actions (бесплатно, но медленнее).
- **Recording mode:** `maestro record flow.yaml` — открывает приложение и
  записывает действия в YAML. **Огромный буст** для первой версии Wave 1.

---

## Что не делать сейчас (Codex)

- **Не угадывать** `id:` локаторов до анализа. YAML в W0 — только smoke с `text: ".*"`.
- **Не писать флоу** в `mobile/flows/driver/` до Wave 1.
- **Не менять** `tests/` и `web_ui/` ради совместимости.
- **Не пытаться** запустить smoke без устройства/maestro — тест уйдёт в skip, это **ожидаемо**.
- **Не добавлять** Appium параллельно — выбран Maestro, не размножаем фреймворки.
- **Не использовать** `runScript:` внутри YAML для API вызовов в W0 —
  pytest-обёртка делает это чище через `mobile/seed/api_seed.py`.
