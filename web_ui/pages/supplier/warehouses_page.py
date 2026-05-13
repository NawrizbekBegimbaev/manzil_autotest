"""Supplier warehouses — `/warehouses`.

Per matrix: ADMIN + DISPATCHER can CRUD; MANAGER cannot (no «Добавить
склад» button + page hidden from sidebar). Address is snapshotted into
orders at publish-time.

Live recon notes:
- Header heading: «Склады»
- Subheader paragraph: «Список складов погрузки…»
- Action button: «Добавить склад» (in header)
- Table columns: Название, Город, Адрес, Действия
- Row actions: Редактировать (icon), Удалить (icon) — no visible labels,
  only icons; located by their role-name attributes.
- Add dialog title: «Добавить склад погрузки»  (NOT just «Добавить склад»).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from web_ui.pages._base import BasePage


class SupplierWarehousesPage(BasePage):
    path = "/warehouses"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Склады").first

    @property
    def add_warehouse_button(self):
        return self.page.get_by_role("button", name="Добавить склад")

    def row_by_name(self, name: str):
        return self.page.get_by_role("row").filter(has_text=name)

    def edit_warehouse(self, name: str) -> None:
        self.row_by_name(name).get_by_role("button", name="Редактировать").click()

    def click_delete_button(self, name: str) -> None:
        """Click the row's «Удалить» icon — this fires `window.confirm()`.

        Caller MUST install a dialog handler (`handle_next_confirm`) before
        this call, otherwise Playwright will auto-dismiss and the request
        won't be sent.
        """
        self.row_by_name(name).get_by_role("button", name="Удалить").click()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)


class WarehouseDialog:
    """Modal opened by «Добавить склад» / «Редактировать».

    Title is «Добавить склад погрузки» (create) — for edit it's likely
    «Редактировать склад» (refine on first edit-test).
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    @property
    def root(self):
        return self.page.get_by_role("dialog").filter(has_text="склад")

    @property
    def title(self):
        return self.root.get_by_role("heading").first

    @property
    def name_input(self):
        return self.root.get_by_role("textbox", name="Название склада")

    @property
    def city_input(self):
        return self.root.get_by_role("textbox", name="Город")

    @property
    def address_input(self):
        return self.root.get_by_role("textbox", name="Адрес")

    @property
    def active_checkbox(self):
        return self.root.get_by_role(
            "checkbox", name="Активен (доступен при создании заявки)",
        )

    @property
    def save_button(self):
        return self.root.get_by_role("button", name="Создать").or_(
            self.root.get_by_role("button", name="Сохранить"),
        )

    @property
    def cancel_button(self):
        return self.root.get_by_role("button", name="Отмена")

    def fill(self, *, name: str, city: str, address: str) -> None:
        self.name_input.fill(name)
        self.city_input.fill(city)
        self.address_input.fill(address)

    def submit(self) -> None:
        self.save_button.click()
