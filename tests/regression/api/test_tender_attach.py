"""API — Transport order-driver attach/replace/start (04_tendering_transport.json, part 4).

API-TND-096…157 — POST/PUT/DELETE /transport/orders/{id}/drivers, start, available-drivers,
order-drivers, vehicle-types, locations. Плюс МНОГОРАУНДОВЫЕ ГОНКИ: double-attach (один заказ,
залочен), attach-одного-водителя-на-ДВА-заказа (лок на заказ, не на водителя — претендент на
busy-конфликт), start×replace.

Коды ошибок различимы (busy-on-another-order / driver-cap-exceeded / driver-already-attached /
plate-busy / blacklisted / card-id-required / drivers-incomplete / not-owned / not-selected /
drivers-not-editable / must-keep-driver) — сверено с OrderDriverService. Прогон на DEV.
"""

from __future__ import annotations

import concurrent.futures as cf
import random
import string
import uuid

import pytest

from config.settings import get_settings
from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api]

_PAGE_SHAPE = get_settings().page_shape


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _err_fields(r):
    try:
        return {e.get("field") for e in (r.json().get("errors") or [])}
    except Exception:  # noqa: BLE001
        return set()


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _page(r):
    b = r.json()
    if _PAGE_SHAPE == "nested":
        assert isinstance(b, dict) and "page" in b, "MNZL-245: ожидался вложенный page"
        return b["page"]
    return b


def _d(n):
    return "".join(random.choices(string.digits, k=n))


def _plate():
    return "01A" + _d(4)


# ─── fixtures / helpers ──────────────────────────────────────────────────────


@pytest.fixture
def carrier(api):
    return api("transport_admin")


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def mk_driver(carrier):
    """Водитель dev-перевозчика БЕЗ cardId на файле (cardId передаём в assignment)."""
    created = []

    def _mk(card=None):
        body = {"fullName": "AT Driver", "phone": "+99890" + _d(7)}
        if card:
            body["cardId"] = card
        r = carrier.post("/transport/drivers", json=body)
        assert r.status_code == 201, f"driver setup: {r.status_code} {r.text[:160]}"
        created.append(r.json()["id"])
        return r.json()["id"]

    yield _mk
    for did in reversed(created):
        try:
            carrier.delete(f"/transport/drivers/{did}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def fresh_carrier(dev_api, cfg):
    created = []
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")

    def _mk():
        phone = "+99890" + _d(7)
        body = {"name": f"AT-TC-{_d(10)}", "tin": _d(9), "address": "Tashkent, Sayyod 1",
                "transportTypes": ["AUTO"], "isAll": True, "cityIds": [], "blacklistWarehouseIds": [],
                "admin": {"fullName": "AT C2", "phone": phone, "password": cfg.dev_account_password}}
        r = dev_api.request("POST", "/super-admin/transport-companies", sa, json=body)
        assert r.status_code == 201, f"fresh_carrier: {r.status_code} {r.text[:160]}"
        cid = r.json()["id"]
        created.append(cid)
        return RoleClient(dev_api, dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")), cid

    yield _mk
    for cid in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


def _assign(did, plate=None, card="__default__"):
    a = {"driverId": did, "licensePlate": plate or _plate()}
    if card == "__default__":
        a["cardId"] = _d(18)
    elif card is not None:
        a["cardId"] = card
    return a


def _attach(carrier, oid, *assignments):
    return carrier.post(f"/transport/orders/{oid}/drivers", json={"drivers": list(assignments)})


def _busy_driver(carrier, mk_driver, order_factory):
    """Водитель, занятый на ДРУГОМ активном заказе (для busy-on-another-order)."""
    other = order_factory.make("SELECTED")
    d = mk_driver()
    assert _attach(carrier, other["id"], _assign(d)).status_code in (200, 201), "busy setup"
    return d


# ═══ POST attach (096…113) ═══════════════════════════════════════════════════


@pytest.mark.high
def test_attach_happy_096(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    r = _attach(carrier, o["id"], _assign(d, plate="沪A12345"))
    assert r.status_code == 200, f"[API-TND-096] {r.status_code} {r.text[:160]}"
    assert any(x.get("licensePlate") == "沪A12345" for x in r.json()), f"[API-TND-096] plate не сохранён: {r.json()}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_attach_on_inwork_097(carrier, mk_driver, order_factory):
    o = order_factory.make("IN_WORK", drivers_count=2)  # 1 из 2 привязан фабрикой, ещё можно добавить
    d = mk_driver()
    # фабрика привязала 2 (полный комплект) — открепим одного, чтобы освободить место
    attached = _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))
    carrier.delete(f"/transport/orders/{o['id']}/drivers/{attached[0]['driverId'] if attached and 'driverId' in attached[0] else attached[0]['id']}")
    r = _attach(carrier, o["id"], _assign(d))
    assert r.status_code == 200, f"[API-TND-097] attach на IN_WORK: {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_attach_not_editable_098(carrier, mk_driver, order_factory):
    o = order_factory.make("IN_TRANSIT")
    d = mk_driver()
    r = _attach(carrier, o["id"], _assign(d))
    assert r.status_code == 409 and _code(r) == "error.order.drivers-not-editable", f"[API-TND-098] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_attach_not_owned_099(carrier, mk_driver, order_factory):
    o = order_factory.make("PUBLISHED")  # не awarded нашей компании
    d = mk_driver()
    r = _attach(carrier, o["id"], _assign(d))
    assert r.status_code == 404 and _code(r) == "error.order.not-owned-by-transport", f"[API-TND-099] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_attach_foreign_driver_100(carrier, fresh_carrier, order_factory):
    o = order_factory.make("SELECTED")
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": "+99890" + _d(7)}).json()["id"]
    r = _attach(carrier, o["id"], _assign(foreign))
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-TND-100] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_attach_busy_101(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    busy = _busy_driver(carrier, mk_driver, order_factory)
    r = _attach(carrier, o["id"], _assign(busy))
    assert r.status_code == 409 and _code(r) == "error.driver.busy-on-another-order", f"[API-TND-101] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.boundary
def test_attach_cap_exceeded_102(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")  # driversCount=1
    assert _attach(carrier, o["id"], _assign(mk_driver())).status_code == 200
    r = _attach(carrier, o["id"], _assign(mk_driver()))
    assert r.status_code == 409 and _code(r) == "error.order.driver-cap-exceeded", f"[API-TND-102] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_attach_exactly_two_103(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED", drivers_count=2)
    r = _attach(carrier, o["id"], _assign(mk_driver()), _assign(mk_driver()))
    assert r.status_code == 200 and len(r.json()) == 2, f"[API-TND-103] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.validation
def test_attach_card_required_104(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()  # без cardId на файле
    r = _attach(carrier, o["id"], _assign(d, card=None))  # и без cardId в assignment
    assert r.status_code == 400 and _code(r) == "error.driver.card-id-required", f"[API-TND-104] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_attach_card_in_assignment_105(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    r = _attach(carrier, o["id"], _assign(d, card="AB123"))
    assert r.status_code == 200, f"[API-TND-105] {r.status_code} {r.text[:160]}"
    assert carrier.get(f"/transport/drivers/{d}").json().get("cardId") == "AB123", "[API-TND-105] cardId не сохранён"


@pytest.mark.high
@pytest.mark.lifecycle
def test_attach_blacklisted_106(carrier, s_admin, api, mk_driver, order_factory):
    """Blacklist требует COMPLETED-заказ, к которому водитель был привязан. Строим полный
    lifecycle с D → complete → блокируем D → на НОВОМ заказе attach D → blacklisted."""
    warehouse = api("shipper_warehouse")
    o1 = order_factory.make("SELECTED")
    d = mk_driver()
    assert _attach(carrier, o1["id"], _assign(d)).status_code == 200, "[API-TND-106] attach setup"
    assert carrier.post(f"/transport/orders/{o1['id']}/start").status_code == 200, "[API-TND-106] start"
    warehouse.post(f"/warehouse/orders/{o1['id']}/communication", json={"status": "CONFIRMED"})
    warehouse.post(f"/warehouse/orders/{o1['id']}/goods-sent")
    assert s_admin.post(f"/shipper/orders/{o1['id']}/complete").status_code == 200, "[API-TND-106] complete"
    bl = s_admin.post(f"/shipper/orders/{o1['id']}/blacklist", json={"driverId": d, "reason": "AT blacklist"})
    assert bl.status_code in (200, 201), f"[API-TND-106] blacklist setup: {bl.status_code} {bl.text[:160]}"
    o2 = order_factory.make("SELECTED")
    r = _attach(carrier, o2["id"], _assign(d))
    assert r.status_code == 409 and _code(r) == "error.driver.blacklisted", f"[API-TND-106] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_attach_plate_busy_107(carrier, mk_driver, order_factory):
    plate = "77X" + _d(4)
    o1 = order_factory.make("SELECTED")
    assert _attach(carrier, o1["id"], _assign(mk_driver(), plate=plate)).status_code == 200
    o2 = order_factory.make("SELECTED")
    r = _attach(carrier, o2["id"], _assign(mk_driver(), plate=plate.lower() + " "))  # нормализация регистра/пробелов
    assert r.status_code == 409 and _code(r) == "error.order.plate-busy", f"[API-TND-107] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_attach_idempotent_108(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    assert _attach(carrier, o["id"], _assign(d, plate="AA111")).status_code == 200
    r = _attach(carrier, o["id"], _assign(d, plate="BB222"))  # повторный — no-op, plate НЕ обновляется
    assert r.status_code == 200, f"[API-TND-108] {r.status_code}"
    plates = {x["licensePlate"] for x in _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))}
    assert "AA111" in plates and "BB222" not in plates, f"[API-TND-108] plate не должен обновляться: {plates}"


@pytest.mark.high
@pytest.mark.validation
def test_attach_empty_list_109(carrier, order_factory):
    o = order_factory.make("SELECTED")
    r = carrier.post(f"/transport/orders/{o['id']}/drivers", json={"drivers": []})
    assert r.status_code == 400 and "drivers" in _err_fields(r), f"[API-TND-109] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_attach_too_many_110(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED", drivers_count=2)
    r = _attach(carrier, o["id"], _assign(mk_driver()), _assign(mk_driver()), _assign(mk_driver()))
    assert r.status_code == 400 and "drivers" in _err_fields(r), f"[API-TND-110] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_attach_item_validation_111(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    r1 = carrier.post(f"/transport/orders/{o['id']}/drivers", json={"drivers": [{"licensePlate": "AA1"}]})
    assert r1.status_code == 400, f"[API-TND-111] no driverId: {r1.status_code}"
    r2 = carrier.post(f"/transport/orders/{o['id']}/drivers", json={"drivers": [{"driverId": d, "licensePlate": ""}]})
    assert r2.status_code == 400, f"[API-TND-111] blank plate: {r2.status_code}"
    r3 = carrier.post(f"/transport/orders/{o['id']}/drivers", json={"drivers": [{"driverId": d, "licensePlate": "P" * 21}]})
    assert r3.status_code == 400, f"[API-TND-111] plate>20: {r3.status_code}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_attach_race_cap_112(carrier, mk_driver, order_factory, cfg):
    """Двойной attach разных водителей на driversCount=1 (один заказ, залочен): один 200,
    второй 409 cap-exceeded, НИКОГДА 500. 12 раундов."""
    from utils.api_client import ApiClient
    tok = carrier.token
    seen = []
    for _ in range(12):
        o = order_factory.make("SELECTED")
        d1, d2 = mk_driver(), mk_driver()
        clients = [(ApiClient(cfg, base_url=cfg.dev_url), d1), (ApiClient(cfg, base_url=cfg.dev_url), d2)]

        def fire(cd):
            c, d = cd
            return c.request("POST", f"/transport/orders/{o['id']}/drivers", tok,
                             json={"drivers": [{"driverId": d, "licensePlate": _plate(), "cardId": _d(18)}]}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, clients))
        seen.extend(rc)
        assert rc.count(200) == 1, f"ровно один attach должен пройти на cap=1, получили {rc}"
        assert len(_content(carrier.get(f"/transport/orders/{o['id']}/drivers"))) == 1, "должен быть ровно 1 водитель"
    assert 500 not in seen, f"[API-TND-112][race attach cap] 500 недопустим (заказ залочен): {seen}"


@pytest.mark.medium
@pytest.mark.rbac
def test_attach_rbac_113(api, order_factory):
    o = order_factory.make("SELECTED")
    r = _attach(api("shipper_admin"), o["id"], _assign(str(uuid.uuid4())))
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-113] {r.status_code}/{_code(r)}"


# ═══ PUT set drivers (114…122) ═══════════════════════════════════════════════


def _set(carrier, oid, *assignments):
    return carrier.put(f"/transport/orders/{oid}/drivers", json={"drivers": list(assignments)})


@pytest.mark.high
def test_set_happy_114(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED", drivers_count=2)
    a, b = mk_driver(), mk_driver()
    assert _attach(carrier, o["id"], _assign(a), _assign(b)).status_code == 200
    r = _set(carrier, o["id"], _assign(b, plate="KEEP1"))  # оставить только B
    assert r.status_code == 200, f"[API-TND-114] {r.status_code} {r.text[:160]}"
    ids = {x.get("driverId") or x.get("id") for x in _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))}
    assert b in ids and a not in ids, f"[API-TND-114] набор не приведён к [B]: {ids}"


@pytest.mark.medium
def test_set_swap_115(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    b = mk_driver()
    r = _set(carrier, o["id"], _assign(b))
    assert r.status_code == 200, f"[API-TND-115] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
def test_set_plate_refresh_116(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a, plate="OLD11")).status_code == 200
    r = _set(carrier, o["id"], _assign(a, plate="NEW22"))
    assert r.status_code == 200, f"[API-TND-116] {r.status_code}"
    plates = {x["licensePlate"] for x in _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))}
    assert "NEW22" in plates, f"[API-TND-116] plate не обновлён: {plates}"


@pytest.mark.medium
@pytest.mark.validation
def test_set_empty_117(carrier, order_factory):
    o = order_factory.make("SELECTED")
    r = carrier.put(f"/transport/orders/{o['id']}/drivers", json={"drivers": []})
    assert r.status_code == 400 and "drivers" in _err_fields(r), f"[API-TND-117] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
@pytest.mark.boundary
def test_set_over_cap_118(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")  # cap=1
    r = _set(carrier, o["id"], _assign(mk_driver()), _assign(mk_driver()))
    assert r.status_code == 409 and _code(r) == "error.order.driver-cap-exceeded", f"[API-TND-118] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_set_not_owned_and_not_editable_119(carrier, mk_driver, order_factory):
    pub = order_factory.make("PUBLISHED")
    assert _code(_set(carrier, pub["id"], _assign(mk_driver()))) == "error.order.not-owned-by-transport", "[API-TND-119] not-owned"
    it = order_factory.make("IN_TRANSIT")
    r = _set(carrier, it["id"], _assign(mk_driver()))
    assert r.status_code == 409 and _code(r) == "error.order.drivers-not-editable", f"[API-TND-119] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_set_busy_120(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    busy = _busy_driver(carrier, mk_driver, order_factory)
    r = _set(carrier, o["id"], _assign(busy))
    assert r.status_code == 409 and _code(r) == "error.driver.busy-on-another-order", f"[API-TND-120] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_set_error_matrix_121(carrier, fresh_carrier, s_admin, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    # чужой → not-found
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": "+99890" + _d(7)}).json()["id"]
    assert _code(_set(carrier, o["id"], _assign(foreign))) == "error.driver.not-found", "[API-TND-121] foreign"
    # без cardId → card-id-required
    nocard = mk_driver()
    assert _code(_set(carrier, o["id"], _assign(nocard, card=None))) == "error.driver.card-id-required", "[API-TND-121] card"


@pytest.mark.low
@pytest.mark.rbac
def test_set_rbac_122(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").put(f"/transport/orders/{o['id']}/drivers", json={"drivers": [_assign(str(uuid.uuid4()))]})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-122] {r.status_code}/{_code(r)}"


# ═══ PUT replace one driver (123…132) ════════════════════════════════════════


def _replace(carrier, oid, current, new_did, plate=None, card="__default__"):
    body = _assign(new_did, plate, card)
    return carrier.put(f"/transport/orders/{oid}/drivers/{current}", json=body)


@pytest.mark.high
def test_replace_happy_123(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    b = mk_driver()
    r = _replace(carrier, o["id"], a, b, plate="A2")
    assert r.status_code == 200, f"[API-TND-123] {r.status_code} {r.text[:160]}"
    ids = {x.get("driverId") or x.get("id") for x in _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))}
    assert b in ids and a not in ids, f"[API-TND-123] {ids}"


@pytest.mark.medium
def test_replace_same_driver_124(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a, plate="OLD")).status_code == 200
    r = _replace(carrier, o["id"], a, a, plate="NEWP")
    assert r.status_code == 200, f"[API-TND-124] {r.status_code}"


@pytest.mark.high
@pytest.mark.negative
def test_replace_not_attached_125(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    r = _replace(carrier, o["id"], str(uuid.uuid4()), mk_driver())
    assert r.status_code == 404 and _code(r) == "error.order.driver-not-attached", f"[API-TND-125] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.negative
def test_replace_already_attached_126(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED", drivers_count=2)
    a, b = mk_driver(), mk_driver()
    assert _attach(carrier, o["id"], _assign(a), _assign(b)).status_code == 200
    r = _replace(carrier, o["id"], a, b)  # B уже на заказе
    assert r.status_code == 409 and _code(r) == "error.order.driver-already-attached", f"[API-TND-126] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_replace_busy_127(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    busy = _busy_driver(carrier, mk_driver, order_factory)
    r = _replace(carrier, o["id"], a, busy)
    assert r.status_code == 409 and _code(r) == "error.driver.busy-on-another-order", f"[API-TND-127] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_replace_error_matrix_128(carrier, fresh_carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": "+99890" + _d(7)}).json()["id"]
    assert _code(_replace(carrier, o["id"], a, foreign)) == "error.driver.not-found", "[API-TND-128] foreign"
    nocard = mk_driver()
    assert _code(_replace(carrier, o["id"], a, nocard, card=None)) == "error.driver.card-id-required", "[API-TND-128] card"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_replace_plate_busy_129(carrier, mk_driver, order_factory):
    plate = "88Y" + _d(4)
    other = order_factory.make("SELECTED")
    assert _attach(carrier, other["id"], _assign(mk_driver(), plate=plate)).status_code == 200
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    r = _replace(carrier, o["id"], a, mk_driver(), plate=plate)
    assert r.status_code == 409 and _code(r) == "error.order.plate-busy", f"[API-TND-129] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_replace_not_owned_not_editable_130(carrier, mk_driver, order_factory):
    pub = order_factory.make("PUBLISHED")
    assert _code(_replace(carrier, pub["id"], str(uuid.uuid4()), mk_driver())) == "error.order.not-owned-by-transport", "[API-TND-130] not-owned"
    it = order_factory.make("IN_TRANSIT")
    r = _replace(carrier, it["id"], str(uuid.uuid4()), mk_driver())
    assert r.status_code == 409 and _code(r) == "error.order.drivers-not-editable", f"[API-TND-130] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_replace_validation_131(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    a = mk_driver()
    assert _attach(carrier, o["id"], _assign(a)).status_code == 200
    r1 = carrier.put(f"/transport/orders/{o['id']}/drivers/{a}", json={"licensePlate": "AA1"})
    assert r1.status_code == 400, f"[API-TND-131] no driverId: {r1.status_code}"
    r2 = carrier.put(f"/transport/orders/{o['id']}/drivers/{a}", json={"driverId": mk_driver(), "licensePlate": ""})
    assert r2.status_code == 400, f"[API-TND-131] blank plate: {r2.status_code}"


@pytest.mark.low
@pytest.mark.rbac
def test_replace_rbac_132(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").put(f"/transport/orders/{o['id']}/drivers/{uuid.uuid4()}", json=_assign(str(uuid.uuid4())))
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-132] {r.status_code}/{_code(r)}"


# ═══ POST start (133…138) ════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_start_happy_133(carrier, s_admin, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    assert _attach(carrier, o["id"], _assign(mk_driver())).status_code == 200
    r = carrier.post(f"/transport/orders/{o['id']}/start")
    assert r.status_code == 200, f"[API-TND-133] {r.status_code} {r.text[:160]}"
    assert s_admin.get(f"/shipper/orders/{o['id']}").json()["order"]["status"] == "IN_WORK", "[API-TND-133] не IN_WORK"


@pytest.mark.high
@pytest.mark.lifecycle
def test_start_incomplete_134(carrier, order_factory):
    o = order_factory.make("SELECTED")  # без привязанных водителей
    r = carrier.post(f"/transport/orders/{o['id']}/start")
    assert r.status_code == 409 and _code(r) == "error.order.drivers-incomplete", f"[API-TND-134] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_start_not_selected_135(carrier, order_factory):
    o = order_factory.make("IN_WORK")  # уже IN_WORK
    r = carrier.post(f"/transport/orders/{o['id']}/start")
    assert r.status_code == 409 and _code(r) == "error.order.not-selected", f"[API-TND-135] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_start_not_owned_136(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = carrier.post(f"/transport/orders/{o['id']}/start")
    assert r.status_code == 404 and _code(r) == "error.order.not-owned-by-transport", f"[API-TND-136] {r.status_code}/{_code(r)}"


@pytest.mark.xdist_group("start_race")
@pytest.mark.medium
@pytest.mark.lifecycle
def test_start_double_race_137(carrier, mk_driver, order_factory, cfg):
    """Двойной start (один заказ, залочен lockForFulfillment): один 200, второй 409
    (not-selected / concurrent-modification), НИКОГДА 500. 12 раундов."""
    from utils.api_client import ApiClient
    tok = carrier.token
    seen = []
    for _ in range(12):
        o = order_factory.make("SELECTED")
        _attach(carrier, o["id"], _assign(mk_driver()))
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]

        def fire(c):
            return c.request("POST", f"/transport/orders/{o['id']}/start", tok).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, clients))
        seen.extend(rc)
        assert rc.count(200) == 1, f"ровно один start должен пройти, получили {rc}"
    assert 500 not in seen, f"[API-TND-137][race start] 500 недопустим (заказ залочен): {seen}"


@pytest.mark.medium
@pytest.mark.rbac
def test_start_rbac_138(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").post(f"/transport/orders/{o['id']}/start")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-138] {r.status_code}/{_code(r)}"


# ═══ DELETE detach (139…144) ═════════════════════════════════════════════════


@pytest.mark.high
def test_detach_selected_139(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    assert _attach(carrier, o["id"], _assign(d)).status_code == 200
    r = carrier.delete(f"/transport/orders/{o['id']}/drivers/{d}")
    assert r.status_code == 204, f"[API-TND-139] {r.status_code}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_detach_must_keep_140(carrier, order_factory):
    o = order_factory.make("IN_WORK")  # 1 водитель, IN_WORK
    d = _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))[0]
    did = d.get("driverId") or d.get("id")
    r = carrier.delete(f"/transport/orders/{o['id']}/drivers/{did}")
    assert r.status_code == 409 and _code(r) == "error.order.must-keep-driver", f"[API-TND-140] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_detach_one_of_two_141(carrier, order_factory):
    o = order_factory.make("IN_WORK", drivers_count=2)
    d = _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))[0]
    did = d.get("driverId") or d.get("id")
    r = carrier.delete(f"/transport/orders/{o['id']}/drivers/{did}")
    assert r.status_code == 204, f"[API-TND-141] {r.status_code} {r.text[:120]}"


@pytest.mark.high
@pytest.mark.negative
def test_detach_not_attached_142(carrier, order_factory):
    o = order_factory.make("SELECTED")
    r = carrier.delete(f"/transport/orders/{o['id']}/drivers/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.order.driver-not-attached", f"[API-TND-142] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_detach_not_owned_not_editable_143(carrier, order_factory):
    pub = order_factory.make("PUBLISHED")
    assert _code(carrier.delete(f"/transport/orders/{pub['id']}/drivers/{uuid.uuid4()}")) == "error.order.not-owned-by-transport", "[API-TND-143] not-owned"
    it = order_factory.make("IN_TRANSIT")
    r = carrier.delete(f"/transport/orders/{it['id']}/drivers/{uuid.uuid4()}")
    assert r.status_code == 409 and _code(r) == "error.order.drivers-not-editable", f"[API-TND-143] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.rbac
def test_detach_rbac_144(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").delete(f"/transport/orders/{o['id']}/drivers/{uuid.uuid4()}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-144] {r.status_code}/{_code(r)}"


# ═══ GET available-drivers (145…149) + BUG-031 проверка ══════════════════════


@pytest.mark.high
def test_available_145(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    attached = mk_driver()
    assert _attach(carrier, o["id"], _assign(attached)).status_code == 200
    free = mk_driver()
    busy = _busy_driver(carrier, mk_driver, order_factory)
    ids = {x.get("id") or x.get("driverId") for x in _content(carrier.get(f"/transport/orders/{o['id']}/available-drivers?size=200"))}
    assert free in ids, "[API-TND-145] свободный водитель должен быть в available"
    assert busy not in ids, "[API-TND-145] занятый на другом заказе исключён"
    assert attached in ids, "[API-TND-145] прикреплённый к ЭТОМУ заказу присутствует (по контракту → BUG-031 клиентский)"


@pytest.mark.high
@pytest.mark.tenancy
def test_available_not_owned_146(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = carrier.get(f"/transport/orders/{o['id']}/available-drivers")
    assert r.status_code == 404 and _code(r) == "error.order.not-owned-by-transport", f"[API-TND-146] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_available_not_editable_147(carrier, order_factory):
    o = order_factory.make("IN_TRANSIT")
    r = carrier.get(f"/transport/orders/{o['id']}/available-drivers")
    assert r.status_code == 409 and _code(r) == "error.order.drivers-not-editable", f"[API-TND-147] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_available_empty_148(carrier, s_admin, fresh_carrier, order_factory):
    """Свежий перевозчик (0 водителей) выигрывает заказ → available-drivers пуст."""
    o = order_factory.make("PUBLISHED")
    c2, _ = fresh_carrier()
    off = c2.post(f"/transport/orders/{o['id']}/offers", json={"price": 500}).json()["id"]
    assert s_admin.post(f"/shipper/orders/{o['id']}/offers/{off}/select").status_code in (200, 201), "[API-TND-148] select"
    r = c2.get(f"/transport/orders/{o['id']}/available-drivers")
    assert r.status_code == 200 and _content(r) == [], f"[API-TND-148] у свежего перевозчика 0 водителей: {r.text[:120]}"


@pytest.mark.low
@pytest.mark.rbac
def test_available_rbac_149(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").get(f"/transport/orders/{o['id']}/available-drivers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-149] {r.status_code}/{_code(r)}"


# ═══ GET order drivers (150…153) ═════════════════════════════════════════════


@pytest.mark.high
def test_order_drivers_150(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")
    d = mk_driver()
    assert _attach(carrier, o["id"], _assign(d, plate="ZZ999")).status_code == 200
    rows = _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))
    row = next((x for x in rows if (x.get("driverId") or x.get("id")) == d), None)
    assert row and row.get("licensePlate") == "ZZ999" and "phone" in row, f"[API-TND-150] {rows}"


@pytest.mark.high
@pytest.mark.tenancy
def test_order_drivers_foreign_151(carrier, order_factory, fresh_carrier):
    # заказ, awarded НЕ нашей компании: свежий заказ фабрики в PUBLISHED (никому) → not-owned
    o = order_factory.make("PUBLISHED")
    r = carrier.get(f"/transport/orders/{o['id']}/drivers")
    assert r.status_code == 404 and _code(r) == "error.order.not-owned-by-transport", f"[API-TND-151] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_order_drivers_empty_152(carrier, order_factory):
    o = order_factory.make("SELECTED")
    r = carrier.get(f"/transport/orders/{o['id']}/drivers")
    assert r.status_code == 200 and _content(r) == [], f"[API-TND-152] {r.text[:120]}"


@pytest.mark.low
@pytest.mark.rbac
def test_order_drivers_rbac_153(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").get(f"/transport/orders/{o['id']}/drivers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-153] {r.status_code}/{_code(r)}"


# ═══ vehicle-types / locations (154…157) ═════════════════════════════════════


@pytest.mark.low
def test_vehicle_types_154(carrier):
    r = carrier.get("/transport/vehicle-types")
    assert r.status_code == 200 and _page(r).get("size") == 20, f"[API-TND-154] {r.status_code}"


@pytest.mark.low
@pytest.mark.rbac
def test_vehicle_types_rbac_155(api):
    r = api("shipper_admin").get("/transport/vehicle-types")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-155] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_locations_156(carrier):
    r = carrier.get("/transport/locations")
    assert r.status_code == 200 and _page(r).get("size") == 20, f"[API-TND-156] {r.status_code}"


@pytest.mark.low
@pytest.mark.rbac
def test_locations_rbac_157(api):
    r = api("shipper_admin").get("/transport/locations")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-157] {r.status_code}/{_code(r)}"


# ═══ КРОСС-ГОНКИ (сверх библиотеки) ══════════════════════════════════════════


@pytest.mark.medium
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-038 / MNZL-280: гонка attach одного водителя на два заказа → двойное назначение (лок на заказ, не на водителя)", strict=True)
def test_race_attach_driver_two_orders(carrier, mk_driver, order_factory, cfg):
    """ГЛАВНАЯ ГОНКА: один водитель прикрепляется к ДВУМ разным заказам параллельно. Лок — на
    ЗАКАЗ (разные строки), не на водителя → busy-check пропускает оба. Инвариант: водитель не
    может быть на двух активных заказах. Корректно: один 200, второй 409 busy-on-another-order,
    водитель ровно на одном заказе. Сейчас (BUG-038) — оба 200, двойное назначение 12/12."""
    from utils.api_client import ApiClient
    tok = carrier.token
    double_assign = 0
    server_500 = 0
    for _ in range(12):
        oa = order_factory.make("SELECTED")
        ob = order_factory.make("SELECTED")
        d = mk_driver()
        jobs = [(ApiClient(cfg, base_url=cfg.dev_url), oa["id"]), (ApiClient(cfg, base_url=cfg.dev_url), ob["id"])]

        def fire(job):
            c, oid = job
            return c.request("POST", f"/transport/orders/{oid}/drivers", tok,
                             json={"drivers": [{"driverId": d, "licensePlate": _plate(), "cardId": _d(18)}]}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, jobs))
        if 500 in rc:
            server_500 += 1
        # фактическое состояние: на скольких заказах реально оказался водитель
        on_a = any((x.get("driverId") or x.get("id")) == d for x in _content(carrier.get(f"/transport/orders/{oa['id']}/drivers")))
        on_b = any((x.get("driverId") or x.get("id")) == d for x in _content(carrier.get(f"/transport/orders/{ob['id']}/drivers")))
        if on_a and on_b:
            double_assign += 1
    assert server_500 == 0, f"[race attach-2-orders] 500 недопустим: {server_500}/12"
    assert double_assign == 0, \
        f"[race attach-2-orders] БАГ: водитель назначен на ДВА активных заказа в {double_assign}/12 раундах (лок на заказ, не на водителя)"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_race_start_x_replace(carrier, mk_driver, order_factory, cfg):
    """Гонка start × replace на одном SELECTED-заказе (оба под локом заказа): без 500; исход
    согласованный (start 200 + replace 409 not-editable/после-старта, либо replace 200 + start)."""
    from utils.api_client import ApiClient
    tok = carrier.token
    seen = []
    for _ in range(12):
        o = order_factory.make("SELECTED")
        a = mk_driver()
        _attach(carrier, o["id"], _assign(a))
        b = mk_driver()
        cs, cr = ApiClient(cfg, base_url=cfg.dev_url), ApiClient(cfg, base_url=cfg.dev_url)

        def do_start():
            return cs.request("POST", f"/transport/orders/{o['id']}/start", tok).status_code

        def do_replace():
            return cr.request("PUT", f"/transport/orders/{o['id']}/drivers/{a}", tok,
                              json={"driverId": b, "licensePlate": _plate(), "cardId": _d(18)}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fs, fr = ex.submit(do_start), ex.submit(do_replace)
            sc, rp = fs.result(), fr.result()
        seen.extend([sc, rp])
        assert sc in (200, 409) and rp in (200, 409), f"[race start×replace] неожиданно {sc}/{rp}"
    assert 500 not in seen, f"[race start×replace] 500 недопустим: {seen}"
