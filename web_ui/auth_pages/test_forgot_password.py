"""Forgot-password page — anonymous, no real reset triggered.

We test page renders, validation kicks in, and the link from /auth/login
works. We do NOT submit a real email — that would trigger an actual
OTP email to a real address.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.auth.forgot_password_page import ForgotPasswordPage
from web_ui.pages.auth.login_page import LoginPage


@pytest.fixture
def forgot(anon_page, settings: Settings) -> ForgotPasswordPage:
    page = ForgotPasswordPage(anon_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.requires_real_account
def test_forgot_password_page_renders(forgot: ForgotPasswordPage) -> None:
    expect(forgot.heading).to_be_visible()
    expect(forgot.email_input).to_be_visible()
    expect(forgot.submit_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.requires_real_account
def test_login_link_navigates_to_forgot_password(
    anon_page, settings: Settings,
) -> None:
    login = LoginPage(anon_page, settings.web_base_url_str)
    login.goto()
    login.forgot_password_link.click()
    anon_page.wait_for_url("**/auth/forgot-password*", timeout=10_000)
    ForgotPasswordPage(anon_page, settings.web_base_url_str).expect_loaded()


@pytest.mark.ui
@pytest.mark.requires_real_account
@pytest.mark.parametrize("bad_email", ["abc", "abc@", "@x.uz"])
def test_invalid_email_shows_inline_error(
    forgot: ForgotPasswordPage, bad_email: str,
) -> None:
    """Same pattern as registration form: inline error «Неверный
    формат email» (or similar) when the email doesn't parse."""
    forgot.email_input.fill(bad_email)
    forgot.submit_button.click()
    # Match by partial — if the exact wording differs from registration,
    # we still catch any «email» / «формат»-shaped error.
    err = forgot.page.get_by_text(
        "Неверный формат email", exact=True,
    ).or_(forgot.page.get_by_text("Укажите корректный email"))
    expect(err.first).to_be_visible(timeout=5_000)
