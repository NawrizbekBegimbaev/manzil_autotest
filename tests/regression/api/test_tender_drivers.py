"""API — Transport drivers CRUD (docs/testcases/api/04_tendering_transport.json, part 3).

API-TND-070…095 — POST/PATCH/DELETE/GET /transport/drivers: создание (имя+телефон+cardId),
уникальность телефона в пределах компании, валидация/границы, soft-delete (свободного;
занятого — 409 busy), BOLA-404 (чужой водитель), RBAC (только TRANSPORT_ADMIN).

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

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


def _phone():
    return "+99890" + _d(7)


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def carrier(api):
    return api("transport_admin")


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def mk_driver(carrier):
    """Factory → создать водителя у dev-перевозчика; удалить на teardown (failure-safe)."""
    created = []

    def _mk(**over):
        body = {"fullName": "AT Driver", "phone": _phone()}
        body.update(over)
        r = carrier.post("/transport/drivers", json=body)
        assert r.status_code == 201, f"driver setup: {r.status_code} {r.text[:160]}"
        created.append(r.json()["id"])
        return r.json(), body

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
        phone = _phone()
        body = {"name": f"AT-TC-{_d(6)}", "tin": _d(9), "address": "Tashkent, Sayyod 1",
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


# ═══ POST /transport/drivers (070…079) ═══════════════════════════════════════


@pytest.mark.high
def test_driver_create_070(mk_driver):
    d, _ = mk_driver()
    assert d.get("cardId") is None and d.get("completedOrders") in (0, None), f"[API-TND-070] {d}"
    assert d.get("currentOrderId") is None, "[API-TND-070] новый водитель не должен быть занят"


@pytest.mark.high
@pytest.mark.negative
def test_driver_dup_phone_071(carrier, mk_driver):
    _, body = mk_driver()
    r = carrier.post("/transport/drivers", json={"fullName": "AT Dup", "phone": body["phone"]})
    assert r.status_code == 409 and _code(r) == "error.driver.phone-exists", f"[API-TND-071] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_driver_same_phone_other_company_072(carrier, mk_driver, fresh_carrier):
    _, body = mk_driver()
    c2, _ = fresh_carrier()
    r = c2.post("/transport/drivers", json={"fullName": "AT Other", "phone": body["phone"]})
    assert r.status_code == 201, f"[API-TND-072] тот же телефон в другой компании должен пройти: {r.status_code} {r.text[:120]}"
    c2.delete(f"/transport/drivers/{r.json()['id']}")


@pytest.mark.high
@pytest.mark.validation
def test_driver_fullname_blank_073(carrier):
    r = carrier.post("/transport/drivers", json={"fullName": "  ", "phone": _phone()})
    assert r.status_code == 400 and "fullName" in _err_fields(r), f"[API-TND-073] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_driver_fullname_boundary_074(carrier, mk_driver):
    assert carrier.post("/transport/drivers", json={"fullName": "A", "phone": _phone()}).status_code == 400, "[API-TND-074] 1 символ"
    mk_driver(fullName="AB")   # 2 ок
    mk_driver(fullName="A" * 255)  # 255 ок
    bad = carrier.post("/transport/drivers", json={"fullName": "A" * 256, "phone": _phone()})
    assert bad.status_code == 400 and "fullName" in _err_fields(bad), f"[API-TND-074] 256: {bad.status_code}"


@pytest.mark.high
@pytest.mark.validation
def test_driver_phone_mask_075(carrier):
    for bad in ("998901234567", "+abc123456789"):
        r = carrier.post("/transport/drivers", json={"fullName": "AT Driver", "phone": bad})
        assert r.status_code == 400 and "phone" in _err_fields(r), f"[API-TND-075] {bad}: {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_driver_phone_boundary_076(carrier, mk_driver):
    mk_driver(phone="+" + _d(10))   # 10 цифр ок
    mk_driver(phone="+" + _d(15))   # 15 цифр ок
    for bad in ("+" + _d(16), "+" + _d(9)):
        r = carrier.post("/transport/drivers", json={"fullName": "AT Driver", "phone": bad})
        assert r.status_code == 400 and "phone" in _err_fields(r), f"[API-TND-076] {bad}: {r.status_code}"


@pytest.mark.medium
@pytest.mark.validation
def test_driver_phone_required_077(carrier):
    r = carrier.post("/transport/drivers", json={"fullName": "AT Driver"})
    assert r.status_code == 400 and "phone" in _err_fields(r), f"[API-TND-077] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_driver_cardid_boundary_078(carrier, mk_driver):
    mk_driver(cardId="c" * 32)   # 32 ок
    bad = carrier.post("/transport/drivers", json={"fullName": "AT Driver", "phone": _phone(), "cardId": "c" * 33})
    assert bad.status_code == 400 and "cardId" in _err_fields(bad), f"[API-TND-078] 33: {bad.status_code} {_err_fields(bad)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_driver_create_rbac_079(api):
    r = api("shipper_admin").post("/transport/drivers", json={"fullName": "AT Driver", "phone": _phone()})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-079] {r.status_code}/{_code(r)}"


# ═══ PATCH /transport/drivers/{id} (080…086) ═════════════════════════════════


@pytest.mark.high
def test_driver_patch_080(carrier, mk_driver):
    d, body = mk_driver()
    r = carrier.patch(f"/transport/drivers/{d['id']}", json={"fullName": "AT Renamed"})
    assert r.status_code == 200 and r.json()["fullName"] == "AT Renamed", f"[API-TND-080] {r.status_code}"
    assert r.json().get("phone") == body["phone"], "[API-TND-080] телефон не должен меняться"


@pytest.mark.high
@pytest.mark.negative
def test_driver_patch_dup_phone_081(carrier, mk_driver):
    _, b1 = mk_driver()
    d2, _ = mk_driver()
    r = carrier.patch(f"/transport/drivers/{d2['id']}", json={"phone": b1["phone"]})
    assert r.status_code == 409 and _code(r) == "error.driver.phone-exists", f"[API-TND-081] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_driver_patch_same_phone_082(carrier, mk_driver):
    d, body = mk_driver()
    r = carrier.patch(f"/transport/drivers/{d['id']}", json={"phone": body["phone"]})
    assert r.status_code == 200, f"[API-TND-082] тот же телефон не должен триггерить phone-exists: {r.status_code}"


@pytest.mark.high
@pytest.mark.tenancy
def test_driver_patch_foreign_083(carrier, fresh_carrier):
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": _phone()}).json()["id"]
    r = carrier.patch(f"/transport/drivers/{foreign}", json={"fullName": "Hack"})
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-TND-083] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_driver_patch_fullname_short_084(carrier, mk_driver):
    d, _ = mk_driver()
    r = carrier.patch(f"/transport/drivers/{d['id']}", json={"fullName": "A"})
    assert r.status_code == 400 and "fullName" in _err_fields(r), f"[API-TND-084] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_driver_patch_phone_mask_085(carrier, mk_driver):
    d, _ = mk_driver()
    r = carrier.patch(f"/transport/drivers/{d['id']}", json={"phone": "12345"})
    assert r.status_code == 400 and "phone" in _err_fields(r), f"[API-TND-085] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_driver_patch_rbac_086(api):
    r = api("shipper_admin").patch(f"/transport/drivers/{uuid.uuid4()}", json={"fullName": "XY"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-086] {r.status_code}/{_code(r)}"


# ═══ DELETE /transport/drivers/{id} (087…090) ════════════════════════════════


@pytest.mark.high
def test_driver_delete_087(carrier):
    d = carrier.post("/transport/drivers", json={"fullName": "AT Del", "phone": _phone()}).json()
    assert carrier.delete(f"/transport/drivers/{d['id']}").status_code == 204, "[API-TND-087] delete"
    ids = {x["id"] for x in _content(carrier.get("/transport/drivers?size=200"))}
    assert d["id"] not in ids, "[API-TND-087] удалённый водитель не должен быть в списке"


@pytest.mark.high
@pytest.mark.lifecycle
def test_driver_delete_busy_088(carrier, mk_driver, order_factory):
    o = order_factory.make("SELECTED")  # заказ закреплён за dev-перевозчиком
    d, _ = mk_driver()
    att = carrier.post(f"/transport/orders/{o['id']}/drivers",
                       json={"drivers": [{"driverId": d["id"], "licensePlate": "01A" + _d(3) + "AA", "cardId": _d(18)}]})
    assert att.status_code in (200, 201), f"[API-TND-088] attach setup: {att.status_code} {att.text[:160]}"
    r = carrier.delete(f"/transport/drivers/{d['id']}")
    assert r.status_code == 409 and _code(r) == "error.driver.busy-cannot-delete", f"[API-TND-088] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_driver_delete_foreign_089(carrier, fresh_carrier):
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": _phone()}).json()["id"]
    r = carrier.delete(f"/transport/drivers/{foreign}")
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-TND-089] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_driver_delete_rbac_090(api):
    r = api("shipper_admin").delete(f"/transport/drivers/{uuid.uuid4()}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-090] {r.status_code}/{_code(r)}"


# ═══ GET /transport/drivers (091…095) ════════════════════════════════════════


@pytest.mark.high
def test_driver_list_091(carrier, mk_driver):
    mk_driver()
    r = carrier.get("/transport/drivers")
    assert r.status_code == 200 and _page(r).get("size") == 20, f"[API-TND-091] {r.status_code}"
    rows = _content(r)
    assert rows and all("completedOrders" in x for x in rows), "[API-TND-091] нет completedOrders"


@pytest.mark.low
def test_driver_search_092(carrier, mk_driver):
    d, _ = mk_driver(fullName="Sardor Unique AT")
    rows = _content(carrier.get("/transport/drivers?search=sardor%20unique&size=200"))
    assert any(x["id"] == d["id"] for x in rows), "[API-TND-092] поиск по имени не находит"


@pytest.mark.low
@pytest.mark.rbac
def test_driver_list_rbac_093(api):
    r = api("shipper_admin").get("/transport/drivers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-093] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_driver_get_094(carrier, mk_driver):
    d, _ = mk_driver()
    r = carrier.get(f"/transport/drivers/{d['id']}")
    assert r.status_code == 200 and r.json().get("id") == d["id"] and "completedOrders" in r.json(), f"[API-TND-094] {r.status_code}"


@pytest.mark.high
@pytest.mark.tenancy
def test_driver_get_foreign_095(carrier, fresh_carrier):
    c2, _ = fresh_carrier()
    foreign = c2.post("/transport/drivers", json={"fullName": "AT F", "phone": _phone()}).json()["id"]
    assert carrier.get(f"/transport/drivers/{foreign}").status_code == 404, "[API-TND-095] чужой водитель"
    assert carrier.get(f"/transport/drivers/{uuid.uuid4()}").status_code == 404, "[API-TND-095] несуществующий"
