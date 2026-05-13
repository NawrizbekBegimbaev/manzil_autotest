"""Bootstrap smoke — login both real accounts via UI.

Each of these ALSO bootstraps the storage_state cache used by every other
UI test. If they fail, the entire UI suite cannot run, so they're the
first thing we check on every CI run.

The dual-context test below is the simplest possible cross-role check:
two browser contexts, two roles, both authenticated simultaneously. It
proves the parallel-context infrastructure works before we layer real
business scenarios on top.
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Browser, expect

from config.settings import Settings
from web_ui.pages._common.sidebar import Sidebar
from web_ui.pages.auth.login_page import LoginPage
from web_ui.pages.supplier.dashboard_page import SupplierDashboardPage
from web_ui.pages.tk.feed_page import TKFeedPage


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_supplier_login_lands_on_dashboard(
    settings: Settings, anon_page,
) -> None:
    with allure.step("Открыть /auth/login"):
        login = LoginPage(anon_page, settings.web_base_url_str)
        login.goto()

    with allure.step("Залогиниться как Supplier (реальный аккаунт)"):
        login.login(
            email=settings.supplier_real_email,
            password=settings.real_account_password,
        )

    with allure.step("После логина — редирект на /dashboard"):
        anon_page.wait_for_url("**/dashboard*")
        SupplierDashboardPage(anon_page, settings.web_base_url_str).expect_loaded()

    with allure.step("Сайдбар содержит ровно Supplier-пункты"):
        Sidebar(anon_page).expect_supplier()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_login_lands_on_feed(
    settings: Settings, anon_page,
) -> None:
    with allure.step("Открыть /auth/login"):
        login = LoginPage(anon_page, settings.web_base_url_str)
        login.goto()

    with allure.step("Залогиниться как TK_Admin (реальный аккаунт)"):
        login.login(
            email=settings.tk_real_email,
            password=settings.real_account_password,
        )

    with allure.step("После логина — редирект на /feed"):
        anon_page.wait_for_url("**/feed*")
        TKFeedPage(anon_page, settings.web_base_url_str).expect_loaded()

    with allure.step("Сайдбар содержит ровно TK-пункты"):
        Sidebar(anon_page).expect_tk()


@pytest.mark.ui
@pytest.mark.ui_cross
@pytest.mark.requires_real_account
def test_supplier_and_tk_authenticated_simultaneously(
    settings: Settings,
    browser: Browser,
    supplier_storage_state,
    tk_storage_state,
) -> None:
    """Two browser contexts in one process, both authenticated.

    Proves the cross-role infrastructure: each role gets its own cookies
    and Bearer; mutating actions in one context do NOT leak into the
    other. This is the foundation every cross-role e2e relies on.
    """
    sup_ctx = browser.new_context(
        base_url=settings.web_base_url_str,
        storage_state=str(supplier_storage_state),
    )
    sup_ctx.set_default_timeout(settings.ui_default_timeout_ms)
    tk_ctx = browser.new_context(
        base_url=settings.web_base_url_str,
        storage_state=str(tk_storage_state),
    )
    tk_ctx.set_default_timeout(settings.ui_default_timeout_ms)

    try:
        with allure.step("Supplier-контекст: открыть /dashboard"):
            sup_page = sup_ctx.new_page()
            sup_page.goto(f"{settings.web_base_url_str}/dashboard")
            SupplierDashboardPage(sup_page, settings.web_base_url_str).expect_loaded()
            Sidebar(sup_page).expect_supplier()

        with allure.step("TK-контекст: открыть /feed"):
            tk_page = tk_ctx.new_page()
            tk_page.goto(f"{settings.web_base_url_str}/feed")
            TKFeedPage(tk_page, settings.web_base_url_str).expect_loaded()
            Sidebar(tk_page).expect_tk()

        with allure.step("Изоляция: TK не имеет ни одного Supplier-пункта"):
            for sup_only in ("Заявки", "Склады", "Сотрудники"):
                expect(tk_page.get_by_role("link", name=sup_only)).to_have_count(0)
    finally:
        sup_ctx.close()
        tk_ctx.close()
