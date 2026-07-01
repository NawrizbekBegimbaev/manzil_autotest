"""SUPER_ADMIN → Грузоотправители: list + create-dialog Page Object.

Creating a shipper company also provisions a login account (phone + password
set right in the dialog), so the workflow reuses these credentials to log in as
the new shipper admin in a separate context.
"""

from __future__ import annotations

from pages.base_page import BasePage
from utils.data import ShipperData

PATH = "/super-admin/partners/shipper-companies"


class ShipperCompaniesPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить грузоотправителя")
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Создать", exact=True)
        self.toast_created = page.get_by_text("Грузоотправитель создан")

    def open(self) -> "ShipperCompaniesPage":
        self.goto(PATH)
        return self

    def open_create(self) -> "ShipperCompaniesPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def fill_create(self, data: ShipperData, password: str) -> "ShipperCompaniesPage":
        """Fill every required field of the create dialog (no submit)."""
        self._field("name").fill(data.name)
        self._field("prefix").fill(data.prefix)
        self._field("tin").fill(data.tin)
        self._field("address").fill(data.address)
        self.dialog.get_by_role("radio", name="Активен").check()
        self._field("fullName").fill(data.full_name)
        self.fill_phone(self._field("phone"), data.phone)
        self._field("password").fill(password)
        self._field("passwordConfirm").fill(password)
        return self

    def submit(self) -> "ShipperCompaniesPage":
        self.submit_button.click()
        return self

    def search(self, text: str) -> "ShipperCompaniesPage":
        box = self.page.get_by_placeholder("ФИО / телефон / компания")
        box.fill(text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def delete_row(self, text: str) -> "ShipperCompaniesPage":
        """Find a row by text and delete it via the action menu + confirm dialog."""
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self

    def open_card(self, text: str) -> "ShipperCompaniesPage":
        self.search(text)
        self.row(text).first.click()
        return self

    def open_edit(self, text: str) -> "ShipperCompaniesPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Редактировать").click()
        self.dialog.wait_for(state="visible")
        return self

    def set_name(self, new_name: str) -> "ShipperCompaniesPage":
        self._field("name").fill(new_name)
        return self

    def set_active(self, active: bool) -> "ShipperCompaniesPage":
        label = "Активен" if active else "Заблокирован"
        self.dialog.get_by_role("radio", name=label, exact=True).check()
        return self

    def save(self) -> "ShipperCompaniesPage":
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self
