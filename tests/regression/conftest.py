"""Regression-suite fixtures — DEV-targeted, fully isolated from the staging UAT.

The daily UAT (``tests/uat``) keeps using the root ``conftest`` against staging.
This suite instead:

* points every client at ``cfg.dev_url``;
* provisions a **fresh tenant on DEV via API** at session start (shipper company +
  transport company + a staff member per shipper role), and **deletes it** at
  teardown — nothing persists between runs;
* caches **one login per role** (``ApiClient.token`` under a lock);
* exposes ``dev_api`` (raw, unauthenticated — for login/refresh/logout/ratelimit
  cases) and ``api(role)`` (a Bearer-bound thin client for role-gated cases).

Provisioning contracts follow CLAUDE.md → «Важные грабли» (tin 9 digits, prefix 4
upper-latin, address ≥2 chars, ``PATCH /shipper/staff`` with a FULL body to grant
capabilities).
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass, field

import pytest

from config.settings import get_settings
from utils.api_client import ApiClient

# Password for every account this suite creates on DEV — sourced from .env
# (DEV_ACCOUNT_PASSWORD), never hardcoded. Created-on-dev throwaways only.
NEW_PWD = get_settings().dev_account_password
ADDR = "Tashkent, Sayyod 1"

# Shipper staff roles to provision (role → clientType for its login).
SHIPPER_STAFF_ROLES = {
    "shipper_manager": ("SHIPPER_MANAGER", "WEB"),
    "shipper_operator": ("SHIPPER_OPERATOR", "WEB"),
    "shipper_warehouse": ("SHIPPER_WAREHOUSE", "WAREHOUSE_APP"),
    "shipper_dispatcher": ("SHIPPER_DISPATCHER", "WEB"),
}


def _digits(n: int) -> str:
    return "".join(random.choices(string.digits, k=n))


def _uphone() -> str:
    return "+99890" + _digits(7)


def _utin() -> str:
    return _digits(9)


def _uprefix() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=4))


def _uname(kind: str) -> str:
    # 10 цифр — иначе имена компаний коллидят с орфанами прошлых прогонов (409 name-already-used)
    return f"AT-{kind}-{_digits(10)}"


@dataclass
class DevTenant:
    """Everything a regression test needs to log in as any provisioned role.

    ``roles`` maps a role key → (phone, password, clientType).
    """

    shipper_id: str
    transport_id: str
    roles: dict[str, tuple[str, str, str]] = field(default_factory=dict)


# ─── raw client + retry helpers (DEV is intermittently flaky) ────────────────


@pytest.fixture(scope="session")
def cfg():
    return get_settings()


@pytest.fixture(scope="session")
def dev_api(cfg):
    """Raw, unauthenticated API client pointed at DEV. Use for login / refresh /
    logout / ratelimit cases that must not share the token cache."""
    if not cfg.dev_super_admin_phone or not cfg.dev_super_admin_password:
        pytest.skip("DEV_SUPER_ADMIN_* not set (.env) — regression needs DEV access")
    if not cfg.dev_account_password:
        pytest.skip("DEV_ACCOUNT_PASSWORD not set (.env) — cannot provision tenant")
    return ApiClient(cfg, base_url=cfg.dev_url)


def _post(api: ApiClient, path: str, token: str, body: dict, retries: int = 5, ok=(200, 201)):
    r = None
    for _ in range(retries):
        r = api.request("POST", path, token, json=body)
        if r.status_code in ok:
            return r
        time.sleep(3)
    raise RuntimeError(f"POST {path}: {r.status_code if r else '?'} {(r.text[:160] if r else '')}")


def _login(api: ApiClient, phone: str, client_type: str, pwd: str = NEW_PWD, retries: int = 8) -> str:
    r = None
    for _ in range(retries):
        r = api.login(phone, pwd, client_type)
        if r.status_code == 200:
            return r.json()["accessToken"]
        time.sleep(3)
    raise RuntimeError(f"login {phone}/{client_type}: {r.status_code if r else '?'}")


# ─── fresh tenant on DEV (session-scoped) ────────────────────────────────────


@pytest.fixture(scope="session")
def dev_tenant(cfg, dev_api) -> DevTenant:
    sa = _login(dev_api, cfg.dev_super_admin_phone, "WEB", cfg.dev_super_admin_password)

    # 1) Shipper company → ADMIN
    aphone = _uphone()
    sid = _post(dev_api, "/super-admin/shipper-companies", sa, {
        "name": _uname("SC"), "tin": _utin(), "prefix": _uprefix(), "address": ADDR,
        "admin": {"fullName": "AT Admin", "phone": aphone, "password": NEW_PWD},
    }).json()["id"]

    # 2) Transport company → CARRIER
    cphone = _uphone()
    tid = _post(dev_api, "/super-admin/transport-companies", sa, {
        "name": _uname("TC"), "tin": _utin(), "address": ADDR,
        "admin": {"fullName": "AT Carrier", "phone": cphone, "password": NEW_PWD},
    }).json()["id"]

    roles: dict[str, tuple[str, str, str]] = {
        "super_admin": (cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB"),
        "shipper_admin": (aphone, NEW_PWD, "WEB"),
        "transport_admin": (cphone, NEW_PWD, "TRANSPORT_COMPANY_APP"),
    }

    # 3) Shipper staff, one per role
    adm = _login(dev_api, aphone, "WEB")
    for key, (role, ctype) in SHIPPER_STAFF_ROLES.items():
        phone = _uphone()
        _post(dev_api, "/shipper/staff", adm, {
            "fullName": f"AT {role}", "phone": phone, "password": NEW_PWD, "role": role,
        })
        roles[key] = (phone, NEW_PWD, ctype)

    tenant = DevTenant(shipper_id=sid, transport_id=tid, roles=roles)
    yield tenant

    # Teardown — delete both companies (cascades staff/logins). Best-effort.
    for path in (f"/super-admin/shipper-companies/{sid}",
                 f"/super-admin/transport-companies/{tid}"):
        try:
            dev_api.request("DELETE", path, sa)
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture(scope="session")
def api_dev_roles(dev_tenant) -> dict[str, tuple[str, str, str]]:
    """role → (phone, password, clientType) for every provisioned role."""
    return dict(dev_tenant.roles)


# ─── Bearer-bound thin client, `api(role)` factory ───────────────────────────


class RoleClient:
    """Wraps the shared DEV ApiClient with a fixed role token; verbs auto-attach
    the Bearer. Assertions live in the tests — verbs never raise on 4xx/5xx."""

    def __init__(self, client: ApiClient, token: str):
        self._c = client
        self.token = token

    def get(self, path: str, **kw):
        return self._c.request("GET", path, self.token, **kw)

    def post(self, path: str, **kw):
        return self._c.request("POST", path, self.token, **kw)

    def put(self, path: str, **kw):
        return self._c.request("PUT", path, self.token, **kw)

    def patch(self, path: str, **kw):
        return self._c.request("PATCH", path, self.token, **kw)

    def delete(self, path: str, **kw):
        return self._c.request("DELETE", path, self.token, **kw)

    def request(self, method: str, path: str, **kw):
        return self._c.request(method, path, self.token, **kw)


@pytest.fixture(scope="session")
def api(dev_api, api_dev_roles):
    """Factory: ``api(role)`` → RoleClient with the role's Bearer already set.
    One login per role per run (ApiClient.token cache)."""
    cache: dict[str, RoleClient] = {}

    def _for(role: str) -> RoleClient:
        if role not in cache:
            phone, pwd, ctype = api_dev_roles[role]
            tok = dev_api.token(phone, pwd, ctype)
            cache[role] = RoleClient(dev_api, tok)
        return cache[role]

    return _for


# ─── registration (MNZL-269) provisioning ───────────────────────────────────


@pytest.fixture(scope="session")
def reg_phone():
    """Factory → a fresh, unregistered +99890 phone for the registration cases.

    Dedicated to registration/reset OTP flows: negatives create no account (the
    challenge expires in 5 min), so nothing persists. Never reuses the ratelimit
    or provisioned-tenant phones."""
    return _uphone


@pytest.fixture(scope="session")
def vehicle_type_id(dev_api, api_dev_roles) -> str:
    """First vehicle-type id on DEV — needed to create the admin-side driver used by
    the login / clientType / verification-review cases (no OTP path)."""
    sa = dev_api.token(*api_dev_roles["super_admin"])
    r = dev_api.request("GET", "/super-admin/vehicle-types?page=0&size=1", sa)
    if r.status_code != 200:
        pytest.skip(f"vehicle-types unavailable on DEV: {r.status_code}")
    body = r.json()
    items = body.get("content", body if isinstance(body, list) else [])
    if not items:
        pytest.skip("no vehicle types on DEV — cannot provision an admin driver")
    return items[0]["id"]


@dataclass
class AdminDriver:
    """A VERIFIED self-employed driver created via the super-admin API (no OTP).

    Stands in for a transporter account in the cases that don't need the PENDING
    self-registration state: driver login / wrong-app, verification-review on an
    already-transporter, the verificationStatus list filter.
    """

    driver_id: str
    user_id: str
    phone: str
    password: str
    status: str


@pytest.fixture(scope="session")
def admin_driver(dev_api, api_dev_roles, vehicle_type_id) -> AdminDriver:
    """Create one self-employed driver (role DRIVER, VERIFIED) on DEV via
    ``POST /super-admin/drivers`` — no OTP involved — and delete it at teardown."""
    sa = dev_api.token(*api_dev_roles["super_admin"])
    phone = _uphone()
    r = _post(dev_api, "/super-admin/drivers", sa, {
        "fullName": _uname("REGDRV"), "phone": phone, "password": NEW_PWD,
        "vehicleTypeId": vehicle_type_id, "cardId": "AA" + _digits(7),
    })
    body = r.json()
    drv = AdminDriver(driver_id=body["id"], user_id=body["userId"], phone=phone,
                      password=NEW_PWD, status=body.get("verificationStatus", "VERIFIED"))
    yield drv
    try:
        dev_api.request("DELETE", f"/super-admin/drivers/{drv.driver_id}", sa)
    except Exception:  # noqa: BLE001
        pass


def _make_driver(dev_api, sa: str, vehicle_type_id: str, active: bool) -> tuple[str, str]:
    """Create a self-employed driver via super-admin; return (driver_id, phone)."""
    phone = _uphone()
    r = _post(dev_api, "/super-admin/drivers", sa, {
        "fullName": _uname("REGST"), "phone": phone, "password": NEW_PWD,
        "vehicleTypeId": vehicle_type_id, "cardId": "AA" + _digits(7), "active": active,
    })
    return r.json()["id"], phone


@pytest.fixture(scope="session")
def blocked_driver_phone(dev_api, api_dev_roles, vehicle_type_id) -> str:
    """Phone of a DEACTIVATED (active=false) driver — 'phone taken' for registration."""
    sa = dev_api.token(*api_dev_roles["super_admin"])
    did, phone = _make_driver(dev_api, sa, vehicle_type_id, active=False)
    yield phone
    try:
        dev_api.request("DELETE", f"/super-admin/drivers/{did}", sa)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture(scope="session")
def deleted_driver_phone(dev_api, api_dev_roles, vehicle_type_id) -> str:
    """Phone of a SOFT-DELETED driver — still 'phone taken' (no self-service revive)."""
    sa = dev_api.token(*api_dev_roles["super_admin"])
    did, phone = _make_driver(dev_api, sa, vehicle_type_id, active=True)
    dev_api.request("DELETE", f"/super-admin/drivers/{did}", sa)  # soft-delete now
    return phone


@pytest.fixture(scope="session")
def shipper_user_id(dev_api, api_dev_roles) -> str:
    """The SHIPPER_ADMIN's own user id (via /me) — a NON-transporter subject for the
    verification-review 'not-a-transporter' case."""
    tok = dev_api.token(*api_dev_roles["shipper_admin"])
    r = dev_api.request("GET", "/me", tok)
    if r.status_code != 200:
        pytest.skip(f"/me unavailable for shipper_admin: {r.status_code}")
    return r.json()["id"]


# ─── order-lifecycle provisioning ────────────────────────────────────────────


@pytest.fixture
def order_factory(dev_api, api_dev_roles):
    """Factory → order in any lifecycle status via the honest API chain (company A).
    Warehouse creates, carrier bids/drives, admin selects/completes/cancels.
    Every created order is driven to a terminal state and deleted at teardown."""
    from tests.regression.order_lifecycle import OrderFactory

    f = OrderFactory(
        dev_api,
        dev_api.token(*api_dev_roles["super_admin"]),
        dev_api.token(*api_dev_roles["shipper_warehouse"]),
        dev_api.token(*api_dev_roles["shipper_admin"]),
        dev_api.token(*api_dev_roles["transport_admin"]),
    )
    yield f
    f.teardown()
