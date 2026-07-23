"""API — RBAC ролевые/метод-гейты, DRIVER-контракт, tenancy-404, auth-edge, сводные линтеры.

Ролевой отказ (@PreAuthorize hasAnyRole) → 403 code=FORBIDDEN.
Capability-отказ (@RequiresCapability) → 403 code=error.forbidden.
Кросс-тенантный чужой ресурс → 404 (скрытие существования), НЕ 403.
Нет токена → 401 UNAUTHORIZED; деактивирован → 401 error.unauthorized; компания заблокирована
→ 403 error.company.blocked (per-request CurrentUserService.assertAccessible).

Разделы: /shipper/** (4 office-роли) · /warehouse/** (4 office + WAREHOUSE; goods-sent/communication
— только WAREHOUSE) · /transport/** (TRANSPORT_ADMIN) · /super-admin/** (SUPER_ADMIN) ·
/orders/{id}/view (TRANSPORT_ADMIN + DRIVER). DRIVER входит только через TRANSPORT_COMPANY_APP
(→ MNZL-269), достаёт лишь /me* и /orders/{id}/view.

Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

from tests.regression.conftest import RoleClient
from tests.regression.order_lifecycle import OrderFactory

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.rbac]

_FORB = "error.forbidden"
_ROLE_FORB = "FORBIDDEN"
_ADDR = "Tashkent"


def _d(n):
    return "".join(random.choices(string.digits, k=n))


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def cap(s_admin, dev_api, pwd):
    created = []

    def _mk(role, grants=None):
        phone = "+99890" + _d(7)
        sid = s_admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role}).json()["id"]
        created.append(sid)
        if grants:
            s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
        c = RoleClient(dev_api, dev_api.token(phone, pwd, "WEB"))
        c.staff_id, c.phone = sid, phone
        return c

    yield _mk
    for sid in reversed(created):
        try:
            s_admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def driver(dev_api, cfg):
    """Self-employed DRIVER: логин только TRANSPORT_COMPANY_APP (→ MNZL-269). Отдаёт RoleClient."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", sa).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    created = []

    def _mk():
        phone = "+99890" + _d(7)
        r = dev_api.request("POST", "/super-admin/drivers", sa, json={"fullName": "AT Driver", "phone": phone, "password": cfg.dev_account_password, "vehicleTypeId": vt})
        assert r.status_code == 201, f"driver setup: {r.status_code} {r.text[:120]}"
        created.append(r.json()["id"])
        c = RoleClient(dev_api, dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP"))
        c.phone = phone
        return c

    yield _mk
    for did in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/drivers/{did}", sa)
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def fresh_company(dev_api, cfg, api_dev_roles):
    """Свежая shipper-компания: admin + warehouse; строит COMPLETED/любые заказы. Teardown удаляет."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    carrier = dev_api.token(cph, cpw, cct)
    companies = []

    class _Co:
        def __init__(self, cid, admin_tok, staff_admin, factory):
            self.id, self.admin, self.staff_admin, self._f = cid, admin_tok, staff_admin, factory

        def make(self, status="PUBLISHED"):
            return self._f.make(status)

    def _mk():
        aphone = "+99890" + _d(7)
        r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json={
            "name": f"AT-B-{_d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": _d(9), "address": _ADDR, "admin": {"fullName": "AT B Admin", "phone": aphone, "password": cfg.dev_account_password}})
        assert r.status_code == 201, f"fresh company: {r.status_code} {r.text[:160]}"
        cid = r.json()["id"]
        companies.append(cid)
        adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
        whp = "+99890" + _d(7)
        dev_api.request("POST", "/shipper/staff", adm, json={"fullName": "AT B Warehouse", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
        whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
        f = OrderFactory(dev_api, sa, whb, adm, carrier)
        return _Co(cid, RoleClient(dev_api, adm), RoleClient(dev_api, adm), f)

    yield _mk
    for cid in reversed(companies):
        try:
            dev_api.request("DELETE", f"/super-admin/shipper-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


# ═══ Ролевые гейты разделов (012–017, 057, 061–064, 067, 095) ═════════════════


@pytest.mark.high
@pytest.mark.security
def test_warehouse_not_in_shipper_gate_012(api):
    """API-RBAC-012: SHIPPER_WAREHOUSE вообще не допущен к /shipper/** → 403 FORBIDDEN (ролевой, не error.forbidden)."""
    wh = api("shipper_warehouse")
    for p in ("/shipper/orders", "/shipper/reports/orders"):
        r = wh.get(p)
        assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-012] WAREHOUSE {p} → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_super_admin_role_gates_013(api):
    """API-RBAC-013: SUPER_ADMIN — свой раздел 200, но /shipper/** → 403 FORBIDDEN (не в office-ролях)."""
    sa = api("super_admin")
    assert sa.get("/super-admin/shipper-companies").status_code == 200, "[API-RBAC-013] свой раздел"
    r = sa.get("/shipper/orders")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-013] super→shipper → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_transport_admin_role_gates_014(api):
    """API-RBAC-014: TRANSPORT_ADMIN — /transport/feed 200, /shipper/** → 403 FORBIDDEN."""
    ta = api("transport_admin")
    assert ta.get("/transport/feed").status_code == 200, "[API-RBAC-014] свой раздел"
    r = ta.get("/shipper/orders")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-014] transport→shipper → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_driver_no_gate_015(driver):
    """API-RBAC-015: DRIVER не допущен ни к shipper/transport/super-admin → 403 FORBIDDEN."""
    d = driver()
    for p in ("/shipper/orders", "/transport/feed", "/super-admin/shipper-companies"):
        r = d.get(p)
        assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-015] DRIVER {p} → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_driver_view_allowed_016(driver, order_factory):
    """API-RBAC-016: DRIVER → POST /orders/{id}/view → 2xx (единственный доменный эндпойнт для водителя)."""
    d = driver()
    o = order_factory.make("PUBLISHED")
    r = d.request("POST", f"/orders/{o['id']}/view")
    assert r.status_code in (200, 204), f"[API-RBAC-016] DRIVER view → {r.status_code}/{_code(r)} {r.text[:120]}"


@pytest.mark.low
@pytest.mark.security
def test_shipper_no_view_017(cap, order_factory):
    """API-RBAC-017: shipper-роль → POST /orders/{id}/view → 403 FORBIDDEN (только TRANSPORT_ADMIN/DRIVER)."""
    op = cap("SHIPPER_OPERATOR")
    o = order_factory.make("PUBLISHED")
    r = op.request("POST", f"/orders/{o['id']}/view")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-017] operator view → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_driver_login_clienttypes_057(dev_api, cfg, driver):
    """API-RBAC-057 (→ MNZL-269): DRIVER входит только TRANSPORT_COMPANY_APP; WEB/WAREHOUSE_APP → wrong-app."""
    d = driver()  # уже вошёл через TRANSPORT_COMPANY_APP в фикстуре (200)
    for ct in ("WEB", "WAREHOUSE_APP"):
        r = dev_api.login(d.phone, cfg.dev_account_password, ct)
        assert r.status_code == 403 and _code(r) == "error.wrong-app", f"[API-RBAC-057] DRIVER {ct} → {r.status_code}/{_code(r)}"
    r = dev_api.login(d.phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")
    assert r.status_code == 200 and r.json().get("accessToken"), "[API-RBAC-057] DRIVER TRANSPORT_COMPANY_APP → 200"


@pytest.mark.high
@pytest.mark.security
def test_transport_gate_sweep_061(api, cap, driver):
    """API-RBAC-061: /transport/** закрыт для office/warehouse/driver → 403 FORBIDDEN."""
    clients = [("MANAGER", cap("SHIPPER_MANAGER")), ("WAREHOUSE", api("shipper_warehouse")), ("DRIVER", driver())]
    for name, c in clients:
        r = c.get("/transport/feed")
        assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-061] {name} → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.security
def test_warehouse_only_methods_063(cap, order_factory):
    """API-RBAC-063: goods-sent/communication раздела склада — только SHIPPER_WAREHOUSE → office → 403 FORBIDDEN."""
    op = cap("SHIPPER_OPERATOR")  # к /warehouse допущен по роли, но методы warehouse-only
    o = order_factory.make("IN_WORK")
    r1 = op.request("POST", f"/warehouse/orders/{o['id']}/goods-sent")
    r2 = op.request("POST", f"/warehouse/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r1.status_code == 403 and _code(r1) == _ROLE_FORB, f"[API-RBAC-063] goods-sent → {r1.status_code}/{_code(r1)}"
    assert r2.status_code == 403 and _code(r2) == _ROLE_FORB, f"[API-RBAC-063] communication → {r2.status_code}/{_code(r2)}"


@pytest.mark.medium
@pytest.mark.security
def test_warehouse_order_detail_warehouse_only_062(s_admin, order_factory):
    """API-RBAC-062: GET /warehouse/orders/{id} (вариант для приложения склада) — только SHIPPER_WAREHOUSE.
    Office-роль (admin) → 403 FORBIDDEN (метод-левел ролевое ограничение поверх класс-гейта)."""
    o = order_factory.make("PUBLISHED")
    r = s_admin.get(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-062] office → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_warehouse_get_no_capability_064(cap):
    """API-RBAC-064: GET раздела склада не гейтится capability → DISPATCHER (без ORDER_ENTRY) → 200."""
    dp = cap("SHIPPER_DISPATCHER")
    assert dp.get("/warehouse/orders").status_code == 200, "[API-RBAC-064] GET /warehouse/orders"
    assert dp.get("/warehouse/orders/summary").status_code == 200, "[API-RBAC-064] GET /warehouse/orders/summary"


@pytest.mark.medium
@pytest.mark.security
def test_super_admin_drivers_gate_095(api, driver):
    """API-RBAC-095: /super-admin/drivers — только SUPER_ADMIN; DRIVER → 403 FORBIDDEN."""
    d = driver()
    r = d.get("/super-admin/drivers")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-095] DRIVER GET → {r.status_code}/{_code(r)}"


# ═══ Метод-гейты capability на разделе грузоотправителя (069–072, 088) ════════


@pytest.mark.low
@pytest.mark.capability
def test_order_review_drivers_069(cap, order_factory):
    """API-RBAC-069: GET /shipper/orders/{id}/drivers требует ORDER_REVIEW — у DISPATCHER есть → 200."""
    dp = cap("SHIPPER_DISPATCHER")
    o = order_factory.make("PUBLISHED")
    assert dp.get(f"/shipper/orders/{o['id']}/drivers").status_code == 200, "[API-RBAC-069]"


@pytest.mark.low
@pytest.mark.capability
def test_order_review_dispatch_log_070(cap, order_factory):
    """API-RBAC-070: GET /shipper/orders/{id}/dispatch-log требует ORDER_REVIEW — у OPERATOR есть → 200."""
    op = cap("SHIPPER_OPERATOR")
    o = order_factory.make("PUBLISHED")
    assert op.get(f"/shipper/orders/{o['id']}/dispatch-log").status_code == 200, "[API-RBAC-070]"


@pytest.mark.medium
@pytest.mark.capability
def test_departures_group_071(cap, order_factory):
    """API-RBAC-071: departures/summary + enter-1c закрыты правом DEPARTURES — OPERATOR без него → 403 error.forbidden."""
    op = cap("SHIPPER_OPERATOR")
    o = order_factory.make("PUBLISHED")
    r1 = op.get("/shipper/departures/summary")
    r2 = op.request("POST", f"/shipper/orders/{o['id']}/enter-1c")
    assert r1.status_code == 403 and _code(r1) == _FORB, f"[API-RBAC-071] summary → {r1.status_code}/{_code(r1)}"
    assert r2.status_code == 403 and _code(r2) == _FORB, f"[API-RBAC-071] enter-1c → {r2.status_code}/{_code(r2)}"


@pytest.mark.medium
@pytest.mark.capability
def test_order_fulfill_group_072(cap, order_factory):
    """API-RBAC-072: republish/communication закрыты правом ORDER_FULFILL — DISPATCHER без него → 403 error.forbidden."""
    dp = cap("SHIPPER_DISPATCHER")
    o = order_factory.make("PUBLISHED")
    _bogus = {"cargoType": "AUTO", "currency": "CNY", "loadDate": "2026-07-23", "vehicleTypeId": str(uuid.uuid4()),
              "driversCount": 1, "fromWarehouseId": str(uuid.uuid4()), "toWarehouseId": str(uuid.uuid4()), "notes": "x"}
    r1 = dp.request("POST", f"/shipper/orders/{o['id']}/republish", json=_bogus)
    r2 = dp.request("POST", f"/shipper/orders/{o['id']}/communication", json={"status": "CONFIRMED"})
    assert r1.status_code == 403 and _code(r1) == _FORB, f"[API-RBAC-072] republish → {r1.status_code}/{_code(r1)}"
    assert r2.status_code == 403 and _code(r2) == _FORB, f"[API-RBAC-072] communication → {r2.status_code}/{_code(r2)}"


@pytest.mark.medium
@pytest.mark.capability
def test_reports_class_gate_088(cap):
    """API-RBAC-088: весь блок отчётов закрыт правом REPORTS — MANAGER без него → 403 error.forbidden (3 эндпойнта)."""
    m = cap("SHIPPER_MANAGER")
    for p in ("/shipper/reports/orders", "/shipper/reports/companies", "/shipper/dashboard/stats"):
        r = m.get(p)
        assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-088] {p} → {r.status_code}/{_code(r)}"


# ═══ Tenancy / BOLA → 404 (041, 046, 073, 090, 092) ═══════════════════════════


@pytest.mark.high
@pytest.mark.tenancy
def test_staff_foreign_404_041(s_admin, fresh_company, pwd, dev_api, cfg):
    """API-RBAC-041: PATCH чужого сотрудника → 404 error.employee.not-found (скрытие существования)."""
    co = fresh_company()
    bphone = "+99890" + _d(7)
    bsid = co.admin.post("/shipper/staff", json={"fullName": "AT B Staff", "phone": bphone, "password": pwd, "role": "SHIPPER_OPERATOR"}).json()["id"]
    r = s_admin.patch(f"/shipper/staff/{bsid}", json={"fullName": "AT X", "phone": bphone, "role": "SHIPPER_OPERATOR"})
    assert r.status_code == 404 and _code(r) == "error.employee.not-found", f"[API-RBAC-041] → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_company_scope_046(s_admin, fresh_company):
    """API-RBAC-046: shipper A → /super-admin/{B} → 403 FORBIDDEN (раздел super-admin); своя компания — из токена."""
    co = fresh_company()
    r = s_admin.get(f"/super-admin/shipper-companies/{co.id}")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-046] shipper→super-admin → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_tender_select_foreign_073(cap, fresh_company):
    """API-RBAC-073: TENDER_SELECT есть, но чужой заказ → 404 (tenancy-скоуп прячет чужой ресурс)."""
    m = cap("SHIPPER_MANAGER", grants=["TENDER_SELECT", "SEE_PRICES"])
    co = fresh_company()
    o = co.make("QUOTED")
    r = m.request("POST", f"/shipper/orders/{o['id']}/offers/{uuid.uuid4()}/select")
    assert r.status_code == 404 and _code(r) in ("error.order.not-found", "error.offer.not-found"), f"[API-RBAC-073] → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_transport_feed_foreign_090(api, fresh_company):
    """API-RBAC-090: TRANSPORT_ADMIN → чужой/невидимый заказ фида → 404 error.order.not-found."""
    r = api("transport_admin").get(f"/transport/feed/{random.randint(900000000, 999999999)}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-RBAC-090] недоступный/несуществующий заказ фида → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_warehouse_foreign_order_092(api, fresh_company):
    """API-RBAC-092: SHIPPER_WAREHOUSE компании A → заказ компании B → 404 error.order.not-found."""
    wh = api("shipper_warehouse")
    co = fresh_company()
    o = co.make("PUBLISHED")
    r = wh.get(f"/warehouse/orders/{o['id']}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-RBAC-092] → {r.status_code}/{_code(r)}"


# ═══ Auth-edge (049, 051, 052) ════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.security
def test_deactivated_user_401_049(s_admin, dev_api, pwd):
    """API-RBAC-049: деактивированный юзер со свежим токеном → /me → 401 error.unauthorized."""
    phone = "+99890" + _d(7)
    sid = s_admin.post("/shipper/staff", json={"fullName": "AT Deact", "phone": phone, "password": pwd, "role": "SHIPPER_OPERATOR"}).json()["id"]
    tok = dev_api.login(phone, pwd, "WEB").json()["accessToken"]
    s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Deact", "phone": phone, "role": "SHIPPER_OPERATOR", "active": False})
    r = dev_api.request("GET", "/me", tok)
    assert r.status_code == 401 and _code(r) == "error.unauthorized", f"[API-RBAC-049] → {r.status_code}/{_code(r)}"
    s_admin.delete(f"/shipper/staff/{sid}")


@pytest.mark.high
@pytest.mark.security
@pytest.mark.tenancy
def test_blocked_company_403_051(dev_api, cfg, fresh_company):
    """API-RBAC-051: компания заблокирована (active=false) → 403 error.company.blocked тем же токеном."""
    co = fresh_company()
    # свежий токен админа компании B
    tok = co.admin.token
    assert dev_api.request("GET", "/shipper/orders", tok).status_code == 200, "[API-RBAC-051] до блокировки 200"
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    # заблокировать компанию через PATCH active=false (нужно полное тело)
    cur = dev_api.request("GET", f"/super-admin/shipper-companies/{co.id}", sa).json()
    dev_api.request("PATCH", f"/super-admin/shipper-companies/{co.id}", sa, json={
        "name": cur["name"], "prefix": cur["prefix"], "tin": cur["tin"], "address": cur.get("address") or _ADDR,
        "active": False, "admin": {"fullName": cur["adminFullName"], "phone": cur["adminPhone"]}})
    r = dev_api.request("GET", "/shipper/orders", tok)
    assert r.status_code == 403 and _code(r) == "error.company.blocked", f"[API-RBAC-051] → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_refresh_deactivated_052(s_admin, dev_api, pwd):
    """API-RBAC-052: refresh деактивированного аккаунта → 401 error.invalid-credentials (сессия завершается)."""
    phone = "+99890" + _d(7)
    sid = s_admin.post("/shipper/staff", json={"fullName": "AT R", "phone": phone, "password": pwd, "role": "SHIPPER_OPERATOR"}).json()["id"]
    login = dev_api.login(phone, pwd, "WEB").json()
    s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT R", "phone": phone, "role": "SHIPPER_OPERATOR", "active": False})
    r = dev_api.refresh(login["refreshToken"])
    assert r.status_code == 401 and _code(r) == "error.invalid-credentials", f"[API-RBAC-052] → {r.status_code}/{_code(r)}"
    s_admin.delete(f"/shipper/staff/{sid}")


# ═══ Сводные линтеры кода отказа (075, 076, 077, 078, 084, 086, 087) ══════════


@pytest.mark.high
@pytest.mark.security
def test_dual_code_one_url_076(api, cap):
    """API-RBAC-076: один URL /shipper/reports/orders — WAREHOUSE → FORBIDDEN (роль), OPERATOR → error.forbidden (право)."""
    r_role = api("shipper_warehouse").get("/shipper/reports/orders")
    r_cap = cap("SHIPPER_OPERATOR").get("/shipper/reports/orders")
    assert r_role.status_code == 403 and _code(r_role) == _ROLE_FORB, f"[API-RBAC-076] WAREHOUSE → {r_role.status_code}/{_code(r_role)}"
    assert r_cap.status_code == 403 and _code(r_cap) == _FORB, f"[API-RBAC-076] OPERATOR → {r_cap.status_code}/{_code(r_cap)}"


@pytest.mark.medium
@pytest.mark.security
def test_gate_order_role_first_077(api, fresh_company):
    """API-RBAC-077: роль → право → tenancy; WAREHOUSE на чужой DELETE order — отказ на РОЛИ (FORBIDDEN), до tenancy-404."""
    wh = api("shipper_warehouse")  # не в /shipper-гейте
    co = fresh_company()
    o = co.make("PUBLISHED")
    r = wh.request("DELETE", f"/shipper/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-077] → {r.status_code}/{_code(r)} (роль раньше tenancy)"


@pytest.mark.medium
@pytest.mark.capability
def test_method_level_precedence_078(cap, order_factory):
    """API-RBAC-078: внутри раздела права точечные — OPERATOR: orders 200, departures 403, delete 403."""
    op = cap("SHIPPER_OPERATOR")
    o = order_factory.make("PUBLISHED")
    assert op.get("/shipper/orders").status_code == 200, "[API-RBAC-078] ORDER_REVIEW есть"
    assert op.get("/shipper/departures?tab=IN_TRANSIT").status_code == 403 and _code(op.get("/shipper/departures?tab=IN_TRANSIT")) == _FORB, "[API-RBAC-078] нет DEPARTURES"
    r = op.request("DELETE", f"/shipper/orders/{o['id']}")
    assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-078] нет ORDER_DELETE → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.security
def test_clienttype_spoof_084(dev_api, cfg, api):
    """API-RBAC-084: clientType — UX-guard логина, не security-граница. WAREHOUSE-токен → /shipper/** → 403 FORBIDDEN."""
    wh = api("shipper_warehouse")
    r = wh.get("/shipper/orders")
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-084] warehouse-токен на shipper → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.security
def test_all_capability_gates_error_forbidden_086(cap, order_factory):
    """API-RBAC-086 (линтер): КАЖДЫЙ capability-гейт при отсутствии права → error.forbidden (не FORBIDDEN).
    Отклонение = потенциальный баг-конвенции (эскалировать, не синхронизировать молча)."""
    op = cap("SHIPPER_OPERATOR")  # нет DEPARTURES/REPORTS/TENDER_SELECT/SEE_PRICES/ORDER_DELETE/WH_DIR_WRITE/BLACKLIST/SMS_*
    o = order_factory.make("PUBLISHED")
    gated = [
        ("GET", f"/shipper/orders/{o['id']}/offers", None),        # SEE_PRICES
        ("POST", f"/shipper/orders/{o['id']}/sms", None),          # SMS_BLAST
        ("GET", "/shipper/sms-logs", None),                        # SMS_JOURNAL
        ("GET", "/shipper/departures?tab=IN_TRANSIT", None),       # DEPARTURES
        ("GET", "/shipper/reports/orders", None),                  # REPORTS
        ("DELETE", f"/shipper/orders/{o['id']}", None),            # ORDER_DELETE
        ("GET", "/shipper/blacklist", None),                       # BLACKLIST
    ]
    bad = []
    for m, p, b in gated:
        r = op.request(m, p, json=b) if b else op.request(m, p)
        if not (r.status_code == 403 and _code(r) == _FORB):
            bad.append(f"{m} {p} → {r.status_code}/{_code(r)}")
    assert not bad, f"[API-RBAC-086] capability-гейты с НЕ error.forbidden (конвенция нарушена): {bad}"


@pytest.mark.high
@pytest.mark.security
def test_all_role_gates_forbidden_087(api, cap, driver):
    """API-RBAC-087 (линтер): КАЖДЫЙ ролевой гейт при недопущенной роли → FORBIDDEN (не error.forbidden).
    Отклонение = потенциальный баг-конвенции (эскалировать, не синхронизировать молча)."""
    wh, ta, sa, d = api("shipper_warehouse"), api("transport_admin"), api("super_admin"), driver()
    cases = [
        (wh, "GET", "/shipper/orders"),          # warehouse → shipper
        (ta, "GET", "/shipper/orders"),          # transport → shipper
        (sa, "GET", "/shipper/orders"),          # super → shipper
        (cap("SHIPPER_MANAGER"), "GET", "/transport/feed"),  # office → transport
        (d, "GET", "/transport/feed"),           # driver → transport
        (wh, "GET", "/super-admin/shipper-companies"),  # warehouse → super
    ]
    bad = []
    for c, m, p in cases:
        r = c.request(m, p)
        if not (r.status_code == 403 and _code(r) == _ROLE_FORB):
            bad.append(f"{p} → {r.status_code}/{_code(r)}")
    assert not bad, f"[API-RBAC-087] ролевые гейты с НЕ FORBIDDEN (конвенция нарушена): {bad}"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.security
def test_fail_closed_admin_075(s_admin, order_factory):
    """API-RBAC-075 (линтер fail-closed): SHIPPER_ADMIN с полным набором прав НЕ должен ловить 403 error.forbidden
    ни на одном capability-гейте (иначе гейт подключён неверно — не видит пользователя)."""
    o = order_factory.make("PUBLISHED")
    endpoints = [
        ("GET", "/shipper/orders"), ("GET", "/shipper/warehouses"), ("GET", "/shipper/reports/orders"),
        ("GET", "/shipper/reports/companies"), ("GET", "/shipper/dashboard/stats"),
        ("GET", "/shipper/departures?tab=IN_TRANSIT"), ("GET", "/shipper/departures/summary"),
        ("GET", f"/shipper/orders/{o['id']}/offers"), ("GET", "/shipper/sms-logs"),
        ("GET", f"/shipper/orders/{o['id']}/drivers"), ("GET", f"/shipper/orders/{o['id']}/dispatch-log"),
        ("GET", "/shipper/blacklist"),
    ]
    bad = []
    for m, p in endpoints:
        r = s_admin.request(m, p)
        if r.status_code == 403 and _code(r) == _FORB:
            bad.append(f"{m} {p}")
    assert not bad, f"[API-RBAC-075] админ поймал error.forbidden (fail-closed дефект подключения гейта): {bad}"
