"""Pre-OTP coverage of the TK registration form.

Mirror of the supplier pre-OTP suite. Same field set, same inline error
messages — only the heading and the company-name label differ
(«Регистрация транспортной компании», «Название ТК»).
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.auth.register_tk_form import RegisterTKForm

ERR_COMPANY_SHORT = "Название не короче 2 символов"
ERR_TIN_LEN = "ИНН от 8 до 18 символов"
ERR_FULLNAME_SHORT = "ФИО не короче 2 символов"
ERR_EMAIL_FORMAT = "Неверный формат email"
ERR_PHONE_FORMAT = "Укажите корректный телефон"
ERR_PASSWORD_SHORT = "Не менее 8 символов"


@pytest.fixture
def tk_form(anon_page, settings: Settings) -> RegisterTKForm:
    form = RegisterTKForm(anon_page, settings.web_base_url_str)
    form.goto()
    # Heading sometimes lags behind the URL change on cold-loaded pages.
    expect(form.heading).to_be_visible(timeout=15_000)
    return form


@pytest.mark.ui
@pytest.mark.ui_tk
def test_form_renders_all_fields(tk_form: RegisterTKForm) -> None:
    for input_locator in (
        tk_form.company_name_input,
        tk_form.tin_input,
        tk_form.full_name_input,
        tk_form.email_input,
        tk_form.phone_input,
        tk_form.password_input,
        tk_form.confirm_password_input,
    ):
        expect(input_locator).to_be_visible()
    expect(tk_form.submit_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
def test_empty_submit_shows_all_required_errors(tk_form: RegisterTKForm) -> None:
    with allure.step("Submit пустой формы регистрации ТК"):
        tk_form.submit()
    for err in (
        ERR_COMPANY_SHORT,
        ERR_TIN_LEN,
        ERR_FULLNAME_SHORT,
        ERR_EMAIL_FORMAT,
        ERR_PHONE_FORMAT,
        ERR_PASSWORD_SHORT,
    ):
        expect(tk_form.field_error(err)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.parametrize("tin", ["", "1", "1234567", "1" * 19])
def test_invalid_tin_shows_error(tk_form: RegisterTKForm, tin: str) -> None:
    tk_form.tin_input.fill(tin)
    tk_form.submit()
    expect(tk_form.field_error(ERR_TIN_LEN)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.parametrize("bad_email", ["abc", "abc@def", "@x.uz"])
def test_invalid_email_shows_error(tk_form: RegisterTKForm, bad_email: str) -> None:
    tk_form.email_input.fill(bad_email)
    tk_form.submit()
    expect(tk_form.field_error(ERR_EMAIL_FORMAT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.parametrize("bad_phone", ["abc", "12345", "+99812"])
def test_invalid_phone_shows_error(tk_form: RegisterTKForm, bad_phone: str) -> None:
    tk_form.phone_input.fill(bad_phone)
    tk_form.submit()
    expect(tk_form.field_error(ERR_PHONE_FORMAT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.parametrize("pwd", ["", "short", "1234567"])
def test_short_password_shows_error(tk_form: RegisterTKForm, pwd: str) -> None:
    tk_form.password_input.fill(pwd)
    tk_form.submit()
    expect(tk_form.field_error(ERR_PASSWORD_SHORT)).to_be_visible()
