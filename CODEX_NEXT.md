# CODEX_NEXT.md — отложенные задачи

> N1 (initial commit) и N2 (CI workflows) вынесены в отдельные файлы для
> параллельной отдачи Codex'у:
> - `CODEX_COMMIT.md` — initial git commit
> - `CODEX_CI.md` — GitHub Actions
>
> В этом файле остаются **N3** (зависит от N1) и **N4** (заблокирован
> backend-ask'ом). Активировать **по очереди**, не параллелить.

---

## Задача N3 — BRD §4 full tender E2E — верификация

**Когда брать:** после того как N1 (`CODEX_COMMIT.md`) закрыт — на HEAD есть
4 коммита и зелёный API-сьют.

**Контекст:** E2E-тест уже **написан** в `tests/e2e/test_full_tender_flow.py` —
13 шагов через два `ApiClient` (supplier + TK). После починок V1+V2 большая
часть инфраструктуры здорова — пора прогнать и зафиксировать, что (если что)
ещё мешает.

### Ожидаемые блокеры (из `bug.txt`)

| Шаг E2E | Бекенд-зависимость | Bug |
|---|---|---|
| 7 — Supplier create order | POST /orders должен принимать новый payload | Закрыто V2 (через dispatcher) |
| 8 — TK видит в /feed | TK_ADMIN JWT не должен биться 401 на /feed | **BUG-008 P0** — открыт |
| 9 — TK submits offer | POST /orders/{id}/offers | (нет известных багов) |
| 12 — Supplier selectWinner | POST /orders/{id}/offers/{id}/select для SUPPLIER_ADMIN | **BUG-004 P1** — открыт |
| 13 — Supplier complete | POST /orders/{id}/complete | (нет известных багов) |

**Прогноз:** E2E **не пройдёт** до закрытия BUG-008 и BUG-004 на стороне
backend. Цель задачи — точно подтвердить это и красиво зафиксировать.

### Шаг N3.1 — прогнать E2E изолированно

```bash
pytest tests/e2e/test_full_tender_flow.py -v --tb=long -s 2>&1 | tee /tmp/manzil_e2e_run.log
```

Запускать **без xdist** (по умолчанию `serial` маркер), чтобы исключить race.

### Шаг N3.2 — классифицировать падение

Прочитать лог и ответить:

1. **Где упал?** Конкретный `allure.step` (шаги 1-13, см. файл). В логе ищем последний успешный `with allure.step(...)` перед traceback.
2. **Почему?** HTTP-статус и `ProblemDetail.detail` из тела ответа.
3. **Совпадает ли с прогнозом выше?** Если да — это известный backend-баг (BUG-008/004), не наш.
4. **Если упал не на ожидаемом шаге** — это новый сюжет: либо новый bug, либо что-то не дочинил Codex в V1/V2.

### Шаг N3.3 — обновить артефакты

**Если E2E упал на BUG-008 (шаг 8):**
- В `tests/e2e/test_full_tender_flow.py` **временно** обернуть тест в `@pytest.mark.xfail(reason="BUG-008: TK_ADMIN JWT 401 on /feed — backend, P0")`.
- В `NOW.md` пометить: «E2E parked: blocked on BUG-008. Re-enable when backend fixes.»

**Если упал на BUG-004 (шаг 12):**
- Аналогично xfail, причина `"BUG-004: SUPPLIER_ADMIN 403 on /offers/{id}/select — backend, P1"`.

**Если упал где-то ещё:**
- НЕ маркировать xfail без явного описания корня.
- Завести запись в `bug.txt` (новый BUG-XXX) с шагами воспроизведения из лога.
- Доложить пользователю, остановиться.

**Если прошёл (неожиданная победа):**
- Снять xfail если был.
- В `NOW.md` пометить: «BRD §4 E2E — GREEN на 2026-MM-DD ✅».
- Это значит BUG-008 и BUG-004 закрыты — обновить `bug.txt` соответствующе.

### Шаг N3.4 — добавить smoke-вариант (опционально)

Если шаги 7-13 заблокированы backend-багами надолго, имеет смысл написать
**частичный E2E** — шаги 1-6 (registration + warehouse + vehicle + order create
до фазы tendering). Это `tests/e2e/test_supplier_setup_flow.py` — отдельный
файл, маркер `e2e_partial`, не блокируется BUG-008/004. Спека — отдельный
блок в `NOW.md` "Следующие блоки", не делать прямо сейчас.

### Чего НЕ делать

- НЕ переписывать `test_full_tender_flow.py` под "обход" багов. BRD §4
  требует именно сквозной сценарий — обходить = ложная зелёнка.
- НЕ маркировать xfail без точной ссылки на конкретный bug из `bug.txt`.
- НЕ запускать E2E под xdist (`-n N`) — тест помечен `serial` намеренно
  (shared accounts, последовательный state).

---

## Задача N4 — Telegram OTP для mobile-register

**Когда брать:** **заблокирован** backend-ask'ом до тех пор, пока не появится
dev-endpoint для отдачи OTP. Активный шаг прямо сейчас — только N4.3 (зафиксить
backend ask в `BACKEND_ASKS.md`). N4.1 и N4.2 можно сделать после, когда
становится понятно, нужны они или нет.

**Контекст:** Mobile driver registration требует Telegram OTP. Сейчас:
- `TELEGRAM_OTP_MODE=fixed`, `TELEGRAM_OTP=123456` в `.env`.
- Бекенд **не принимает** `123456` — POST `/verify` → 400 (3 теста падают).
- `utils/otp.py` уже имеет pluggable архитектуру (FIXED / ENDPOINT / MAILHOG) — менять её не надо, нужен только рабочий endpoint **или** скип.

В отличие от email-OTP (мы решили через Gmail IMAP), у Telegram нет
такого же "общего ящика" — каждый driver-аккаунт привязывается к свежему
номеру, который мы не контролируем.

### Стратегия — 3 шага

| Шаг | Что | Срок | Зависит от |
|---|---|---|---|
| N4.1 | Probe — точно подтвердить что `fixed=123456` не работает | сейчас | — |
| N4.2 | Временный скип `requires_telegram_otp` тестов с явной причиной | сейчас | N4.1 закончил |
| N4.3 | Договорённость с backend о dev-endpoint `/dev/last-otp/{phone}` | offline, переговоры | — |

### Шаг N4.1 — probe Telegram OTP

Скрипт `/tmp/probe_telegram_otp.py`:

```python
"""Probe: какой код принимает POST /auth/mobile/registrations/verify в dev."""
from __future__ import annotations

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import DriverRegistrationStartRequest, VerifyMobileOtpRequest
from config.settings import Settings
from data.phone_pool import PhonePool

settings = Settings()
client = ApiClient(settings)
phone = PhonePool(settings).lease().__enter__()
print("Probe phone:", phone)

# Step 1: start
start = auth_ep.start_driver_registration(
    client, DriverRegistrationStartRequest(phone=phone)
)
print("Deeplink:", start.telegram_deep_link)

# Try different OTP codes against /verify and see what backend says
candidates = ["123456", "000000", "111111", "0000", "1234"]
for code in candidates:
    try:
        r = client._client.post(
            "/api/v1/auth/mobile/registrations/verify",
            json={"phone": phone, "code": code},
            headers={"Content-Type": "application/json"},
        )
        print(f"  code={code!r:>10} → {r.status_code}  {r.text[:200]}")
    except Exception as e:
        print(f"  code={code!r:>10} → EXC {e!r}")
```

**Что искать в выводе:**
- Если для всех кодов 400 с одинаковым `detail` — backend **не имеет**
  фиксированного dev-кода, нужен endpoint.
- Если для какого-то кода 200/204 — backend имеет dev-код, мы просто
  не угадали. Тогда обновить `.env.example` и `TELEGRAM_OTP`.
- Если `detail` намекает на формат ("expected 4 digits") — следовать подсказке.

**Результат N4.1 определяет ход N4.2.**

### Шаг N4.2 — временный скип, если probe не вскрыл рабочий код

Если probe показал, что dev-фиксированного кода нет — **до договорённости
с backend** все mobile-register тесты должны скипаться чисто, а не падать
с 400.

Найти все тесты с `requires_telegram_otp` и заменить их фикстурный
доступ к OTP на **session-scoped probe-фикстуру**, которая один раз
проверяет работоспособность Telegram-OTP режима и `pytest.skip`-ит
весь блок если режим не работает.

Добавить в `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def telegram_otp_available(settings: Settings) -> bool:
    """One-time probe at session start. Skips telegram-OTP tests cleanly
    if dev backend doesn't accept the configured fixed code.

    Why session-scoped: we don't want each test to burn a phone and a
    backend OTP-start just to figure out we'll skip.
    """
    if settings.telegram_otp_mode is not OtpMode.FIXED:
        return True  # endpoint mode — trust the config
    from utils.otp import _telegram_fixed_works_in_dev
    return _telegram_fixed_works_in_dev(settings)


@pytest.fixture(autouse=True)
def _skip_if_no_telegram_otp(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("requires_telegram_otp"):
        if not request.getfixturevalue("telegram_otp_available"):
            pytest.skip("Telegram OTP not capturable in current mode — see CLAUDE.md OQ#3")
```

И в `utils/otp.py` добавить `_telegram_fixed_works_in_dev(settings)` —
зарегистрировать одного драйвера, попробовать verify, вернуть True/False.

**Альтернатива (проще):** просто помечать каждый `requires_telegram_otp`-тест
`@pytest.mark.skipif(settings.telegram_otp_mode is OtpMode.FIXED, reason="...")`.
Менее гибко, но меньше кода. Решить по результатам N4.1.

### Шаг N4.3 — backend ask

Создать файл `BACKEND_ASKS.md` в корне со списком известных просьб к
backend-команде. Туда первая запись:

```markdown
# Backend Asks — список договорённостей с backend-командой

## OTP capture для тестов

### Telegram OTP (driver mobile-register) — открыто

**Проблема:** dev-инстанс выдаёт реальный OTP в Telegram-чат, тесты не
могут его прочитать программно. Фиксированного dev-кода нет (probe
2026-05-XX подтвердил).

**Просьба:**
- Добавить dev-only endpoint `GET /dev/last-otp/{phone}` → `{"code": "123456"}`,
  доступный только при `app.env=dev` без авторизации (или с shared dev-secret в header).
- Возвращать последний сгенерированный OTP для указанного номера.
- TTL — как у самого OTP (5 минут).

**Альтернатива:** дев-режим, в котором для всех номеров `OTP=123456`. Минус —
тесты на TTL/expiry становятся непроверяемыми.

**Impact:** разблокирует 3+ теста mobile-register, открывает 1 шаг E2E
для драйверского сценария (вне BRD §4, но в roadmap).

**Owner:** [TBD — обсудить с backend-lead]
**Filed:** 2026-05-13
```

Когда endpoint появится:
1. В `.env.example` обновить `TELEGRAM_OTP_MODE=endpoint` + `TELEGRAM_OTP_ENDPOINT=...`.
2. В `utils/otp.py` дописать ветку `OtpMode.ENDPOINT` для Telegram (для email уже есть, можно скопировать паттерн).
3. Снять `_skip_if_no_telegram_otp` гард или дать ему пропускать тесты в `endpoint` режиме.

### Чего НЕ делать

- НЕ ставить MTProto/Telethon — это излишество для dev-тестов; договориться с backend проще.
- НЕ скипать тесты молча через `pytest.mark.skip` без reason. Always с причиной + ссылкой на этот документ или OQ#3 в CLAUDE.md.
- НЕ менять `utils/otp.py` чтобы он retry-ил OTP — корень в backend, а не в нашем коде.
