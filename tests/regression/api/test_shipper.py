"""API — Shipper (docs/testcases/api/03_shipper_orders_staff.json).

Sub-checkpoint 1 — Staff management (API-SHP-001…041): list/filter/search/pagination,
tenancy (own company only), RBAC (SHIPPER_ADMIN only), create/update/delete with capability
grants and warehouse-allow-lists. Orders + lifecycle + departures follow in later sections.

One test ↔ one case ID. Assertions compare `expected` exactly (status + code + errors[]).
Created staff cleaned up via `track` (failure-safe). Runs on DEV.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

from config.settings import get_settings

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
        assert isinstance(b, dict) and "page" in b, f"MNZL-245: ожидался вложенный page: {sorted(b) if isinstance(b, dict) else type(b)}"
        return b["page"]
    return b


def _uphone():
    return "+99890" + "".join(random.choices(string.digits, k=7))


STAFF_ROLES = ("SHIPPER_MANAGER", "SHIPPER_OPERATOR", "SHIPPER_DISPATCHER", "SHIPPER_WAREHOUSE")


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def make_staff(admin, pwd):
    """Factory → create a staff in company A; each is deleted at teardown (failure-safe)."""
    created = []

    def _mk(role="SHIPPER_MANAGER", **over):
        body = {"fullName": "AT Staff", "phone": _uphone(), "password": pwd, "role": role}
        body.update(over)
        r = admin.post("/shipper/staff", json=body)
        assert r.status_code == 201, f"staff setup: {r.status_code} {r.text[:160]}"
        created.append(r.json()["id"])
        return r.json(), body

    yield _mk
    for sid in reversed(created):
        try:
            admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture(scope="session")
def tenant_b(dev_api, cfg):
    """A SECOND shipper company (B) with an admin and one staff — for tenancy checks.
    Provisioned on DEV via super-admin; deleted at session end."""
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
    st = dev_api.request("POST", "/shipper/staff", adm,
                         json={"fullName": "AT B Staff", "phone": "+99890" + d(7),
                               "password": cfg.dev_account_password, "role": "SHIPPER_MANAGER"})
    assert st.status_code == 201, f"tenant B staff: {st.status_code} {st.text[:160]}"
    yield {"admin_token": adm, "staff_id": st.json()["id"]}
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


# ═══ STAFF — list / filter / search / pagination (001…007) ══════════════════


@pytest.mark.high
def test_staff_list_001(admin):
    r = admin.get("/shipper/staff")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SHP-001] {r.status_code}"
    assert all(s.get("role") in STAFF_ROLES for s in _content(r)), "[API-SHP-001] non-staff role leaked (admin?)"


def test_staff_filter_role_002(admin, make_staff):
    make_staff("SHIPPER_MANAGER")
    lst = _content(admin.get("/shipper/staff?role=SHIPPER_MANAGER&size=200"))
    assert all(s["role"] == "SHIPPER_MANAGER" for s in lst), "[API-SHP-002] role filter leaked"


def test_staff_filter_active_003(admin):
    r = admin.get("/shipper/staff?active=false&size=200")
    assert r.status_code == 200 and all(s.get("active") is False for s in _content(r)), "[API-SHP-003] active filter leaked"


def test_staff_search_004(admin, make_staff):
    s, body = make_staff("SHIPPER_MANAGER", fullName="Dilshod AT")
    lst = _content(admin.get("/shipper/staff?search=dilsh&size=200"))
    assert any(x["id"] == s["id"] for x in lst), "[API-SHP-004] case-insensitive search missed"


def test_staff_search_empty_005(admin):
    r = admin.get("/shipper/staff?search=zzz-none-" + uuid.uuid4().hex[:6])
    assert r.status_code == 200 and _page(r).get("totalElements") == 0, f"[API-SHP-005] {r.text[:120]}"


def test_staff_pagination_006(admin):
    r = admin.get("/shipper/staff?page=1&size=5&sort=fullName,asc")
    assert r.status_code == 200, f"[API-SHP-006] {r.status_code}"
    pg = _page(r)
    assert pg.get("page") == 1 and pg.get("size") == 5 and len(_content(r)) <= 5, f"[API-SHP-006] {pg}"


@pytest.mark.high
@pytest.mark.tenancy
def test_staff_tenancy_007(admin, tenant_b):
    ids = {s["id"] for s in _content(admin.get("/shipper/staff?size=200"))}
    assert tenant_b["staff_id"] not in ids, "[API-SHP-007] company B staff visible to company A admin"


# ═══ STAFF — RBAC + 401 (008…013, 026/027, 036, 041) ════════════════════════

_STAFF_RBAC_GET = [
    ("API-SHP-008", "shipper_manager"), ("API-SHP-009", "shipper_operator"),
    ("API-SHP-010", "shipper_dispatcher"), ("API-SHP-012", "transport_admin"),
]


@pytest.mark.rbac
@pytest.mark.parametrize("cid,role", _STAFF_RBAC_GET, ids=[c[0] for c in _STAFF_RBAC_GET])
def test_staff_rbac_get(api, cid, role):
    r = api(role).get("/shipper/staff")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[{cid}] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_staff_rbac_warehouse_011(api):
    r = api("shipper_warehouse").get("/shipper/staff")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-011] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_staff_no_token_013(dev_api):
    r = dev_api.request("GET", "/shipper/staff", None)
    assert r.status_code == 401, f"[API-SHP-013] {r.status_code}"
    assert _code(r) == "UNAUTHORIZED", f"[API-SHP-013] code={_code(r)}"  # entry-point (как AUTH-079/SA-161)


# ═══ STAFF — create (014…027) ═══════════════════════════════════════════════


@pytest.mark.high
def test_staff_create_manager_014(admin, make_staff, dev_api, pwd):
    s, body = make_staff("SHIPPER_MANAGER")
    assert s.get("role") == "SHIPPER_MANAGER" and s.get("active") is True, f"[API-SHP-014] {s}"
    login = dev_api.login(body["phone"], pwd, "WEB")
    assert login.status_code == 200, f"[API-SHP-014] new staff cannot log in: {login.status_code}"


@pytest.mark.high
def test_staff_create_warehouse_allowed_015(admin, make_staff):
    s, _ = make_staff("SHIPPER_WAREHOUSE", allowedFromWarehouseIds=[], allowedToWarehouseIds=[])
    assert s.get("role") == "SHIPPER_WAREHOUSE", f"[API-SHP-015] {s.get('role')}"
    assert "allowedFromWarehouseIds" in s and "allowedToWarehouseIds" in s, f"[API-SHP-015] {sorted(s)}"


@pytest.mark.high
def test_staff_create_grant_capability_016(admin, make_staff):
    s, _ = make_staff("SHIPPER_MANAGER", capabilities=["REPORTS", "ORDER_DELETE"])
    granted = set(s.get("grantedCapabilities") or s.get("granted") or [])
    assert {"REPORTS", "ORDER_DELETE"}.issubset(granted), f"[API-SHP-016] granted={granted}"
    eff = set(s.get("effectiveCapabilities") or [])
    assert "REPORTS" in eff, f"[API-SHP-016] effective missing REPORTS: {eff}"


STAFF_VALIDATION = [
    ("API-SHP-017", {"fullName": ""}, "fullName"),
    ("API-SHP-018", {"fullName": "A"}, "fullName"),
    ("API-SHP-020", {"phone": "8901112233"}, "phone"),
    ("API-SHP-021", {"password": "123"}, "password"),
    ("API-SHP-022", {"role": None}, "role"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,over,field", STAFF_VALIDATION, ids=[c[0] for c in STAFF_VALIDATION])
def test_staff_create_validation(admin, pwd, cid, over, field):
    body = {"fullName": "AT Staff", "phone": _uphone(), "password": pwd, "role": "SHIPPER_MANAGER"}
    body.update(over)
    if over.get("role", "x") is None:
        del body["role"]
    r = admin.post("/shipper/staff", json=body)
    assert r.status_code == 400, f"[{cid}] {over}: {r.status_code} {r.text[:160]}"
    assert field in _err_fields(r), f"[{cid}] errors={_err_fields(r)} missing {field}"


@pytest.mark.high
def test_staff_create_invalid_role_023(admin, pwd):
    r = admin.post("/shipper/staff", json={"fullName": "AT Staff", "phone": _uphone(), "password": pwd, "role": "SHIPPER_ADMIN"})
    assert r.status_code == 400 and _code(r) == "error.invalid-role", f"[API-SHP-023] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_staff_create_locations_warehouse_only_024(admin, pwd):
    r = admin.post("/shipper/staff", json={"fullName": "AT Staff", "phone": _uphone(), "password": pwd,
                                           "role": "SHIPPER_MANAGER", "allowedFromWarehouseIds": [str(uuid.uuid4())]})
    assert r.status_code == 400 and _code(r) == "error.staff.locations-order-entry-only", f"[API-SHP-024] {r.status_code}/{_code(r)}"


def test_staff_create_dup_phone_025(admin, make_staff, pwd):
    s, body = make_staff("SHIPPER_MANAGER")
    r = admin.post("/shipper/staff", json={"fullName": "AT Staff 2", "phone": body["phone"], "password": pwd, "role": "SHIPPER_OPERATOR"})
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SHP-025] {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_staff_create_rbac_manager_026(api, pwd):
    r = api("shipper_manager").post("/shipper/staff", json={"fullName": "X Y", "phone": _uphone(), "password": pwd, "role": "SHIPPER_OPERATOR"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-026] {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_staff_create_rbac_warehouse_027(api, pwd):
    r = api("shipper_warehouse").post("/shipper/staff", json={"fullName": "X Y", "phone": _uphone(), "password": pwd, "role": "SHIPPER_OPERATOR"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-027] {r.status_code}/{_code(r)}"


# ═══ STAFF — update PATCH (028…036) ═════════════════════════════════════════


@pytest.mark.high
def test_staff_update_028(admin, make_staff, dev_api, pwd):
    s, body = make_staff("SHIPPER_MANAGER")
    new_pwd = "Aa1!" + uuid.uuid4().hex[:12]  # валидный по политике, не хардкод реального пароля
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "AT Staff Renamed", "phone": body["phone"], "password": new_pwd, "role": "SHIPPER_MANAGER"})
    assert r.status_code == 200 and r.json()["fullName"] == "AT Staff Renamed", f"[API-SHP-028] {r.status_code} {r.text[:160]}"
    assert dev_api.login(body["phone"], new_pwd, "WEB").status_code == 200, "[API-SHP-028] new password not applied"


def test_staff_update_password_optional_029(admin, make_staff, dev_api, pwd):
    s, body = make_staff("SHIPPER_MANAGER")
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "AT Renamed", "phone": body["phone"], "role": "SHIPPER_MANAGER"})
    assert r.status_code == 200, f"[API-SHP-029] {r.status_code}"
    assert dev_api.login(body["phone"], pwd, "WEB").status_code == 200, "[API-SHP-029] old password stopped working"


@pytest.mark.high
@pytest.mark.tenancy
def test_staff_update_tenancy_030(admin, tenant_b):
    r = admin.patch(f"/shipper/staff/{tenant_b['staff_id']}", json={"fullName": "Hacked", "phone": _uphone(), "role": "SHIPPER_MANAGER"})
    assert r.status_code == 404 and _code(r) == "error.employee.not-found", f"[API-SHP-030] {r.status_code}/{_code(r)}"


def test_staff_update_invalid_role_032(admin, make_staff):
    s, body = make_staff("SHIPPER_MANAGER")
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "AT Staff", "phone": body["phone"], "role": "SHIPPER_ADMIN"})
    assert r.status_code == 400 and _code(r) == "error.invalid-role", f"[API-SHP-032] {r.status_code}/{_code(r)}"


def test_staff_update_locations_warehouse_only_033(admin, make_staff):
    s, body = make_staff("SHIPPER_MANAGER")
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "AT Staff", "phone": body["phone"], "role": "SHIPPER_MANAGER", "allowedToWarehouseIds": [str(uuid.uuid4())]})
    assert r.status_code == 400 and _code(r) == "error.staff.locations-order-entry-only", f"[API-SHP-033] {r.status_code}/{_code(r)}"


def test_staff_update_validation_034(admin, make_staff):
    s, body = make_staff("SHIPPER_MANAGER")
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "", "phone": body["phone"], "role": "SHIPPER_MANAGER"})
    assert r.status_code == 400 and "fullName" in _err_fields(r), f"[API-SHP-034] {r.status_code} {_err_fields(r)}"


def test_staff_update_replace_grants_035(admin, make_staff):
    s, body = make_staff("SHIPPER_MANAGER", capabilities=["REPORTS"])
    r = admin.patch(f"/shipper/staff/{s['id']}", json={"fullName": "AT Staff", "phone": body["phone"], "role": "SHIPPER_MANAGER", "capabilities": ["ORDER_DELETE"]})
    assert r.status_code == 200, f"[API-SHP-035] {r.status_code}"
    granted = set(r.json().get("grantedCapabilities") or r.json().get("granted") or [])
    assert granted == {"ORDER_DELETE"}, f"[API-SHP-035] grants not fully replaced: {granted}"


@pytest.mark.rbac
def test_staff_update_rbac_036(api, make_staff):
    s, body = make_staff("SHIPPER_MANAGER")
    r = api("shipper_manager").patch(f"/shipper/staff/{s['id']}", json={"fullName": "XY", "phone": body["phone"], "role": "SHIPPER_MANAGER"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-036] {r.status_code}/{_code(r)}"


# ═══ STAFF — delete (037…041) ═══════════════════════════════════════════════


@pytest.mark.high
def test_staff_delete_037(admin, pwd, dev_api):
    phone = _uphone()
    s = admin.post("/shipper/staff", json={"fullName": "AT Del", "phone": phone, "password": pwd, "role": "SHIPPER_MANAGER"}).json()
    r = admin.delete(f"/shipper/staff/{s['id']}")
    assert r.status_code == 204, f"[API-SHP-037] {r.status_code}"
    assert dev_api.login(phone, pwd, "WEB").status_code != 200, "[API-SHP-037] deleted staff can still log in"


@pytest.mark.high
@pytest.mark.tenancy
def test_staff_delete_tenancy_038(admin, tenant_b):
    r = admin.delete(f"/shipper/staff/{tenant_b['staff_id']}")
    assert r.status_code == 404 and _code(r) == "error.employee.not-found", f"[API-SHP-038] {r.status_code}/{_code(r)}"


def test_staff_delete_idempotent_040(admin, pwd):
    phone = _uphone()
    s = admin.post("/shipper/staff", json={"fullName": "AT Del", "phone": phone, "password": pwd, "role": "SHIPPER_MANAGER"}).json()
    assert admin.delete(f"/shipper/staff/{s['id']}").status_code == 204
    r2 = admin.delete(f"/shipper/staff/{s['id']}")
    assert r2.status_code == 404 and _code(r2) == "error.employee.not-found", f"[API-SHP-040] {r2.status_code}/{_code(r2)}"


@pytest.mark.rbac
def test_staff_delete_rbac_041(api, make_staff):
    s, _ = make_staff("SHIPPER_MANAGER")
    r = api("shipper_manager").delete(f"/shipper/staff/{s['id']}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SHP-041] {r.status_code}/{_code(r)}"


# ═══ пропущенные при первом заходе кейсы (019 / 031 / 039) ═══════════════════


@pytest.mark.low
@pytest.mark.boundary
def test_staff_fullname_boundary_019(admin, pwd, dev_api):
    ok = admin.post("/shipper/staff", json={"fullName": "A" * 255, "phone": _uphone(), "password": pwd, "role": "SHIPPER_MANAGER"})
    assert ok.status_code == 201, f"[API-SHP-019] fullName=255 должно проходить: {ok.status_code} {ok.text[:120]}"
    admin.delete(f"/shipper/staff/{ok.json()['id']}")
    bad = admin.post("/shipper/staff", json={"fullName": "A" * 256, "phone": _uphone(), "password": pwd, "role": "SHIPPER_MANAGER"})
    assert bad.status_code == 400 and "fullName" in _err_fields(bad), f"[API-SHP-019] fullName=256: {bad.status_code} {_err_fields(bad)}"


def _self_user_id(admin):
    me = admin.get("/me").json()
    return me.get("id") or me.get("userId")


@pytest.mark.negative
def test_staff_update_non_staff_role_404_031(admin):
    """Цель — сам админ (роль SHIPPER_ADMIN вне STAFF_ROLES) → эндпойнт правит только staff-роли."""
    uid = _self_user_id(admin)
    r = admin.patch(f"/shipper/staff/{uid}", json={"fullName": "X Y", "phone": _uphone(), "role": "SHIPPER_MANAGER"})
    assert r.status_code == 404 and _code(r) == "error.employee.not-found", f"[API-SHP-031] {r.status_code}/{_code(r)}"


@pytest.mark.negative
def test_staff_delete_non_staff_role_404_039(admin):
    uid = _self_user_id(admin)
    r = admin.delete(f"/shipper/staff/{uid}")
    assert r.status_code == 404 and _code(r) == "error.employee.not-found", f"[API-SHP-039] {r.status_code}/{_code(r)}"
