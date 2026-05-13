"""Account drawer: per-role identity + logout.

The drawer (right side panel) shows: name, role label, company name,
email; menu items (Профиль, Уведомления); logout button. Role label is
visible — confirms the realm role binding rendered correctly.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages._common.account_drawer import AccountDrawer
from web_ui.pages.auth.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_drawer_shows_admin_role_and_email(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    drawer = AccountDrawer(supplier_admin_page)
    drawer.open()
    expect(supplier_admin_page.get_by_text(settings.supplier_admin_real_email)).to_be_visible()
    expect(supplier_admin_page.get_by_text("Поставщик · Администратор")).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_drawer_shows_dispatcher_role(
    supplier_dispatcher_page, settings: Settings,
) -> None:
    supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/orders")
    AccountDrawer(supplier_dispatcher_page).open()
    expect(
        supplier_dispatcher_page.get_by_text(settings.supplier_dispatcher_real_email),
    ).to_be_visible()
    expect(
        supplier_dispatcher_page.get_by_text("Поставщик · Диспетчер"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_drawer_shows_manager_role(
    supplier_manager_page, settings: Settings,
) -> None:
    supplier_manager_page.goto(f"{settings.web_base_url_str}/orders")
    AccountDrawer(supplier_manager_page).open()
    expect(
        supplier_manager_page.get_by_text(settings.supplier_manager_real_email),
    ).to_be_visible()
    expect(
        supplier_manager_page.get_by_text("Поставщик · Менеджер"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_logout_returns_to_login_page(anon_page, settings: Settings) -> None:
    """Logout via UI redirects back to /auth/login.

    Uses a FRESH anon login (not the cached storage_state) to avoid
    revoking the session that other tests in the same run rely on.
    """
    login = LoginPage(anon_page, settings.web_base_url_str)
    login.goto()
    login.login(
        email=settings.supplier_admin_real_email,
        password=settings.real_account_password,
    )
    anon_page.wait_for_url("**/dashboard*")
    AccountDrawer(anon_page).logout()
    anon_page.wait_for_url("**/auth/login*")
    LoginPage(anon_page, settings.web_base_url_str).expect_loaded()
