"""SHIPPER ADMIN → Склады: list + inline add/edit/delete Page Object."""

from __future__ import annotations

from pages.base_page import BasePage

PATH = "/shipper/warehouses"


class WarehousesPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить склад")
        self.dialog = page.get_by_role("dialog")

    def open(self) -> "WarehousesPage":
        self.goto(PATH)
        return self

    def _field(self, name: str):
        return self.dialog.locator(f"input[name={name}]")

    def add(self, name: str, address: str = "Sayyod 1") -> "WarehousesPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        self._field("name").fill(name)
        # Страна (countryId) → Город (cityId): two MUI selects, city depends on country.
        self.dialog.get_by_role("combobox").nth(0).click()
        self.page.get_by_role("option").first.click()
        self.dialog.get_by_role("combobox").nth(1).click()
        self.page.get_by_role("option").first.click()
        self._field("address").fill(address)
        self.dialog.get_by_role("button", name="Добавить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def search(self, text: str) -> "WarehousesPage":
        self.filter_search("Название или адрес", text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def delete_row(self, text: str) -> "WarehousesPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        self.activate(row.get_by_role("button", name="Удалить"))  # in-grid icon → keyboard
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
