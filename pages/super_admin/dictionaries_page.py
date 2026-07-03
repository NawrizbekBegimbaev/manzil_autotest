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

    def open_add(self) -> "CitiesPage":
        """Open the «Новое административное деление» dialog. Non-destructive: the
        cities list is a GLOBAL platform reference with no per-row delete, so tests
        verify the add form and cancel (submitting would pollute shared data)."""
        self.add_button.first.wait_for(state="visible")
        # Occasionally the first click doesn't open the dialog (re-render race) —
        # retry once before failing.
        for _ in range(2):
            self.add_button.first.click()
            try:
                self.dialog.wait_for(state="visible", timeout=5000)
                return self
            except Exception:
                continue
        self.dialog.wait_for(state="visible")
        return self

    def cancel(self) -> "CitiesPage":
        self.dialog.get_by_role("button", name="Отмена").click()
        self.dialog.wait_for(state="hidden")
        return self

    def add(self, code: str, name: str, pinyin: str) -> "CitiesPage":
        """Fill + submit a new top-level division (Код GB / Название иероглифы /
        Пиньинь; parent left empty). NOTE: there is no UI delete for cities, so
        avoid calling this against the shared staging dictionary in daily runs."""
        self.open_add()
        tbs = self.dialog.get_by_role("textbox")
        tbs.nth(0).fill(code)
        tbs.nth(1).fill(name)
        tbs.nth(2).fill(pinyin)
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
        self.activate(row.get_by_role("button", name="Удалить"))  # in-grid icon → keyboard
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
        self.activate(row.get_by_role("button", name="Удалить"))  # in-grid icon → keyboard
        self.page.get_by_role("dialog").get_by_role("button", name="Удалить").click()
        row.wait_for(state="detached")
        return self
