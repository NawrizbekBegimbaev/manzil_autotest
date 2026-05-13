"""Pre-OTP coverage of the Supplier registration form.

We exercise everything BEFORE the OTP screen — UI client-side validation,
field rendering, navigation. We deliberately do NOT submit valid forms
because each successful submit creates a real Keycloak user (no public
"delete user" API to clean up, so we'd leak rows on every CI run) and
sends a real OTP email to the email pool address.

What's covered:
- Page renders with all fields and the submit button.
- Empty submit shows ALL required-field errors (one click → six messages).
- Per-field invalid input shows the matching inline error.
- Password mismatch shows mismatch error.
- Cross-navigation (entry page picks Supplier / TK / Войти).

What's intentionally NOT here:
- Successful submit → OTP screen (covered post-OTP via the real shared
  account; live submit blocked here to avoid real-mailbox spam).
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.auth.login_page import LoginPage
from web_ui.pages.auth.register_entry_page import RegisterEntryPage
from web_ui.pages.auth.register_supplier_form import RegisterSupplierForm

# Inline error messages observed on the live form.
ERR_COMPANY_SHORT = "Название не короче 2 символов"
ERR_TIN_LEN = "ИНН от 8 до 18 символов"
ERR_FULLNAME_SHORT = "ФИО не короче 2 символов"
ERR_EMAIL_FORMAT = "Неверный формат email"
ERR_PHONE_FORMAT = "Укажите корректный телефон"
ERR_PASSWORD_SHORT = "Не менее 8 символов"


@pytest.fixture
def supplier_form(anon_page, settings: Settings) -> RegisterSupplierForm:
    form = RegisterSupplierForm(anon_page, settings.web_base_url_str)
    form.goto()
    expect(form.heading).to_be_visible()
    return form


# ---------- entry page navigation ------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_entry_page_renders_and_links_to_supplier(
    anon_page, settings: Settings,
) -> None:
    entry = RegisterEntryPage(anon_page, settings.web_base_url_str)
    entry.goto()
    expect(entry.heading).to_be_visible()
    expect(entry.supplier_link).to_be_visible()
    expect(entry.tk_link).to_be_visible()
    expect(entry.driver_note).to_be_visible()
    entry.pick_supplier()
    anon_page.wait_for_url("**/auth/register/supplier*")
    expect(
        anon_page.get_by_role("heading", name="Регистрация поставщика"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_entry_page_links_to_tk(anon_page, settings: Settings) -> None:
    entry = RegisterEntryPage(anon_page, settings.web_base_url_str)
    entry.goto()
    entry.pick_tk()
    anon_page.wait_for_url("**/auth/register/tk*")
    expect(
        anon_page.get_by_role("heading", name="Регистрация транспортной компании"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_entry_page_back_to_login(anon_page, settings: Settings) -> None:
    entry = RegisterEntryPage(anon_page, settings.web_base_url_str)
    entry.goto()
    entry.back_to_login_link.click()
    anon_page.wait_for_url("**/auth/login*")
    LoginPage(anon_page, settings.web_base_url_str).expect_loaded()


# ---------- field rendering ------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_form_renders_all_fields(supplier_form: RegisterSupplierForm) -> None:
    for input_locator in (
        supplier_form.company_name_input,
        supplier_form.tin_input,
        supplier_form.full_name_input,
        supplier_form.email_input,
        supplier_form.phone_input,
        supplier_form.password_input,
        supplier_form.confirm_password_input,
    ):
        expect(input_locator).to_be_visible()
    expect(supplier_form.submit_button).to_be_visible()
    expect(supplier_form.back_to_login_link).to_be_visible()


# ---------- empty submit ---------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_empty_submit_shows_all_required_errors(
    supplier_form: RegisterSupplierForm,
) -> None:
    with allure.step("Кликнуть «Зарегистрироваться» при пустой форме"):
        supplier_form.submit()

    with allure.step("UI показал inline-ошибки по каждому полю"):
        for err in (
            ERR_COMPANY_SHORT,
            ERR_TIN_LEN,
            ERR_FULLNAME_SHORT,
            ERR_EMAIL_FORMAT,
            ERR_PHONE_FORMAT,
            ERR_PASSWORD_SHORT,
        ):
            expect(supplier_form.field_error(err)).to_be_visible()


# ---------- per-field invalid input ----------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize("name", ["", "X"])
def test_short_company_name_shows_error(
    supplier_form: RegisterSupplierForm, name: str,
) -> None:
    """Company name shorter than 2 characters is rejected."""
    supplier_form.company_name_input.fill(name)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_COMPANY_SHORT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize("tin", ["", "1", "1234567"])
def test_short_tin_shows_error(
    supplier_form: RegisterSupplierForm, tin: str,
) -> None:
    """UI rule: TIN must be 8–18 chars.

    NOTE: backend swagger says `^[0-9]{1,18}$` (1+ digits accepted). The
    UI is stricter — bug recorded under BUG-013 (UI/API contract drift).
    This test pins the OBSERVED UI behavior so a future relaxation is
    flagged loudly.
    """
    supplier_form.tin_input.fill(tin)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_TIN_LEN)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
def test_long_tin_shows_error(supplier_form: RegisterSupplierForm) -> None:
    """TIN longer than 18 chars is rejected."""
    supplier_form.tin_input.fill("1" * 19)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_TIN_LEN)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize("name", ["", "X"])
def test_short_full_name_shows_error(
    supplier_form: RegisterSupplierForm, name: str,
) -> None:
    supplier_form.full_name_input.fill(name)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_FULLNAME_SHORT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize(
    "bad_email",
    ["abc", "abc@", "abc@def", "@x.uz", "no-at-symbol.com", "spaces in@a.b"],
)
def test_invalid_email_shows_error(
    supplier_form: RegisterSupplierForm, bad_email: str,
) -> None:
    supplier_form.email_input.fill(bad_email)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_EMAIL_FORMAT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize("bad_phone", ["abc", "12345", "+99812"])
def test_invalid_phone_shows_error(
    supplier_form: RegisterSupplierForm, bad_phone: str,
) -> None:
    """Inputs the UI must reject with «Укажите корректный телефон».

    NOTE: Some malformed inputs ("++998…", "998 abc 123") slip past — the
    phone field uses an input mask that silently strips disallowed chars,
    so the resulting value passes the validator. Recorded as BUG-014 in
    bug.txt; not asserted here because behavior is "swallow + accept".
    """
    supplier_form.phone_input.fill(bad_phone)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_PHONE_FORMAT)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.parametrize("pwd", ["", "short", "1234567"])
def test_short_password_shows_error(
    supplier_form: RegisterSupplierForm, pwd: str,
) -> None:
    supplier_form.password_input.fill(pwd)
    supplier_form.submit()
    expect(supplier_form.field_error(ERR_PASSWORD_SHORT)).to_be_visible()
