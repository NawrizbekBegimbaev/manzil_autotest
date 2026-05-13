"""Supplier orders list — `/orders`.

Columns: Номер, Груз, Маршрут, Дата, Статус.

Live recon (2026-05-04):
- Status filter is now a row of CHIP-BUTTONS, not a combobox:
  «Все статусы» / «Активные» / «Подтверждённые» / «В работе» /
  «Завершённые» / «Черновики».
- Pagination added: «Строк на странице» combobox (10 default), prev/next.

Per matrix:
- ADMIN + MANAGER see all company orders.
- DISPATCHER sees own drafts (and presumably published).
- Only DISPATCHER has the "Создать заявку" button (so it's hidden for
  ADMIN / MANAGER — verified by an RBAC test).
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class SupplierOrdersListPage(BasePage):
    path = "/orders"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Заявки").first

    @property
    def search_input(self):
        return self.page.get_by_role("textbox", name="Поиск")

    def status_chip(self, name: str):
        """Status filter chip — actually a MUI Tab (`role="tab"`),
        not a button (live recon 2026-05-04)."""
        return self.page.get_by_role("tab", name=name, exact=True)

    @property
    def filter_all_chip(self):
        return self.status_chip("Все статусы")

    @property
    def filter_active_chip(self):
        return self.status_chip("Активные")

    @property
    def filter_drafts_chip(self):
        return self.status_chip("Черновики")

    @property
    def page_size_select(self):
        return self.page.get_by_role("combobox", name="Строк на странице")

    @property
    def create_button(self):
        # DISPATCHER-only; expected hidden for ADMIN/MANAGER.
        return self.page.get_by_role("button", name="Создать заявку").or_(
            self.page.get_by_role("button", name="Создать черновик"),
        )

    def row_by_number(self, mzl_number: str):
        """Locate a row by its order number (e.g. "MZL-0003")."""
        return self.page.get_by_role("row").filter(has_text=mzl_number)

    def open_order(self, mzl_number: str) -> None:
        self.row_by_number(mzl_number).click()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
