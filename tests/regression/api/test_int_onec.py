"""API — 1С inbound webhook (06_integrations_sms_dicts.json, INT-001…024).

`POST /api/v1/integrations/1c/shipments/status` и `.../batch`. 1С зовёт вебхук, когда
машина прибыла в пункт назначения → заказ IN_TRANSIT → COMPLETED. Аутентификация —
shared-secret заголовок `X-Webhook-Token` (не Keycloak-JWT): одиночный эндпойнт
объявлен `permitAll`, контроллер сам делает константно-временную проверку токена
(`MessageDigest.isEqual`). Пустой/незаданный секрет → fail-closed (все запросы 401).

СОСТОЯНИЕ СТЕНДА (dev, проверено 2026-07-23):
- `ONEC_WEBHOOK_SECRET` на dev ПУСТ → эндпойнт fail-closed: валидный токен получить
  нельзя, любой запрос с телом-корректным → 401 error.unauthorized. Поэтому happy-path,
  идемпотентность и доменные ошибки (404/409 по госномеру) чёрным ящиком недостижимы —
  в JSON помечены `automation:backend` (нужен секрет стенда), теста здесь нет.
- Автоматизируемо на dev: (а) негативы аутентификации 003…006 (все → 401 error.unauthorized,
  т.к. секрет пуст → fail-closed — это ровно состояние INT-006); (б) валидация тела
  007/008/015 (400 ДО проверки токена: @Valid резолвится раньше тела метода).

BUG-040: батч-эндпойнт НЕ внесён в `permitAll` (матчер — точный путь без `/**`) →
проваливается в `anyRequest().authenticated()` и требует JWT прежде своей же shared-secret
проверки → недостижим для 1С. Батч-кейсы 019…022 — xfail(strict) на корректный контракт.

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
