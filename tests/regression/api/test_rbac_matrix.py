"""API — RBAC capability-матрица + живые гранты/отзыв (07_rbac_capabilities.json).

Два независимых гейта на каждом запросе:
1. Ролевой (класс-левел @PreAuthorize hasAnyRole) — отказ → HTTP 403 code=FORBIDDEN.
2. Capability (@RequiresCapability, CapabilityAspect) — отказ → HTTP 403 code=error.forbidden.
Гранты НЕ в JWT: effectiveCapabilities = defaults(role) ∪ granted читаются из БД на КАЖДЫЙ
запрос (CapabilityDirectory) — выдача/отзыв действуют мгновенно тем же токеном. Роль тоже
грузится из БД (@CurrentUser), поэтому смена роли меняет capability-дефолты СРАЗУ, без релогина
(RBAC-080 уточнён по факту); релогин нужен лишь ролевому @PreAuthorize-гейту секции (роль в JWT).

Порядок на POST/PATCH-эндпойнте: @Valid тела (400 BAD_REQUEST) → ролевой гейт/capability
(403) → сервис (400/404 по ресурсу). Проверено на dev: невалидное тело даёт 400 РАНЬШЕ
capability-гейта, структурно-валидное «пустышка»-тело — 403 (capability до резолва ресурса).
Поэтому негативы capability шлют структурно-валидное bogus-тело.

Дефолты (RoleCapabilityDefaults): ADMIN=все 13; MANAGER={ORDER_REVIEW,ORDER_FULFILL,DEPARTURES,
SMS_BLAST,SMS_JOURNAL,WH_DIR_READ}; OPERATOR={ORDER_REVIEW,ORDER_FULFILL,ORDER_ENTRY,WH_DIR_READ};
DISPATCHER={ORDER_REVIEW,DEPARTURES,SMS_BLAST,SMS_JOURNAL,WH_DIR_READ}; WAREHOUSE={ORDER_ENTRY}.
Admin-only-grantable: TENDER_SELECT,REPORTS,WH_DIR_WRITE,ORDER_DELETE,BLACKLIST,SEE_PRICES.

Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import datetime
import random
import string
import uuid

import pytest

from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.rbac]

# ═══ Кросс-кредит: RBAC-кейсы, уже покрытые существующими тестами (см. CLAUDE.md) ═══
# Полное совпадение контракта (роль×эндпойнт×код×capability) — вторая ID-метка, без дубля кода.
# coverage_map считает эти API-RBAC-0XX как покрытые по регулярке.
#   API-RBAC-001 → INT-066 (ролевой отказ → FORBIDDEN)
#   API-RBAC-002 → INT-064 (capability-отказ → error.forbidden)
#   API-RBAC-022 → INT-064 + INT-068 (SMS_BLAST: нет→403 / +грант→204)
#   API-RBAC-023 → INT-076 + INT-077 (SMS_JOURNAL: нет→403 / +грант→200)
#   API-RBAC-025 → TND-066 (TENDER_SELECT: select без гранта→403)
#   API-RBAC-028 → SHP-016 (грант ORDER_DELETE в granted/effective)
#   API-RBAC-029 → INT-136 + INT-137 (BLACKLIST: нет→403 / +грант→201)
#   API-RBAC-030 → TND-052 (SEE_PRICES: список офферов без права → цена скрыта)
#   API-RBAC-031 → TND-053 (SEE_PRICES: +грант → цена видна)
#   API-RBAC-038 → SHP-023 + SHP-032 (роль вне STAFF_ROLES → 400 error.invalid-role)
#   API-RBAC-042 → test_orders_tenancy_053 (чужой заказ → 404 error.order.not-found)
#   API-RBAC-043 → TND-022 (чужой оффер → 404 error.offer.not-found)
#   API-RBAC-044 → TND-095 (чужой водитель → 404 error.driver.not-found)
#   API-RBAC-045 → SHP-157 (чужой склад → 403 = BUG-036/MNZL-276)
#   API-RBAC-047 → AUTH-079 (нет токена → 401)
#   API-RBAC-048 → AUTH-080 (протухший/битый bearer → 401)
#   API-RBAC-053 → AUTH test_login_positive (WEB-матрица ролей)
#   API-RBAC-054 → AUTH test_login_wrong_app (WAREHOUSE в WEB → wrong-app)
#   API-RBAC-055 → AUTH login (WAREHOUSE_APP только склад)
#   API-RBAC-056 → AUTH login (TRANSPORT_COMPANY_APP только транспорт)
#   API-RBAC-058 → AUTH test_login_wrong_app (wrong-app только после верных кредов)
#   API-RBAC-059 → INT-108/111/124 (CN/KG запись только SUPER_ADMIN → 403 FORBIDDEN)
#   API-RBAC-060 → SA-158/159 (не-супер → 403 FORBIDDEN на /super-admin/**)
#   API-RBAC-065 → INT-057 + INT-058 (files: без токена→401 / любая роль→201)
#   API-RBAC-066 → AUTH /me + devices (self-эндпойнты — только аутентификация)
#   API-RBAC-068 → INT-003/004/005/006 (1C X-Webhook-Token негативы → 401)
#   API-RBAC-074 → AUTH-065 (super_admin effectiveCapabilities == [])
#   API-RBAC-082 → AUTH /me admin (полный набор capability роли)
#   API-RBAC-085 → INT-083 + INT-095 (общие справочники: без токена → 401; читаются любой ролью)
#   API-RBAC-089 → AUTH ratelimit/iplimit (брутфорс-лимитер логина)
#   API-RBAC-091 → INT-147 (delete чужой записи ЧС → 404 error.blacklist.not-found)
#   API-RBAC-094 → WH-001 (SHIPPER_WAREHOUSE проходит роль + ORDER_ENTRY → create 2xx)

_FORB = "error.forbidden"    # capability-отказ
_ROLE_FORB = "FORBIDDEN"     # ролевой отказ


def _d(n):
    return "".join(random.choices(string.digits, k=n))


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _bogus_wh_order():
    """Структурно-валидное тело warehouse-заказа со случайными UUID-ref — проходит @Valid,
    но падает на сервисе (400/404). Для проверки capability-гейта (403 до резолва ресурса)."""
    return {"cargoType": "AUTO", "currency": "CNY", "loadDate": datetime.date.today().isoformat(),
            "vehicleTypeId": str(uuid.uuid4()), "driversCount": 1,
            "fromWarehouseId": str(uuid.uuid4()), "toWarehouseId": str(uuid.uuid4()), "notes": "AT rbac"}


def _bogus_wh_dir():
    """Структурно-валидное тело склада-справочника с несуществующей division — проходит @Valid."""
    return {"divisionCountry": "CN", "divisionCode": "000000", "name": f"AT-WH-{_d(5)}", "address": "No. 1 Test Rd"}


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def refs(order_factory):
    """(vehicleTypeId, fromWarehouseId, toWarehouseId) компании A — для реальных create-позитивов."""
    vt, locs = order_factory._ensure_refs()
    return vt, locs[0], locs[1]


@pytest.fixture
def valid_wh_order(refs):
    vt, frm, to = refs
    def _mk():
        return {"cargoType": "AUTO", "currency": "CNY", "loadDate": datetime.date.today().isoformat(),
                "vehicleTypeId": vt, "driversCount": 1, "fromWarehouseId": frm, "toWarehouseId": to, "notes": "AT rbac"}
    return _mk


@pytest.fixture
def cleanup(s_admin):
    """Удалить созданные в позитивах ресурсы (заказы/склады) в teardown."""
    trash = []  # (path,) под админом компании A
    yield trash
    for path in reversed(trash):
        try:
            s_admin.delete(path)
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def cap(s_admin, dev_api, pwd):
    """staff(role) с опц. грантами; объект несёт staff_id/phone для live-grant."""
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


def _staff_row(s_admin, sid):
    """StaffResponse из списка (одиночного GET /staff/{id} нет)."""
    rows = s_admin.get("/shipper/staff?size=200").json()
    rows = rows.get("content", rows) if isinstance(rows, dict) else rows
    return next((x for x in rows if x.get("id") == sid), {})


def _regrant(s_admin, c, role, caps):
    return s_admin.patch(f"/shipper/staff/{c.staff_id}", json={"fullName": "AT Cap", "phone": c.phone, "role": role, "capabilities": caps})


# ═══ Матрица роль × дефолтные capability (004–011) ════════════════════════════


@pytest.mark.high
@pytest.mark.capability
def test_admin_all_caps_004(s_admin, order_factory):
    """API-RBAC-004: SHIPPER_ADMIN имеет ALL — ни один capability-гейт не даёт 403."""
    o = order_factory.make("PUBLISHED")
    for m, p in [("GET", "/shipper/orders"), ("GET", "/shipper/warehouses"), ("GET", "/shipper/reports/orders"),
                 ("GET", "/shipper/departures?tab=IN_TRANSIT"), ("GET", f"/shipper/orders/{o['id']}/offers"), ("GET", "/shipper/sms-logs")]:
        r = s_admin.request(m, p)
        assert r.status_code == 200, f"[API-RBAC-004] {m} {p} → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_manager_defaults_005(cap):
    """API-RBAC-005: MANAGER-дефолты (ORDER_REVIEW, DEPARTURES, SMS_JOURNAL, WH_DIR_READ) → 200."""
    m = cap("SHIPPER_MANAGER")
    for p in ("/shipper/orders", "/shipper/departures?tab=IN_TRANSIT", "/shipper/sms-logs", "/shipper/warehouses"):
        assert m.get(p).status_code == 200, f"[API-RBAC-005] MANAGER {p} должен быть 200"


@pytest.mark.high
@pytest.mark.capability
def test_manager_missing_caps_006(cap, order_factory):
    """API-RBAC-006: MANAGER без SEE_PRICES/REPORTS/ORDER_ENTRY/WH_DIR_WRITE/ORDER_DELETE/BLACKLIST → 403 error.forbidden."""
    m = cap("SHIPPER_MANAGER")
    o = order_factory.make("PUBLISHED")
    checks = [
        m.request("GET", f"/shipper/orders/{o['id']}/offers"),        # SEE_PRICES
        m.request("GET", "/shipper/reports/orders"),                   # REPORTS
        m.request("POST", "/warehouse/orders", json=_bogus_wh_order()),  # ORDER_ENTRY
        m.request("POST", "/shipper/warehouses", json=_bogus_wh_dir()),  # WH_DIR_WRITE
        m.request("DELETE", f"/shipper/orders/{o['id']}"),             # ORDER_DELETE
        m.request("GET", "/shipper/blacklist"),                        # BLACKLIST
    ]
    for r in checks:
        assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-006] {r.request.method} {r.request.path_url} → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_operator_defaults_007(cap, valid_wh_order, cleanup):
    """API-RBAC-007: OPERATOR-дефолты — ORDER_ENTRY есть (единственная office-роль с ним по умолчанию) → create 2xx."""
    op = cap("SHIPPER_OPERATOR")
    assert op.get("/shipper/orders").status_code == 200, "[API-RBAC-007] ORDER_REVIEW"
    assert op.get("/shipper/warehouses").status_code == 200, "[API-RBAC-007] WH_DIR_READ"
    r = op.request("POST", "/warehouse/orders", json=valid_wh_order())
    assert r.status_code in (200, 201), f"[API-RBAC-007] OPERATOR ORDER_ENTRY create → {r.status_code}/{_code(r)}"
    cleanup.append(f"/shipper/orders/{r.json()['id']}")


@pytest.mark.medium
@pytest.mark.capability
def test_operator_missing_caps_008(cap):
    """API-RBAC-008: OPERATOR без DEPARTURES/SMS_JOURNAL → 403 error.forbidden."""
    op = cap("SHIPPER_OPERATOR")
    for p in ("/shipper/departures?tab=IN_TRANSIT", "/shipper/sms-logs"):
        r = op.get(p)
        assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-008] OPERATOR {p} → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_dispatcher_defaults_009(cap):
    """API-RBAC-009: DISPATCHER-дефолты (ORDER_REVIEW, DEPARTURES, SMS_JOURNAL, WH_DIR_READ) → 200."""
    dp = cap("SHIPPER_DISPATCHER")
    for p in ("/shipper/orders", "/shipper/departures?tab=IN_TRANSIT", "/shipper/sms-logs", "/shipper/warehouses"):
        assert dp.get(p).status_code == 200, f"[API-RBAC-009] DISPATCHER {p} должен быть 200"


@pytest.mark.medium
@pytest.mark.capability
def test_dispatcher_missing_caps_010(cap):
    """API-RBAC-010: DISPATCHER без ORDER_FULFILL и ORDER_ENTRY → 403 error.forbidden."""
    dp = cap("SHIPPER_DISPATCHER")
    r1 = dp.request("POST", f"/shipper/orders/{uuid.uuid4().int % 100000}/complete")  # ORDER_FULFILL (числовой id)
    r2 = dp.request("POST", "/warehouse/orders", json=_bogus_wh_order())               # ORDER_ENTRY
    assert r1.status_code == 403 and _code(r1) == _FORB, f"[API-RBAC-010] complete → {r1.status_code}/{_code(r1)}"
    assert r2.status_code == 403 and _code(r2) == _FORB, f"[API-RBAC-010] warehouse/orders → {r2.status_code}/{_code(r2)}"


@pytest.mark.high
@pytest.mark.capability
def test_warehouse_order_entry_011(api, valid_wh_order, s_admin, cleanup):
    """API-RBAC-011: SHIPPER_WAREHOUSE={ORDER_ENTRY} → создание warehouse-заказа 2xx."""
    wh = api("shipper_warehouse")
    r = wh.request("POST", "/warehouse/orders", json=valid_wh_order())
    assert r.status_code in (200, 201), f"[API-RBAC-011] WAREHOUSE ORDER_ENTRY create → {r.status_code}/{_code(r)}"
    cleanup.append(f"/shipper/orders/{r.json()['id']}")


# ═══ Одиночная capability: нет → 403, +грант → 2xx (018–027) ══════════════════


@pytest.mark.medium
@pytest.mark.capability
def test_order_review_all_office_018(cap):
    """API-RBAC-018: ORDER_REVIEW в дефолте всех office-ролей → GET /shipper/orders 200."""
    for role in ("SHIPPER_MANAGER", "SHIPPER_OPERATOR", "SHIPPER_DISPATCHER"):
        assert cap(role).get("/shipper/orders").status_code == 200, f"[API-RBAC-018] {role}"


@pytest.mark.high
@pytest.mark.capability
def test_order_fulfill_grant_019(cap, s_admin, order_factory):
    """API-RBAC-019: DISPATCHER без ORDER_FULFILL → 403; +грант → complete 2xx (тем же токеном)."""
    dp = cap("SHIPPER_DISPATCHER")
    o = order_factory.make("IN_TRANSIT")
    assert dp.request("POST", f"/shipper/orders/{o['id']}/complete").status_code == 403, "[API-RBAC-019] без гранта"
    _regrant(s_admin, dp, "SHIPPER_DISPATCHER", ["ORDER_FULFILL"])
    r = dp.request("POST", f"/shipper/orders/{o['id']}/complete")
    assert r.status_code in (200, 204), f"[API-RBAC-019] +ORDER_FULFILL → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_order_entry_grant_020(cap, s_admin, valid_wh_order, cleanup):
    """API-RBAC-020: MANAGER без ORDER_ENTRY → 403; +грант → create warehouse-заказа 2xx."""
    m = cap("SHIPPER_MANAGER")
    assert m.request("POST", "/warehouse/orders", json=_bogus_wh_order()).status_code == 403, "[API-RBAC-020] без гранта"
    _regrant(s_admin, m, "SHIPPER_MANAGER", ["ORDER_ENTRY"])
    r = m.request("POST", "/warehouse/orders", json=valid_wh_order())
    assert r.status_code in (200, 201), f"[API-RBAC-020] +ORDER_ENTRY create → {r.status_code}/{_code(r)}"
    cleanup.append(f"/shipper/orders/{r.json()['id']}")


@pytest.mark.high
@pytest.mark.capability
def test_departures_grant_021(cap, s_admin):
    """API-RBAC-021: OPERATOR без DEPARTURES → 403; +грант → GET /shipper/departures 200."""
    op = cap("SHIPPER_OPERATOR")
    assert op.get("/shipper/departures?tab=IN_TRANSIT").status_code == 403, "[API-RBAC-021] без гранта"
    _regrant(s_admin, op, "SHIPPER_OPERATOR", ["DEPARTURES"])
    assert op.get("/shipper/departures?tab=IN_TRANSIT").status_code == 200, "[API-RBAC-021] +DEPARTURES"


@pytest.mark.high
@pytest.mark.capability
def test_reports_grant_024(cap, s_admin):
    """API-RBAC-024: DISPATCHER без REPORTS → 403; +грант → reports/orders + dashboard/stats 200."""
    dp = cap("SHIPPER_DISPATCHER")
    assert dp.get("/shipper/reports/orders").status_code == 403, "[API-RBAC-024] без гранта"
    _regrant(s_admin, dp, "SHIPPER_DISPATCHER", ["REPORTS"])
    assert dp.get("/shipper/reports/orders").status_code == 200, "[API-RBAC-024] reports/orders"
    assert dp.get("/shipper/dashboard/stats").status_code == 200, "[API-RBAC-024] dashboard/stats (тот же класс-гейт REPORTS)"


@pytest.mark.low
@pytest.mark.capability
def test_wh_dir_read_all_office_026(cap):
    """API-RBAC-026: WAREHOUSE_DIRECTORY_READ в дефолте всех office-ролей → GET /shipper/warehouses 200."""
    assert cap("SHIPPER_DISPATCHER").get("/shipper/warehouses").status_code == 200, "[API-RBAC-026]"


@pytest.mark.high
@pytest.mark.capability
def test_wh_dir_write_grant_027(cap, s_admin, order_factory, cleanup):
    """API-RBAC-027: OPERATOR без WH_DIR_WRITE → 403; +грант → POST /shipper/warehouses 2xx."""
    op = cap("SHIPPER_OPERATOR")
    assert op.request("POST", "/shipper/warehouses", json=_bogus_wh_dir()).status_code == 403, "[API-RBAC-027] без гранта"
    _regrant(s_admin, op, "SHIPPER_OPERATOR", ["WAREHOUSE_DIRECTORY_WRITE"])
    # реальная division компании A (из refs фабрики нельзя — берём известный CN-код)
    vt, locs = order_factory._ensure_refs()
    body = {"divisionCountry": "CN", "divisionCode": "330782", "name": f"AT-WH-{_d(5)}", "address": "No. 12 Test Rd"}
    r = op.request("POST", "/shipper/warehouses", json=body)
    assert r.status_code in (200, 201), f"[API-RBAC-027] +WH_DIR_WRITE → {r.status_code}/{_code(r)} {r.text[:120]}"
    cleanup.append(f"/shipper/warehouses/{r.json()['id']}")


# ═══ SEE_PRICES фильтр (032) ══════════════════════════════════════════════════


@pytest.mark.medium
@pytest.mark.capability
def test_see_prices_departures_filter_032(cap):
    """API-RBAC-032: DISPATCHER (DEPARTURES есть) без SEE_PRICES + priceMin/priceMax → 403 error.forbidden."""
    dp = cap("SHIPPER_DISPATCHER")
    r = dp.get("/shipper/departures?tab=IN_TRANSIT&priceMin=1&priceMax=999999")
    assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-032] price-фильтр без SEE_PRICES → {r.status_code}/{_code(r)}"
    assert dp.get("/shipper/departures?tab=IN_TRANSIT").status_code == 200, "[API-RBAC-032] без price-фильтра список открыт"


# ═══ /me effectiveCapabilities (033) ══════════════════════════════════════════


@pytest.mark.medium
@pytest.mark.capability
def test_me_effective_caps_033(cap):
    """API-RBAC-033: /me effectiveCapabilities = defaults(OPERATOR) ∪ {REPORTS-грант}."""
    op = cap("SHIPPER_OPERATOR", grants=["REPORTS"])
    caps = set(op.get("/me").json().get("effectiveCapabilities") or [])
    assert {"ORDER_REVIEW", "ORDER_FULFILL", "ORDER_ENTRY", "WAREHOUSE_DIRECTORY_READ"} <= caps, f"[API-RBAC-033] нет дефолтов OPERATOR: {caps}"
    assert "REPORTS" in caps, f"[API-RBAC-033] грант REPORTS не отражён: {caps}"


# ═══ Живые гранты/отзыв — JWT-less, из БД каждый запрос (034, 035) ═════════════


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.security
def test_revoke_live_034(cap, s_admin):
    """API-RBAC-034 ⭐: отзыв REPORTS действует НЕМЕДЛЕННО тем же токеном (гранты не в JWT, читаются из БД)."""
    dp = cap("SHIPPER_DISPATCHER", grants=["REPORTS"])
    assert dp.get("/shipper/reports/orders").status_code == 200, "[API-RBAC-034] шаг 1: с грантом 200"
    _regrant(s_admin, dp, "SHIPPER_DISPATCHER", [])  # отзыв
    r = dp.get("/shipper/reports/orders")
    assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-034] после отзыва тем же токеном → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_grant_live_035(cap, s_admin, order_factory):
    """API-RBAC-035: выдача ORDER_FULFILL действует немедленно тем же токеном (без релогина)."""
    dp = cap("SHIPPER_DISPATCHER")
    o = order_factory.make("IN_TRANSIT")
    assert dp.request("POST", f"/shipper/orders/{o['id']}/complete").status_code == 403, "[API-RBAC-035] шаг 1: без права 403"
    _regrant(s_admin, dp, "SHIPPER_DISPATCHER", ["ORDER_FULFILL"])
    r = dp.request("POST", f"/shipper/orders/{o['id']}/complete")
    assert r.status_code in (200, 204), f"[API-RBAC-035] сразу после гранта → {r.status_code}/{_code(r)}"


# ═══ Нормализация грантов / эскалация (037, 039, 040, 080, 081) ═══════════════


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.security
def test_grant_normalization_037(s_admin, pwd):
    """API-RBAC-037: только capability сверх дефолта роли пишутся в granted; дефолтные отбрасываются."""
    phone = "+99890" + _d(7)
    sid = s_admin.post("/shipper/staff", json={"fullName": "AT Norm", "phone": phone, "password": pwd, "role": "SHIPPER_OPERATOR"}).json()["id"]
    try:
        s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Norm", "phone": phone, "role": "SHIPPER_OPERATOR", "capabilities": ["ORDER_REVIEW", "REPORTS"]})
        st = _staff_row(s_admin, sid)
        granted = set(st.get("grantedCapabilities") or [])
        eff = set(st.get("effectiveCapabilities") or [])
        assert granted == {"REPORTS"}, f"[API-RBAC-037] granted = {{REPORTS}} (ORDER_REVIEW дефолтный, отброшен): {granted}"
        assert "REPORTS" in eff and "ORDER_REVIEW" in eff, f"[API-RBAC-037] effective = дефолт ∪ REPORTS: {eff}"
    finally:
        s_admin.delete(f"/shipper/staff/{sid}")


@pytest.mark.high
@pytest.mark.security
def test_non_admin_no_staff_mgmt_039(cap, pwd):
    """API-RBAC-039: не-админ office-роль не управляет персоналом → 403 FORBIDDEN (ролевой гейт)."""
    m = cap("SHIPPER_MANAGER")
    r = m.request("POST", "/shipper/staff", json={"fullName": "AT X", "phone": "+99890" + _d(7), "password": pwd, "role": "SHIPPER_OPERATOR"})
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-039] POST staff менеджером → {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.security
def test_no_self_service_040(cap):
    """API-RBAC-040: сотрудник не может менять свою роль/гранты сам → PATCH staff → 403 FORBIDDEN."""
    op = cap("SHIPPER_OPERATOR")
    r = op.request("PATCH", f"/shipper/staff/{op.staff_id}", json={"fullName": "AT X", "phone": op.phone, "role": "SHIPPER_ADMIN", "capabilities": ["REPORTS"]})
    assert r.status_code == 403 and _code(r) == _ROLE_FORB, f"[API-RBAC-040] self-PATCH → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.security
def test_role_change_live_capabilities_080(cap, s_admin):
    """API-RBAC-080: смена роли отражается в дефолтном наборе capability НЕМЕДЛЕННО тем же токеном.
    Уточнено по факту: caller.getRole() грузится из БД (@CurrentUser), не из JWT — поэтому смена
    роли OPERATOR→DISPATCHER мгновенно убирает ORDER_ENTRY (403), без релогина. (Прежний expected
    «нужен релогин» неверен: роль читается из БД, как и гранты. Ролевой @PreAuthorize-гейт секции
    по-прежнему берёт роль из JWT — но capability-дефолты живут из БД.)"""
    op = cap("SHIPPER_OPERATOR")  # ORDER_ENTRY по дефолту
    assert op.request("POST", "/warehouse/orders", json=_bogus_wh_order()).status_code != 403, "[API-RBAC-080] OPERATOR имеет ORDER_ENTRY (гейт пройден)"
    assert op.get("/me").json().get("role") == "SHIPPER_OPERATOR", "[API-RBAC-080] исходная роль OPERATOR"
    s_admin.patch(f"/shipper/staff/{op.staff_id}", json={"fullName": "AT Cap", "phone": op.phone, "role": "SHIPPER_DISPATCHER"})
    # тот же токен: роль и дефолтные capability уже DISPATCHER (нет ORDER_ENTRY) → 403 error.forbidden
    assert op.get("/me").json().get("role") == "SHIPPER_DISPATCHER", "[API-RBAC-080] роль из БД сменилась тем же токеном"
    r = op.request("POST", "/warehouse/orders", json=_bogus_wh_order())
    assert r.status_code == 403 and _code(r) == _FORB, f"[API-RBAC-080] ORDER_ENTRY снят мгновенно (роль из БД) → {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
@pytest.mark.security
def test_role_change_to_warehouse_clears_grants_081(s_admin, pwd):
    """API-RBAC-081: перевод office→SHIPPER_WAREHOUSE обнуляет персональные гранты (warehouse → Set.of())."""
    phone = "+99890" + _d(7)
    sid = s_admin.post("/shipper/staff", json={"fullName": "AT W", "phone": phone, "password": pwd, "role": "SHIPPER_OPERATOR"}).json()["id"]
    try:
        s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT W", "phone": phone, "role": "SHIPPER_OPERATOR", "capabilities": ["REPORTS"]})
        s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT W", "phone": phone, "role": "SHIPPER_WAREHOUSE"})
        st = _staff_row(s_admin, sid)
        granted = set(st.get("grantedCapabilities") or [])
        eff = set(st.get("effectiveCapabilities") or [])
        assert not granted, f"[API-RBAC-081] гранты должны обнулиться при переводе в WAREHOUSE: {granted}"
        assert eff == {"ORDER_ENTRY"}, f"[API-RBAC-081] effective = {{ORDER_ENTRY}}: {eff}"
    finally:
        s_admin.delete(f"/shipper/staff/{sid}")
