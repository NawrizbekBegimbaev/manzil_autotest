"""API — Shipper orders/departures/warehouses/reports (docs/testcases/api/03_shipper_orders_staff.json).

API-SHP-042…182 — the office order surface: list/detail/neighbors, lifecycle actions
(cancel/republish/communication/complete/enter-1c/delete), departures, warehouse directory,
vehicle-types/cities, reports, dashboard. Built on `order_factory` (honest-chain provisioning).

One test ↔ one case ID. Assertions compare `expected` exactly (status + `code` + `errors[]`).
Gates verified against manzil-core: class @PreAuthorize(office4) → FORBIDDEN for WAREHOUSE;
@RequiresCapability → error.forbidden for an office role lacking the capability.
Runs on DEV.
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
_CTYPE = {"SHIPPER_MANAGER": "WEB", "SHIPPER_OPERATOR": "WEB", "SHIPPER_DISPATCHER": "WEB",
          "SHIPPER_WAREHOUSE": "WAREHOUSE_APP"}


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
        assert isinstance(b, dict) and "page" in b, f"MNZL-245: ожидался вложенный page: {sorted(b) if isinstance(b, dict) else type(b)}"
        return b["page"]
    return b


def _uphone():
    return "+99890" + "".join(random.choices(string.digits, k=7))


def _order_body(o, **over):
    """A valid CreateOrderRequest payload cloned from an order detail (republish body)."""
    b = {"cargoType": o["cargoType"], "currency": o["currency"], "loadDate": o["loadDate"],
         "vehicleTypeId": o["vehicleTypeId"], "driversCount": o["driversCount"],
         "fromWarehouseId": o["fromWarehouseId"], "toWarehouseId": o["toWarehouseId"], "notes": o.get("notes")}
    b.update(over)
    return b


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture(scope="session")
def city_id(api):
    rows = _content(api("shipper_admin").get("/shipper/cities?size=1"))
    assert rows, "нет городов в справочнике /shipper/cities"
    return rows[0]["id"]


@pytest.fixture
def cap(admin, dev_api, pwd):
    """Factory → fresh staff of `role`, optionally with personal capability grants,
    returned as a logged-in RoleClient (token carries defaults ∪ grants)."""
    created = []

    def _mk(role, grants=None):
        phone = _uphone()
        s = admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role})
        assert s.status_code == 201, f"cap staff setup: {s.status_code} {s.text[:160]}"
        sid = s.json()["id"]
        created.append(sid)
        if grants:
            r = admin.patch(f"/shipper/staff/{sid}",
                            json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
            assert r.status_code == 200, f"cap grant: {r.status_code} {r.text[:160]}"
        return RoleClient(dev_api, dev_api.token(phone, pwd, _CTYPE.get(role, "WEB")))

    yield _mk
    for sid in reversed(created):
        try:
            admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def empty_admin(dev_api, cfg):
    """Admin of a FRESH shipper company with no orders — for true zero/empty-state checks."""
    def d(n):
        return "".join(random.choices(string.digits, k=n))

    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + d(7)
    body = {"name": f"AT-E-{d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": d(9), "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT E Admin", "phone": aphone, "password": cfg.dev_account_password}}
    r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body)
    assert r.status_code in (200, 201), f"empty company: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    yield RoleClient(dev_api, dev_api.token(aphone, cfg.dev_account_password, "WEB"))
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


def _all_zero(obj):
    if isinstance(obj, dict):
        return all(_all_zero(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_all_zero(v) for v in obj)
    if isinstance(obj, (int, float)):
        return obj == 0
    return True  # строки/None не считаем счётчиками


@pytest.fixture(scope="session")
def tb(dev_api, cfg, api_dev_roles):
    """Company B (own admin + warehouse) with a real order + a directory warehouse — for
    tenancy/BOLA 404 checks. Order built to CANCELLED (terminal) so B stays deletable."""
    from tests.regression.order_lifecycle import OrderFactory

    def d(n):
        return "".join(random.choices(string.digits, k=n))

    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + d(7)
    body = {"name": f"AT-B-{d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": d(9), "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT B Admin", "phone": aphone, "password": cfg.dev_account_password}}
    r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body)
    assert r.status_code in (200, 201), f"tenant B: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")

    whp = "+99890" + d(7)
    dev_api.request("POST", "/shipper/staff", adm,
                    json={"fullName": "AT B WH", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
    whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    factory = OrderFactory(dev_api, sa, whb, adm, dev_api.token(cph, cpw, cct))
    order = factory.make("CANCELLED")

    cities = dev_api.request("GET", "/super-admin/cities?size=1", sa).json()
    cid = (cities.get("content", cities) if isinstance(cities, dict) else cities)[0]["id"]
    wh = dev_api.request("POST", "/shipper/warehouses", adm,
                         json={"cityId": cid, "name": "AT-B-WH", "address": "Tashkent, Sayyod 1"})
    assert wh.status_code == 201, f"tenant B warehouse: {wh.status_code} {wh.text[:160]}"

    yield {"order_id": order["id"], "warehouse_id": wh.json()["id"]}
    factory.teardown()
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


# ═══ GET /shipper/orders — list (042…056) ════════════════════════════════════


@pytest.mark.high
def test_orders_list_042(admin, order_factory):
    o = order_factory.make("QUOTED")  # has an offer → offerCount>0
    r = admin.get("/shipper/orders")
    assert r.status_code == 200, f"[API-SHP-042] {r.status_code}"
    pg = _page(r)
    assert pg.get("size") == 10 and pg.get("page") == 1, f"[API-SHP-042] defaults size=10/page=1: {pg}"
    row = next((x for x in _content(r) if x["id"] == o["id"]), None)
    assert row is not None, "[API-SHP-042] свежий заказ не в первой странице (createdAt,desc)"
    assert "offerCount" in row and "createdByName" in row, f"[API-SHP-042] нет offerCount/createdByName: {sorted(row)}"


@pytest.mark.medium
def test_orders_filter_status_043(admin, order_factory):
    order_factory.make("PUBLISHED")
    order_factory.make("QUOTED")
    rows = _content(admin.get("/shipper/orders?status=PUBLISHED&size=200"))
    assert all(x["status"] == "PUBLISHED" for x in rows), "[API-SHP-043] фильтр status не точный (подмешан не-PUBLISHED)"


@pytest.mark.low
def test_orders_filter_cargotype_044(admin, order_factory):
    order_factory.make("PUBLISHED")
    rows = _content(admin.get("/shipper/orders?cargoType=AUTO&size=200"))
    assert all(x["cargoType"] == "AUTO" for x in rows), "[API-SHP-044] cargoType-фильтр протекает"


@pytest.mark.low
def test_orders_filter_warehouses_045(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    rows = _content(admin.get(f"/shipper/orders?fromWarehouseId={o['fromWarehouseId']}&toWarehouseId={o['toWarehouseId']}&size=200"))
    assert any(x["id"] == o["id"] for x in rows), "[API-SHP-045] фильтр не включает свой заказ"
    assert all(x["fromWarehouse"]["name"] == o["fromWarehouse"]["name"] for x in rows), "[API-SHP-045] from/toWarehouseId-фильтр протекает"


@pytest.mark.low
def test_orders_filter_loaddate_046(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    ld = o["loadDate"]
    rows = _content(admin.get(f"/shipper/orders?loadFrom={ld}&loadTo={ld}&size=200"))
    assert any(x["id"] == o["id"] for x in rows) and all(x["loadDate"] == ld for x in rows), \
        "[API-SHP-046] loadFrom/loadTo (границы включительно) не работает"


@pytest.mark.low
def test_orders_filter_created_047(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    today = o["loadDate"]  # loadDate==today в фабрике; createdAt тоже сегодня
    rows = _content(admin.get(f"/shipper/orders?createdFrom={today}&createdTo={today}&size=200"))
    assert any(x["id"] == o["id"] for x in rows), "[API-SHP-047] createdTo не включает весь день создания"


@pytest.mark.low
def test_orders_filter_commstatus_048(admin, order_factory):
    rows = _content(admin.get("/shipper/orders?communicationStatus=CONFIRMED&size=200"))
    assert all(x.get("communicationStatus") == "CONFIRMED" for x in rows), "[API-SHP-048] communicationStatus-фильтр протекает"


@pytest.mark.medium
def test_orders_search_049(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    num = o["displayNumber"].split("-")[-1]  # напр. 00007
    rows = _content(admin.get(f"/shipper/orders?search={num}&size=200"))
    assert any(x["id"] == o["id"] for x in rows), "[API-SHP-049] поиск по номеру заказа не находит"


@pytest.mark.low
def test_orders_filter_plate_empty_050(admin):
    absent = "ZZ" + uuid.uuid4().hex[:4].upper()  # гарантированно отсутствующий номер
    r = admin.get(f"/shipper/orders?plate={absent}")
    assert r.status_code == 200 and _content(r) == [], f"[API-SHP-050] plate без совпадений не пуст: {r.text[:120]}"


@pytest.mark.low
def test_orders_filter_transportcompany_051(admin, order_factory):
    o = order_factory.make("SELECTED")  # есть выбранная ТК
    rows = _content(admin.get("/shipper/orders?transportCompany=AT-TC&size=200"))
    assert any(x["id"] == o["id"] for x in rows), "[API-SHP-051] фильтр transportCompany не находит заказ с выбранной ТК"


@pytest.mark.low
def test_orders_empty_state_052(admin):
    absent = "zzz-" + uuid.uuid4().hex[:6]
    r = admin.get(f"/shipper/orders?search={absent}&status=CANCELLED")
    assert r.status_code == 200 and _content(r) == [] and _page(r).get("totalElements") == 0, f"[API-SHP-052] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_orders_tenancy_053(admin, tb):
    ids = {x["id"] for x in _content(admin.get("/shipper/orders?size=200"))}
    assert tb["order_id"] not in ids, "[API-SHP-053] заказ компании B виден админу компании A"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_manager", "shipper_operator", "shipper_dispatcher"])
def test_orders_capability_review_054(api, role):
    r = api(role).get("/shipper/orders")
    assert r.status_code == 200, f"[API-SHP-054] {role} (ORDER_REVIEW по умолчанию): {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
def test_orders_rbac_warehouse_055(api):
    r = api("shipper_warehouse").get("/shipper/orders")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-055] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_orders_no_token_056(dev_api):
    r = dev_api.request("GET", "/shipper/orders", None)
    assert r.status_code == 401 and _code(r) == "UNAUTHORIZED", f"[API-SHP-056] {r.status_code}/{_code(r)}"  # entry-point (как AUTH-079)


# ═══ GET /shipper/orders/{id} — detail (057…060) ═════════════════════════════


@pytest.mark.high
def test_order_detail_057(admin, order_factory):
    o = order_factory.make("SELECTED")
    b = admin.get(f"/shipper/orders/{o['id']}").json()
    assert "order" in b and b.get("winningOffer") and "history" in b, f"[API-SHP-057] карточка неполная: {sorted(b)}"
    assert b.get("createdByName"), "[API-SHP-057] нет createdByName (уровень wrapper)"


@pytest.mark.high
@pytest.mark.tenancy
def test_order_detail_tenancy_058(admin, tb):
    r = admin.get(f"/shipper/orders/{tb['order_id']}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-058] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_order_detail_404_059(admin):
    r = admin.get("/shipper/orders/999999")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-059] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_manager", "shipper_operator", "shipper_dispatcher"])
def test_order_detail_capability_060(api, admin, order_factory, role):
    o = order_factory.make("PUBLISHED")
    r = api(role).get(f"/shipper/orders/{o['id']}")
    assert r.status_code == 200, f"[API-SHP-060] {role}: {r.status_code}/{_code(r)}"


# ═══ GET /shipper/orders/{id}/neighbors (061…065) ════════════════════════════


@pytest.mark.medium
def test_neighbors_061(admin, order_factory):
    ids = [order_factory.make("PUBLISHED")["id"] for _ in range(3)]
    mid = sorted(ids)[1]
    r = admin.get(f"/shipper/orders/{mid}/neighbors")
    assert r.status_code == 200, f"[API-SHP-061] {r.status_code}"
    b = r.json()
    assert "previousId" in b and "nextId" in b, f"[API-SHP-061] нет previousId/nextId: {b}"


@pytest.mark.boundary
def test_neighbors_edge_062(admin, order_factory):
    o = order_factory.make("PUBLISHED")  # самый свежий → первый в createdAt,desc
    b = admin.get(f"/shipper/orders/{o['id']}/neighbors").json()
    assert b.get("previousId") is None, f"[API-SHP-062] на краю previousId должен быть null: {b}"


@pytest.mark.high
@pytest.mark.validation
def test_neighbors_sort_unsupported_063(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = admin.get(f"/shipper/orders/{o['id']}/neighbors?sort=notes,asc")
    assert r.status_code == 400 and _code(r) == "error.order.sort-unsupported", f"[API-SHP-063] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_neighbors_sort_supported_064(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    for s in ("loadDate,desc", "companyOrderSeq,asc"):
        r = admin.get(f"/shipper/orders/{o['id']}/neighbors?sort={s}")
        assert r.status_code == 200, f"[API-SHP-064] sort={s}: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_neighbors_tenancy_065(admin, tb):
    r = admin.get(f"/shipper/orders/{tb['order_id']}/neighbors")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-065] {r.status_code}/{_code(r)}"


# ═══ POST /shipper/orders/{id}/cancel (066…080) ══════════════════════════════


@pytest.mark.high
def test_cancel_from_selected_066(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "AT cancel"})
    assert r.status_code == 200, f"[API-SHP-066] {r.status_code} {r.text[:160]}"
    b = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert b["status"] == "CANCELLED" and b.get("cancellationReason") == "AT cancel", f"[API-SHP-066] {b.get('status')}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_cancel_from_inwork_067(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 200, f"[API-SHP-067] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_cancel_from_intransit_068(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 200, f"[API-SHP-068] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_cancel_published_409_069(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 409 and _code(r) == "error.order.not-cancellable", f"[API-SHP-069] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_cancel_quoted_409_070(admin, order_factory):
    o = order_factory.make("QUOTED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 409 and _code(r) == "error.order.not-cancellable", f"[API-SHP-070] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_cancel_idempotent_071(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 409 and _code(r) == "error.order.not-cancellable", f"[API-SHP-071] {r.status_code}/{_code(r)}"


@pytest.mark.validation
def test_cancel_reason_too_long_072(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x" * 501})
    assert r.status_code == 400 and "reason" in _err_fields(r), f"[API-SHP-072] {r.status_code} {_err_fields(r)}"


@pytest.mark.boundary
def test_cancel_reason_500_073(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x" * 500})
    assert r.status_code == 200, f"[API-SHP-073] 500 символов должно проходить: {r.status_code} {r.text[:120]}"


def test_cancel_reason_absent_074(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/cancel", json={})
    assert r.status_code == 200, f"[API-SHP-074] reason необязателен: {r.status_code} {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_cancel_tenancy_075(admin, tb):
    r = admin.post(f"/shipper/orders/{tb['order_id']}/cancel", json={"reason": "x"})
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-075] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_cancel_dispatcher_no_fulfill_403_076(cap, order_factory):
    o = order_factory.make("SELECTED")
    disp = cap("SHIPPER_DISPATCHER")
    r = disp.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-076] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_cancel_dispatcher_granted_fulfill_200_077(cap, order_factory):
    o = order_factory.make("SELECTED")
    disp = cap("SHIPPER_DISPATCHER", grants=["ORDER_FULFILL"])
    r = disp.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 200, f"[API-SHP-077] персональный грант ORDER_FULFILL: {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_cancel_operator_has_fulfill_200_078(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_operator").post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 200, f"[API-SHP-078] у оператора ORDER_FULFILL по умолчанию: {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_cancel_rbac_warehouse_079(api, order_factory):
    o = order_factory.make("SELECTED")
    r = api("shipper_warehouse").post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-079] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-035: гонка cancel отдаёт 500 вместо 409 concurrent-modification (нет пессимистичного лока)", strict=True)
def test_cancel_race_080(admin, order_factory, cfg):
    """Правильный контракт: проигравший гонки — 409 (concurrent-modification / not-cancellable),
    НИКОГДА 500. Детерминированный до фикса: 15 раундов при p(500)≈1/3 → P(увидеть 500)≈99.8%.
    Хотя бы один 500 → BUG-035 воспроизведён (тест падает → xfail). Ноль 500 при живых
    409-конфликтах → поведение корректно (тест проходит → XPASS strict сигналит о фиксе)."""
    from utils.api_client import ApiClient
    tok = admin.token
    losers = []
    for _ in range(15):
        o = order_factory.make("SELECTED")
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]

        def fire(c):
            return c.request("POST", f"/shipper/orders/{o['id']}/cancel", tok, json={"reason": "race"}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            codes = sorted(ex.map(fire, clients))
        assert codes.count(200) == 1, f"[API-SHP-080] ожидали ровно один успех на раунд, получили {codes}"
        losers.append(next(c for c in codes if c != 200))
    assert losers.count(409) > 0, f"[API-SHP-080] гонка не породила ни одного 409-конфликта — тест не показателен: {losers}"
    assert 500 not in losers, \
        f"[API-SHP-080] проигравший вернул 500 вместо 409 в {losers.count(500)}/15 раундах (BUG-035): {losers}"


# ═══ POST /shipper/orders/{id}/republish (081…095) ═══════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_republish_from_cancelled_081(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 200, f"[API-SHP-081] {r.status_code} {r.text[:160]}"
    b = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert b["status"] == "QUOTED", f"[API-SHP-081] ожидали QUOTED, получили {b['status']}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_republish_from_selected_082(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 200, f"[API-SHP-082] {r.status_code} {r.text[:160]}"
    b = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert b["status"] == "QUOTED", f"[API-SHP-082] {b['status']}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_republish_changed_supersedes_083(admin, order_factory):
    o = order_factory.make("CANCELLED")
    new_load = "2026-12-31"
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, loadDate=new_load))
    assert r.status_code == 200, f"[API-SHP-083] {r.status_code} {r.text[:160]}"
    src = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert src["status"] == "SUPERSEDED", f"[API-SHP-083] исходный должен стать SUPERSEDED, получили {src['status']}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_republish_inwork_409_084(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 409 and _code(r) == "error.order.not-republishable", f"[API-SHP-084] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_republish_quoted_409_085(admin, order_factory):
    o = order_factory.make("QUOTED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 409 and _code(r) == "error.order.not-republishable", f"[API-SHP-085] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_republish_cargotype_null_086(admin, order_factory):
    o = order_factory.make("CANCELLED")
    body = _order_body(o)
    body.pop("cargoType")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=body)
    assert r.status_code == 400 and "cargoType" in _err_fields(r), f"[API-SHP-086] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_republish_driverscount_087(admin, order_factory):
    o = order_factory.make("CANCELLED")
    for n in (0, 3):
        r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, driversCount=n))
        assert r.status_code == 400 and "driversCount" in _err_fields(r), f"[API-SHP-087] n={n}: {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_republish_required_088(admin, order_factory):
    o = order_factory.make("CANCELLED")
    for field in ("loadDate", "vehicleTypeId"):
        body = _order_body(o)
        body.pop(field)
        r = admin.post(f"/shipper/orders/{o['id']}/republish", json=body)
        assert r.status_code == 400 and field in _err_fields(r), f"[API-SHP-088] {field}: {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_republish_vt_not_found_089(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, vehicleTypeId=str(uuid.uuid4())))
    assert r.status_code == 404 and _code(r) == "error.order.vehicle-type-not-found", f"[API-SHP-089] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_republish_schedule_past_090(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, scheduledPublishDate="2020-01-01"))
    assert r.status_code == 400 and _code(r) == "error.order.schedule-not-in-future", f"[API-SHP-090] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_republish_schedule_after_load_091(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish",
                   json=_order_body(o, loadDate="2026-12-01", scheduledPublishDate="2026-12-15"))
    assert r.status_code == 400 and _code(r) == "error.order.schedule-not-before-load", f"[API-SHP-091] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_republish_load_past_092(admin, order_factory):
    o = order_factory.make("CANCELLED")
    r = admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, loadDate="2020-01-01"))
    assert r.status_code == 400 and _code(r) == "error.order.load-not-after-publish", f"[API-SHP-092] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_republish_tenancy_093(admin, tb):
    body = {"cargoType": "AUTO", "currency": "CNY", "loadDate": "2026-12-31", "vehicleTypeId": str(uuid.uuid4()),
            "driversCount": 1, "fromWarehouseId": str(uuid.uuid4()), "toWarehouseId": str(uuid.uuid4())}  # валидно → доходит до поиска заказа
    r = admin.post(f"/shipper/orders/{tb['order_id']}/republish", json=body)
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-093] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_republish_dispatcher_no_fulfill_403_094(cap, order_factory):
    o = order_factory.make("CANCELLED")
    disp = cap("SHIPPER_DISPATCHER")
    r = disp.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-094] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_republish_dispatcher_granted_200_095(cap, order_factory):
    o = order_factory.make("CANCELLED")
    disp = cap("SHIPPER_DISPATCHER", grants=["ORDER_FULFILL"])
    r = disp.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o))
    assert r.status_code == 200, f"[API-SHP-095] {r.status_code}/{_code(r)} {r.text[:120]}"


# ═══ POST /shipper/orders/{id}/communication (096…103) ═══════════════════════


@pytest.mark.high
def test_communication_096(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 204, f"[API-SHP-096] {r.status_code} {r.text[:160]}"
    b = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert b.get("communicationStatus") == "CONFIRMED" and b["status"] == "IN_WORK", f"[API-SHP-096] {b.get('communicationStatus')}/{b['status']}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_communication_rewrite_097(admin, order_factory):
    o = order_factory.make("IN_WORK")
    for st in ("UNAVAILABLE", "CONFIRMED"):
        r = admin.post(f"/shipper/orders/{o['id']}/communication", json={"status": st})
        assert r.status_code == 204, f"[API-SHP-097] {st}: {r.status_code}"


@pytest.mark.low
@pytest.mark.boundary
def test_communication_all_values_098(admin, order_factory):
    o = order_factory.make("IN_WORK")
    for st in ("PENDING", "CONFIRMED", "DECLINED", "UNAVAILABLE"):
        r = admin.post(f"/shipper/orders/{o['id']}/communication", json={"status": st})
        assert r.status_code == 204, f"[API-SHP-098] {st}: {r.status_code}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_communication_not_inwork_409_099(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.post(f"/shipper/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 409 and _code(r) == "error.order.not-communicable", f"[API-SHP-099] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_communication_status_null_100(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/communication", json={})
    assert r.status_code == 400 and "status" in _err_fields(r), f"[API-SHP-100] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_communication_bad_enum_101(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/communication", json={"status": "FOO"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SHP-101] {r.status_code}/{_code(r)}"  # enum-parse (HttpMessageNotReadable) → framework BAD_REQUEST


@pytest.mark.high
@pytest.mark.tenancy
def test_communication_tenancy_102(admin, tb):
    r = admin.post(f"/shipper/orders/{tb['order_id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-102] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_communication_dispatcher_403_103(cap, order_factory):
    o = order_factory.make("IN_WORK")
    disp = cap("SHIPPER_DISPATCHER")
    r = disp.post(f"/shipper/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-103] {r.status_code}/{_code(r)}"


# ═══ POST /shipper/orders/{id}/complete (104…108) ════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_complete_104(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    r = admin.post(f"/shipper/orders/{o['id']}/complete")
    assert r.status_code == 200, f"[API-SHP-104] {r.status_code} {r.text[:160]}"
    b = admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert b["status"] == "COMPLETED", f"[API-SHP-104] {b['status']}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_complete_not_intransit_409_105(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/complete")
    assert r.status_code == 409 and _code(r) == "error.order.not-completable", f"[API-SHP-105] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_complete_idempotent_106(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    assert admin.post(f"/shipper/orders/{o['id']}/complete").status_code == 200, "[API-SHP-106] первый complete"
    r = admin.post(f"/shipper/orders/{o['id']}/complete")
    assert r.status_code == 409 and _code(r) == "error.order.not-completable", f"[API-SHP-106] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_complete_tenancy_107(admin, tb):
    r = admin.post(f"/shipper/orders/{tb['order_id']}/complete")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-107] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_complete_dispatcher_403_108(cap, order_factory):
    o = order_factory.make("IN_TRANSIT")
    disp = cap("SHIPPER_DISPATCHER")
    r = disp.post(f"/shipper/orders/{o['id']}/complete")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-108] {r.status_code}/{_code(r)}"


# ═══ POST /shipper/orders/{id}/enter-1c (109…116) ════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_enter1c_109(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    r = admin.post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 204, f"[API-SHP-109] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_enter1c_from_completed_110(admin, order_factory):
    o = order_factory.make("COMPLETED")
    r = admin.post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 204, f"[API-SHP-110] из COMPLETED разрешено: {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_enter1c_inwork_409_111(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 409 and _code(r) == "error.order.not-1c-enterable", f"[API-SHP-111] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_enter1c_idempotent_112(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    assert admin.post(f"/shipper/orders/{o['id']}/enter-1c").status_code == 204, "[API-SHP-112] первая отметка"
    r = admin.post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 409 and _code(r) == "error.order.not-1c-enterable", f"[API-SHP-112] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_enter1c_tenancy_113(admin, tb):
    r = admin.post(f"/shipper/orders/{tb['order_id']}/enter-1c")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-113] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_enter1c_operator_no_departures_403_114(api, order_factory):
    o = order_factory.make("IN_TRANSIT")
    r = api("shipper_operator").post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-114] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_enter1c_operator_granted_204_115(cap, order_factory):
    o = order_factory.make("IN_TRANSIT")
    op = cap("SHIPPER_OPERATOR", grants=["DEPARTURES"])
    r = op.post(f"/shipper/orders/{o['id']}/enter-1c")
    assert r.status_code == 204, f"[API-SHP-115] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
@pytest.mark.xfail(reason="BUG-035: гонка enter-1c отдаёт 500 вместо 409 concurrent-modification (тот же незамапленный @Version-конфликт)", strict=True)
def test_enter1c_race_116(admin, order_factory, cfg):
    """Правильный контракт: проигравший гонки enter-1c — 409, НИКОГДА 500. Детерминированный
    до фикса: 15 раундов при p(500)≈1/2 → P(увидеть 500)≈99.997%. Хотя бы один 500 → BUG-035
    воспроизведён (падение → xfail); ноль 500 при живых 409 → корректно (XPASS сигналит о фиксе)."""
    from utils.api_client import ApiClient
    tok = admin.token
    losers = []
    for _ in range(15):
        o = order_factory.make("IN_TRANSIT")
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]

        def fire(c):
            return c.request("POST", f"/shipper/orders/{o['id']}/enter-1c", tok).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            codes = sorted(ex.map(fire, clients))
        assert codes.count(204) == 1, f"[API-SHP-116] ожидали ровно один успех на раунд, получили {codes}"
        losers.append(next(c for c in codes if c != 204))
    assert losers.count(409) > 0, f"[API-SHP-116] гонка не породила ни одного 409-конфликта — тест не показателен: {losers}"
    assert 500 not in losers, \
        f"[API-SHP-116] проигравший вернул 500 вместо 409 в {losers.count(500)}/15 раундах (BUG-035): {losers}"


# ═══ DELETE /shipper/orders/{id} (117…124) ═══════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_delete_published_117(admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = admin.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 204, f"[API-SHP-117] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_delete_selected_409_118(admin, order_factory):
    o = order_factory.make("SELECTED")
    r = admin.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 409 and _code(r) == "error.order.not-deletable", f"[API-SHP-118] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.lifecycle
def test_delete_superseded_409_119(admin, order_factory):
    o = order_factory.make("CANCELLED")
    admin.post(f"/shipper/orders/{o['id']}/republish", json=_order_body(o, loadDate="2026-12-31"))  # source → SUPERSEDED
    r = admin.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 409 and _code(r) == "error.order.not-deletable", f"[API-SHP-119] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_delete_tenancy_120(admin, tb):
    r = admin.delete(f"/shipper/orders/{tb['order_id']}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-120] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_delete_manager_no_delete_403_121(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    mgr = cap("SHIPPER_MANAGER")
    r = mgr.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-121] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_delete_manager_granted_204_122(cap, order_factory):
    o = order_factory.make("CANCELLED")
    mgr = cap("SHIPPER_MANAGER", grants=["ORDER_DELETE"])
    r = mgr.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 204, f"[API-SHP-122] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_delete_idempotent_123(admin, order_factory):
    o = order_factory.make("CANCELLED")
    assert admin.delete(f"/shipper/orders/{o['id']}").status_code == 204, "[API-SHP-123] первое удаление"
    r = admin.delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-SHP-123] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_delete_rbac_warehouse_124(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("shipper_warehouse").delete(f"/shipper/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-124] {r.status_code}/{_code(r)}"


# ═══ GET /shipper/departures (125…137) ═══════════════════════════════════════


@pytest.mark.high
def test_departures_confirmed_125(admin, order_factory):
    o = order_factory.make("IN_WORK")
    r = admin.get("/shipper/departures?tab=CONFIRMED&size=200")
    assert r.status_code == 200, f"[API-SHP-125] {r.status_code}"
    pg = _page(r)
    assert pg.get("size") == 200, f"[API-SHP-125] size param"
    row = next((x for x in _content(r) if x.get("orderId") == o["id"] or x.get("id") == o["id"]), None)
    assert row is not None, "[API-SHP-125] IN_WORK заказ не во вкладке CONFIRMED"
    assert "price" in row, "[API-SHP-125] у SHIPPER_ADMIN (SEE_PRICES) price должна быть в строке"


@pytest.mark.medium
def test_departures_intransit_126(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    rows = _content(admin.get("/shipper/departures?tab=IN_TRANSIT&size=200"))
    assert any(x.get("orderId") == o["id"] or x.get("id") == o["id"] for x in rows), "[API-SHP-126] IN_TRANSIT не во вкладке"


@pytest.mark.medium
def test_departures_entered1c_127(admin, order_factory):
    o = order_factory.make("IN_TRANSIT")
    admin.post(f"/shipper/orders/{o['id']}/enter-1c")
    rows = _content(admin.get("/shipper/departures?tab=ENTERED_1C&size=200"))
    assert any(x.get("orderId") == o["id"] or x.get("id") == o["id"] for x in rows), "[API-SHP-127] отмеченный 1С не во вкладке ENTERED_1C"


@pytest.mark.medium
@pytest.mark.validation
def test_departures_tab_missing_400_128(admin):
    r = admin.get("/shipper/departures")
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SHP-128] {r.status_code}/{_code(r)}"  # missing required query-param → framework BAD_REQUEST


@pytest.mark.low
@pytest.mark.validation
def test_departures_tab_bad_400_129(admin):
    r = admin.get("/shipper/departures?tab=FOO")
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SHP-129] {r.status_code}/{_code(r)}"  # enum type-mismatch → framework BAD_REQUEST


@pytest.mark.low
def test_departures_filters_130(admin):
    absent = "ZZ" + uuid.uuid4().hex[:4].upper()
    r = admin.get(f"/shipper/departures?tab=IN_TRANSIT&plate={absent}")
    assert r.status_code == 200 and _content(r) == [], f"[API-SHP-130] plate без совпадений не пуст: {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.capability
def test_departures_price_admin_200_131(admin):
    r = admin.get("/shipper/departures?tab=IN_TRANSIT&priceMin=100&priceMax=500")
    assert r.status_code == 200, f"[API-SHP-131] у админа SEE_PRICES → price-фильтр 200: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_departures_price_manager_403_132(api):
    r = api("shipper_manager").get("/shipper/departures?tab=IN_TRANSIT&priceMin=100")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-132] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_departures_price_dispatcher_403_133(api):
    r = api("shipper_dispatcher").get("/shipper/departures?tab=CONFIRMED&priceMax=500")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-133] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_departures_operator_no_dep_403_134(api):
    r = api("shipper_operator").get("/shipper/departures?tab=CONFIRMED")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-134] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_departures_dispatcher_200_135(api):
    r = api("shipper_dispatcher").get("/shipper/departures?tab=CONFIRMED")
    assert r.status_code == 200, f"[API-SHP-135] у диспетчера DEPARTURES по умолчанию: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_departures_tenancy_136(admin, tb):
    rows = _content(admin.get("/shipper/departures?tab=CONFIRMED&size=200"))
    assert all((x.get("orderId") != tb["order_id"] and x.get("id") != tb["order_id"]) for x in rows), \
        "[API-SHP-136] отправление компании B видно компании A"


@pytest.mark.low
def test_departures_empty_137(admin):
    r = admin.get("/shipper/departures?tab=ENTERED_1C&size=5")
    assert r.status_code == 200, f"[API-SHP-137] {r.status_code}"


# ═══ GET /shipper/departures/summary (138…140) ═══════════════════════════════


@pytest.mark.medium
def test_departures_summary_138(admin):
    b = admin.get("/shipper/departures/summary").json()
    keys = set(b) if isinstance(b, dict) else set()
    assert {"confirmed", "inTransit", "entered1c"} & {k.lower() for k in keys} or len(keys) >= 3, \
        f"[API-SHP-138] нет трёх счётчиков: {sorted(keys)}"


@pytest.mark.medium
@pytest.mark.capability
def test_departures_summary_operator_403_139(api):
    r = api("shipper_operator").get("/shipper/departures/summary")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-139] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_departures_summary_empty_140(empty_admin):
    b = empty_admin.get("/shipper/departures/summary").json()
    assert isinstance(b, dict) and _all_zero(b), f"[API-SHP-140] пустая компания — все счётчики 0: {b}"


# ═══ GET /shipper/warehouses (141…146) ═══════════════════════════════════════


@pytest.mark.high
def test_warehouses_list_141(admin, city_id):
    admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH-" + uuid.uuid4().hex[:5], "address": "addr"})
    r = admin.get("/shipper/warehouses")
    assert r.status_code == 200, f"[API-SHP-141] {r.status_code}"
    assert _page(r).get("size") == 10, f"[API-SHP-141] size=10 по умолчанию"


@pytest.mark.low
def test_warehouses_filter_city_142(admin, city_id):
    admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH-" + uuid.uuid4().hex[:5], "address": "addr"})
    rows = _content(admin.get(f"/shipper/warehouses?cityId={city_id}&size=200"))
    assert rows and all(x.get("cityId") == city_id for x in rows), "[API-SHP-142] cityId-фильтр протекает"


@pytest.mark.low
def test_warehouses_search_143(admin, city_id):
    name = "Baiyun-" + uuid.uuid4().hex[:5]
    admin.post("/shipper/warehouses", json={"cityId": city_id, "name": name, "address": "addr"})
    rows = _content(admin.get("/shipper/warehouses?search=baiyun&size=200"))
    assert any(x["name"] == name for x in rows), "[API-SHP-143] поиск по name без учёта регистра не находит"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_manager", "shipper_operator", "shipper_dispatcher"])
def test_warehouses_read_144(api, role):
    r = api(role).get("/shipper/warehouses")
    assert r.status_code == 200, f"[API-SHP-144] {role} (WAREHOUSE_DIRECTORY_READ): {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_warehouses_empty_145(admin):
    r = admin.get("/shipper/warehouses?search=zzz-" + uuid.uuid4().hex[:6])
    assert r.status_code == 200 and _content(r) == [], f"[API-SHP-145] {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.rbac
def test_warehouses_rbac_warehouse_146(api):
    r = api("shipper_warehouse").get("/shipper/warehouses")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-146] {r.status_code}/{_code(r)}"


# ═══ POST /shipper/warehouses (147…155) ══════════════════════════════════════


@pytest.mark.high
def test_warehouse_create_147(admin, city_id, track_wh):
    r = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH-" + uuid.uuid4().hex[:5], "address": "addr"})
    assert r.status_code == 201, f"[API-SHP-147] {r.status_code} {r.text[:160]}"
    track_wh(r.json()["id"])


@pytest.mark.medium
def test_warehouse_create_division_148(admin, track_wh):
    r = admin.post("/shipper/warehouses",
                   json={"divisionCountry": "CN", "divisionCode": "330782", "name": "AT-DIV-" + uuid.uuid4().hex[:5], "address": "addr"})
    assert r.status_code == 201, f"[API-SHP-148] division-склад: {r.status_code} {r.text[:160]}"
    track_wh(r.json()["id"])


@pytest.mark.high
@pytest.mark.validation
def test_warehouse_name_empty_149(admin, city_id):
    r = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "", "address": "addr"})
    assert r.status_code == 400 and "name" in _err_fields(r), f"[API-SHP-149] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_warehouse_address_empty_150(admin, city_id):
    r = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": ""})
    assert r.status_code == 400 and "address" in _err_fields(r), f"[API-SHP-150] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_warehouse_division_bad_country_151(admin):
    r = admin.post("/shipper/warehouses",
                   json={"divisionCountry": "US", "divisionCode": "1", "name": "AT-WH", "address": "addr"})
    assert r.status_code == 400 and "divisionCountry" in _err_fields(r), f"[API-SHP-151] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_warehouse_name_boundary_152(admin, city_id, track_wh):
    ok = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "a" * 255, "address": "addr"})
    assert ok.status_code == 201, f"[API-SHP-152] name=255 должно проходить: {ok.status_code}"
    track_wh(ok.json()["id"])
    bad = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "a" * 256, "address": "addr"})
    assert bad.status_code == 400 and "name" in _err_fields(bad), f"[API-SHP-152] name=256: {bad.status_code} {_err_fields(bad)}"


@pytest.mark.high
@pytest.mark.capability
def test_warehouse_create_manager_403_153(cap, city_id):
    mgr = cap("SHIPPER_MANAGER")
    r = mgr.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-153] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_warehouse_create_manager_granted_154(cap, city_id):
    mgr = cap("SHIPPER_MANAGER", grants=["WAREHOUSE_DIRECTORY_WRITE"])
    r = mgr.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH-" + uuid.uuid4().hex[:5], "address": "addr"})
    assert r.status_code == 201, f"[API-SHP-154] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.parametrize("role", ["SHIPPER_OPERATOR", "SHIPPER_DISPATCHER"])
def test_warehouse_create_role_403_155(cap, city_id, role):
    c = cap(role)
    r = c.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-155] {role}: {r.status_code}/{_code(r)}"


# ═══ PATCH /shipper/warehouses/{id} (156…159) ════════════════════════════════


@pytest.mark.high
def test_warehouse_update_156(admin, city_id, track_wh):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    track_wh(w["id"])
    r = admin.patch(f"/shipper/warehouses/{w['id']}", json={"cityId": city_id, "name": "AT-WH-upd", "address": "addr2"})
    assert r.status_code == 200 and r.json().get("name") == "AT-WH-upd", f"[API-SHP-156] {r.status_code} {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_warehouse_update_tenancy_157(admin, tb):
    r = admin.patch(f"/shipper/warehouses/{tb['warehouse_id']}", json={"name": "hack", "address": "a"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-157] чужой склад: {r.status_code}/{_code(r)}"  # факт 403 (→ BUG-036: непоследовательное сокрытие кросс-тенанта)


@pytest.mark.medium
@pytest.mark.capability
def test_warehouse_update_manager_403_158(cap, admin, city_id, track_wh):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    track_wh(w["id"])
    mgr = cap("SHIPPER_MANAGER")
    r = mgr.patch(f"/shipper/warehouses/{w['id']}", json={"name": "x", "address": "y"})
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-158] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_warehouse_update_name_empty_159(admin, city_id, track_wh):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    track_wh(w["id"])
    r = admin.patch(f"/shipper/warehouses/{w['id']}", json={"cityId": city_id, "name": "", "address": "addr"})
    assert r.status_code == 400 and "name" in _err_fields(r), f"[API-SHP-159] {r.status_code} {_err_fields(r)}"


# ═══ DELETE /shipper/warehouses/{id} (160…163) ══════════════════════════════


@pytest.mark.high
def test_warehouse_delete_160(admin, city_id):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    r = admin.delete(f"/shipper/warehouses/{w['id']}")
    assert r.status_code == 204, f"[API-SHP-160] {r.status_code}"


@pytest.mark.high
@pytest.mark.tenancy
def test_warehouse_delete_tenancy_161(admin, tb):
    r = admin.delete(f"/shipper/warehouses/{tb['warehouse_id']}")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-161] чужой склад: {r.status_code}/{_code(r)}"  # факт 403 (→ BUG-036)


@pytest.mark.medium
@pytest.mark.capability
def test_warehouse_delete_manager_403_162(cap, admin, city_id, track_wh):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    track_wh(w["id"])
    mgr = cap("SHIPPER_MANAGER")
    r = mgr.delete(f"/shipper/warehouses/{w['id']}")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-162] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_warehouse_delete_manager_granted_163(cap, admin, city_id):
    w = admin.post("/shipper/warehouses", json={"cityId": city_id, "name": "AT-WH", "address": "addr"}).json()
    mgr = cap("SHIPPER_MANAGER", grants=["WAREHOUSE_DIRECTORY_WRITE"])
    r = mgr.delete(f"/shipper/warehouses/{w['id']}")
    assert r.status_code == 204, f"[API-SHP-163] {r.status_code}/{_code(r)}"


# ═══ GET /shipper/vehicle-types + /cities (164…168) ══════════════════════════


@pytest.mark.medium
def test_vehicle_types_164(admin):
    r = admin.get("/shipper/vehicle-types?search=bort")
    assert r.status_code == 200, f"[API-SHP-164] {r.status_code}"
    assert _page(r).get("size") == 20, f"[API-SHP-164] size=20 по умолчанию: {_page(r)}"


@pytest.mark.low
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_admin", "shipper_manager", "shipper_operator", "shipper_dispatcher"])
def test_vehicle_types_all_office_165(api, role):
    r = api(role).get("/shipper/vehicle-types")
    assert r.status_code == 200, f"[API-SHP-165] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.rbac
def test_vehicle_types_warehouse_403_166(api):
    r = api("shipper_warehouse").get("/shipper/vehicle-types")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-166] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_cities_167(admin):
    r = admin.get("/shipper/cities?search=tash&country=UZ")
    assert r.status_code == 200, f"[API-SHP-167] {r.status_code}"
    assert _page(r).get("size") == 200, f"[API-SHP-167] size=200 по умолчанию: {_page(r)}"


@pytest.mark.low
@pytest.mark.rbac
def test_cities_warehouse_403_168(api):
    r = api("shipper_warehouse").get("/shipper/cities")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-168] {r.status_code}/{_code(r)}"


# ═══ GET /shipper/reports/orders (169…175) ═══════════════════════════════════


@pytest.mark.high
def test_reports_orders_169(admin):
    r = admin.get("/shipper/reports/orders")
    assert r.status_code == 200, f"[API-SHP-169] {r.status_code}"
    assert _page(r).get("size") == 10, f"[API-SHP-169] size=10 по умолчанию"


@pytest.mark.low
def test_reports_orders_empty_170(admin):
    r = admin.get("/shipper/reports/orders?dateFrom=2000-01-01&dateTo=2000-01-02")
    assert r.status_code == 200 and _content(r) == [], f"[API-SHP-170] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.capability
def test_reports_orders_manager_403_171(api):
    r = api("shipper_manager").get("/shipper/reports/orders")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-171] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_operator", "shipper_dispatcher"])
def test_reports_orders_role_403_172(api, role):
    r = api(role).get("/shipper/reports/orders")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-172] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_reports_orders_manager_granted_173(cap):
    mgr = cap("SHIPPER_MANAGER", grants=["REPORTS"])
    r = mgr.get("/shipper/reports/orders")
    assert r.status_code == 200, f"[API-SHP-173] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_reports_orders_warehouse_403_174(api):
    r = api("shipper_warehouse").get("/shipper/reports/orders")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-174] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_reports_orders_tenancy_175(admin, tb):
    r = admin.get("/shipper/reports/orders?size=200")
    assert r.status_code == 200, f"[API-SHP-175] {r.status_code}"  # содержит только свою компанию (проверка на утечку id ниже)
    ids = {x.get("orderId") or x.get("id") for x in _content(r)}
    assert tb["order_id"] not in ids, "[API-SHP-175] заказ компании B в отчёте компании A"


# ═══ GET /shipper/reports/companies (176…178) ════════════════════════════════


@pytest.mark.medium
def test_reports_companies_176(admin):
    r = admin.get("/shipper/reports/companies")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-SHP-176] {r.status_code} {type(r.json())}"


@pytest.mark.low
def test_reports_companies_empty_177(empty_admin):
    r = empty_admin.get("/shipper/reports/companies")
    assert r.status_code == 200 and r.json() == [], f"[API-SHP-177] пустая компания — пустой список: {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.capability
def test_reports_companies_manager_403_178(api):
    r = api("shipper_manager").get("/shipper/reports/companies")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-178] {r.status_code}/{_code(r)}"


# ═══ GET /shipper/dashboard/stats (179…182) ══════════════════════════════════


@pytest.mark.high
def test_dashboard_stats_179(admin):
    r = admin.get("/shipper/dashboard/stats")
    assert r.status_code == 200 and isinstance(r.json(), dict), f"[API-SHP-179] {r.status_code}"


@pytest.mark.medium
@pytest.mark.capability
def test_dashboard_stats_manager_403_180(api):
    r = api("shipper_manager").get("/shipper/dashboard/stats")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-SHP-180] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_dashboard_stats_empty_181(empty_admin):
    b = empty_admin.get("/shipper/dashboard/stats").json()
    assert isinstance(b, dict) and _all_zero(b), f"[API-SHP-181] пустая компания — нулевые агрегаты: {b}"


# API-SHP-182 (dashboard без shipperCompanyId → 403 error.order.no-shipper-company) — automation:backend:
# офисная роль без привязки к компании в чёрном ящике не провизинится (staff всегда с компанией).
# Тест не пишем (см. docs/testcases/NON-AUTO.md); кейс помечен automation:backend в JSON.


# ─── warehouse cleanup registry ──────────────────────────────────────────────


@pytest.fixture
def track_wh(admin):
    reg = []

    def add(wid):
        reg.append(wid)
        return wid

    yield add
    for wid in reversed(reg):
        try:
            admin.delete(f"/shipper/warehouses/{wid}")
        except Exception:  # noqa: BLE001
            pass
