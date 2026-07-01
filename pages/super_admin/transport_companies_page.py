"""SUPER_ADMIN → Транспортные компании: list + create-dialog Page Object.

Like the shipper form, creating a carrier provisions a login (phone + password).
Minimal create: pick one transport type and "Принимать все направления" so the
city autocomplete is not required.
"""

from __future__ import annotations

from pages.base_page import BasePage
from utils.data import CarrierData

PATH = "/super-admin/partners/transport-companies"


class TransportCompaniesPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить компанию")
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Создать", exact=True)
        self.toast_created = page.get_by_text("Транспортная компания создана")

    def open(self) -> "TransportCompaniesPage":
        self.goto(PATH)
        return self

    def open_create(self) -> "TransportCompaniesPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def fill_create(self, data: CarrierData, password: str) -> "TransportCompaniesPage":
        self._field("companyName").fill(data.name)
        self._field("tin").fill(data.tin)
        self._field("address").fill(data.address)
        self.dialog.get_by_role("checkbox", name="Автомобильный").check()
        self.dialog.get_by_role("checkbox", name="Принимать все направления").check()
        self.dialog.get_by_role("radio", name="Активен").check()
        self._field("fullName").fill(data.full_name)
        self.fill_phone(self._field("phone"), data.phone)
        self._field("password").fill(password)
        self._field("passwordConfirm").fill(password)
        return self

    def submit(self) -> "TransportCompaniesPage":
        self.submit_button.click()
        return self

    def search(self, text: str) -> "TransportCompaniesPage":
        self.page.get_by_placeholder("ФИО / телефон / компания").fill(text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def delete_row(self, text: str) -> "TransportCompaniesPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self

    def open_edit(self, text: str) -> "TransportCompaniesPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Редактировать").click()
        self.dialog.wait_for(state="visible")
        return self

    def set_name(self, new_name: str) -> "TransportCompaniesPage":
        self._field("companyName").fill(new_name)
        return self

    def save(self) -> "TransportCompaniesPage":
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self
