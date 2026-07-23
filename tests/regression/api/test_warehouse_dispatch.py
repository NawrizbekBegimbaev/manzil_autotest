"""API — Warehouse dispatch: communication + goods-sent (05_warehouse_dispatch.json).

Race-критичный под-блок первым: `goodsSent` и `setCommunication` в OrderService читают заказ
через `findByIdAndShipperCompanyId` БЕЗ `ForUpdate` (карта локов — как в BUG-035). Гонки
double-goods-sent, goods-sent×cancel, communication×replace-driver — 12 раундов, ждём, не
даст ли незалоченный @Version-конфликт 500 (новая поверхность MNZL-275).

Warehouse-эндпойнты гейтятся ТОЛЬКО ролью SHIPPER_WAREHOUSE (офисные, включая admin → FORBIDDEN).
Прогон на DEV.
"""

from __future__ import annotations

import concurrent.futures as cf
import random
import string

import pytest

from config.settings import get_settings

pytestmark = [pytest.mark.regression, pytest.mark.api]


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


def _d(n):
    return "".join(random.choices(string.digits, k=n))


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def warehouse(api):
    return api("shipper_warehouse")


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def carrier(api):
    return api("transport_admin")


def _comm(warehouse, oid, status):
    return warehouse.post(f"/warehouse/orders/{oid}/communication", json={"status": status})


def _order_status(s_admin, oid):
    return s_admin.get(f"/shipper/orders/{oid}").json()["order"]["status"]


@pytest.fixture(scope="session")
def foreign_order_id(dev_api, cfg, api_dev_roles):
    """Заказ чужой компании (B) — для tenancy 404."""
    from tests.regression.order_lifecycle import OrderFactory

    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + _d(7)
    body = {"name": f"AT-B-{_d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": _d(9), "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT B Admin", "phone": aphone, "password": cfg.dev_account_password}}
    r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body)
    assert r.status_code in (200, 201), f"tenant B: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
    whp = "+99890" + _d(7)
    dev_api.request("POST", "/shipper/staff", adm,
                    json={"fullName": "AT B WH", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
    whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    factory = OrderFactory(dev_api, sa, whb, adm, dev_api.token(cph, cpw, cct))
    order = factory.make("IN_WORK")
    yield order["id"]
    factory.teardown()
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


# ═══ POST communication (079…087) ═══════════════════════════════════════════


@pytest.mark.high
def test_comm_happy_079(warehouse, s_admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = _comm(warehouse, o["id"], "CONFIRMED")
    assert r.status_code == 204, f"[API-WH-079] {r.status_code} {r.text[:160]}"
    assert s_admin.get(f"/shipper/orders/{o['id']}").json()["order"].get("communicationStatus") == "CONFIRMED", "[API-WH-079] commStatus"


@pytest.mark.medium
def test_comm_values_080(warehouse, order_factory):
    o = order_factory.make("IN_WORK")
    for st in ("PENDING", "DECLINED", "UNAVAILABLE", "CONFIRMED"):
        assert _comm(warehouse, o["id"], st).status_code == 204, f"[API-WH-080] {st}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_comm_idempotent_081(warehouse, s_admin, order_factory):
    o = order_factory.make("IN_WORK")
    for st in ("CONFIRMED", "PENDING", "CONFIRMED"):
        assert _comm(warehouse, o["id"], st).status_code == 204, f"[API-WH-081] {st}"
    assert _order_status(s_admin, o["id"]) == "IN_WORK", "[API-WH-081] основной статус не должен меняться"


@pytest.mark.medium
@pytest.mark.validation
def test_comm_status_required_082(warehouse, order_factory):
    o = order_factory.make("IN_WORK")
    r = warehouse.post(f"/warehouse/orders/{o['id']}/communication", json={})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-082] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_comm_bad_enum_083(warehouse, order_factory):
    o = order_factory.make("IN_WORK")
    r = warehouse.post(f"/warehouse/orders/{o['id']}/communication", json={"status": "FOO"})
    assert r.status_code == 400, f"[API-WH-083] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_comm_not_inwork_084(warehouse, order_factory):
    o = order_factory.make("SELECTED")
    r = _comm(warehouse, o["id"], "CONFIRMED")
    assert r.status_code == 409 and _code(r) == "error.order.not-communicable", f"[API-WH-084] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_comm_tenancy_085(warehouse, foreign_order_id):
    r = _comm(warehouse, foreign_order_id, "CONFIRMED")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-085] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
def test_comm_rbac_admin_086(api, order_factory):
    o = order_factory.make("IN_WORK")
    r = api("shipper_admin").post(f"/warehouse/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-086] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_comm_rbac_operator_087(api, order_factory):
    o = order_factory.make("IN_WORK")
    r = api("shipper_operator").post(f"/warehouse/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-087] {r.status_code}/{_code(r)}"


# ═══ POST goods-sent (088…093) ══════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_goods_sent_happy_088(warehouse, s_admin, order_factory):
    o = order_factory.make("IN_WORK")
    assert _comm(warehouse, o["id"], "CONFIRMED").status_code == 204
    r = warehouse.post(f"/warehouse/orders/{o['id']}/goods-sent")
    assert r.status_code == 200, f"[API-WH-088] {r.status_code} {r.text[:160]}"
    assert _order_status(s_admin, o["id"]) == "IN_TRANSIT", "[API-WH-088] не IN_TRANSIT"


@pytest.mark.high
@pytest.mark.lifecycle
def test_goods_sent_not_confirmed_089(warehouse, order_factory):
    o = order_factory.make("IN_WORK")  # commStatus PENDING
    _comm(warehouse, o["id"], "PENDING")
    r = warehouse.post(f"/warehouse/orders/{o['id']}/goods-sent")
    assert r.status_code == 409 and _code(r) == "error.order.not-ready-for-transit", f"[API-WH-089] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_goods_sent_not_inwork_090(warehouse, order_factory):
    o = order_factory.make("SELECTED")
    r = warehouse.post(f"/warehouse/orders/{o['id']}/goods-sent")
    assert r.status_code == 409 and _code(r) == "error.order.not-ready-for-transit", f"[API-WH-090] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_goods_sent_idempotent_091(warehouse, order_factory):
    o = order_factory.make("IN_TRANSIT")  # уже IN_TRANSIT
    r = warehouse.post(f"/warehouse/orders/{o['id']}/goods-sent")
    assert r.status_code == 409 and _code(r) == "error.order.not-ready-for-transit", f"[API-WH-091] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_goods_sent_tenancy_092(warehouse, foreign_order_id):
    r = warehouse.post(f"/warehouse/orders/{foreign_order_id}/goods-sent")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-092] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
def test_goods_sent_rbac_093(api, order_factory):
    o = order_factory.make("IN_WORK")
    r = api("shipper_manager").post(f"/warehouse/orders/{o['id']}/goods-sent")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-093] {r.status_code}/{_code(r)}"


# ═══ ГОНКИ (сверх библиотеки) — незалоченные goods-sent / communication ══════


@pytest.mark.medium
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-035 / MNZL-275: double-goods-sent даёт 500 вместо 409 (goodsSent без пессимистичного лока)", strict=True)
def test_race_double_goods_sent(warehouse, s_admin, order_factory, cfg):
    """Двойной goods-sent (IN_WORK+CONFIRMED, БЕЗ лока): один 200 (IN_TRANSIT), второй 409
    not-ready-for-transit, НИКОГДА 500. `goodsSent` без findByIdForUpdate — кандидат в новую
    поверхность MNZL-275; 12 раундов проверяют, не даёт ли @Version-конфликт 500."""
    from utils.api_client import ApiClient
    tok = warehouse.token
    losers = []
    for _ in range(12):
        o = order_factory.make("IN_WORK")
        assert _comm(warehouse, o["id"], "CONFIRMED").status_code == 204
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]

        def fire(c):
            return c.request("POST", f"/warehouse/orders/{o['id']}/goods-sent", tok).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, clients))
        assert rc.count(200) == 1, f"[race double-goods-sent] ровно один 200, получили {rc}"
        losers.append(next(c for c in rc if c != 200))
    assert 500 not in losers, f"[race double-goods-sent] 500 — новая поверхность MNZL-275: {losers}"


@pytest.mark.medium
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-035 / MNZL-275: goods-sent×cancel (оба без лока) даёт 500 вместо 409", strict=True)
def test_race_goods_sent_x_cancel(warehouse, s_admin, order_factory, cfg):
    """КРОСС-ГОНКА двух НЕзалоченных путей: goods-sent (warehouse) × cancel (admin) на одном
    IN_WORK+CONFIRMED заказе. Оба без findByIdForUpdate (корень BUG-035) → проверяем, не даёт
    ли пересечение 500. Корректно: 200/204 + согласованный исход, без 500."""
    from utils.api_client import ApiClient
    wtok, atok = warehouse.token, s_admin.token
    codes = []
    for _ in range(12):
        o = order_factory.make("IN_WORK")
        _comm(warehouse, o["id"], "CONFIRMED")
        cg, cc = ApiClient(cfg, base_url=cfg.dev_url), ApiClient(cfg, base_url=cfg.dev_url)

        def do_goods():
            return cg.request("POST", f"/warehouse/orders/{o['id']}/goods-sent", wtok).status_code

        def do_cancel():
            return cc.request("POST", f"/shipper/orders/{o['id']}/cancel", atok, json={"reason": "race"}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fg, fc = ex.submit(do_goods), ex.submit(do_cancel)
            gc, cnl = fg.result(), fc.result()
        codes.extend([gc, cnl])
    assert 500 not in codes, f"[race goods-sent×cancel] 500 — новая поверхность BUG-035/MNZL-275: {codes}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_race_communication_x_replace(warehouse, carrier, order_factory, cfg):
    """КРОСС-ГОНКА: communication (warehouse, БЕЗ лока) × replace-driver (carrier, ЗАЛОЧЕН,
    сбрасывает commStatus). Пересечение незалоченного и залоченного путей на одном заказе —
    проверяем отсутствие 500."""
    from utils.api_client import ApiClient
    wtok, ctok = warehouse.token, carrier.token
    codes = []
    for _ in range(12):
        o = order_factory.make("IN_WORK")
        cur = _content(carrier.get(f"/transport/orders/{o['id']}/drivers"))[0]
        cur_id = cur.get("driverId") or cur.get("id")
        nd = carrier.post("/transport/drivers", json={"fullName": "AT R", "phone": "+99890" + _d(7)}).json()["id"]
        cw, cr = ApiClient(cfg, base_url=cfg.dev_url), ApiClient(cfg, base_url=cfg.dev_url)

        def do_comm():
            return cw.request("POST", f"/warehouse/orders/{o['id']}/communication", wtok, json={"status": "CONFIRMED"}).status_code

        def do_replace():
            return cr.request("PUT", f"/transport/orders/{o['id']}/drivers/{cur_id}", ctok,
                              json={"driverId": nd, "licensePlate": "01A" + _d(4), "cardId": _d(18)}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fc, fr = ex.submit(do_comm), ex.submit(do_replace)
            cc, rp = fc.result(), fr.result()
        codes.extend([cc, rp])
        assert cc in (204, 409) and rp in (200, 409), f"[race comm×replace] неожиданно {cc}/{rp}"
        carrier.delete(f"/transport/drivers/{nd}")
    assert 500 not in codes, f"[race comm×replace] 500 — новая поверхность MNZL-275: {codes}"
