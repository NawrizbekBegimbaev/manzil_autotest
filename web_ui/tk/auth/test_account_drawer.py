"""TK account drawer — identity + logout."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages._common.account_drawer import AccountDrawer
from web_ui.pages.auth.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_drawer_shows_tk_role_and_email(
    tk_page, settings: Settings,
) -> None:
    tk_page.goto(f"{settings.web_base_url_str}/feed")
    AccountDrawer(tk_page).open()
    expect(tk_page.get_by_text(settings.tk_real_email)).to_be_visible()
    # Role label observed (live): «ТК · Администратор» — UI uses the
    # short form, not «Транспортная компания · Администратор».
    expect(
        tk_page.get_by_text("ТК · Администратор"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_logout_returns_to_login(anon_page, settings: Settings) -> None:
    """Fresh login (not cached) so we don't revoke the session that
    sibling tests rely on."""
    login = LoginPage(anon_page, settings.web_base_url_str)
    login.goto()
    login.login(
        email=settings.tk_real_email,
        password=settings.real_account_password,
    )
    anon_page.wait_for_url("**/feed*")
    AccountDrawer(anon_page).logout()
    anon_page.wait_for_url("**/auth/login*")
    LoginPage(anon_page, settings.web_base_url_str).expect_loaded()
