"""Supplier employees — delete-confirm modal opens with the right text.

CRITICAL constraint: the three TeamQa accounts (admin/dispatcher/manager)
are SHARED real Keycloak users — we MUST NOT actually delete any of
them; the entire web_ui suite would break.

Compromise:
- Test that the kebab → «Удалить» menuitem fires `window.confirm()`
  with the correct message, then DISMISS unconditionally.
- Don't drive an accept-and-delete flow from UI — that would risk
  losing the dispatcher/manager fixture across runs.

For real "create + delete" coverage you'd invite a fresh employee, but
dev backend has no admin DELETE-user API, so the invited rows would
leak — same dead-end as registration submit. Skipped.
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages._common.native_confirm import handle_next_confirm
from web_ui.pages.supplier.employees_page import SupplierEmployeesPage


@pytest.fixture
def employees(supplier_admin_page, settings: Settings) -> SupplierEmployeesPage:
    page = SupplierEmployeesPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_kebab_menu_shows_block_and_delete_options(
    employees: SupplierEmployeesPage,
    settings: Settings,
) -> None:
    """Open the row's kebab — see «Заблокировать» and «Удалить»."""
    employees.open_row_menu(settings.supplier_dispatcher_real_email)
    expect(
        employees.page.locator(".MuiMenuItem-root").filter(has_text="Заблокировать"),
    ).to_be_visible()
    expect(
        employees.page.locator(".MuiMenuItem-root").filter(has_text="Удалить"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_delete_menuitem_fires_confirm_with_employee_name(
    employees: SupplierEmployeesPage,
    settings: Settings,
) -> None:
    """Click «Удалить» — native confirm appears mentioning the employee.
    DISMISS — the shared dispatcher account must remain intact."""
    with allure.step("Open kebab on the dispatcher row, click «Удалить»"):
        employees.open_row_menu(settings.supplier_dispatcher_real_email)
        with handle_next_confirm(employees.page, accept=False) as captured:
            employees.click_delete_in_menu()
        assert captured.appeared, "expected window.confirm to appear"
        # Per recon the message format is «Удалить сотрудника «<full_name>»?».
        assert "Удалить сотрудника" in captured.message, (
            f"confirm message: {captured.message!r}"
        )

    with allure.step("Dispatcher row still present (we dismissed)"):
        employees.page.wait_for_timeout(500)
        expect(
            employees.row_by_email(settings.supplier_dispatcher_real_email),
        ).to_be_visible()
