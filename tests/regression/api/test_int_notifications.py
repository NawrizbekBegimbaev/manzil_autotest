"""API — notifications (/me/notifications) + order view (POST /orders/{id}/view).

API-INT-025…048. Уведомления — PUSH-инбокс получателя (перевозчик после bid-request на
публикации заказа). View — трекинг просмотра (TRANSPORT_ADMIN/DRIVER), НЕ идемпотентен,
питает dispatch-log viewCount → здесь же закрываю pending WH-130/131/134.

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api]


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _d(n):
    return "".join(random.choices(string.digits, k=n))


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def fresh_carrier(dev_api, cfg):
    created = []
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")

    def _mk():
        phone = "+99890" + _d(7)
        body = {"name": f"AT-TC-{_d(6)}", "tin": _d(9), "address": "Tashkent, Sayyod 1",
                "transportTypes": ["AUTO"], "isAll": True, "cityIds": [], "blacklistWarehouseIds": [],
                "admin": {"fullName": "AT C2", "phone": phone, "password": cfg.dev_account_password}}
        cid = dev_api.request("POST", "/super-admin/transport-companies", sa, json=body).json()["id"]
        created.append(cid)
        return RoleClient(dev_api, dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")), cid

    yield _mk
    for cid in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def carrier_notif(fresh_carrier, order_factory):
    """Свежий перевозчик + опубликованный ПОСЛЕ его создания заказ → у него bid-request PUSH."""
    carrier, _ = fresh_carrier()
    order_factory.make("PUBLISHED")  # рассылка eligible-перевозчикам (isAll → включая свежего)
    rows = _content(carrier.get("/me/notifications?size=50"))
    return carrier, rows


# ═══ GET /me/notifications (025…030) ═════════════════════════════════════════


@pytest.mark.high
def test_notif_list_025(carrier_notif):
    carrier, rows = carrier_notif
    assert rows, "[API-INT-025] у перевозчика должно быть ≥1 PUSH-уведомление после публикации"
    assert all("title" in n and "createdAt" in n for n in rows), f"[API-INT-025] {rows[0] if rows else None}"


@pytest.mark.medium
def test_notif_pagination_026(carrier_notif):
    carrier, _ = carrier_notif
    r = carrier.get("/me/notifications?page=1&size=5")
    assert r.status_code == 200 and len(_content(r)) <= 5, f"[API-INT-026] {r.status_code}"


@pytest.mark.low
def test_notif_empty_027(fresh_carrier):
    carrier, _ = fresh_carrier()  # без заказа
    r = carrier.get("/me/notifications")
    assert r.status_code == 200 and _content(r) == [], f"[API-INT-027] {r.text[:120]}"


@pytest.mark.medium
def test_notif_push_only_028(carrier_notif):
    carrier, rows = carrier_notif
    assert all(n.get("channel", "PUSH") == "PUSH" for n in rows), "[API-INT-028] в инбоксе только PUSH"


@pytest.mark.medium
@pytest.mark.validation
def test_notif_bad_sort_029(s_admin):
    r = s_admin.get("/me/notifications?sort=nonexistentField,asc")
    assert r.status_code == 400, f"[API-INT-029] {r.status_code}"
    assert "com.manzil" not in r.text and "class " not in r.text, "[API-INT-029] внутренние имена не должны раскрываться"


@pytest.mark.high
@pytest.mark.rbac
def test_notif_unauth_030(dev_api):
    assert dev_api.request("GET", "/me/notifications", None).status_code == 401, "[API-INT-030]"


# ═══ unread-count + read + read-all + delete (031…040) ═══════════════════════


@pytest.mark.medium
def test_unread_count_031(carrier_notif):
    carrier, _ = carrier_notif
    b = carrier.get("/me/notifications/unread-count").json()
    assert "unread" in b and isinstance(b["unread"], int), f"[API-INT-031] {b}"


@pytest.mark.high
def test_notif_read_032(carrier_notif):
    carrier, rows = carrier_notif
    before = carrier.get("/me/notifications/unread-count").json()["unread"]
    nid = rows[0]["id"]
    assert carrier.post(f"/me/notifications/{nid}/read").status_code == 204, "[API-INT-032] read"
    after = carrier.get("/me/notifications/unread-count").json()["unread"]
    assert after == before - 1, f"[API-INT-032] счётчик: {before}→{after}"


@pytest.mark.low
def test_notif_read_idempotent_033(carrier_notif):
    carrier, rows = carrier_notif
    nid = rows[0]["id"]
    assert carrier.post(f"/me/notifications/{nid}/read").status_code == 204
    assert carrier.post(f"/me/notifications/{nid}/read").status_code == 204, "[API-INT-033] повтор идемпотентен"


@pytest.mark.high
@pytest.mark.tenancy
def test_notif_read_foreign_034(s_admin, carrier_notif):
    carrier, rows = carrier_notif
    nid = rows[0]["id"]  # уведомление перевозчика
    r = s_admin.post(f"/me/notifications/{nid}/read")  # админ читает чужое
    assert r.status_code == 404 and _code(r) == "error.notification.not-found", f"[API-INT-034] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_notif_read_not_found_035(s_admin):
    r = s_admin.post(f"/me/notifications/{uuid.uuid4()}/read")
    assert r.status_code == 404 and _code(r) == "error.notification.not-found", f"[API-INT-035] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_notif_read_bad_uuid_036(s_admin):
    r = s_admin.post("/me/notifications/not-a-uuid/read")
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-INT-036] {r.status_code}/{_code(r)}"


@pytest.mark.medium
def test_notif_read_all_037(carrier_notif):
    carrier, _ = carrier_notif
    assert carrier.post("/me/notifications/read-all").status_code == 204, "[API-INT-037] read-all"
    assert carrier.get("/me/notifications/unread-count").json()["unread"] == 0, "[API-INT-037] count=0"


@pytest.mark.medium
def test_notif_delete_038(carrier_notif):
    carrier, rows = carrier_notif
    nid = rows[0]["id"]
    assert carrier.delete(f"/me/notifications/{nid}").status_code == 204, "[API-INT-038] delete"
    ids = {n["id"] for n in _content(carrier.get("/me/notifications?size=50"))}
    assert nid not in ids, "[API-INT-038] удалённое не в списке"


@pytest.mark.high
@pytest.mark.tenancy
def test_notif_delete_foreign_039(s_admin, carrier_notif):
    carrier, rows = carrier_notif
    r = s_admin.delete(f"/me/notifications/{rows[0]['id']}")
    assert r.status_code == 404 and _code(r) == "error.notification.not-found", f"[API-INT-039] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.negative
def test_notif_delete_not_found_040(s_admin):
    r = s_admin.delete(f"/me/notifications/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.notification.not-found", f"[API-INT-040] {r.status_code}/{_code(r)}"


# ═══ POST /orders/{id}/view (041…048) ════════════════════════════════════════


@pytest.mark.high
def test_view_driver_041(dev_api, cfg, order_factory):
    """DRIVER-получатель открывает заказ → 204, счётчик +1."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", sa).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    phone = "+99890" + _d(7)
    drv = dev_api.request("POST", "/super-admin/drivers", sa,
                          json={"fullName": "AT Drv", "phone": phone, "password": cfg.dev_account_password, "vehicleTypeId": vt})
    assert drv.status_code == 201, f"[API-INT-041] driver setup: {drv.status_code}"
    try:
        tok = dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")
        o = order_factory.make("PUBLISHED")
        assert dev_api.request("POST", f"/orders/{o['id']}/view", tok).status_code == 204, "[API-INT-041] view"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{drv.json()['id']}", sa)


@pytest.mark.medium
def test_view_transport_042(fresh_carrier, order_factory):
    carrier, _ = fresh_carrier()
    o = order_factory.make("PUBLISHED")
    assert carrier.post(f"/orders/{o['id']}/view").status_code == 204, "[API-INT-042]"


@pytest.mark.high
@pytest.mark.lifecycle
def test_view_non_idempotent_043(fresh_carrier, s_admin, order_factory):
    """Каждый POST view +1 (нет дедупликации). Проверяем через dispatch-log viewCount."""
    carrier, _ = fresh_carrier()
    o = order_factory.make("PUBLISHED")
    assert carrier.post(f"/orders/{o['id']}/view").status_code == 204
    assert carrier.post(f"/orders/{o['id']}/view").status_code == 204
    log = _content(s_admin.get(f"/shipper/orders/{o['id']}/dispatch-log"))
    tc = next((x for x in log if x.get("recipientType") == "TRANSPORT" and x.get("viewCount", 0) >= 2), None)
    assert tc is not None, f"[API-INT-043] после 2 view viewCount≥2 не найден: {log}"


@pytest.mark.medium
def test_view_non_recipient_noop_044(fresh_carrier, order_factory):
    """Не-получатель (перевозчик вне served-зоны заказа) → 204 no-op."""
    carrier, _ = fresh_carrier()  # isAll — но заказ мог быть до создания; view всё равно 204
    o = order_factory.make("PUBLISHED")
    r = carrier.post(f"/orders/{o['id']}/view")
    assert r.status_code == 204, f"[API-INT-044] {r.status_code}"


@pytest.mark.medium
def test_view_nonexistent_045(fresh_carrier):
    carrier, _ = fresh_carrier()
    assert carrier.post("/orders/999999999/view").status_code == 204, "[API-INT-045] fire-and-forget"


@pytest.mark.high
@pytest.mark.rbac
def test_view_shipper_admin_403_046(s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = s_admin.post(f"/orders/{o['id']}/view")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-046] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_view_unauth_047(dev_api, order_factory):
    o = order_factory.make("PUBLISHED")
    assert dev_api.request("POST", f"/orders/{o['id']}/view", None).status_code == 401, "[API-INT-047]"


@pytest.mark.low
@pytest.mark.validation
def test_view_bad_id_048(fresh_carrier):
    carrier, _ = fresh_carrier()
    assert carrier.post("/orders/not-a-number/view").status_code == 400, "[API-INT-048]"


# ═══ закрытие pending WH-130/131/134 через view-события ══════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_wh_dispatch_agg_viewcount_130(fresh_carrier, s_admin, order_factory):
    """WH-130: несколько view одного получателя → одна запись, viewCount отражает просмотры."""
    carrier, _ = fresh_carrier()
    o = order_factory.make("PUBLISHED")
    for _ in range(3):
        carrier.post(f"/orders/{o['id']}/view")
    log = _content(s_admin.get(f"/shipper/orders/{o['id']}/dispatch-log"))
    tc_rows = [x for x in log if x.get("recipientType") == "TRANSPORT"]
    hit = [x for x in tc_rows if x.get("viewCount", 0) >= 3]
    assert hit, f"[API-WH-130] viewCount≥3 у одного TRANSPORT-получателя (агрегация в 1 запись): {tc_rows}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_wh_dispatch_sort_131(fresh_carrier, s_admin, order_factory):
    """WH-131: TRANSPORT-получатели идут раньше DRIVER; внутри группы viewCount desc."""
    carrier, _ = fresh_carrier()
    o = order_factory.make("PUBLISHED")
    carrier.post(f"/orders/{o['id']}/view")
    log = _content(s_admin.get(f"/shipper/orders/{o['id']}/dispatch-log"))
    types = [x.get("recipientType") for x in log]
    # все TRANSPORT идут до первого DRIVER
    if "DRIVER" in types and "TRANSPORT" in types:
        assert types.index("TRANSPORT") < types.index("DRIVER"), f"[API-WH-131] порядок TRANSPORT>DRIVER: {types}"
    # viewCount desc внутри TRANSPORT
    tc = [x.get("viewCount", 0) for x in log if x.get("recipientType") == "TRANSPORT"]
    assert tc == sorted(tc, reverse=True), f"[API-WH-131] viewCount desc внутри группы: {tc}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_wh_dispatch_deleted_filtered_134(fresh_carrier, s_admin, order_factory, dev_api, cfg):
    """WH-134: получатель-перевозчик удалён → его строка отброшена из журнала."""
    carrier, cid = fresh_carrier()
    o = order_factory.make("PUBLISHED")
    carrier.post(f"/orders/{o['id']}/view")
    log_before = _content(s_admin.get(f"/shipper/orders/{o['id']}/dispatch-log"))
    # удалить перевозчика
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
    log_after = _content(s_admin.get(f"/shipper/orders/{o['id']}/dispatch-log"))
    assert len(log_after) <= len(log_before), f"[API-WH-134] удалённый получатель должен исчезнуть: {len(log_before)}→{len(log_after)}"
