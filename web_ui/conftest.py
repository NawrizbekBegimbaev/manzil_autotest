"""Web-UI conftest — browser/context/page fixtures and role helpers.

Why a custom layer instead of plain pytest-playwright defaults:
- We share two real Keycloak accounts (Supplier, TK) across tests, so we
  cache their `storage_state` (cookies + Bearer JWT in localStorage) on
  disk after the first login. Subsequent tests open a fresh context with
  the cached state and skip the login screen entirely — fast AND
  faithful (real session, not a backdoor).
- For cross-role e2e we need TWO contexts in one test, each with its own
  role's storage. Plain `page` fixture is single-role.
- Cleanup of created data (orders/warehouses/vehicles/offers) goes
  through the API, not the UI — much faster, more reliable, and the API
  client is already set up.

Markers:
    `requires_real_account` — uses the shared accounts (xdist-unsafe per
                               account; mark as @serial too if mutating).
    `ui_supplier` / `ui_tk` / `ui_cross` — role classification.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import WebLoginRequest
from config.settings import Settings
from web_ui.pages._common.account_drawer import AccountDrawer
from web_ui.pages._common.sidebar import Sidebar
from web_ui.pages.auth.login_page import LoginPage

# ---------- Playwright lifecycle (session-scoped) -------------------------


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright: Playwright, settings: Settings) -> Iterator[Browser]:
    """One headless Chromium per test session.

    Set UI_HEADED=1 in `.env` to watch locally; CI keeps it headless.
    """
    browser_obj = playwright.chromium.launch(
        headless=not settings.ui_headed,
        slow_mo=settings.ui_slow_mo_ms,
    )
    try:
        yield browser_obj
    finally:
        browser_obj.close()


# ---------- storage-state cache (per-role, session-scoped) -----------------
#
# After first successful UI login, save cookies+localStorage to a JSON file.
# Subsequent contexts load from this file so most tests skip the login form.

_STATE_DIR = Path(".playwright-state")


def _state_path(role: str) -> Path:
    return _STATE_DIR / f"{role}.json"


def _login_and_save_state(
    *, browser: Browser, settings: Settings, email: str, password: str, role: str,
) -> Path:
    """Open a fresh context, perform a real UI login, save the state."""
    _STATE_DIR.mkdir(exist_ok=True)
    context = browser.new_context(base_url=settings.web_base_url_str)
    context.set_default_timeout(settings.ui_default_timeout_ms)
    page = context.new_page()
    login = LoginPage(page, settings.web_base_url_str)
    login.goto()
    login.login(email=email, password=password)
    # Landing page by role:
    #   TK_ADMIN              → /feed
    #   SUPPLIER_ADMIN        → /dashboard
    #   SUPPLIER_DISPATCHER   → /orders
    #   SUPPLIER_MANAGER      → /orders
    landing_glob = {
        "tk": "**/feed*",
        "supplier_admin": "**/dashboard*",
        "supplier_dispatcher": "**/orders*",
        "supplier_manager": "**/orders*",
    }[role]
    page.wait_for_url(landing_glob, timeout=settings.ui_default_timeout_ms)
    target = _state_path(role)
    context.storage_state(path=str(target))
    context.close()
    return target


@pytest.fixture(scope="session")
def supplier_admin_storage_state(browser: Browser, settings: Settings) -> Path:
    return _login_and_save_state(
        browser=browser,
        settings=settings,
        email=settings.supplier_admin_real_email,
        password=settings.real_account_password,
        role="supplier_admin",
    )


@pytest.fixture(scope="session")
def supplier_dispatcher_storage_state(browser: Browser, settings: Settings) -> Path:
    return _login_and_save_state(
        browser=browser,
        settings=settings,
        email=settings.supplier_dispatcher_real_email,
        password=settings.real_account_password,
        role="supplier_dispatcher",
    )


@pytest.fixture(scope="session")
def supplier_manager_storage_state(browser: Browser, settings: Settings) -> Path:
    return _login_and_save_state(
        browser=browser,
        settings=settings,
        email=settings.supplier_manager_real_email,
        password=settings.real_account_password,
        role="supplier_manager",
    )


# Backwards-compatibility alias — legacy `supplier_storage_state` was the
# admin login. Keep it pointing at the admin so existing smoke tests stay
# valid without edit churn.
@pytest.fixture(scope="session")
def supplier_storage_state(supplier_admin_storage_state: Path) -> Path:
    return supplier_admin_storage_state


@pytest.fixture(scope="session")
def tk_storage_state(browser: Browser, settings: Settings) -> Path:
    return _login_and_save_state(
        browser=browser,
        settings=settings,
        email=settings.tk_real_email,
        password=settings.real_account_password,
        role="tk",
    )


# ---------- per-test contexts (function-scoped) ---------------------------


def _new_context(
    browser: Browser, settings: Settings, *, storage_state: Path | None = None,
) -> BrowserContext:
    context = browser.new_context(
        base_url=settings.web_base_url_str,
        storage_state=str(storage_state) if storage_state else None,
        record_video_dir=None,
    )
    context.set_default_timeout(settings.ui_default_timeout_ms)
    if settings.ui_trace_on_failure:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
    return context


def _stop_tracing(context: BrowserContext, settings: Settings, *, name: str) -> None:
    if not settings.ui_trace_on_failure:
        return
    trace_dir = Path("playwright-traces")
    trace_dir.mkdir(exist_ok=True)
    context.tracing.stop(path=str(trace_dir / f"{name}.zip"))


@pytest.fixture
def anon_context(
    browser: Browser, settings: Settings, request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    """Anonymous (no storage) — for login/registration form tests."""
    context = _new_context(browser, settings)
    try:
        yield context
    finally:
        _stop_tracing(context, settings, name=request.node.name + "-anon")
        context.close()


@pytest.fixture
def anon_page(anon_context: BrowserContext) -> Page:
    return anon_context.new_page()


def _supplier_role_context(
    browser: Browser,
    settings: Settings,
    storage_state: Path,
    request: pytest.FixtureRequest,
    role_label: str,
) -> Iterator[BrowserContext]:
    context = _new_context(browser, settings, storage_state=storage_state)
    try:
        yield context
    finally:
        _stop_tracing(context, settings, name=f"{request.node.name}-{role_label}")
        context.close()


@pytest.fixture
def supplier_admin_context(
    browser: Browser,
    settings: Settings,
    supplier_admin_storage_state: Path,
    request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    yield from _supplier_role_context(
        browser, settings, supplier_admin_storage_state, request, "supplier-admin",
    )


@pytest.fixture
def supplier_admin_page(supplier_admin_context: BrowserContext) -> Page:
    return supplier_admin_context.new_page()


@pytest.fixture
def supplier_dispatcher_context(
    browser: Browser,
    settings: Settings,
    supplier_dispatcher_storage_state: Path,
    request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    yield from _supplier_role_context(
        browser, settings, supplier_dispatcher_storage_state, request,
        "supplier-dispatcher",
    )


@pytest.fixture
def supplier_dispatcher_page(supplier_dispatcher_context: BrowserContext) -> Page:
    return supplier_dispatcher_context.new_page()


@pytest.fixture
def supplier_manager_context(
    browser: Browser,
    settings: Settings,
    supplier_manager_storage_state: Path,
    request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    yield from _supplier_role_context(
        browser, settings, supplier_manager_storage_state, request,
        "supplier-manager",
    )


@pytest.fixture
def supplier_manager_page(supplier_manager_context: BrowserContext) -> Page:
    return supplier_manager_context.new_page()


# Legacy aliases (admin = default supplier).
@pytest.fixture
def supplier_context(supplier_admin_context: BrowserContext) -> BrowserContext:
    return supplier_admin_context


@pytest.fixture
def supplier_page(supplier_admin_page: Page) -> Page:
    return supplier_admin_page


@pytest.fixture
def tk_context(
    browser: Browser,
    settings: Settings,
    tk_storage_state: Path,
    request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    """Authenticated as the real TK_Admin account."""
    context = _new_context(browser, settings, storage_state=tk_storage_state)
    try:
        yield context
    finally:
        _stop_tracing(context, settings, name=request.node.name + "-tk")
        context.close()


@pytest.fixture
def tk_page(tk_context: BrowserContext) -> Page:
    return tk_context.new_page()


# ---------- API-backdoor clients for cleanup / setup ----------------------


def _api_client_for(settings: Settings, *, email: str, password: str) -> ApiClient:
    """Return an API client logged in as the given real account.

    Used for fast teardown (delete created warehouses/vehicles/orders) and
    occasional setup (create a published order so a TK-side test has
    something to react to).
    """
    client = ApiClient(settings)
    tokens = auth_ep.web_login(client, WebLoginRequest(email=email, password=password))
    client.set_token(tokens.access_token)
    return client


@pytest.fixture
def supplier_admin_api(settings: Settings) -> Iterator[ApiClient]:
    client = _api_client_for(
        settings,
        email=settings.supplier_admin_real_email,
        password=settings.real_account_password,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def supplier_dispatcher_api(settings: Settings) -> Iterator[ApiClient]:
    client = _api_client_for(
        settings,
        email=settings.supplier_dispatcher_real_email,
        password=settings.real_account_password,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def supplier_manager_api(settings: Settings) -> Iterator[ApiClient]:
    client = _api_client_for(
        settings,
        email=settings.supplier_manager_real_email,
        password=settings.real_account_password,
    )
    try:
        yield client
    finally:
        client.close()


# Legacy alias used by older code: `supplier_api` ≡ `supplier_admin_api`.
@pytest.fixture
def supplier_api(supplier_admin_api: ApiClient) -> ApiClient:
    return supplier_admin_api


@pytest.fixture
def tk_api(settings: Settings) -> Iterator[ApiClient]:
    client = _api_client_for(
        settings,
        email=settings.tk_real_email,
        password=settings.real_account_password,
    )
    try:
        yield client
    finally:
        client.close()


# ---------- common page helpers (cheap re-bind on each test) --------------


@pytest.fixture
def supplier_sidebar(supplier_admin_page: Page) -> Sidebar:
    return Sidebar(supplier_admin_page)


@pytest.fixture
def tk_sidebar(tk_page: Page) -> Sidebar:
    return Sidebar(tk_page)


@pytest.fixture
def supplier_account(supplier_admin_page: Page) -> AccountDrawer:
    return AccountDrawer(supplier_admin_page)


@pytest.fixture
def tk_account(tk_page: Page) -> AccountDrawer:
    return AccountDrawer(tk_page)
