"""SHIPPER ADMIN → Сотрудники: create-dialog Page Object.

Used to provision a MANAGER login: the shipper admin creates a staff member with
role "Менеджер" (phone + password), which the suite then logs in as.
"""

from __future__ import annotations

from pages.base_page import BasePage
from utils.data import StaffData

PATH = "/shipper/staff"


class StaffPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить сотрудника")
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Создать", exact=True)
        self.toast_created = page.get_by_text("Сотрудник создан")

    def open(self) -> "StaffPage":
        self.goto(PATH)
        return self

    def open_create(self) -> "StaffPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def create(self, data: StaffData, password: str, role_label: str) -> "StaffPage":
        self._field("fullName").fill(data.full_name)
        self.fill_phone(self._field("phone"), data.phone)
        self.dialog.get_by_role("combobox").first.click()
        self.page.get_by_role("option", name=role_label, exact=True).click()
        self.dialog.get_by_role("radio", name="Активен", exact=True).check()
        self._field("password").fill(password)
        self._field("passwordConfirm").fill(password)
        self.submit_button.click()
        return self

    def search(self, text: str) -> "StaffPage":
        box = self.page.get_by_placeholder("Введите ФИО или телефон")
        if box.count():
            box.fill(text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def open_edit(self, text: str) -> "StaffPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Редактировать").click()
        self.dialog.wait_for(state="visible")
        return self

    def set_name(self, new_name: str) -> "StaffPage":
        self._field("fullName").fill(new_name)
        return self

    def save(self) -> "StaffPage":
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def delete_row(self, text: str) -> "StaffPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
