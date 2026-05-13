"""Supplier employees — `/employees`.

ADMIN-only per matrix. Columns: ФИО, Email, Роль (combobox: Администратор
/ Диспетчер / Менеджер), Статус (Активен / Приглашён / Заблокирован),
Создан, Действия (kebab/icon).

Roles map (UI label → Keycloak realm role):
- Администратор → SUPPLIER_ADMIN
- Диспетчер     → SUPPLIER_DISPATCHER
- Менеджер      → SUPPLIER_MANAGER

Live recon: invite dialog has ФИО, Email, Роль (default «Диспетчер»).
No phone or password fields — invitee receives an email link to set
their own password (`/auth/invitations/accept?token=…`).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from web_ui.pages._base import BasePage


class SupplierEmployeesPage(BasePage):
    path = "/employees"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Сотрудники").first

    @property
    def add_button(self):
        return self.page.get_by_role("button", name="Добавить сотрудника")

    @property
    def status_filter(self):
        return self.page.get_by_role("combobox", name="Статус")

    @property
    def search_input(self):
        return self.page.get_by_role("textbox", name="Поиск")

    def row_by_email(self, email: str):
        return self.page.get_by_role("row").filter(has_text=email)

    def role_select_for(self, email: str):
        return self.row_by_email(email).get_by_role("combobox")

    def open_row_menu(self, email: str) -> None:
        """Open the kebab/more menu for the row matching this email.

        The Действия column has a single icon-only button (no aria-label
        per recon) — locate by structure: last button in the row.
        """
        self.row_by_email(email).locator("button").last.click()

    def click_delete_in_menu(self) -> None:
        """Click the «Удалить» menuitem in the open kebab menu — fires
        `window.confirm()`. Caller must install a dialog handler first.
        """
        self.page.get_by_role("menuitem", name="Удалить").or_(
            self.page.locator(".MuiMenuItem-root").filter(has_text="Удалить"),
        ).first.click()

    def click_block_in_menu(self) -> None:
        self.page.get_by_role("menuitem", name="Заблокировать").or_(
            self.page.locator(".MuiMenuItem-root").filter(has_text="Заблокировать"),
        ).first.click()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)


class InviteEmployeeDialog:
    """Modal opened by «Добавить сотрудника» — invite by email + role."""

    def __init__(self, page: Page) -> None:
        self.page = page

    @property
    def root(self):
        return self.page.get_by_role("dialog", name="Добавить сотрудника")

    @property
    def full_name_input(self):
        return self.root.get_by_role("textbox", name="ФИО")

    @property
    def email_input(self):
        return self.root.get_by_role("textbox", name="Email")

    @property
    def role_select(self):
        return self.root.get_by_role("combobox", name="Роль")

    @property
    def submit_button(self):
        # Same text as the opener — disambiguate by scoping to the dialog.
        return self.root.get_by_role("button", name="Добавить сотрудника")

    @property
    def cancel_button(self):
        return self.root.get_by_role("button", name="Отмена")
