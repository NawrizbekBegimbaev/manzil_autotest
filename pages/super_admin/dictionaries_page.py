"""SUPER_ADMIN → Справочники: Города и Типы транспорта.

Inline add/edit dialogs. Row actions are IconButtons with aria-label
«Редактировать» / «Удалить».
"""

from __future__ import annotations

from pages.base_page import BasePage

CITIES_PATH = "/super-admin/cities"
VEHICLE_TYPES_PATH = "/super-admin/vehicle-types"


class CitiesPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить", exact=True)
        self.dialog = page.get_by_role("dialog")

    def open(self) -> "CitiesPage":
        self.goto(CITIES_PATH)
        return self

    def add(self, name: str, country: str) -> "CitiesPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        # First text input = Название; the combobox = Страна.
        self.dialog.get_by_role("textbox").first.fill(name)
        self.dialog.get_by_role("combobox").first.click()
        self.page.get_by_role("option", name=country, exact=True).click()
        self.dialog.get_by_role("button", name="Добавить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def search(self, text: str) -> "CitiesPage":
        box = self.page.get_by_placeholder("Название города")
        if box.count():
            box.fill(text)
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def delete_row(self, text: str) -> "CitiesPage":
        self.search(text)
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self


class VehicleTypesPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.add_button = page.get_by_role("button", name="Добавить", exact=True)
        self.dialog = page.get_by_role("dialog")

    def open(self) -> "VehicleTypesPage":
        self.goto(VEHICLE_TYPES_PATH)
        return self

    def add(self, name: str) -> "VehicleTypesPage":
        self.add_button.click()
        self.dialog.wait_for(state="visible")
        self.dialog.get_by_role("textbox").first.fill(name)
        self.dialog.get_by_role("button", name="Добавить", exact=True).click()
        self.dialog.wait_for(state="hidden")
        return self

    def row(self, text: str):
        return self.page.get_by_role("row").filter(has_text=text)

    def delete_row(self, text: str) -> "VehicleTypesPage":
        row = self.row(text).first
        row.wait_for(state="visible")
        row.get_by_role("button", name="Удалить").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
