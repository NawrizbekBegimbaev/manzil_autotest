"""SUPER_ADMIN → Водители: list + create-dialog Page Object.

Creating a self-employed driver provisions a DRIVER login. The create dialog has
extra fields (vehicle type, license, etc.); only required ones are filled.
"""

from __future__ import annotations

from pages.base_page import BasePage
from utils.data import DriverData

PATH = "/super-admin/partners/drivers"


class DriversPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить водителя")
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Создать", exact=True)
        self.toast_created = page.get_by_text("Водитель создан")

    def open(self) -> "DriversPage":
        self.goto(PATH)
        return self

    def open_create(self) -> "DriversPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def fill_create(self, data: DriverData, password: str) -> "DriversPage":
        self._field("realName").fill(data.full_name)
        self.fill_phone(self._field("phone"), data.phone)
        # Vehicle type is the only select (combobox) in the dialog — pick the first option.
        self.dialog.get_by_role("combobox").first.click()
        self.page.get_by_role("option").first.click()
        self.dialog.get_by_role("radio", name="Активен", exact=True).check()
        self._field("password").fill(password)
        self._field("passwordConfirm").fill(password)
        return self

    def search(self, text: str) -> "DriversPage":
        self.filter_search("ФИО / телефон / гос. номер", text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def open_edit(self, text: str) -> "DriversPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        self.open_row_menu(row)
        self.page.get_by_role("menuitem", name="Редактировать").click()
        self.dialog.wait_for(state="visible")
        return self

    def set_name(self, new_name: str) -> "DriversPage":
        self._field("realName").fill(new_name)
        return self

    def save(self) -> "DriversPage":
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def delete_row(self, text: str) -> "DriversPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        self.open_row_menu(row)
        self.page.get_by_role("menuitem", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
