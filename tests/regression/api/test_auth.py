"""API — Аутентификация / /me / устройства (docs/testcases/api/01_auth_me_devices.json).

One test ↔ one case ID (in the docstring / parametrize id). Assertions compare the
case `expected` exactly: HTTP status + problem+json `code` + `errors[]` by field +
token presence. Nothing is weakened to make a test pass — a divergence is a bug.

Isolation rules (CLAUDE.md):
* Any test that causes a **failed credential login** (401 invalid-credentials) burns
  the login-attempt budget (5/phone, 30/IP per 10 min). Those + the rate-limit cases
  carry ``@pytest.mark.ratelimit`` → run serially, separately from ``-n auto``, on
  throwaway phones — never on the shared provisioned roles.
* Positive logins, wrong-app (correct password, not counted), validation-400 (rejected
  before the credential check), /me, devices, refresh-happy, logout — parallel-safe.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.api]


# ─── helpers ─────────────────────────────────────────────────────────────────


def _rand_phone() -> str:
    return "+99890" + "".join(random.choices(string.digits, k=7))


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _errors(r):
    try:
        return r.json().get("errors") or []
    except Exception:  # noqa: BLE001
        return []


def _err_fields(r):
    return {e.get("field") for e in _errors(r)}


def _detail(r):
    try:
        return r.json().get("detail")
    except Exception:  # noqa: BLE001
        return None


def _has_tokens(r) -> bool:
    try:
        b = r.json()
        return bool(b.get("accessToken") and b.get("refreshToken"))
    except Exception:  # noqa: BLE001
        return False


VALID_PWD_BODY = {"emasDeviceId": "at-dev", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"}


# ─── POST /auth/login — positive (role × allowed clientType) ─────────────────

# role key → (clientType that IS allowed)
POSITIVE_LOGIN = [
    ("API-AUTH-001", "super_admin", "WEB"),
    ("API-AUTH-002", "shipper_admin", "WEB"),
    ("API-AUTH-003", "shipper_manager", "WEB"),
    ("API-AUTH-004", "shipper_operator", "WEB"),
    ("API-AUTH-005", "shipper_dispatcher", "WEB"),
    ("API-AUTH-006", "transport_admin", "WEB"),  # carrier allowed on WEB too
    ("API-AUTH-007", "transport_admin", "TRANSPORT_COMPANY_APP"),
    ("API-AUTH-008", "shipper_warehouse", "WAREHOUSE_APP"),
]


@pytest.mark.high
@pytest.mark.parametrize("cid,role,ctype", POSITIVE_LOGIN, ids=[c[0] for c in POSITIVE_LOGIN])
def test_login_positive(dev_api, api_dev_roles, cid, role, ctype):
    """Positive login: role reaches 200 with a token pair on its allowed clientType."""
    phone, pwd, _ = api_dev_roles[role]
    r = dev_api.login(phone, pwd, ctype)
    assert r.status_code == 200, f"[{cid}] {role}/{ctype}: {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("accessToken") and b.get("refreshToken"), f"[{cid}] no token pair: {b}"
    assert b.get("expiresIn") and b.get("tokenType"), f"[{cid}] missing expiresIn/tokenType: {b}"


# ─── POST /auth/login — wrong-app (correct password, NOT counted) ────────────

WRONG_APP = [
    ("API-AUTH-009", "shipper_warehouse", "WEB"),
    ("API-AUTH-013", "shipper_operator", "TRANSPORT_COMPANY_APP"),
    ("API-AUTH-014", "transport_admin", "WAREHOUSE_APP"),
    ("API-AUTH-015", "super_admin", "WAREHOUSE_APP"),
]


@pytest.mark.rbac
@pytest.mark.parametrize("cid,role,ctype", WRONG_APP, ids=[c[0] for c in WRONG_APP])
def test_login_wrong_app(dev_api, api_dev_roles, cid, role, ctype):
    """403 error.wrong-app: correct password, clientType not allowed for the role."""
    phone, pwd, _ = api_dev_roles[role]
    r = dev_api.login(phone, pwd, ctype)
    assert r.status_code == 403, f"[{cid}] {role}/{ctype}: {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.wrong-app", f"[{cid}] code={_code(r)} != error.wrong-app"
    assert not _has_tokens(r), f"[{cid}] tokens leaked on wrong-app"


# ─── POST /auth/login — validation (400, rejected before credential check) ───

# (cid, body, expected error field or None if just "400 BAD_REQUEST")
LOGIN_VALIDATION = [
    ("API-AUTH-023", {"password": "x", "clientType": "WEB"}, "phone"),          # phone missing
    ("API-AUTH-024", {"phone": "998901234567", "password": "x", "clientType": "WEB"}, "phone"),  # no +
    ("API-AUTH-025", {"phone": "+99890ABC4567", "password": "x", "clientType": "WEB"}, "phone"),
    ("API-AUTH-026", {"phone": "+123456789", "password": "x", "clientType": "WEB"}, "phone"),    # 9 digits
    ("API-AUTH-027", {"phone": "+1234567890123456", "password": "x", "clientType": "WEB"}, "phone"),  # 16
    ("API-AUTH-030", {"phone": "+998901234567", "clientType": "WEB"}, "password"),   # password missing
    ("API-AUTH-031", {"phone": "+998901234567", "password": "x" * 129, "clientType": "WEB"}, "password"),
    ("API-AUTH-033", {"phone": "+998901234567", "password": "x"}, "clientType"),      # clientType missing
    ("API-AUTH-034", {"phone": "+998901234567", "password": "x", "clientType": "MOBILE_XYZ"}, None),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,body,field", LOGIN_VALIDATION, ids=[c[0] for c in LOGIN_VALIDATION])
def test_login_validation(dev_api, cid, body, field):
    """400 BAD_REQUEST on malformed login body; errors[] names the offending field."""
    r = dev_api.request("POST", "/auth/login", None, json=body)
    assert r.status_code == 400, f"[{cid}] {body}: {r.status_code} {r.text[:160]}"
    assert _code(r) == "BAD_REQUEST", f"[{cid}] code={_code(r)}"
    if field:
        assert field in _err_fields(r), f"[{cid}] errors fields={_err_fields(r)} missing '{field}'"


def test_login_validation_multi_035(dev_api):
    """API-AUTH-035: {phone:'abc', password:'', clientType:null} → all three fields in errors[]."""
    r = dev_api.request("POST", "/auth/login", None, json={"phone": "abc", "password": "", "clientType": None})
    assert r.status_code == 400, f"[API-AUTH-035] {r.status_code} {r.text[:160]}"
    fields = _err_fields(r)
    for f in ("phone", "password", "clientType"):
        assert f in fields, f"[API-AUTH-035] errors fields={fields} missing '{f}'"


def test_login_broken_json_036(dev_api):
    """API-AUTH-036: non-JSON body → 400 BAD_REQUEST, never 500."""
    r = dev_api.request("POST", "/auth/login", None, data="not-a-json",
                        headers={"Content-Type": "application/json"})
    assert r.status_code == 400, f"[API-AUTH-036] expected 400, got {r.status_code}: {r.text[:160]}"


# boundary phone/password that must NOT 400 (proceeds to 401 for unknown creds)
NO_400 = [
    ("API-AUTH-028", "+1234567890"),          # exactly 10 digits — min
    ("API-AUTH-029", "+123456789012345"),     # exactly 15 digits — max
]


@pytest.mark.boundary
@pytest.mark.parametrize("cid,phone", NO_400, ids=[c[0] for c in NO_400])
def test_login_phone_boundary_ok(dev_api, cid, phone):
    """Boundary phone length is accepted (no 400) — unknown account then yields 401."""
    r = dev_api.request("POST", "/auth/login", None,
                        json={"phone": phone, "password": "whatever", "clientType": "WEB"})
    assert r.status_code != 400, f"[{cid}] {phone}: unexpected 400 {r.text[:160]}"
    assert r.status_code in (401,), f"[{cid}] {phone}: expected 401, got {r.status_code}"


def test_login_password_128_ok_032(dev_api):
    """API-AUTH-032: 128-char password is accepted (no 400) — unknown account → 401."""
    r = dev_api.request("POST", "/auth/login", None,
                        json={"phone": "+998909999999", "password": "x" * 128, "clientType": "WEB"})
    assert r.status_code != 400, f"[API-AUTH-032] unexpected 400: {r.text[:160]}"
    assert r.status_code == 401, f"[API-AUTH-032] expected 401, got {r.status_code}"


# ─── GET /me — role identity + effectiveCapabilities ─────────────────────────

# Combined into the tests below: API-AUTH-073 (in 066), API-AUTH-075 (in 067),
# API-AUTH-078 (in 070) — asserted there, listed here for ID traceability.
OPERATOR_CAPS = {"ORDER_REVIEW", "ORDER_FULFILL", "ORDER_ENTRY", "WAREHOUSE_DIRECTORY_READ"}
DISPATCHER_CAPS = {"ORDER_REVIEW", "DEPARTURES", "SMS_BLAST", "SMS_JOURNAL", "WAREHOUSE_DIRECTORY_READ"}
WAREHOUSE_CAPS = {"ORDER_ENTRY"}
ADMIN_MUST_HAVE = {"ORDER_ENTRY", "SEE_PRICES", "SMS_BLAST", "REPORTS", "DEPARTURES", "BLACKLIST"}


@pytest.mark.high
def test_me_super_admin_065(api):
    r = api("super_admin").get("/me")
    assert r.status_code == 200, f"[API-AUTH-065] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("role") == "SUPER_ADMIN", f"[API-AUTH-065] role={b.get('role')}"
    assert "company" not in b, f"[API-AUTH-065] company должно отсутствовать: {b.get('company')}"
    assert b.get("effectiveCapabilities") == [], f"[API-AUTH-065] caps={b.get('effectiveCapabilities')}"


@pytest.mark.high
def test_me_shipper_admin_066_073(api):
    r = api("shipper_admin").get("/me")
    assert r.status_code == 200, f"[API-AUTH-066] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("role") == "SHIPPER_ADMIN"
    assert (b.get("company") or {}).get("type") == "SHIPPER", f"[API-AUTH-066] company={b.get('company')}"
    caps = set(b.get("effectiveCapabilities") or [])
    assert ADMIN_MUST_HAVE.issubset(caps), f"[API-AUTH-066/073] admin caps missing {ADMIN_MUST_HAVE - caps}"


@pytest.mark.high
def test_me_manager_no_order_entry_067_075(api):
    r = api("shipper_manager").get("/me")
    assert r.status_code == 200, f"[API-AUTH-067] {r.status_code}"
    b = r.json()
    assert b.get("role") == "SHIPPER_MANAGER"
    caps = set(b.get("effectiveCapabilities") or [])
    assert "ORDER_ENTRY" not in caps, f"[API-AUTH-067/075] manager unexpectedly has ORDER_ENTRY: {caps}"


@pytest.mark.high
def test_me_operator_068(api):
    r = api("shipper_operator").get("/me")
    assert r.status_code == 200, f"[API-AUTH-068] {r.status_code}"
    caps = set(r.json().get("effectiveCapabilities") or [])
    assert caps == OPERATOR_CAPS, f"[API-AUTH-068] operator caps={caps} != {OPERATOR_CAPS}"


@pytest.mark.high
def test_me_dispatcher_069(api):
    r = api("shipper_dispatcher").get("/me")
    assert r.status_code == 200, f"[API-AUTH-069] {r.status_code}"
    caps = set(r.json().get("effectiveCapabilities") or [])
    assert caps == DISPATCHER_CAPS, f"[API-AUTH-069] dispatcher caps={caps} != {DISPATCHER_CAPS}"


@pytest.mark.high
def test_me_warehouse_070_078(api):
    r = api("shipper_warehouse").get("/me")
    assert r.status_code == 200, f"[API-AUTH-070] {r.status_code}"
    b = r.json()
    caps = set(b.get("effectiveCapabilities") or [])
    assert caps == WAREHOUSE_CAPS, f"[API-AUTH-070] warehouse caps={caps} != {WAREHOUSE_CAPS}"
    assert "allowedFromWarehouseIds" in b and "allowedToWarehouseIds" in b, \
        f"[API-AUTH-070/078] warehouse allowed-lists missing: {sorted(b)}"


@pytest.mark.high
def test_me_transport_admin_071(api):
    r = api("transport_admin").get("/me")
    assert r.status_code == 200, f"[API-AUTH-071] {r.status_code}"
    b = r.json()
    assert b.get("role") == "TRANSPORT_ADMIN"
    assert (b.get("company") or {}).get("type") == "TRANSPORT", f"[API-AUTH-071] company={b.get('company')}"
    assert b.get("effectiveCapabilities") == [], f"[API-AUTH-071] caps={b.get('effectiveCapabilities')}"


@pytest.mark.parametrize("role", ["super_admin", "transport_admin"], ids=["API-AUTH-076-sa", "API-AUTH-076-tc"])
def test_me_non_shipper_empty_caps_076(api, role):
    """API-AUTH-076: non-shipper roles → effectiveCapabilities == [] (DRIVER part: manual)."""
    r = api(role).get("/me")
    assert r.status_code == 200, f"[API-AUTH-076/{role}] {r.status_code}"
    assert r.json().get("effectiveCapabilities") == [], f"[API-AUTH-076/{role}] caps not empty"


def test_me_warehouse_fields_for_admin_077(api):
    """API-AUTH-077: implemented behaviour — for SHIPPER_ADMIN the allowed-warehouse
    lists are serialized as EMPTY (no real data), and the default-warehouse fields are
    omitted (unset → not returned)."""
    r = api("shipper_admin").get("/me")
    assert r.status_code == 200
    b = r.json()
    assert b.get("allowedFromWarehouseIds") == [], f"[API-AUTH-077] allowedFrom={b.get('allowedFromWarehouseIds')!r}"
    assert b.get("allowedToWarehouseIds") == [], f"[API-AUTH-077] allowedTo={b.get('allowedToWarehouseIds')!r}"
    for f in ("defaultFromWarehouseId", "defaultToWarehouseId"):
        assert f not in b, f"[API-AUTH-077] '{f}' unexpectedly present for admin"


@pytest.mark.high
def test_me_no_token_079(dev_api):
    r = dev_api.request("GET", "/me", None)
    assert r.status_code == 401, f"[API-AUTH-079] {r.status_code}"
    assert _code(r) == "UNAUTHORIZED", f"[API-AUTH-079] code={_code(r)}"


@pytest.mark.high
def test_me_bad_bearer_080(dev_api):
    """API-AUTH-080: malformed/expired bearer → 401 with EMPTY body; the error lives in
    the WWW-Authenticate header (error=invalid_token), not a JSON code. This differs from
    no-token (079), which returns a JSON body with code=UNAUTHORIZED."""
    r = dev_api.request("GET", "/me", None, headers={"Authorization": "Bearer invalid.jwt"})
    assert r.status_code == 401, f"[API-AUTH-080] {r.status_code}"
    wa = r.headers.get("www-authenticate", "")
    assert "invalid_token" in wa, f"[API-AUTH-080] www-authenticate={wa!r}"


# ─── POST /me/devices — register + validation + BOLA ─────────────────────────


@pytest.mark.high
def test_device_register_warehouse_086(api):
    r = api("shipper_warehouse").post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r.status_code == 200, f"[API-AUTH-086] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("id") and b.get("app") == "WAREHOUSE" and b.get("platform") == "ANDROID"
    assert b.get("language") == "ru" and b.get("apnsEnv") == "PRODUCT", f"[API-AUTH-086] {b}"


def test_device_register_ios_dev_087(api):
    r = api("transport_admin").post("/me/devices", json={
        "emasDeviceId": f"ios-{uuid.uuid4().hex[:8]}", "platform": "IOS", "app": "DRIVER",
        "language": "uz", "apnsEnv": "DEV"})
    assert r.status_code == 200, f"[API-AUTH-087] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("apnsEnv") == "DEV" and b.get("language") == "uz", f"[API-AUTH-087] {b}"


def test_device_upsert_088(api):
    dev = api("shipper_warehouse")
    did = f"dup-{uuid.uuid4().hex[:8]}"
    r1 = dev.post("/me/devices", json={"emasDeviceId": did, "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r1.status_code == 200, f"[API-AUTH-088] first {r1.status_code}"
    r2 = dev.post("/me/devices", json={"emasDeviceId": did, "platform": "IOS", "app": "WAREHOUSE", "language": "uz"})
    assert r2.status_code == 200, f"[API-AUTH-088] second {r2.status_code}"
    assert r1.json()["id"] == r2.json()["id"], "[API-AUTH-088] upsert created a duplicate id"
    assert r2.json()["language"] == "uz", "[API-AUTH-088] fields not overwritten on upsert"


def test_device_apns_default_089(api):
    r = api("shipper_warehouse").post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r.status_code == 200
    assert r.json().get("apnsEnv") == "PRODUCT", f"[API-AUTH-089] apnsEnv={r.json().get('apnsEnv')}"


def test_device_language_normalize_unsupported_090(api):
    r = api("shipper_warehouse").post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "xx"})
    assert r.status_code == 200, f"[API-AUTH-090] {r.status_code}"
    assert r.json().get("language") == "ru", f"[API-AUTH-090] language={r.json().get('language')}"


def test_device_language_normalize_case_091(api):
    r = api("shipper_warehouse").post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ZH"})
    assert r.status_code == 200
    assert r.json().get("language") == "zh", f"[API-AUTH-091] language={r.json().get('language')}"


DEVICE_VALIDATION = [
    ("API-AUTH-092", {"emasDeviceId": "d", "platform": "ANDROID", "app": "WAREHOUSE", "language": ""}, "language"),
    ("API-AUTH-093", {"emasDeviceId": "d", "platform": "ANDROID", "app": "WAREHOUSE", "language": "123456789"}, "language"),
    ("API-AUTH-094", {"emasDeviceId": "", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"}, "emasDeviceId"),
    ("API-AUTH-095", {"emasDeviceId": "x" * 257, "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"}, "emasDeviceId"),
    ("API-AUTH-096", {"emasDeviceId": "d", "app": "WAREHOUSE", "language": "ru"}, "platform"),
    ("API-AUTH-097", {"emasDeviceId": "d", "platform": "WINDOWS", "app": "WAREHOUSE", "language": "ru"}, None),
    ("API-AUTH-098", {"emasDeviceId": "d", "platform": "ANDROID", "language": "ru"}, "app"),
    ("API-AUTH-099", {"emasDeviceId": "d", "platform": "ANDROID", "app": "ADMIN", "language": "ru"}, None),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,body,field", DEVICE_VALIDATION, ids=[c[0] for c in DEVICE_VALIDATION])
def test_device_validation(api, cid, body, field):
    r = api("shipper_warehouse").post("/me/devices", json=body)
    assert r.status_code == 400, f"[{cid}] {body}: {r.status_code} {r.text[:160]}"
    if field:
        assert field in _err_fields(r), f"[{cid}] errors={_err_fields(r)} missing '{field}'"


def test_device_no_token_102(dev_api):
    r = dev_api.request("POST", "/me/devices", None, json={
        "emasDeviceId": "d", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r.status_code == 401, f"[API-AUTH-102] {r.status_code}"
    assert _code(r) == "UNAUTHORIZED", f"[API-AUTH-102] code={_code(r)}"


def test_device_any_role_may_register_103(api):
    r = api("super_admin").post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r.status_code == 200, f"[API-AUTH-103] super-admin device register {r.status_code} {r.text[:160]}"


def test_device_rebind_101(api):
    did = f"shared-{uuid.uuid4().hex[:8]}"
    r1 = api("shipper_admin").post("/me/devices", json={
        "emasDeviceId": did, "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r1.status_code == 200, f"[API-AUTH-101] owner register {r1.status_code}"
    r2 = api("shipper_manager").post("/me/devices", json={
        "emasDeviceId": did, "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r2.status_code == 200, f"[API-AUTH-101] rebind {r2.status_code} {r2.text[:160]}"


# ─── PATCH / DELETE /me/devices/{id} — happy, validation, BOLA, idempotency ──


def _register_device(client) -> str:
    r = client.post("/me/devices", json={
        "emasDeviceId": f"at-{uuid.uuid4().hex[:8]}", "platform": "ANDROID", "app": "WAREHOUSE", "language": "ru"})
    assert r.status_code == 200, f"device setup: {r.status_code} {r.text[:160]}"
    return r.json()["id"]


@pytest.mark.high
def test_device_patch_language_104(api):
    dev = api("shipper_warehouse")
    did = _register_device(dev)
    r = dev.patch(f"/me/devices/{did}", json={"language": "ky"})
    assert r.status_code == 200, f"[API-AUTH-104] {r.status_code} {r.text[:160]}"
    assert r.json().get("language") == "ky", f"[API-AUTH-104] language={r.json().get('language')}"


def test_device_patch_language_normalize_105(api):
    dev = api("shipper_warehouse")
    did = _register_device(dev)
    r = dev.patch(f"/me/devices/{did}", json={"language": "xx"})
    assert r.status_code == 200
    assert r.json().get("language") == "ru", f"[API-AUTH-105] language={r.json().get('language')}"


@pytest.mark.high
def test_device_patch_bola_106(api):
    d2 = _register_device(api("shipper_admin"))          # owned by admin
    r = api("shipper_manager").patch(f"/me/devices/{d2}", json={"language": "ru"})
    assert r.status_code == 404, f"[API-AUTH-106] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.device.not-found", f"[API-AUTH-106] code={_code(r)}"


def test_device_patch_missing_107(api):
    r = api("shipper_warehouse").patch(f"/me/devices/{uuid.uuid4()}", json={"language": "ru"})
    assert r.status_code == 404, f"[API-AUTH-107] {r.status_code}"
    assert _code(r) == "error.device.not-found", f"[API-AUTH-107] code={_code(r)}"


@pytest.mark.high
def test_device_patch_language_empty_108(api):
    did = _register_device(api("shipper_warehouse"))
    r = api("shipper_warehouse").patch(f"/me/devices/{did}", json={"language": ""})
    assert r.status_code == 400, f"[API-AUTH-108] {r.status_code}"
    assert "language" in _err_fields(r), f"[API-AUTH-108] errors={_err_fields(r)}"


def test_device_patch_language_too_long_109(api):
    did = _register_device(api("shipper_warehouse"))
    r = api("shipper_warehouse").patch(f"/me/devices/{did}", json={"language": "123456789"})
    assert r.status_code == 400, f"[API-AUTH-109] {r.status_code}"
    assert "language" in _err_fields(r), f"[API-AUTH-109] errors={_err_fields(r)}"


def test_device_patch_bad_uuid_110(api):
    r = api("shipper_warehouse").patch("/me/devices/not-a-uuid", json={"language": "ru"})
    assert r.status_code == 400, f"[API-AUTH-110] {r.status_code}"
    assert _code(r) == "BAD_REQUEST", f"[API-AUTH-110] code={_code(r)}"


def test_device_patch_no_token_111(dev_api):
    r = dev_api.request("PATCH", f"/me/devices/{uuid.uuid4()}", None, json={"language": "ru"})
    assert r.status_code == 401, f"[API-AUTH-111] {r.status_code}"
    assert _code(r) == "UNAUTHORIZED", f"[API-AUTH-111] code={_code(r)}"


@pytest.mark.high
def test_device_delete_and_idempotency_112_115(api):
    dev = api("shipper_warehouse")
    did = _register_device(dev)
    r = dev.delete(f"/me/devices/{did}")
    assert r.status_code == 204, f"[API-AUTH-112] {r.status_code} {r.text[:160]}"
    r2 = dev.delete(f"/me/devices/{did}")
    assert r2.status_code == 404, f"[API-AUTH-115] re-delete {r2.status_code}"
    assert _code(r2) == "error.device.not-found", f"[API-AUTH-115] code={_code(r2)}"


@pytest.mark.high
def test_device_delete_bola_113(api):
    d2 = _register_device(api("shipper_admin"))
    r = api("shipper_manager").delete(f"/me/devices/{d2}")
    assert r.status_code == 404, f"[API-AUTH-113] {r.status_code}"
    assert _code(r) == "error.device.not-found", f"[API-AUTH-113] code={_code(r)}"


def test_device_delete_missing_114(api):
    r = api("shipper_warehouse").delete(f"/me/devices/{uuid.uuid4()}")
    assert r.status_code == 404, f"[API-AUTH-114] {r.status_code}"
    assert _code(r) == "error.device.not-found", f"[API-AUTH-114] code={_code(r)}"


def test_device_delete_bad_uuid_116(api):
    r = api("shipper_warehouse").delete("/me/devices/xyz")
    assert r.status_code == 400, f"[API-AUTH-116] {r.status_code}"
    assert _code(r) == "BAD_REQUEST", f"[API-AUTH-116] code={_code(r)}"


def test_device_delete_no_token_117(dev_api):
    r = dev_api.request("DELETE", f"/me/devices/{uuid.uuid4()}", None)
    assert r.status_code == 401, f"[API-AUTH-117] {r.status_code}"
    assert _code(r) == "UNAUTHORIZED", f"[API-AUTH-117] code={_code(r)}"


# ─── POST /auth/refresh & /auth/logout — happy paths + validation ────────────
# Use a FRESH login (throwaway refresh token) so shared sessions are untouched.


def _fresh_login(dev_api, api_dev_roles, role="shipper_admin"):
    phone, pwd, _ = api_dev_roles[role]
    r = dev_api.login(phone, pwd, "WEB")
    assert r.status_code == 200, f"fresh login setup: {r.status_code} {r.text[:160]}"
    return r.json()


@pytest.mark.high
def test_refresh_rotation_051_052(dev_api, api_dev_roles):
    tok = _fresh_login(dev_api, api_dev_roles)
    r = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": tok["refreshToken"]})
    assert r.status_code == 200, f"[API-AUTH-051] {r.status_code} {r.text[:160]}"
    assert _has_tokens(r), "[API-AUTH-051] refresh returned no token pair"
    assert r.json()["refreshToken"] != tok["refreshToken"], "[API-AUTH-051] refresh not rotated"
    # 052: reuse of the old (rotated) token → 401
    r2 = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": tok["refreshToken"]})
    assert r2.status_code == 401, f"[API-AUTH-052] reuse {r2.status_code}"
    assert _code(r2) == "error.invalid-credentials", f"[API-AUTH-052] code={_code(r2)}"


def test_refresh_garbage_054(dev_api):
    r = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": "garbage"})
    assert r.status_code == 401, f"[API-AUTH-054] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-054] code={_code(r)}"


@pytest.mark.high
def test_refresh_validation_empty_055(dev_api):
    r = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": ""})
    assert r.status_code == 400, f"[API-AUTH-055] {r.status_code}"
    assert _code(r) == "BAD_REQUEST", f"[API-AUTH-055] code={_code(r)}"
    assert "refreshToken" in _err_fields(r), f"[API-AUTH-055] errors={_err_fields(r)}"


@pytest.mark.high
def test_logout_and_revoke_060(dev_api, api_dev_roles):
    tok = _fresh_login(dev_api, api_dev_roles)
    r = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": tok["refreshToken"]})
    assert r.status_code == 204, f"[API-AUTH-060] {r.status_code} {r.text[:160]}"
    # revoked: refresh with it now 401
    r2 = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": tok["refreshToken"]})
    assert r2.status_code == 401, f"[API-AUTH-060] post-logout refresh {r2.status_code}"


def test_logout_unknown_token_061(dev_api):
    r = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": "unknown-or-revoked"})
    assert r.status_code == 204, f"[API-AUTH-061] {r.status_code}"


@pytest.mark.high
def test_logout_validation_062(dev_api):
    r = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": ""})
    assert r.status_code == 400, f"[API-AUTH-062] {r.status_code}"
    assert "refreshToken" in _err_fields(r), f"[API-AUTH-062] errors={_err_fields(r)}"


def test_logout_idempotent_063(dev_api, api_dev_roles):
    tok = _fresh_login(dev_api, api_dev_roles)
    r1 = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": tok["refreshToken"]})
    r2 = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": tok["refreshToken"]})
    assert r1.status_code == 204 and r2.status_code == 204, f"[API-AUTH-063] {r1.status_code}/{r2.status_code}"


def test_logout_no_bearer_064(dev_api, api_dev_roles):
    tok = _fresh_login(dev_api, api_dev_roles)
    r = dev_api.request("POST", "/auth/logout", None, json={"refreshToken": tok["refreshToken"]})
    assert r.status_code == 204, f"[API-AUTH-064] logout without Authorization {r.status_code}"


# ─── Failed-credential + rate-limit cases (SERIAL, dedicated phones) ─────────
# These burn the login-attempt budget (5/phone, 30/IP) → never on shared roles,
# never under -n auto. Run with:  pytest -m ratelimit  (serial).

I18N = [
    ("API-AUTH-044", "zh", "用户名或密码错误"),
    ("API-AUTH-045", "uz", "Noto'g'ri login yoki parol"),
    ("API-AUTH-046", "ky", "Туура эмес логин же сырсөз"),
    ("API-AUTH-048", "ru", "Неверный логин или пароль"),
    ("API-AUTH-049", "fr", "Неверный логин или пароль"),  # unsupported → ru
]


@pytest.mark.ratelimit
@pytest.mark.i18n
@pytest.mark.parametrize("cid,lang,detail", I18N, ids=[c[0] for c in I18N])
def test_login_invalid_i18n(dev_api, cid, lang, detail):
    """Localized 401 detail for invalid credentials (unknown random phone per call)."""
    r = dev_api.request("POST", "/auth/login", None,
                        json={"phone": _rand_phone(), "password": "wrong", "clientType": "WEB"},
                        headers={"Accept-Language": lang})
    assert r.status_code == 401, f"[{cid}] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.invalid-credentials", f"[{cid}] code={_code(r)}"
    assert _detail(r) == detail, f"[{cid}] detail={_detail(r)!r} != {detail!r}"


@pytest.mark.ratelimit
@pytest.mark.i18n
def test_login_wrong_app_i18n_zh_050(dev_api, api_dev_roles):
    """API-AUTH-050: wrong-app detail localizes (zh)."""
    phone, pwd, _ = api_dev_roles["shipper_warehouse"]
    r = dev_api.request("POST", "/auth/login", None,
                        json={"phone": phone, "password": pwd, "clientType": "WEB"},
                        headers={"Accept-Language": "zh"})
    assert r.status_code == 403, f"[API-AUTH-050] {r.status_code}"
    assert _code(r) == "error.wrong-app", f"[API-AUTH-050] code={_code(r)}"
    assert _detail(r) == "您无权访问此应用", f"[API-AUTH-050] detail={_detail(r)!r}"


@pytest.mark.ratelimit
def test_login_wrong_password_018(dev_api, api_dev_roles):
    """API-AUTH-018: existing account + wrong password → 401 invalid-credentials."""
    phone, _pwd, _ = api_dev_roles["shipper_operator"]
    r = dev_api.login(phone, "definitely-wrong", "WEB")
    assert r.status_code == 401, f"[API-AUTH-018] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-018] code={_code(r)}"
    assert not _has_tokens(r), "[API-AUTH-018] tokens on bad password"


@pytest.mark.ratelimit
def test_login_unknown_phone_019(dev_api):
    """API-AUTH-019: unknown phone → 401 invalid-credentials (indistinguishable)."""
    r = dev_api.login(_rand_phone(), "whatever", "WEB")
    assert r.status_code == 401, f"[API-AUTH-019] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-019] code={_code(r)}"


@pytest.mark.ratelimit
def test_login_wrong_app_not_counted_017(dev_api, api_dev_roles):
    """API-AUTH-017: warehouse account + WRONG password + WEB → 401 (not 403 wrong-app)."""
    phone, _pwd, _ = api_dev_roles["shipper_warehouse"]
    r = dev_api.login(phone, "wrong-pass", "WEB")
    assert r.status_code == 401, f"[API-AUTH-017] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-017] code={_code(r)}"


@pytest.mark.ratelimit
def test_ratelimit_phone_429_037(dev_api, cfg):
    """API-AUTH-037: 5 failed attempts on one phone → 6th (even correct) → 429."""
    phone = cfg.ratelimit_phone_1 or _rand_phone()
    codes = [dev_api.login(phone, "wrong", "WEB").status_code for _ in range(5)]
    assert all(c == 401 for c in codes), f"[API-AUTH-037] pre-limit codes={codes}"
    r6 = dev_api.login(phone, "wrong-again", "WEB")
    assert r6.status_code == 429, f"[API-AUTH-037] 6th expected 429, got {r6.status_code} {r6.text[:160]}"
    assert _code(r6) == "error.too-many-attempts", f"[API-AUTH-037] code={_code(r6)}"


@pytest.mark.ratelimit
def test_refresh_no_ratelimit_059(dev_api):
    """API-AUTH-059: /auth/refresh is NOT rate-limited — 20 bad tokens all 401, never 429."""
    codes = [dev_api.request("POST", "/auth/refresh", None,
                             json={"refreshToken": "bad"}).status_code for _ in range(20)]
    assert all(c == 401 for c in codes), f"[API-AUTH-059] codes seen={set(codes)} (429 would be a limiter leak)"


# ─── Account-state cases (create burner staff, mutate, assert) ───────────────


@pytest.fixture
def newpwd(cfg):
    return cfg.dev_account_password


def _make_staff(admin, pwd, role="SHIPPER_OPERATOR", caps=None):
    """Create a throwaway staff via the shipper admin. Returns (id, phone, role).
    Cleaned up when the tenant company is deleted (cascade) at session teardown."""
    phone = _rand_phone()
    full = f"AT {role}"
    r = admin.post("/shipper/staff", json={"fullName": full, "phone": phone, "password": pwd, "role": role})
    assert r.status_code in (200, 201), f"staff setup: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    if caps:
        rp = admin.patch(f"/shipper/staff/{sid}",
                         json={"fullName": full, "phone": phone, "role": role, "capabilities": caps})
        assert rp.status_code == 200, f"grant setup: {rp.status_code} {rp.text[:160]}"
    return sid, phone, role


def _deactivate(admin, sid, phone, role):
    r = admin.patch(f"/shipper/staff/{sid}",
                    json={"fullName": f"AT {role}", "phone": phone, "role": role, "active": False})
    assert r.status_code == 200, f"deactivate setup: {r.status_code} {r.text[:160]}"


def test_login_soft_deleted_020(dev_api, api, newpwd):
    """API-AUTH-020: deleted account → 401 invalid-credentials (deletion not revealed)."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd)
    api("shipper_admin").delete(f"/shipper/staff/{sid}")
    r = dev_api.login(phone, newpwd, "WEB")
    assert r.status_code == 401, f"[API-AUTH-020] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-020] code={_code(r)}"


def test_login_deactivated_021(dev_api, api, newpwd):
    """API-AUTH-021: deactivated account → 401 invalid-credentials."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd)
    _deactivate(api("shipper_admin"), sid, phone, role)
    r = dev_api.login(phone, newpwd, "WEB")
    assert r.status_code == 401, f"[API-AUTH-021] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-021] code={_code(r)}"


@pytest.mark.high
def test_refresh_after_deactivation_056(dev_api, api, newpwd):
    """API-AUTH-056: refresh re-checks account status → deactivated → 401 invalid-credentials."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd)
    tok = dev_api.login(phone, newpwd, "WEB").json()
    _deactivate(api("shipper_admin"), sid, phone, role)
    r = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": tok["refreshToken"]})
    assert r.status_code == 401, f"[API-AUTH-056] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-056] code={_code(r)}"


@pytest.mark.high
def test_me_after_soft_delete_082(dev_api, api, newpwd):
    """API-AUTH-082: valid token but user deleted → 401 error.unauthorized (immediate)."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd)
    tok = dev_api.login(phone, newpwd, "WEB").json()
    api("shipper_admin").delete(f"/shipper/staff/{sid}")
    r = dev_api.request("GET", "/me", None, headers={"Authorization": f"Bearer {tok['accessToken']}"})
    assert r.status_code == 401, f"[API-AUTH-082] {r.status_code}"
    assert _code(r) == "error.unauthorized", f"[API-AUTH-082] code={_code(r)}"


@pytest.mark.high
def test_me_after_deactivation_083(dev_api, api, newpwd):
    """API-AUTH-083: valid token but account deactivated → 401 error.unauthorized."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd)
    tok = dev_api.login(phone, newpwd, "WEB").json()
    _deactivate(api("shipper_admin"), sid, phone, role)
    r = dev_api.request("GET", "/me", None, headers={"Authorization": f"Bearer {tok['accessToken']}"})
    assert r.status_code == 401, f"[API-AUTH-083] {r.status_code}"
    assert _code(r) == "error.unauthorized", f"[API-AUTH-083] code={_code(r)}"


def test_me_operator_granted_see_prices_074(dev_api, api, newpwd):
    """API-AUTH-074: personal grant merges with role set — operator + SEE_PRICES."""
    sid, phone, role = _make_staff(api("shipper_admin"), newpwd, caps=["SEE_PRICES"])
    tok = dev_api.login(phone, newpwd, "WEB").json()["accessToken"]
    r = dev_api.request("GET", "/me", None, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, f"[API-AUTH-074] {r.status_code}"
    caps = set(r.json().get("effectiveCapabilities") or [])
    assert OPERATOR_CAPS.issubset(caps), f"[API-AUTH-074] missing operator defaults: {OPERATOR_CAPS - caps}"
    assert "SEE_PRICES" in caps, f"[API-AUTH-074] granted SEE_PRICES not in caps: {caps}"


@pytest.mark.rbac
def test_forbidden_two_kinds_085(api, dev_api, api_dev_roles):
    """API-AUTH-085: role-forbidden → code=FORBIDDEN; domain-forbidden → specific key."""
    r1 = api("shipper_admin").get("/super-admin/shipper-companies")
    assert r1.status_code == 403, f"[API-AUTH-085] role {r1.status_code}"
    assert _code(r1) == "FORBIDDEN", f"[API-AUTH-085] role code={_code(r1)}"
    phone, pwd, _ = api_dev_roles["shipper_warehouse"]
    r2 = dev_api.login(phone, pwd, "WEB")  # warehouse via WEB → domain wrong-app
    assert r2.status_code == 403, f"[API-AUTH-085] domain {r2.status_code}"
    assert _code(r2) == "error.wrong-app", f"[API-AUTH-085] domain code={_code(r2)}"


@pytest.mark.ratelimit
def test_wrong_app_not_counted_016(dev_api, api_dev_roles):
    """API-AUTH-016: 10× wrong-app (correct password) don't count → success afterwards."""
    phone, pwd, _ = api_dev_roles["shipper_warehouse"]
    for i in range(10):
        r = dev_api.login(phone, pwd, "WEB")
        assert r.status_code == 403 and _code(r) == "error.wrong-app", \
            f"[API-AUTH-016] attempt {i}: {r.status_code}/{_code(r)}"
    ok = dev_api.login(phone, pwd, "WAREHOUSE_APP")
    assert ok.status_code == 200, f"[API-AUTH-016] success after 10 wrong-app: {ok.status_code} {ok.text[:160]}"


@pytest.mark.iplimit
def test_ratelimit_reset_after_success_038(dev_api, api, newpwd):
    """API-AUTH-038: a success resets the phone bucket → 5 more attempts available (401, not 429).
    Marked `iplimit` — its 9 failed logins push the ratelimit group over the 30/10-min IP
    budget; run isolated via `-m iplimit`."""
    _sid, phone, _role = _make_staff(api("shipper_admin"), newpwd)
    for _ in range(4):
        assert dev_api.login(phone, "wrong", "WEB").status_code == 401
    ok = dev_api.login(phone, newpwd, "WEB")
    assert ok.status_code == 200, f"[API-AUTH-038] success should reset bucket: {ok.status_code} {ok.text[:160]}"
    codes = [dev_api.login(phone, "wrong", "WEB").status_code for _ in range(5)]
    assert all(c == 401 for c in codes), f"[API-AUTH-038] post-reset codes={codes} (429 = bucket not reset)"


# ─── DRIVER login → wrong-app (create self-employed driver on DEV) ───────────


@pytest.fixture
def driver_phone(api, newpwd):
    """Create a self-employed driver on DEV via super-admin. DRIVER is in no
    clientType's allowedRoles, so it can hit /auth/login but always 403 wrong-app."""
    vt = api("shipper_warehouse").get("/warehouse/vehicle-types").json()[0]["id"]
    phone = _rand_phone()
    r = api("super_admin").post("/super-admin/drivers",
                                json={"fullName": "AT Driver", "phone": phone, "password": newpwd, "vehicleTypeId": vt})
    assert r.status_code in (200, 201), f"driver setup: {r.status_code} {r.text[:160]}"
    return phone


# DRIVER is not in WEB / WAREHOUSE_APP allowedRoles → 403 wrong-app there.
_DRIVER_WRONGAPP = [("API-AUTH-010", "WEB"), ("API-AUTH-012", "WAREHOUSE_APP")]


@pytest.mark.rbac
@pytest.mark.parametrize("cid,ctype", _DRIVER_WRONGAPP, ids=[c[0] for c in _DRIVER_WRONGAPP])
def test_driver_login_wrong_app(dev_api, driver_phone, newpwd, cid, ctype):
    r = dev_api.login(driver_phone, newpwd, ctype)
    assert r.status_code == 403, f"[{cid}] {ctype}: {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.wrong-app", f"[{cid}] code={_code(r)}"


@pytest.mark.rbac
def test_driver_login_transport_app_011(dev_api, driver_phone, newpwd):
    """API-AUTH-011: on DEV (MNZL-269) the carrier app also admits DRIVER sign-in →
    200 + tokens. (Staging still returns 403 wrong-app; the library case is staging-era —
    update it when MNZL-269 promotes.)"""
    r = dev_api.login(driver_phone, newpwd, "TRANSPORT_COMPANY_APP")
    assert r.status_code == 200, f"[API-AUTH-011] DEV MNZL-269: {r.status_code} {r.text[:160]}"
    assert _has_tokens(r), "[API-AUTH-011] driver login returned no token pair"


def test_me_driver_072(dev_api, driver_phone, newpwd):
    """API-AUTH-072: GET /me as DRIVER (token via the carrier app) → role DRIVER, no company, caps=[]."""
    tok = dev_api.login(driver_phone, newpwd, "TRANSPORT_COMPANY_APP").json()["accessToken"]
    r = dev_api.request("GET", "/me", None, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, f"[API-AUTH-072] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("role") == "DRIVER", f"[API-AUTH-072] role={b.get('role')}"
    assert "company" not in b, f"[API-AUTH-072] company present: {b.get('company')}"
    assert b.get("effectiveCapabilities") == [], f"[API-AUTH-072] caps={b.get('effectiveCapabilities')}"


# ─── Blocked company (create burner company, PATCH active:false) ─────────────


@pytest.fixture
def blocked_company(api, dev_api, newpwd):
    n = "".join(random.choices(string.digits, k=6))
    aphone = _rand_phone()
    name, tin, prefix = f"AT-BLK-{n}", "".join(random.choices(string.digits, k=9)), \
        "".join(random.choices(string.ascii_uppercase, k=4))
    body = {"name": name, "tin": tin, "prefix": prefix, "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT Blk", "phone": aphone, "password": newpwd}}
    r = api("super_admin").post("/super-admin/shipper-companies", json=body)
    assert r.status_code in (200, 201), f"blk create: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    tok = dev_api.login(aphone, newpwd, "WEB").json()  # tokens BEFORE blocking
    rb = api("super_admin").patch(f"/super-admin/shipper-companies/{sid}", json={
        "name": name, "tin": tin, "prefix": prefix, "address": "Tashkent, Sayyod 1",
        "active": False, "admin": {"fullName": "AT Blk", "phone": aphone}})
    assert rb.status_code == 200, f"block: {rb.status_code} {rb.text[:160]}"
    yield {"phone": aphone, "tokens": tok}
    api("super_admin").delete(f"/super-admin/shipper-companies/{sid}")


def test_login_blocked_company_022(dev_api, blocked_company, newpwd):
    """API-AUTH-022: blocked-company user → 401 invalid-credentials (block hidden at login)."""
    r = dev_api.login(blocked_company["phone"], newpwd, "WEB")
    assert r.status_code == 401, f"[API-AUTH-022] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-022] code={_code(r)}"


def test_refresh_blocked_company_057(dev_api, blocked_company):
    """API-AUTH-057: refresh for a blocked-company user → 401 invalid-credentials."""
    r = dev_api.request("POST", "/auth/refresh", None,
                        json={"refreshToken": blocked_company["tokens"]["refreshToken"]})
    assert r.status_code == 401, f"[API-AUTH-057] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-057] code={_code(r)}"


@pytest.mark.high
def test_me_blocked_company_084(dev_api, blocked_company):
    """API-AUTH-084: valid token but company blocked → 403 error.company.blocked (distinct 403)."""
    r = dev_api.request("GET", "/me", None,
                        headers={"Authorization": f"Bearer {blocked_company['tokens']['accessToken']}"})
    assert r.status_code == 403, f"[API-AUTH-084] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.company.blocked", f"[API-AUTH-084] code={_code(r)}"


# ─── ug i18n (047), revoked refresh (053), throttle-bypass (041), race (100) ─


@pytest.mark.i18n
@pytest.mark.ratelimit
def test_login_invalid_ug_047(dev_api):
    r = dev_api.request("POST", "/auth/login", None,
                        json={"phone": _rand_phone(), "password": "wrong", "clientType": "WEB"},
                        headers={"Accept-Language": "ug"})
    assert r.status_code == 401, f"[API-AUTH-047] {r.status_code}"
    assert _detail(r) == "ئىشلەتكۈچى ئىسمى ياكى مەخپىي نومۇر خاتا", f"[API-AUTH-047] detail={_detail(r)!r}"


def test_refresh_revoked_053(dev_api, api_dev_roles):
    """API-AUTH-053: refresh with a revoked (logged-out) token → 401 invalid-credentials."""
    tok = _fresh_login(dev_api, api_dev_roles)
    dev_api.request("POST", "/auth/logout", None, json={"refreshToken": tok["refreshToken"]})
    r = dev_api.request("POST", "/auth/refresh", None, json={"refreshToken": tok["refreshToken"]})
    assert r.status_code == 401, f"[API-AUTH-053] {r.status_code}"
    assert _code(r) == "error.invalid-credentials", f"[API-AUTH-053] code={_code(r)}"


@pytest.mark.iplimit
def test_throttle_before_credentials_041(dev_api, api, newpwd):
    """API-AUTH-041: after 5 fails, even the correct password → 429 (limit checked first).
    Marked `iplimit` — run isolated: its 5 failures + the other rate-limit tests together
    exceed the 30/10-min IP bucket. Run with `-m iplimit` on its own."""
    _sid, phone, _role = _make_staff(api("shipper_admin"), newpwd)
    for _ in range(5):
        dev_api.login(phone, "wrong", "WEB")
    r = dev_api.login(phone, newpwd, "WEB")
    assert r.status_code == 429, f"[API-AUTH-041] correct pw after 5 fails: {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.too-many-attempts", f"[API-AUTH-041] code={_code(r)}"


def test_device_register_race_100(cfg, api_dev_roles):
    """API-AUTH-100: concurrent registration of the same NEW emasDeviceId → one 200, the rest
    409 error.device.register-conflict. TRUE concurrency needs one HTTP session per thread (a
    shared requests.Session serializes → upsert → no conflict). Retries a few rounds; if the
    in-flight conflict never engages, FAIL (a real signal about the guard) — never skip."""
    import concurrent.futures as cf
    from utils.api_client import ApiClient
    phone, pwd, ctype = api_dev_roles["shipper_warehouse"]
    clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(6)]  # own Session each
    tok = clients[0].token(phone, pwd, ctype)
    for _round in range(3):
        body = {"emasDeviceId": f"race-{uuid.uuid4().hex[:8]}", "platform": "ANDROID",
                "app": "WAREHOUSE", "language": "ru"}
        with cf.ThreadPoolExecutor(max_workers=len(clients)) as ex:
            rs = [f.result() for f in [ex.submit(c.request, "POST", "/me/devices", tok, json=body)
                                       for c in clients]]
        conflicts = [r for r in rs if r.status_code == 409]
        if conflicts:
            assert any(r.status_code == 200 for r in rs), \
                f"[API-AUTH-100] conflict without a winner: {[r.status_code for r in rs]}"
            assert all(_code(r) == "error.device.register-conflict" for r in conflicts), \
                f"[API-AUTH-100] 409 codes: {[_code(r) for r in conflicts]}"
            return
    pytest.fail("[API-AUTH-100] concurrent 409 register-conflict not observed in 3 rounds "
                "of 6-way concurrency — the in-flight guard may be missing")


# NOTE: three cases are genuinely NOT black-box automatable — the X-Forwarded-For rightmost-hop
# (nginx owns the header), the refresh fail-open on a DB fault (needs fault injection), and the
# non-UUID-subject JWT (needs the Keycloak signing key). They carry `"automation": "backend"` in
# the JSON (→ docs/testcases/NON-AUTO.md; backend integration tests in manzil-core), with no code
# here. Everything else is automated (IP-bucket / sliding-window cases are executable but heavy →
# `iplimit`/`slow`, run isolated via run_ratelimit.sh, deselected from the main run).


@pytest.mark.iplimit
def test_ip_ratelimit_31st_039(dev_api):
    """API-AUTH-039: 30 failed logins from one IP (different phones) → the next → 429 by IP."""
    for _ in range(30):
        dev_api.login(_rand_phone(), "wrong", "WEB")
    r = dev_api.login(_rand_phone(), "wrong", "WEB")
    assert r.status_code == 429, f"[API-AUTH-039] 31st: {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.too-many-attempts", f"[API-AUTH-039] code={_code(r)}"


@pytest.mark.iplimit
def test_ip_bucket_not_reset_by_success_040(dev_api, api, newpwd):
    """API-AUTH-040: a success resets the PHONE bucket but not the IP bucket → IP still 429s."""
    _sid, phone, _role = _make_staff(api("shipper_admin"), newpwd)
    for _ in range(29):
        dev_api.login(_rand_phone(), "wrong", "WEB")
    ok = dev_api.login(phone, newpwd, "WEB")
    assert ok.status_code == 200, f"[API-AUTH-040] success at 29 fails: {ok.status_code}"
    r = dev_api.login(_rand_phone(), "wrong", "WEB")
    assert r.status_code == 429, f"[API-AUTH-040] IP bucket after success: {r.status_code}"
    assert _code(r) == "error.too-many-attempts", f"[API-AUTH-040] code={_code(r)}"


@pytest.mark.slow
def test_ratelimit_sliding_window_042(dev_api, cfg):
    """API-AUTH-042: attempts older than the 10-min window drop off → not 429 afterwards.
    Real 11-min wait — `slow`, run standalone (`-m slow`)."""
    import time
    phone = cfg.ratelimit_phone_2 or _rand_phone()
    for _ in range(5):
        dev_api.login(phone, "wrong", "WEB")
    time.sleep(11 * 60)
    r = dev_api.login(phone, "wrong", "WEB")
    assert r.status_code != 429, f"[API-AUTH-042] after window still 429: {r.text[:160]}"
