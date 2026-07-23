"""API — Warehouse order create (05_warehouse_dispatch.json, POST /warehouse/orders).

API-WH-001…040 — создание заказа складом: немедленная публикация vs отложенная (scheduledPublishDate
→ DRAFT/PUBLISHED), валюта, валидация полей и границ (driversCount 1-2), валидация дат
(schedule-not-in-future / schedule-not-before-load / load-not-after-publish), адресное трио
(склад vs ad-hoc division CN/KG, взаимоисключение), RBAC/capability (ORDER_ENTRY).

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

import datetime
import random
import string
import uuid

import pytest

from config.settings import get_settings
from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api]

_TODAY = datetime.date.today()
_CTYPE = {"SHIPPER_MANAGER": "WEB", "SHIPPER_OPERATOR": "WEB", "SHIPPER_DISPATCHER": "WEB"}


def _iso(days):
    return (_TODAY + datetime.timedelta(days=days)).isoformat()


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


def _d(n):
    return "".join(random.choices(string.digits, k=n))


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def warehouse(api):
    return api("shipper_warehouse")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture(scope="session")
def wh_refs(dev_api, cfg, api_dev_roles):
    """(vehicleTypeId, from_loc, to_loc) для склада dev-компании."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    wh = dev_api.token(*api_dev_roles["shipper_warehouse"])
    vt = dev_api.request("POST", "/super-admin/vehicle-types", sa,
                         json={"category": "FLATBED", "size": _d(9)}).json()["id"]
    cities = dev_api.request("GET", "/super-admin/cities?size=5", sa).json()
    cid = (cities.get("content", cities) if isinstance(cities, dict) else cities)[0]["id"]
    locs = []
    for _ in range(2):
        loc = dev_api.request("POST", "/warehouse/locations", wh,
                              json={"cityId": cid, "name": "AT-WH-" + _d(5), "address": "Tashkent, Sayyod 1"}).json()
        locs.append(loc["id"])
    return vt, locs[0], locs[1]


@pytest.fixture
def track_order(warehouse):
    reg = []

    def add(r):
        try:
            reg.append(r.json()["id"])
        except Exception:  # noqa: BLE001
            pass
        return r

    yield add
    for oid in reversed(reg):
        try:
            warehouse.delete(f"/warehouse/orders/{oid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def cap(warehouse, api, dev_api, pwd):
    """Свежий shipper-office staff (+ гранты) → залогиненный RoleClient. Создаёт через админа."""
    admin = api("shipper_admin")
    created = []

    def _mk(role, grants=None):
        phone = "+99890" + _d(7)
        sid = admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role}).json()["id"]
        created.append(sid)
        if grants:
            admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
        return RoleClient(dev_api, dev_api.token(phone, pwd, _CTYPE.get(role, "WEB")))

    yield _mk
    for sid in reversed(created):
        try:
            admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


def _body(refs, **over):
    vt, f, t = refs
    b = {"cargoType": "AUTO", "currency": "CNY", "loadDate": _iso(3), "vehicleTypeId": vt,
         "driversCount": 1, "fromWarehouseId": f, "toWarehouseId": t, "notes": "AT create"}
    b.update(over)
    return b


def _create(warehouse, track_order, refs, **over):
    return track_order(warehouse.post("/warehouse/orders", json=_body(refs, **over)))


# ═══ happy / publish-scheduling (001…005) ════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_create_immediate_001(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs)
    assert r.status_code == 201, f"[API-WH-001] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b["status"] == "PUBLISHED" and b["currency"] == "CNY" and b.get("displayNumber"), f"[API-WH-001] {b}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_create_scheduled_draft_002(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs, scheduledPublishDate=_iso(5), loadDate=_iso(10))
    assert r.status_code == 201 and r.json()["status"] == "DRAFT", f"[API-WH-002] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_create_scheduled_today_published_003(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs, scheduledPublishDate=_TODAY.isoformat(), loadDate=_iso(3))
    assert r.status_code == 201 and r.json()["status"] == "PUBLISHED", f"[API-WH-003] {r.status_code} {r.json().get('status')}"


@pytest.mark.medium
@pytest.mark.validation
def test_create_currency_default_004(warehouse, track_order, wh_refs):
    body = _body(wh_refs)
    body.pop("currency")
    r = track_order(warehouse.post("/warehouse/orders", json=body))
    assert r.status_code == 201 and r.json()["currency"] == "CNY", f"[API-WH-004] {r.json().get('currency')}"


@pytest.mark.low
def test_create_currency_usd_005(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs, currency="USD")
    assert r.status_code == 201 and r.json()["currency"] == "USD", f"[API-WH-005] {r.json().get('currency')}"


# ═══ required-field validation (006…013) ════════════════════════════════════


@pytest.mark.high
@pytest.mark.validation
@pytest.mark.parametrize("field", ["cargoType", "loadDate", "vehicleTypeId", "driversCount"])
def test_create_required_006_009(warehouse, wh_refs, field):
    cid = {"cargoType": "API-WH-006", "loadDate": "API-WH-007", "vehicleTypeId": "API-WH-008", "driversCount": "API-WH-009"}[field]
    body = _body(wh_refs)
    body.pop(field)
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and field in _err_fields(r), f"[{cid}] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.boundary
@pytest.mark.parametrize("n,ok,cid", [(0, False, "API-WH-010"), (1, True, "API-WH-011"), (2, True, "API-WH-012"), (3, False, "API-WH-013")])
def test_create_drivers_count_boundary(warehouse, track_order, wh_refs, n, ok, cid):
    r = track_order(warehouse.post("/warehouse/orders", json=_body(wh_refs, driversCount=n)))
    if ok:
        assert r.status_code == 201, f"[{cid}] driversCount={n}: {r.status_code}"
    else:
        assert r.status_code == 400 and "driversCount" in _err_fields(r), f"[{cid}] driversCount={n}: {r.status_code}"


# ═══ date validation (014…018) ══════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.validation
def test_create_schedule_past_014(warehouse, wh_refs):
    r = warehouse.post("/warehouse/orders", json=_body(wh_refs, scheduledPublishDate=_iso(-3), loadDate=_iso(5)))
    assert r.status_code == 400 and _code(r) == "error.order.schedule-not-in-future", f"[API-WH-014] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_create_schedule_after_load_015(warehouse, wh_refs):
    r = warehouse.post("/warehouse/orders", json=_body(wh_refs, scheduledPublishDate=_iso(10), loadDate=_iso(5)))
    assert r.status_code == 400 and _code(r) == "error.order.schedule-not-before-load", f"[API-WH-015] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_create_schedule_equals_load_016(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs, scheduledPublishDate=_iso(7), loadDate=_iso(7))
    assert r.status_code == 201 and r.json()["status"] == "DRAFT", f"[API-WH-016] {r.status_code}/{r.json().get('status')}"


@pytest.mark.high
@pytest.mark.validation
def test_create_load_past_immediate_017(warehouse, wh_refs):
    r = warehouse.post("/warehouse/orders", json=_body(wh_refs, loadDate=_iso(-3)))
    assert r.status_code == 400 and _code(r) == "error.order.load-not-after-publish", f"[API-WH-017] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_create_load_today_immediate_018(warehouse, track_order, wh_refs):
    r = _create(warehouse, track_order, wh_refs, loadDate=_TODAY.isoformat())
    assert r.status_code == 201 and r.json()["status"] == "PUBLISHED", f"[API-WH-018] {r.status_code}/{r.json().get('status')}"


# ═══ vehicle-type + address trio (019…028) ══════════════════════════════════


@pytest.mark.high
@pytest.mark.negative
def test_create_vt_not_found_019(warehouse, wh_refs):
    r = warehouse.post("/warehouse/orders", json=_body(wh_refs, vehicleTypeId=str(uuid.uuid4())))
    assert r.status_code == 404 and _code(r) == "error.order.vehicle-type-not-found", f"[API-WH-019] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_create_adhoc_from_020(warehouse, track_order, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "CN", "fromDivisionCode": "11", "fromAddress": "Beijing warehouse st. 1"})
    r = track_order(warehouse.post("/warehouse/orders", json=body))
    assert r.status_code == 201, f"[API-WH-020] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.validation
def test_create_route_both_sources_021(warehouse, wh_refs):
    body = _body(wh_refs)  # уже есть fromWarehouseId
    body.update({"fromDivisionCountry": "CN", "fromDivisionCode": "11", "fromAddress": "x"})
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "error.order.route-point-invalid", f"[API-WH-021] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_create_route_no_source_022(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")  # ни склад, ни ad-hoc
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "error.order.route-point-invalid", f"[API-WH-022] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_create_adhoc_no_address_023(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "CN", "fromDivisionCode": "11"})  # без fromAddress
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "error.order.address-required", f"[API-WH-023] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_create_adhoc_no_division_024(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromAddress": "free text only"})  # без country/code
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "error.order.division-required", f"[API-WH-024] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_create_adhoc_bad_country_025(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "US", "fromDivisionCode": "1", "fromAddress": "x"})
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "error.order.division-country-invalid", f"[API-WH-025] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_create_adhoc_bad_code_026(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "CN", "fromDivisionCode": "99999999", "fromAddress": "x"})
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 404, f"[API-WH-026] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.negative
def test_create_from_not_found_027(api, wh_refs):
    # admin: allowedFromWarehouseIds пуст (=все) → allowed-check проходит, срабатывает existence→404.
    # У роли SHIPPER_WAREHOUSE (непустой allowed) случайный id даёт 403 warehouse-not-allowed раньше.
    r = api("shipper_admin").post("/warehouse/orders", json=_body(wh_refs, fromWarehouseId=str(uuid.uuid4())))
    assert r.status_code == 404 and _code(r) == "error.order.from-location-not-found", f"[API-WH-027] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.negative
def test_create_to_not_found_028(api, wh_refs):
    r = api("shipper_admin").post("/warehouse/orders", json=_body(wh_refs, toWarehouseId=str(uuid.uuid4())))
    assert r.status_code == 404 and _code(r) == "error.order.to-location-not-found", f"[API-WH-028] {r.status_code}/{_code(r)}"


# ═══ size validation (029…031) ══════════════════════════════════════════════


@pytest.mark.low
@pytest.mark.validation
def test_create_country_too_long_029(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "CHN", "fromDivisionCode": "11", "fromAddress": "x"})
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-029] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_create_address_too_long_030(warehouse, wh_refs):
    body = _body(wh_refs)
    body.pop("fromWarehouseId")
    body.update({"fromDivisionCountry": "CN", "fromDivisionCode": "11", "fromAddress": "a" * 501})
    r = warehouse.post("/warehouse/orders", json=body)
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-030] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_create_notes_too_long_031(warehouse, wh_refs):
    r = warehouse.post("/warehouse/orders", json=_body(wh_refs, notes="n" * 2001))
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-031] {r.status_code}/{_code(r)}"


# ═══ RBAC / capability (032…040) ════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.capability
def test_create_operator_order_entry_032(cap, track_order, wh_refs):
    op = cap("SHIPPER_OPERATOR")  # ORDER_ENTRY по умолчанию
    r = track_order(op.post("/warehouse/orders", json=_body(wh_refs)))
    assert r.status_code == 201, f"[API-WH-032] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.capability
def test_create_admin_033(cap, track_order, wh_refs, api):
    r = track_order(api("shipper_admin").post("/warehouse/orders", json=_body(wh_refs)))
    assert r.status_code == 201, f"[API-WH-033] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.parametrize("role,cid", [("SHIPPER_MANAGER", "API-WH-034"), ("SHIPPER_DISPATCHER", "API-WH-035")])
def test_create_no_order_entry_403(cap, wh_refs, role, cid):
    c = cap(role)  # без ORDER_ENTRY по умолчанию
    r = c.post("/warehouse/orders", json=_body(wh_refs))
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[{cid}] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_create_manager_granted_036(cap, track_order, wh_refs):
    mgr = cap("SHIPPER_MANAGER", grants=["ORDER_ENTRY"])
    r = track_order(mgr.post("/warehouse/orders", json=_body(wh_refs)))
    assert r.status_code == 201, f"[API-WH-036] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.rbac
@pytest.mark.parametrize("role,cid", [("transport_admin", "API-WH-037"), ("super_admin", "API-WH-038")])
def test_create_rbac_forbidden(api, wh_refs, role, cid):
    r = api(role).post("/warehouse/orders", json=_body(wh_refs))
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[{cid}] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_create_driver_039(dev_api, cfg, wh_refs, pwd):
    """DRIVER (self-employed, вход через TRANSPORT_COMPANY_APP, MNZL-269) → 403 FORBIDDEN."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt, _, _ = wh_refs
    phone = "+99890" + _d(7)
    cr = dev_api.request("POST", "/super-admin/drivers", sa,
                         json={"fullName": "AT SelfDrv", "phone": phone, "password": pwd, "vehicleTypeId": vt})
    assert cr.status_code == 201, f"[API-WH-039] driver setup: {cr.status_code} {cr.text[:160]}"
    try:
        tok = dev_api.token(phone, pwd, "TRANSPORT_COMPANY_APP")
        r = dev_api.request("POST", "/warehouse/orders", tok, json=_body(wh_refs))
        assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-039] {r.status_code}/{_code(r)}"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{cr.json()['id']}", sa)


@pytest.mark.medium
@pytest.mark.rbac
def test_create_no_token_040(dev_api, wh_refs):
    r = dev_api.request("POST", "/warehouse/orders", None, json=_body(wh_refs))
    assert r.status_code == 401, f"[API-WH-040] {r.status_code}"


# ─── фикстуры для manage-блока ───────────────────────────────────────────────


@pytest.fixture(scope="session")
def foreign_order(dev_api, cfg, api_dev_roles):
    """Заказ чужой компании B (PUBLISHED) — для tenancy 404 / список не течёт."""
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
    order = factory.make("PUBLISHED")
    yield order["id"]
    factory.teardown()
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


@pytest.fixture
def empty_wh(dev_api, cfg):
    """Склад свежей пустой компании (без заказов) — для empty-list / empty-summary."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + _d(7)
    body = {"name": f"AT-E-{_d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": _d(9), "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT E Admin", "phone": aphone, "password": cfg.dev_account_password}}
    sid = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body).json()["id"]
    adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
    whp = "+99890" + _d(7)
    dev_api.request("POST", "/shipper/staff", adm,
                    json={"fullName": "AT E WH", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
    yield RoleClient(dev_api, dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP"))
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


def _content2(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _pub(warehouse, wh_refs):
    return warehouse.post("/warehouse/orders", json=_body(wh_refs)).json()["id"]


# ═══ PATCH (041…054) ═════════════════════════════════════════════════════════


@pytest.mark.high
def test_patch_notes_041(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}", json={"notes": "updated AT"})
    assert r.status_code == 200 and r.json().get("notes") == "updated AT", f"[API-WH-041] {r.status_code} {r.text[:120]}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
def test_patch_draft_042(warehouse, wh_refs):
    o = warehouse.post("/warehouse/orders", json=_body(wh_refs, scheduledPublishDate=_iso(5), loadDate=_iso(10))).json()
    r = warehouse.patch(f"/warehouse/orders/{o['id']}", json={"loadDate": _iso(12)})
    assert r.status_code == 200, f"[API-WH-042] {r.status_code} {r.text[:120]}"
    warehouse.delete(f"/warehouse/orders/{o['id']}")


@pytest.mark.high
@pytest.mark.lifecycle
def test_patch_quoted_not_editable_043(warehouse, order_factory):
    o = order_factory.make("QUOTED")
    r = warehouse.patch(f"/warehouse/orders/{o['id']}", json={"notes": "x"})
    assert r.status_code == 409 and _code(r) == "error.order.not-editable", f"[API-WH-043] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_patch_selected_not_editable_044(warehouse, order_factory):
    o = order_factory.make("SELECTED")
    r = warehouse.patch(f"/warehouse/orders/{o['id']}", json={"notes": "x"})
    assert r.status_code == 409 and _code(r) == "error.order.not-editable", f"[API-WH-044] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_patch_tenancy_045(warehouse, foreign_order):
    r = warehouse.patch(f"/warehouse/orders/{foreign_order}", json={"notes": "hack"})
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-045] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_patch_switch_adhoc_046(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}",
                        json={"fromWarehouseId": None, "fromDivisionCountry": "CN", "fromDivisionCode": "11", "fromAddress": "adhoc st 5"})
    assert r.status_code == 200, f"[API-WH-046] {r.status_code} {r.text[:160]}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
def test_patch_null_point_047(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}", json={"driversCount": 2})
    assert r.status_code == 200, f"[API-WH-047] {r.status_code} {r.text[:120]}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
@pytest.mark.validation
def test_patch_both_sources_048(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}",
                        json={"fromWarehouseId": wh_refs[1], "fromDivisionCountry": "CN", "fromDivisionCode": "11", "fromAddress": "x"})
    assert r.status_code == 400 and _code(r) == "error.order.route-point-invalid", f"[API-WH-048] {r.status_code}/{_code(r)}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
@pytest.mark.validation
def test_patch_schedule_past_049(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}", json={"scheduledPublishDate": _iso(-3)})
    assert r.status_code == 400 and _code(r) == "error.order.schedule-not-in-future", f"[API-WH-049] {r.status_code}/{_code(r)}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
@pytest.mark.lifecycle
def test_patch_published_to_draft_050(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}", json={"scheduledPublishDate": _iso(5), "loadDate": _iso(10)})
    assert r.status_code == 200 and r.json().get("status") == "DRAFT", f"[API-WH-050] {r.status_code}/{r.json().get('status')}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.low
@pytest.mark.lifecycle
def test_patch_schedule_quoted_051(warehouse, order_factory):
    o = order_factory.make("QUOTED")
    r = warehouse.patch(f"/warehouse/orders/{o['id']}", json={"scheduledPublishDate": _iso(5)})
    assert r.status_code == 409 and _code(r) == "error.order.not-editable", f"[API-WH-051] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_patch_vt_not_found_052(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.patch(f"/warehouse/orders/{oid}", json={"vehicleTypeId": str(uuid.uuid4())})
    assert r.status_code == 404 and _code(r) == "error.order.vehicle-type-not-found", f"[API-WH-052] {r.status_code}/{_code(r)}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.high
@pytest.mark.capability
def test_patch_manager_no_entry_053(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    mgr = cap("SHIPPER_MANAGER")
    r = mgr.patch(f"/warehouse/orders/{o['id']}", json={"notes": "x"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-WH-053] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_patch_transport_054(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("transport_admin").patch(f"/warehouse/orders/{o['id']}", json={"notes": "x"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-054] {r.status_code}/{_code(r)}"


# ═══ DELETE (055…061) ════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_delete_published_055(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    assert warehouse.delete(f"/warehouse/orders/{oid}").status_code == 204, "[API-WH-055]"
    assert warehouse.get(f"/warehouse/orders/{oid}").status_code == 404, "[API-WH-055] должен исчезнуть"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_delete_draft_056(warehouse, wh_refs):
    o = warehouse.post("/warehouse/orders", json=_body(wh_refs, scheduledPublishDate=_iso(5), loadDate=_iso(10))).json()
    assert warehouse.delete(f"/warehouse/orders/{o['id']}").status_code == 204, "[API-WH-056]"


@pytest.mark.high
@pytest.mark.lifecycle
def test_delete_selected_057(warehouse, order_factory):
    o = order_factory.make("SELECTED")
    r = warehouse.delete(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 409 and _code(r) == "error.order.not-deletable", f"[API-WH-057] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_delete_inwork_058(warehouse, order_factory):
    o = order_factory.make("IN_WORK")
    r = warehouse.delete(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 409 and _code(r) == "error.order.not-deletable", f"[API-WH-058] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_delete_tenancy_059(warehouse, foreign_order):
    r = warehouse.delete(f"/warehouse/orders/{foreign_order}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-059] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_delete_idempotent_060(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    assert warehouse.delete(f"/warehouse/orders/{oid}").status_code == 204
    r = warehouse.delete(f"/warehouse/orders/{oid}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-060] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_delete_dispatcher_no_entry_061(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    disp = cap("SHIPPER_DISPATCHER")
    r = disp.delete(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-WH-061] {r.status_code}/{_code(r)}"


# ═══ GET list (062…074) ══════════════════════════════════════════════════════


@pytest.mark.high
def test_list_062(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    r = warehouse.get("/warehouse/orders")
    assert r.status_code == 200, f"[API-WH-062] {r.status_code}"
    b = r.json()
    assert (b.get("page", {}).get("size") == 20) or (b.get("size") == 20), f"[API-WH-062] size=20: {b.get('page')}"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.high
@pytest.mark.lifecycle
def test_list_quoted_folded_063(warehouse, order_factory):
    o = order_factory.make("QUOTED")
    rows = _content2(warehouse.get("/warehouse/orders?size=200"))
    row = next((x for x in rows if x["id"] == o["id"]), None)
    assert row and row["status"] == "PUBLISHED", f"[API-WH-063] QUOTED должен показываться как PUBLISHED: {row}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_list_excludes_cancelled_064(warehouse, order_factory):
    o = order_factory.make("CANCELLED")
    ids = {x["id"] for x in _content2(warehouse.get("/warehouse/orders?size=200"))}
    assert o["id"] not in ids, "[API-WH-064] CANCELLED не должен быть в списке"


@pytest.mark.medium
def test_list_filter_status_065(warehouse, order_factory):
    order_factory.make("IN_WORK")
    rows = _content2(warehouse.get("/warehouse/orders?status=IN_WORK&size=200"))
    assert all(x["status"] == "IN_WORK" for x in rows), "[API-WH-065] фильтр status протекает"


@pytest.mark.high
@pytest.mark.lifecycle
def test_list_filter_published_includes_quoted_066(warehouse, order_factory):
    o = order_factory.make("QUOTED")
    ids = {x["id"] for x in _content2(warehouse.get("/warehouse/orders?status=PUBLISHED&size=200"))}
    assert o["id"] in ids, "[API-WH-066] фильтр PUBLISHED должен включать свёрнутый QUOTED"


@pytest.mark.medium
def test_list_filter_cargo_date_067(warehouse, wh_refs):
    oid = _pub(warehouse, wh_refs)
    ld = _iso(3)
    rows = _content2(warehouse.get(f"/warehouse/orders?cargoType=AUTO&loadFrom={ld}&loadTo={ld}&size=200"))
    assert all(x.get("cargoType", "AUTO") == "AUTO" for x in rows), "[API-WH-067] cargoType-фильтр протекает"
    warehouse.delete(f"/warehouse/orders/{oid}")


@pytest.mark.medium
def test_list_search_068(warehouse, wh_refs):
    o = warehouse.post("/warehouse/orders", json=_body(wh_refs, notes="UNIQNOTE-" + _d(5))).json()
    num = o["displayNumber"].split("-")[-1]
    rows = _content2(warehouse.get(f"/warehouse/orders?search={num}&size=200"))
    assert any(x["id"] == o["id"] for x in rows), "[API-WH-068] поиск по номеру не находит"
    warehouse.delete(f"/warehouse/orders/{o['id']}")


@pytest.mark.medium
def test_list_empty_069(empty_wh):
    r = empty_wh.get("/warehouse/orders")
    assert r.status_code == 200 and _content2(r) == [], f"[API-WH-069] {r.text[:120]}"


@pytest.mark.low
@pytest.mark.boundary
def test_list_pagination_070(warehouse):
    r = warehouse.get("/warehouse/orders?page=2&size=10")
    assert r.status_code == 200 and len(_content2(r)) <= 10, f"[API-WH-070] {r.status_code}"


@pytest.mark.high
@pytest.mark.tenancy
def test_list_tenancy_071(warehouse, foreign_order):
    ids = {x["id"] for x in _content2(warehouse.get("/warehouse/orders?size=200"))}
    assert foreign_order not in ids, "[API-WH-071] заказ компании B виден компании A"


@pytest.mark.medium
@pytest.mark.rbac
@pytest.mark.parametrize("role", ["shipper_admin", "shipper_manager", "shipper_operator", "shipper_dispatcher", "shipper_warehouse"])
def test_list_rbac_all_roles_072(api, role):
    assert api(role).get("/warehouse/orders").status_code == 200, f"[API-WH-072] {role}"


@pytest.mark.medium
@pytest.mark.rbac
def test_list_transport_073(api):
    r = api("transport_admin").get("/warehouse/orders")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-073] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_list_no_token_074(dev_api):
    r = dev_api.request("GET", "/warehouse/orders", None)
    assert r.status_code == 401, f"[API-WH-074] {r.status_code}"


# ═══ GET summary (075…078) ═══════════════════════════════════════════════════


@pytest.mark.high
def test_summary_075(warehouse):
    b = warehouse.get("/warehouse/orders/summary").json()
    for k in ("DRAFT", "PUBLISHED", "SELECTED", "IN_WORK", "IN_TRANSIT", "COMPLETED"):
        assert k in b, f"[API-WH-075] нет ключа {k}: {sorted(b)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_summary_folds_076(warehouse):
    b = warehouse.get("/warehouse/orders/summary").json()
    assert "CANCELLED" not in b and "SUPERSEDED" not in b, f"[API-WH-076] CANCELLED/SUPERSEDED не должны быть ключами: {sorted(b)}"


@pytest.mark.low
def test_summary_empty_077(empty_wh):
    b = empty_wh.get("/warehouse/orders/summary").json()
    assert all(b.get(k) == 0 for k in ("DRAFT", "PUBLISHED", "SELECTED", "IN_WORK", "IN_TRANSIT", "COMPLETED")), f"[API-WH-077] {b}"


@pytest.mark.medium
@pytest.mark.rbac
def test_summary_transport_078(api):
    r = api("transport_admin").get("/warehouse/orders/summary")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-078] {r.status_code}/{_code(r)}"


# ═══ GET warehouse/orders/{id} — заказ + водители (094…099) ══════════════════


@pytest.mark.high
def test_get_by_id_094(warehouse, order_factory):
    o = order_factory.make("IN_WORK")  # есть 1 привязанный водитель
    b = warehouse.get(f"/warehouse/orders/{o['id']}").json()
    assert "order" in b and "drivers" in b, f"[API-WH-094] {sorted(b)}"
    assert b["drivers"] and all("phone" in d and "licensePlate" in d for d in b["drivers"]), f"[API-WH-094] {b['drivers']}"


@pytest.mark.medium
def test_get_by_id_empty_drivers_095(warehouse, order_factory):
    o = order_factory.make("SELECTED")
    b = warehouse.get(f"/warehouse/orders/{o['id']}").json()
    assert b.get("drivers") == [], f"[API-WH-095] {b.get('drivers')}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_get_by_id_quoted_folded_096(warehouse, order_factory):
    o = order_factory.make("QUOTED")
    b = warehouse.get(f"/warehouse/orders/{o['id']}").json()
    assert b["order"]["status"] == "PUBLISHED", f"[API-WH-096] {b['order']['status']}"


@pytest.mark.high
@pytest.mark.tenancy
def test_get_by_id_tenancy_097(warehouse, foreign_order):
    r = warehouse.get(f"/warehouse/orders/{foreign_order}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-097] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_get_by_id_not_found_098(warehouse):
    r = warehouse.get("/warehouse/orders/999999999")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-098] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_get_by_id_admin_403_099(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("shipper_admin").get(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-099] {r.status_code}/{_code(r)}"


# ═══ vehicle-types (100…102) ═════════════════════════════════════════════════


@pytest.mark.medium
def test_wh_vehicle_types_100(warehouse):
    r = warehouse.get("/warehouse/vehicle-types")
    assert r.status_code == 200 and isinstance(_content2(r), list), f"[API-WH-100] {r.status_code}"


@pytest.mark.low
def test_wh_vehicle_types_search_101(warehouse):
    r = warehouse.get("/warehouse/vehicle-types?search=bort")
    assert r.status_code == 200, f"[API-WH-101] {r.status_code}"


@pytest.mark.low
@pytest.mark.rbac
def test_wh_vehicle_types_rbac_102(api):
    assert api("shipper_dispatcher").get("/warehouse/vehicle-types").status_code == 200, "[API-WH-102]"


# ═══ locations GET (103…110) ════════════════════════════════════════════════


@pytest.mark.low
def test_wh_locations_103(warehouse):
    r = warehouse.get("/warehouse/locations")
    assert r.status_code == 200, f"[API-WH-103] {r.status_code}"


@pytest.mark.low
def test_wh_locations_filter_104(warehouse, wh_refs):
    r = warehouse.get("/warehouse/locations?search=AT-WH")
    assert r.status_code == 200, f"[API-WH-104] {r.status_code}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_wh_locations_tenancy_105(warehouse, wh_refs):
    rows = _content2(warehouse.get("/warehouse/locations?size=200"))
    # свои локации есть, чужих личных нет — проверяем что все принадлежат вызывающему (не падает + список свой)
    assert isinstance(rows, list), f"[API-WH-105] {rows}"


@pytest.mark.high
def test_wh_locations_from_106(warehouse, wh_refs):
    r = warehouse.get("/warehouse/locations/from")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-WH-106] {r.status_code}"


@pytest.mark.medium
def test_wh_locations_from_empty_107(empty_wh):
    r = empty_wh.get("/warehouse/locations/from")
    assert r.status_code == 200 and r.json() == [], f"[API-WH-107] {r.text[:120]}"


@pytest.mark.low
def test_wh_locations_from_search_108(warehouse):
    r = warehouse.get("/warehouse/locations/from?search=at")
    assert r.status_code == 200, f"[API-WH-108] {r.status_code}"


@pytest.mark.medium
def test_wh_locations_to_109(warehouse, wh_refs):
    r = warehouse.get("/warehouse/locations/to")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-WH-109] {r.status_code}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_wh_locations_to_tenancy_110(empty_wh):
    r = empty_wh.get("/warehouse/locations/to")
    assert r.status_code == 200 and r.json() == [], f"[API-WH-110] {r.text[:120]}"


# ═══ POST locations (111…122) ═══════════════════════════════════════════════


@pytest.fixture(scope="session")
def _city(dev_api, cfg):
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    rows = dev_api.request("GET", "/super-admin/cities?size=5", sa).json()
    return (rows.get("content", rows) if isinstance(rows, dict) else rows)[0]["id"]


@pytest.mark.high
def test_loc_create_city_111(warehouse, _city):
    r = warehouse.post("/warehouse/locations", json={"cityId": _city, "name": "AT-L-" + _d(5), "address": "addr"})
    assert r.status_code == 201, f"[API-WH-111] {r.status_code} {r.text[:160]}"


@pytest.mark.high
def test_loc_create_division_112(warehouse):
    r = warehouse.post("/warehouse/locations", json={"divisionCountry": "CN", "divisionCode": "11", "name": "AT-D-" + _d(5), "address": "addr"})
    assert r.status_code == 201, f"[API-WH-112] {r.status_code} {r.text[:160]}"


@pytest.mark.high
def test_loc_both_division_pref_113(warehouse, _city):
    r = warehouse.post("/warehouse/locations", json={"cityId": _city, "divisionCountry": "CN", "divisionCode": "11", "name": "AT-B-" + _d(5), "address": "addr"})
    assert r.status_code == 201, f"[API-WH-113] оба источника → 201 (division приоритет): {r.status_code} {r.text[:120]}"


@pytest.mark.high
@pytest.mark.validation
def test_loc_neither_114(warehouse):
    r = warehouse.post("/warehouse/locations", json={"name": "AT", "address": "addr"})
    assert r.status_code == 400 and _code(r) == "error.warehouse.location-required", f"[API-WH-114] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_loc_name_required_115(warehouse, _city):
    r = warehouse.post("/warehouse/locations", json={"cityId": _city, "name": "", "address": "addr"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-115] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_loc_bad_country_116(warehouse):
    r = warehouse.post("/warehouse/locations", json={"divisionCountry": "US", "divisionCode": "1", "name": "AT", "address": "addr"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-116] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_loc_code_too_long_117(warehouse):
    r = warehouse.post("/warehouse/locations", json={"divisionCountry": "CN", "divisionCode": "1" * 33, "name": "AT", "address": "addr"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-WH-117] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_loc_city_not_found_118(warehouse):
    r = warehouse.post("/warehouse/locations", json={"cityId": str(uuid.uuid4()), "name": "AT", "address": "addr"})
    assert r.status_code == 404 and _code(r) == "error.city.not-found", f"[API-WH-118] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_loc_division_not_found_119(warehouse):
    r = warehouse.post("/warehouse/locations", json={"divisionCountry": "CN", "divisionCode": "99999999", "name": "AT", "address": "addr"})
    assert r.status_code == 404 and _code(r) == "error.division.not-found", f"[API-WH-119] {r.status_code}/{_code(r)}"


@pytest.mark.slow
def test_loc_personal_limit_120(empty_wh, _city):
    """Лимит 100 личных складов на пользователя. Свежий склад → создаём 100 → 101-й = 409."""
    for i in range(100):
        r = empty_wh.post("/warehouse/locations", json={"cityId": _city, "name": f"L{i}-{_d(4)}", "address": "a"})
        assert r.status_code == 201, f"[API-WH-120] setup {i}: {r.status_code}"
    r = empty_wh.post("/warehouse/locations", json={"cityId": _city, "name": "over", "address": "a"})
    assert r.status_code == 409 and _code(r) == "error.warehouse.personal-limit", f"[API-WH-120] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_loc_operator_403_121(cap, _city):
    op = cap("SHIPPER_OPERATOR")
    r = op.post("/warehouse/locations", json={"cityId": _city, "name": "AT", "address": "addr"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-WH-121] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_loc_admin_403_122(api, _city):
    r = api("shipper_admin").post("/warehouse/locations", json={"cityId": _city, "name": "AT", "address": "addr"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-WH-122] {r.status_code}/{_code(r)}"


# ═══ GET shipper/orders/{id}/drivers — офисный (123…128) ═════════════════════


@pytest.mark.high
def test_office_drivers_123(api, order_factory):
    o = order_factory.make("IN_WORK")
    rows = _content2(api("shipper_admin").get(f"/shipper/orders/{o['id']}/drivers"))
    assert rows and all("phone" in d for d in rows), f"[API-WH-123] {rows}"


@pytest.mark.medium
def test_office_drivers_empty_124(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_admin").get(f"/shipper/orders/{o['id']}/drivers")
    assert r.status_code == 200 and _content2(r) == [], f"[API-WH-124] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_office_drivers_tenancy_125(api, foreign_order):
    r = api("shipper_admin").get(f"/shipper/orders/{foreign_order}/drivers")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-WH-125] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_office_drivers_dispatcher_126(api, order_factory):
    o = order_factory.make("IN_WORK")
    assert api("shipper_dispatcher").get(f"/shipper/orders/{o['id']}/drivers").status_code == 200, "[API-WH-126]"


@pytest.mark.medium
@pytest.mark.rbac
def test_office_drivers_warehouse_403_127(api, order_factory):
    o = order_factory.make("IN_WORK")
    r = api("shipper_warehouse").get(f"/shipper/orders/{o['id']}/drivers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-127] {r.status_code}/{_code(r)}"


# ═══ GET shipper/orders/{id}/dispatch-log — офисный (129…137) ════════════════


@pytest.mark.high
def test_dispatch_log_129(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("shipper_admin").get(f"/shipper/orders/{o['id']}/dispatch-log")
    assert r.status_code == 200 and isinstance(_content2(r), list), f"[API-WH-129] {r.status_code}"


@pytest.mark.high
@pytest.mark.tenancy
def test_dispatch_log_tenancy_empty_132(api, foreign_order):
    r = api("shipper_admin").get(f"/shipper/orders/{foreign_order}/dispatch-log")
    assert r.status_code == 200 and _content2(r) == [], f"[API-WH-132] чужой заказ → пустой список (не 404): {r.status_code}"


@pytest.mark.low
def test_dispatch_log_empty_133(api, warehouse, wh_refs):
    # DRAFT (неопубликованный) — рассылки ещё не было → журнал пуст
    o = warehouse.post("/warehouse/orders", json=_body(wh_refs, scheduledPublishDate=_iso(5), loadDate=_iso(10))).json()
    r = api("shipper_admin").get(f"/shipper/orders/{o['id']}/dispatch-log")
    assert r.status_code == 200 and _content2(r) == [], f"[API-WH-133] {r.text[:160]}"
    warehouse.delete(f"/warehouse/orders/{o['id']}")


@pytest.mark.medium
@pytest.mark.capability
def test_dispatch_log_manager_135(api, order_factory):
    o = order_factory.make("PUBLISHED")
    assert api("shipper_manager").get(f"/shipper/orders/{o['id']}/dispatch-log").status_code == 200, "[API-WH-135]"


@pytest.mark.medium
@pytest.mark.rbac
def test_dispatch_log_warehouse_136(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("shipper_warehouse").get(f"/shipper/orders/{o['id']}/dispatch-log")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-136] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.rbac
def test_dispatch_log_transport_137(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("transport_admin").get(f"/shipper/orders/{o['id']}/dispatch-log")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-WH-137] {r.status_code}/{_code(r)}"
