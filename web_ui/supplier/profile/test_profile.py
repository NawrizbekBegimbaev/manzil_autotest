"""Profile settings page — read view + edit dialog plumbing.

Live recon: drawer→«Профиль» navigates to /settings/profile. Read view
shows ФИО/Email/Телефон/Роль/Организация/ИНН. Edit button opens
inline edit form for ФИО + Телефон only.

We test:
- Page renders with heading and the user's email + role label.
- Edit button reveals editable inputs + Сохранить/Отмена buttons.
- Cancel reverts back to read mode without saving anything (no PATCH
  fired — verified indirectly: re-visiting shows the original value).

NOT tested:
- Actually saving — would mutate the shared admin's name/phone, which
  later RBAC tests rely on for the «Поставщик · Администратор» label.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages._common.account_drawer import AccountDrawer
from web_ui.pages.supplier.profile_page import ProfilePage


@pytest.fixture
def profile(supplier_admin_page, settings: Settings) -> ProfilePage:
    page = ProfilePage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_drawer_profile_menuitem_navigates_to_settings_profile(
    supplier_admin_page, settings: Settings,
) -> None:
    """Drawer Профиль → /settings/profile."""
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    AccountDrawer(supplier_admin_page).open()
    supplier_admin_page.get_by_role("menuitem", name="Профиль").click()
    supplier_admin_page.wait_for_url("**/settings/profile*", timeout=10_000)
    expect(
        supplier_admin_page.get_by_role("heading", name="Профиль"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_profile_page_shows_admin_email_and_role(
    profile: ProfilePage, settings: Settings,
) -> None:
    expect(profile.heading).to_be_visible()
    expect(
        profile.page.get_by_text(settings.supplier_admin_real_email),
    ).to_be_visible()
    expect(
        profile.page.get_by_text("Поставщик · Администратор").first,
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_edit_button_reveals_form(profile: ProfilePage) -> None:
    profile.edit_button.click()
    expect(profile.full_name_input).to_be_visible()
    expect(profile.phone_input).to_be_visible()
    expect(profile.save_button).to_be_visible()
    expect(profile.cancel_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_edit_cancel_does_not_persist_typed_changes(
    profile: ProfilePage, settings: Settings,
) -> None:
    """Type something into ФИО, click «Отмена», reload — original name
    is back. Avoids mutating the shared admin's profile."""
    original = profile.page.get_by_text("Бегимбаев Наврузбек").first.inner_text()

    profile.edit_button.click()
    profile.full_name_input.fill("[E2E-UI] should not persist")
    profile.cancel_button.click()
    profile.page.reload()

    expect(profile.page.get_by_text("[E2E-UI] should not persist")).to_have_count(0)
    expect(profile.page.get_by_text(original).first).to_be_visible()
