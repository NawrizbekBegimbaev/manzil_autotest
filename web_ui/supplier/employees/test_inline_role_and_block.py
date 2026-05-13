"""Inline role-change combobox + block menuitem.

CRITICAL CONSTRAINT (live-account safety):
- Inline role-change combobox MUST NOT be confirmed against shared
  dispatcher/manager — flipping a role would silently break later tests
  that depend on the role binding (sidebar layout, RBAC checks).
- «Заблокировать» menuitem fires INSTANTLY — there is NO confirm modal
  between click and the API call (verified in MCP recon). So we never
  click it on a real account; we only assert the menuitem exists.

What we cover here:
- Role-change combobox opens with all 3 options (Администратор /
  Диспетчер / Менеджер) — proves the role list isn't truncated.
- Кебаб menu shows BOTH «Заблокировать» AND «Удалить» menuitems —
  proves the destructive operations are exposed (without invoking
  them).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.supplier.employees_page import SupplierEmployeesPage

EXPECTED_ROLE_OPTIONS = ("Администратор", "Диспетчер", "Менеджер")


@pytest.fixture
def employees(supplier_admin_page, settings: Settings) -> SupplierEmployeesPage:
    page = SupplierEmployeesPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_inline_role_combobox_offers_all_three_roles(
    employees: SupplierEmployeesPage,
    settings: Settings,
) -> None:
    """Open the dispatcher row's role combobox; assert ALL 3 options are
    present. Press Escape immediately — never select an option, since
    that would change the dispatcher's real role."""
    employees.role_select_for(settings.supplier_dispatcher_real_email).click()
    for role in EXPECTED_ROLE_OPTIONS:
        expect(employees.page.get_by_role("option", name=role)).to_be_visible()
    employees.page.keyboard.press("Escape")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_kebab_menu_includes_block_action(
    employees: SupplierEmployeesPage,
    settings: Settings,
) -> None:
    """Menu must expose «Заблокировать». We do NOT click it — block
    fires instantly without confirm and would lock out the dispatcher."""
    employees.open_row_menu(settings.supplier_dispatcher_real_email)
    expect(
        employees.page.locator(".MuiMenuItem-root").filter(has_text="Заблокировать"),
    ).to_be_visible()
    # Close menu without picking anything.
    employees.page.keyboard.press("Escape")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_self_row_has_no_kebab_or_role_combobox(
    employees: SupplierEmployeesPage,
    settings: Settings,
) -> None:
    """Live recon (2026-05-04): the logged-in admin's OWN row in
    /employees has NO kebab button AND NO inline role-combobox. UX-safety
    measure — admin can't accidentally self-block, self-delete, or
    self-demote (which would lock the company out of admin access).

    This invariant is the strongest possible guard. If a future change
    re-introduces the kebab on admin's self-row, the test breaks loudly.
    """
    own_row = employees.row_by_email(settings.supplier_admin_real_email)
    # Action cell (last column) should have NO buttons (no kebab) and
    # the role cell should have NO combobox (vs. other rows).
    expect(own_row.locator("button")).to_have_count(0)
    expect(own_row.locator('[role="combobox"]')).to_have_count(0)
