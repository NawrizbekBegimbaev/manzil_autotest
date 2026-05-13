"""Anonymous health probes — safe on ANY environment including prod.

These tests:
- DO NOT log in
- DO NOT submit forms
- DO NOT use shared accounts
- DO NOT mutate any state

They just verify the SPA shell loads and the login form renders. Used
as a sanity probe against staging/prod.

Usage:
    MANZIL_ENV=prod    pytest -m smoke -k anonymous_health
    MANZIL_ENV=staging pytest -m smoke -k anonymous_health
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.auth.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.smoke
def test_login_page_renders_on_current_env(
    anon_page, settings: Settings,
) -> None:
    """Login page loads with both inputs + submit button.

    Independent of real accounts and per-env data — just proves the
    deployed bundle serves a usable login screen on whichever env
    `settings.web_base_url` points at.
    """
    login = LoginPage(anon_page, settings.web_base_url_str)
    login.goto()
    expect(login.heading).to_be_visible()
    expect(login.email_input).to_be_visible()
    expect(login.password_input).to_be_visible()
    expect(login.submit_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.smoke
def test_root_redirects_to_login_when_anonymous(
    anon_page, settings: Settings,
) -> None:
    """Visiting `/` while logged-out should land on /auth/login (or
    a public landing). On dev we observed direct redirect to login."""
    anon_page.goto(settings.web_base_url_str + "/")
    anon_page.wait_for_url("**/auth/login*", timeout=10_000)
    LoginPage(anon_page, settings.web_base_url_str).expect_loaded()
