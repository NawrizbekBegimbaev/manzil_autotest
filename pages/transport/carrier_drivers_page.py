"""CARRIER → Водители (/transport/employees): list + create/edit/delete."""

from __future__ import annotations

from pages.base_page import BasePage

PATH = "/transport/employees"


class CarrierDriversPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить", exact=True)
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Создать", exact=True)
        self.toast_created = page.get_by_text("Водитель создан")

    def open(self) -> "CarrierDriversPage":
        self.goto(PATH)
        return self

    def open_create(self) -> "CarrierDriversPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def fill_create(self, full_name: str, phone: str, card_id: str = "AB1234567") -> "CarrierDriversPage":
        self._field("fullName").fill(full_name)
        # This form defaults to +86 (CN) — type the full international number.
        self.fill_phone_intl(self._field("phone"), phone)
        # cardId is required (server 500s when null).
        self._field("cardId").fill(card_id)
        return self

    def search(self, text: str) -> "CarrierDriversPage":
        box = self.page.get_by_placeholder("Поиск (ФИО, телефон)")
        if box.count():
            box.first.fill(text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def open_edit(self, text: str) -> "CarrierDriversPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Редактировать").click()
        self.dialog.wait_for(state="visible")
        return self

    def set_name(self, new_name: str) -> "CarrierDriversPage":
        self._field("fullName").fill(new_name)
        return self

    def save(self) -> "CarrierDriversPage":
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def delete_row(self, text: str) -> "CarrierDriversPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
