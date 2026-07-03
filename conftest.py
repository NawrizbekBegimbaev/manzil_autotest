"""Pytest fixtures: config, browser context args, provisioning, role sessions.

Login model: phone + password, no OTP. SUPER_ADMIN comes from `.env`; ADMIN /
MANAGER / CARRIER are **provisioned by the suite itself** — SUPER_ADMIN creates a
shipper company (→ ADMIN login) and a transport company (→ CARRIER login), and
the shipper ADMIN creates a "Менеджер" staff member (→ MANAGER login). Every role
logs in once per run; its context is reused (no UI logout to switch user). The
provisioned tenants are deleted at session end.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext

from config.settings import Settings, get_settings
from pages.auth.login_page import LoginPage
from pages.shipper.staff_page import StaffPage
from pages.super_admin.shipper_companies_page import ShipperCompaniesPage
from pages.super_admin.transport_companies_page import TransportCompaniesPage
from utils.data import CarrierData, ShipperData, StaffData, TenantCreds


@pytest.fixture(scope="session")
def cfg() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def context_kwargs(cfg: Settings) -> dict:
    return {
        # 1920 wide so the DataGrid «Операции» column (row ⋮ action menu) renders —
        # at 1440 the grid horizontally virtualizes it away and row actions vanish.
        "viewport": {"width": 1920, "height": 1080},
        "locale": cfg.locale,
        "timezone_id": cfg.timezone,
        "ignore_https_errors": True,
    }


# Force the SPA UI language to Russian (assertions are RU). The app persists the
# Tolgee language in localStorage; staging's default can be zh/uz, so we pin it
# before any page script runs.
_FORCE_RU = "try{localStorage.setItem('__tolgee_currentLanguage','ru');}catch(e){}"


def _new_context(browser: Browser, cfg: Settings, kwargs: dict) -> BrowserContext:
    ctx = browser.new_context(**kwargs)
    ctx.add_init_script(_FORCE_RU)
    ctx.set_default_timeout(cfg.default_timeout_ms)
    ctx.set_default_navigation_timeout(cfg.nav_timeout_ms)
    return ctx


def _logged_in_page(browser: Browser, cfg: Settings, kwargs: dict, phone: str, password: str):
    ctx = _new_context(browser, cfg, kwargs)
    page = ctx.new_page()
    LoginPage(page, cfg).login(phone, password)
    return ctx, page


# ─── SUPER_ADMIN (from .env) ─────────────────────────────────────────────────
@pytest.fixture(scope="session")
def super_admin_page(browser: Browser, cfg: Settings, context_kwargs: dict):
    if not cfg.has_creds("super_admin"):
        pytest.skip("No SUPER_ADMIN credentials configured (.env)")
    ctx, page = _logged_in_page(
        browser, cfg, context_kwargs, *cfg.creds("super_admin")
    )
    yield page
    ctx.close()


# ─── Provisioning: ADMIN + CARRIER + MANAGER created by the suite ───────────-
def _is_create(resp, suffix: str) -> bool:
    return resp.request.method == "POST" and resp.url.rstrip("/").endswith(suffix)


@pytest.fixture(scope="session")
def provisioned(
    super_admin_page, browser: Browser, cfg: Settings, context_kwargs: dict
) -> TenantCreds:
    pwd = cfg.new_account_password
    if not pwd:
        pytest.skip("NEW_ACCOUNT_PASSWORD not set (.env) — cannot provision roles")

    # 1) Shipper company → ADMIN login
    sp = ShipperCompaniesPage(super_admin_page, cfg).open()
    sd = ShipperData()
    sp.open_create().fill_create(sd, pwd)
    with super_admin_page.expect_response(
        lambda r: _is_create(r, "/super-admin/shipper-companies")
    ) as r1:
        sp.submit()
    assert r1.value.status in (200, 201), f"shipper provision: {r1.value.status}"

    # 2) Transport company → CARRIER login
    cp = TransportCompaniesPage(super_admin_page, cfg).open()
    cd = CarrierData()
    cp.open_create().fill_create(cd, pwd)
    with super_admin_page.expect_response(
        lambda r: _is_create(r, "/super-admin/transport-companies")
    ) as r2:
        cp.submit()
    assert r2.value.status in (200, 201), f"carrier provision: {r2.value.status}"

    # 3) Shipper ADMIN creates a "Менеджер" staff → MANAGER login
    admin_ctx, admin_page = _logged_in_page(browser, cfg, context_kwargs, sd.phone, pwd)
    md = StaffData()
    staff = StaffPage(admin_page, cfg).open().open_create()
    with admin_page.expect_response(lambda r: _is_create(r, "/shipper/staff")) as r3:
        staff.create(md, pwd, "Менеджер")
    assert r3.value.status in (200, 201), f"manager provision: {r3.value.status}"

    # 4) Shipper ADMIN creates a "Сотрудник склада" staff → WAREHOUSE login (mobile + API-seed)
    wh = StaffData()
    staff_wh = StaffPage(admin_page, cfg).open().open_create()
    with admin_page.expect_response(lambda r: _is_create(r, "/shipper/staff")) as r4:
        staff_wh.create(wh, pwd, "Сотрудник склада")
    assert r4.value.status in (200, 201), f"warehouse provision: {r4.value.status}"
    admin_ctx.close()

    creds = TenantCreds(
        password=pwd,
        admin_phone=sd.phone,
        carrier_phone=cd.phone,
        manager_phone=md.phone,
        shipper_name=sd.name,
        carrier_name=cd.name,
        warehouse_phone=wh.phone,
    )
    yield creds

    # Teardown: delete the tenants (cascades their staff/logins).
    for pageklass, name in (
        (ShipperCompaniesPage, sd.name),
        (TransportCompaniesPage, cd.name),
    ):
        try:
            pageklass(super_admin_page, cfg).open().delete_row(name)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


# ─── Provisioned role sessions ───────────────────────────────────────────────
@pytest.fixture
def make_login(browser: Browser, cfg: Settings, context_kwargs: dict):
    """Factory → logged-in Page in a fresh context (RU pinned). Cleaned up after test."""
    contexts = []

    def _login(phone: str, password: str):
        ctx, page = _logged_in_page(browser, cfg, context_kwargs, phone, password)
        contexts.append(ctx)
        return page

    yield _login
    for ctx in contexts:
        ctx.close()


@pytest.fixture(scope="session")
def admin_page(browser: Browser, cfg: Settings, context_kwargs: dict, provisioned: TenantCreds):
    ctx, page = _logged_in_page(
        browser, cfg, context_kwargs, provisioned.admin_phone, provisioned.password
    )
    yield page
    ctx.close()


@pytest.fixture(scope="session")
def manager_page(browser: Browser, cfg: Settings, context_kwargs: dict, provisioned: TenantCreds):
    ctx, page = _logged_in_page(
        browser, cfg, context_kwargs, provisioned.manager_phone, provisioned.password
    )
    yield page
    ctx.close()


@pytest.fixture(scope="session")
def carrier_page(browser: Browser, cfg: Settings, context_kwargs: dict, provisioned: TenantCreds):
    ctx, page = _logged_in_page(
        browser, cfg, context_kwargs, provisioned.carrier_phone, provisioned.password
    )
    yield page
    ctx.close()


@pytest.fixture(scope="session")
def seeder(provisioned: TenantCreds, cfg: Settings):
    """API-seed helper to prepare orders in a desired status (web preconditions)."""
    from utils.api_seed import ApiSeed

    return ApiSeed(cfg, provisioned)
