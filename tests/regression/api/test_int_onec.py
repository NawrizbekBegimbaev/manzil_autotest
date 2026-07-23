"""API — 1С inbound webhook (06_integrations_sms_dicts.json, INT-001…024).

`POST /api/v1/integrations/1c/shipments/status` и `.../batch`. 1С зовёт вебхук, когда
машина прибыла в пункт назначения → заказ IN_TRANSIT → COMPLETED. Аутентификация —
shared-secret заголовок `X-Webhook-Token` (не Keycloak-JWT): одиночный эндпойнт
объявлен `permitAll`, контроллер сам делает константно-временную проверку токена
(`MessageDigest.isEqual`). Пустой/незаданный секрет → fail-closed (все запросы 401).

СОСТОЯНИЕ СТЕНДА (dev):
- `ONEC_WEBHOOK_SECRET` выдан разработчиками, лежит в `.env` (в git НЕ коммитится). Значение
  токена нигде в коде/логах не печатается. Пусто → happy-path пропускается (skip).
- Негативы аутентификации 003…006 → 401; валидация тела 007/008/015 → 400 (ДО проверки токена,
  @Valid раньше тела метода). Доменные (happy/идемпотентность/404/409) — через OrderFactory.

BUG-040: батч-эндпойнт НЕ внесён в `permitAll` (матчер — точный путь без `/**`) →
проваливается в `anyRequest().authenticated()` и требует JWT прежде своей же shared-secret
проверки → недостижим для 1С. Батч-кейсы 017…024 — xfail(strict) на корректный контракт.

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.security]

_SINGLE = "/integrations/1c/shipments/status"
_BATCH = "/integrations/1c/shipments/status/batch"
_PLATE = "01A000ZZ"


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _fields(r):
    try:
        return [e.get("field") for e in r.json().get("errors", [])]
    except Exception:  # noqa: BLE001
        return []


def _post(dev_api, path, *, token="hook-token", body=None, raw=None, headers=None):
    """Unauthenticated POST (token=None для Bearer) с заголовком X-Webhook-Token."""
    h = {"X-Webhook-Token": token} if token is not None else {}
    if headers:
        h.update(headers)
    kw = {"headers": h}
    if raw is not None:
        kw["data"] = raw
        h["Content-Type"] = "application/json"
    else:
        kw["json"] = body
    return dev_api.request("POST", path, None, **kw)


def _ev(eid="ev-onec-1", plate=_PLATE, event="DELIVERED"):
    return {"eventId": eid, "licensePlate": plate, "event": event}


# ═══ Single — аутентификация (dev fail-closed: секрет пуст → все 401) ═════════


@pytest.mark.high
def test_no_token_003(dev_api):
    """INT-003: нет X-Webhook-Token → 401 error.unauthorized, заказы не меняются."""
    r = _post(dev_api, _SINGLE, token=None, body=_ev())
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-INT-003] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_wrong_token_004(dev_api):
    """INT-004: неверный токен → 401 error.unauthorized."""
    r = _post(dev_api, _SINGLE, token="definitely-wrong-value", body=_ev())
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-INT-004] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_empty_token_005(dev_api):
    """INT-005: пустой токен ≡ отсутствие токена → 401 error.unauthorized."""
    r = _post(dev_api, _SINGLE, token="", body=_ev())
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-INT-005] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_secret_unconfigured_failclosed_006(dev_api):
    """INT-006: секрет на стенде пуст (fail-closed) → любой токен отвергается 401.
    На dev ONEC_WEBHOOK_SECRET пуст — это ровно проверяемое состояние: даже валидно
    выглядящий токен не подходит, интеграция закрыта по умолчанию."""
    r = _post(dev_api, _SINGLE, token="any-value-should-be-rejected", body=_ev())
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-INT-006] {r.status_code}/{_code(r)}"


# ═══ Single — валидация тела (400 ДО проверки токена) ════════════════════════


@pytest.mark.high
@pytest.mark.validation
def test_empty_eventid_007(dev_api):
    """INT-007: пустой eventId → 400 BAD_REQUEST, errors содержит поле eventId.
    Валидация (@Valid) резолвится раньше тела метода, поэтому 400 приходит до 401."""
    r = _post(dev_api, _SINGLE, body=_ev(eid=""))
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-007] {r.status_code}/{_code(r)}"
    assert "eventId" in _fields(r), f"[API-INT-007] нет поля eventId в errors: {_fields(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_empty_plate_008(dev_api):
    """INT-008: пустой licensePlate → 400 BAD_REQUEST, errors содержит поле licensePlate."""
    r = _post(dev_api, _SINGLE, body=_ev(plate=""))
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-008] {r.status_code}/{_code(r)}"
    assert "licensePlate" in _fields(r), f"[API-INT-008] нет поля licensePlate в errors: {_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_malformed_json_015(dev_api):
    """INT-015: синтаксически битый JSON → 400 BAD_REQUEST, обработка не начинается."""
    r = _post(dev_api, _SINGLE, raw='{"eventId":"e", "licensePlate": broken')
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-015] {r.status_code}/{_code(r)}"


# ═══ Batch — BUG-040: JWT-гейт вместо shared-secret (xfail strict) ════════════


@pytest.mark.high
@pytest.mark.xfail(reason="BUG-040: батч не в permitAll → требует JWT (401 UNAUTHORIZED) вместо shared-secret 401 error.unauthorized", strict=True)
def test_batch_no_token_022(dev_api):
    """INT-022: батч без токена → корректно 401 error.unauthorized (проверка токена до обработки).
    Факт (BUG-040): батч JWT-гейтится → 401 UNAUTHORIZED (framework), доменный verifyToken не достигнут."""
    r = _post(dev_api, _BATCH, token=None, body={"items": [_ev()]})
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-INT-022] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
@pytest.mark.xfail(reason="BUG-040: батч требует JWT → 401 UNAUTHORIZED до валидации (без JWT валидация не достигается)", strict=True)
def test_batch_empty_items_019(dev_api):
    """INT-019: пустой items → корректно 400 BAD_REQUEST (@NotEmpty).
    Факт (BUG-040): без JWT батч → 401 UNAUTHORIZED, до валидации не доходит."""
    r = _post(dev_api, _BATCH, body={"items": []})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-019] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.boundary
@pytest.mark.xfail(reason="BUG-040: батч требует JWT → 401 UNAUTHORIZED до валидации размера", strict=True)
def test_batch_oversize_020(dev_api):
    """INT-020: >500 items → корректно 400 (лимит 500, @Size).
    Факт (BUG-040): без JWT → 401 UNAUTHORIZED."""
    r = _post(dev_api, _BATCH, body={"items": [_ev(eid=f"e{i}") for i in range(501)]})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-020] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
@pytest.mark.xfail(reason="BUG-040: батч требует JWT → 401 UNAUTHORIZED до поэлементной валидации", strict=True)
def test_batch_item_empty_eventid_021(dev_api):
    """INT-021: пустой eventId внутри item → корректно 400 (валидация каждого элемента).
    Факт (BUG-040): без JWT → 401 UNAUTHORIZED."""
    r = _post(dev_api, _BATCH, body={"items": [_ev(eid="")]})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-021] {r.status_code}/{_code(r)}"


# ═══════════════════════════════════════════════════════════════════════════════
# Доменные тесты (нужен ONEC_WEBHOOK_SECRET). Секрет из .env, значение не печатается.
# ═══════════════════════════════════════════════════════════════════════════════

import random
import string
from concurrent.futures import ThreadPoolExecutor

_DELIVERED = "error.webhook.no-active-shipment"


def _rid(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@pytest.fixture
def secret(cfg):
    if not cfg.onec_webhook_secret:
        pytest.skip("ONEC_WEBHOOK_SECRET не задан в .env — 1С happy-path пропущен")
    return cfg.onec_webhook_secret


def _hook(dev_api, secret, body, headers=None):
    h = {"X-Webhook-Token": secret}
    if headers:
        h.update(headers)
    return dev_api.request("POST", _SINGLE, None, headers=h, json=body)


def _hook_batch(dev_api, secret, items):
    return dev_api.request("POST", _BATCH, None, headers={"X-Webhook-Token": secret}, json={"items": items})


def _detail(order_factory, oid):
    return order_factory.api.request("GET", f"/shipper/orders/{oid}", order_factory.admin).json()


def _status(order_factory, oid):
    return _detail(order_factory, oid).get("order", {}).get("status")


def _completed_events(order_factory, oid):
    hist = _detail(order_factory, oid).get("history", [])
    return sum(1 for h in hist if "COMPLET" in str(h.get("type", "")))


# ─── happy / идемпотентность / нормализация ──────────────────────────────────


@pytest.mark.high
@pytest.mark.lifecycle
def test_happy_delivery_001(dev_api, secret, order_factory):
    """INT-001: валидный токен + номер единственного IN_TRANSIT заказа → 200; заказ IN_TRANSIT→COMPLETED."""
    o = order_factory.make("IN_TRANSIT")
    plate = order_factory.last_drivers[0]["plate"]
    r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": plate, "event": "DELIVERED"})
    assert r.status_code == 200, f"[API-INT-001] {r.status_code} {r.text[:120]}"
    assert _status(order_factory, o["id"]) == "COMPLETED", "[API-INT-001] заказ не COMPLETED"
    assert _completed_events(order_factory, o["id"]) == 1, "[API-INT-001] ожидался ровно один переход COMPLETED"


@pytest.mark.high
@pytest.mark.idempotency
def test_idempotent_replay_002(dev_api, secret, order_factory):
    """INT-002: повтор того же eventId — тихий no-op (200); заказ остаётся COMPLETED, ровно ОДИН переход."""
    o = order_factory.make("IN_TRANSIT")
    plate = order_factory.last_drivers[0]["plate"]
    eid = f"at-{_rid()}"
    assert _hook(dev_api, secret, {"eventId": eid, "licensePlate": plate}).status_code == 200, "[API-INT-002] первая доставка"
    r2 = _hook(dev_api, secret, {"eventId": eid, "licensePlate": plate})
    assert r2.status_code == 200, f"[API-INT-002] повтор → {r2.status_code}/{_code(r2)} (ожидали тихий 200)"
    assert _status(order_factory, o["id"]) == "COMPLETED", "[API-INT-002] статус изменился"
    assert _completed_events(order_factory, o["id"]) == 1, "[API-INT-002] повторная обработка (>1 перехода COMPLETED)"


@pytest.mark.medium
def test_plate_normalization_009(dev_api, secret, order_factory):
    """INT-009: разделители/регистр номера нормализуются — заказ с 01A123BC найден по '01 a-123.bc'."""
    o = order_factory.make("IN_TRANSIT", plate="01A123BC")
    r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": "01 a-123.bc", "event": "DELIVERED"})
    assert r.status_code == 200, f"[API-INT-009] {r.status_code} {r.text[:120]}"
    assert _status(order_factory, o["id"]) == "COMPLETED", "[API-INT-009] не завершён по нормализованному номеру"


@pytest.mark.high
@pytest.mark.negative
def test_no_active_shipment_010(dev_api, secret):
    """INT-010: нет IN_TRANSIT-заказа с этим номером → 404 error.webhook.no-active-shipment."""
    r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": "ZZ" + _rid(6).upper(), "event": "DELIVERED"})
    assert r.status_code == 404 and _code(r) == _DELIVERED, f"[API-INT-010] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_event_null_defaults_delivered_013(dev_api, secret, order_factory):
    """INT-013: тело без поля event → подставляется DELIVERED; заказ завершается (200)."""
    o = order_factory.make("IN_TRANSIT")
    plate = order_factory.last_drivers[0]["plate"]
    r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": plate})  # без event
    assert r.status_code == 200, f"[API-INT-013] {r.status_code}/{_code(r)}"
    assert _status(order_factory, o["id"]) == "COMPLETED", "[API-INT-013] не завершён при event=null"


@pytest.mark.low
@pytest.mark.boundary
def test_occurred_at_omitted_014(dev_api, secret, order_factory):
    """INT-014: тело без occurredAt → берётся время сервера; 200, заказ завершается."""
    o = order_factory.make("IN_TRANSIT")
    plate = order_factory.last_drivers[0]["plate"]
    r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": plate, "event": "DELIVERED"})  # без occurredAt
    assert r.status_code == 200, f"[API-INT-014] {r.status_code}/{_code(r)}"
    assert _status(order_factory, o["id"]) == "COMPLETED", "[API-INT-014] не завершён без occurredAt"


@pytest.mark.low
@pytest.mark.i18n
def test_i18n_404_localized_016(dev_api, secret):
    """INT-016: 404 no-active-shipment локализован по Accept-Language (5 языков, текст ≠ ключ)."""
    seen = {}
    for lang in ("ru", "zh", "uz", "ky", "ug"):
        r = _hook(dev_api, secret, {"eventId": f"at-{_rid()}", "licensePlate": "ZZ" + _rid(6).upper()},
                  headers={"Accept-Language": lang})
        assert r.status_code == 404 and _code(r) == _DELIVERED, f"[API-INT-016/{lang}] {r.status_code}/{_code(r)}"
        detail = r.json().get("detail") or r.json().get("message") or ""
        assert detail and _DELIVERED not in detail, f"[API-INT-016/{lang}] не локализовано: {detail!r}"
        seen[lang] = detail
    assert len({seen["ru"], seen["zh"], seen["uz"]}) >= 2, f"[API-INT-016] переводы не различаются: {seen}"


# ─── double-status гонка (single-endpoint): 4-я поверхность MNZL-275? ─────────


@pytest.mark.high
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-035/MNZL-275 (4-я поверхность): completeBySystem вебхука 1С без findByIdForUpdate → гонка double-complete даёт 500 вместо 409", strict=True)
def test_race_double_complete_500(dev_api, secret, order_factory):
    """Гонка (сверх библиотеки): два параллельных вебхука на ОДИН IN_TRANSIT-заказ (один номер,
    РАЗНЫЕ eventId) — оба идут в completeBySystem. Ожидаем: ровно один переход COMPLETED, проигравший
    не 500. Если 500 → 4-я поверхность MNZL-275/BUG-035 (мутация статуса заказа без findByIdForUpdate).
    12 раундов — гонка недетерминированная."""
    five_hundreds = []
    for rnd in range(12):
        plate = "01A" + "".join(random.choices(string.digits, k=6))
        o = order_factory.make("IN_TRANSIT", plate=plate)

        def _fire(i):
            return _hook(dev_api, secret, {"eventId": f"race-{rnd}-{i}-{_rid(4)}", "licensePlate": plate})

        with ThreadPoolExecutor(max_workers=2) as ex:
            rs = list(ex.map(_fire, range(2)))
        codes = [r.status_code for r in rs]
        if 500 in codes:
            five_hundreds.append((rnd, codes, [_code(r) for r in rs]))
        # целостность: ровно один переход COMPLETED, заказ завершён
        assert _completed_events(order_factory, o["id"]) == 1, f"[race r{rnd}] переходов COMPLETED != 1 (двойное завершение): codes={codes}"
    assert not five_hundreds, f"double-complete гонка дала 500 (4-я поверхность MNZL-275/BUG-035): {five_hundreds}"


# ─── batch: BUG-040 (JWT-гейт) — xfail на корректный shared-secret контракт ───

_BATCH_BUG = "BUG-040: батч JWT-гейтится (401 UNAUTHORIZED без JWT) — доменное поведение недостижимо для 1С"


@pytest.mark.high
@pytest.mark.xfail(reason=_BATCH_BUG, strict=True)
def test_batch_happy_017(dev_api, secret):
    """INT-017: батч из нескольких событий → 200 с итогами total/succeeded/failed и per-item ok.
    Факт (BUG-040): батч без JWT → 401 UNAUTHORIZED, доменная обработка не достигается."""
    items = [{"eventId": f"at-{_rid()}", "licensePlate": "01A" + _rid(6).upper()} for _ in range(2)]
    r = _hook_batch(dev_api, secret, items)
    assert r.status_code == 200 and (r.json().get("succeeded") or 0) >= 1, f"[API-INT-017] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.xfail(reason=_BATCH_BUG, strict=True)
def test_batch_mixed_018(dev_api, secret):
    """INT-018: смешанный батч (ok + no-active-shipment) → 200, per-item ok/failure; валидный завершён.
    Факт (BUG-040): 401 UNAUTHORIZED."""
    items = [{"eventId": f"at-{_rid()}", "licensePlate": "01A" + _rid(6).upper()},
             {"eventId": f"at-{_rid()}", "licensePlate": "ZZ" + _rid(6).upper()}]
    r = _hook_batch(dev_api, secret, items)
    assert r.status_code == 200, f"[API-INT-018] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.idempotency
@pytest.mark.xfail(reason=_BATCH_BUG, strict=True)
def test_batch_idempotency_race_023(dev_api, secret):
    """INT-023: конкурентный дубль eventId в батче → один ok, другой 409 error.webhook.duplicate-event.
    Факт (BUG-040): 401 UNAUTHORIZED — доменную идемпотентность батча не проверить, пока батч JWT-гейтится."""
    items = [{"eventId": f"at-{_rid()}", "licensePlate": "01A" + _rid(6).upper()}]
    r = _hook_batch(dev_api, secret, items)
    assert r.status_code == 200, f"[API-INT-023] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.idempotency
@pytest.mark.xfail(reason=_BATCH_BUG, strict=True)
def test_batch_replay_024(dev_api, secret):
    """INT-024: повтор всего батча уже обработанных событий → 200, каждый элемент ok (дубли тихо).
    Факт (BUG-040): 401 UNAUTHORIZED."""
    items = [{"eventId": f"at-{_rid()}", "licensePlate": "01A" + _rid(6).upper()}]
    _hook_batch(dev_api, secret, items)
    r = _hook_batch(dev_api, secret, items)
    assert r.status_code == 200, f"[API-INT-024] {r.status_code}/{_code(r)}"
