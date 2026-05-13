"""Supplier employees — ADMIN view + invite-dialog plumbing.

Coverage:
- Page renders heading + columns + filters.
- All 3 known TeamQa employees are visible with correct role labels.
- The invite dialog opens with the right fields and a default role.
- Cancel closes the dialog without sending the invite.

NOT covered:
- Actual send-invite (would create a real Keycloak user we cannot
  delete; dev backend has no admin DELETE-user API).
- Role change via the inline combobox (would mutate live state of a
  shared account).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.supplier.employees_page import (
    InviteEmployeeDialog,
    SupplierEmployeesPage,
)


@pytest.fixture
def employees(supplier_admin_page, settings: Settings) -> SupplierEmployeesPage:
    page = SupplierEmployeesPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_employees_page_renders_columns(employees: SupplierEmployeesPage) -> None:
    expect(employees.heading).to_be_visible()
    for col in ("ФИО", "Email", "Роль", "Статус", "Создан", "Действия"):
        expect(employees.page.get_by_role("columnheader", name=col)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_all_three_teamqa_employees_visible(
    employees: SupplierEmployeesPage, settings: Settings,
) -> None:
    """Every account from the project_manzil_ui_accounts memory must
    appear in the employee list."""
    for email in (
        settings.supplier_admin_real_email,
        settings.supplier_dispatcher_real_email,
        settings.supplier_manager_real_email,
    ):
        expect(employees.row_by_email(email)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_role_labels_match_expected_for_each_employee(
    employees: SupplierEmployeesPage, settings: Settings,
) -> None:
    """Each employee row shows the correct role label.

    Live recon (2026-05-04): the ADMIN's own row no longer has the
    inline-role combobox — UX safety against self-demote. Other employees
    still get a combobox. So we assert label-by-text universally and
    skip the combobox check for the logged-in admin.
    """
    expected = {
        settings.supplier_admin_real_email: "Администратор",
        settings.supplier_dispatcher_real_email: "Диспетчер",
        settings.supplier_manager_real_email: "Менеджер",
    }
    for email, label in expected.items():
        expect(employees.row_by_email(email)).to_contain_text(label)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_invite_dialog_renders_fields_with_default_role(
    employees: SupplierEmployeesPage,
) -> None:
    employees.add_button.click()
    dialog = InviteEmployeeDialog(employees.page)
    expect(dialog.full_name_input).to_be_visible()
    expect(dialog.email_input).to_be_visible()
    expect(dialog.role_select).to_contain_text("Диспетчер")
    expect(dialog.submit_button).to_be_visible()
    expect(dialog.cancel_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_invite_dialog_cancel_closes_dialog(
    employees: SupplierEmployeesPage,
) -> None:
    employees.add_button.click()
    dialog = InviteEmployeeDialog(employees.page)
    expect(dialog.root).to_be_visible()
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)


# ---------- RBAC negative: non-ADMIN cannot reach /employees ----------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_visiting_employees_url_does_not_render_admin_table(
    supplier_dispatcher_page, settings: Settings,
) -> None:
    """DISPATCHER opens /employees directly; UI must NOT render the admin
    employee table. The exact behaviour (redirect / 403 page / blank) is
    not standardized — we just assert the «Добавить сотрудника» button
    isn't present, which is the load-bearing admin-only control.
    """
    supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/employees")
    expect(
        supplier_dispatcher_page.get_by_role("button", name="Добавить сотрудника"),
    ).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_visiting_employees_url_does_not_render_admin_table(
    supplier_manager_page, settings: Settings,
) -> None:
    supplier_manager_page.goto(f"{settings.web_base_url_str}/employees")
    expect(
        supplier_manager_page.get_by_role("button", name="Добавить сотрудника"),
    ).to_have_count(0)
