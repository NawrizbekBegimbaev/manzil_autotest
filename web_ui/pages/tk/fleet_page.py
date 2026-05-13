"""TK fleet (автопарк) — `/fleet`.

Live recon (2026-05-03):
  Heading «Автопарк», subtitle «Список автомобилей вашей компании.
  Используется для фильтрации заявок.»
  Action button «Добавить автомобиль» in header.
  Table columns: Номер, Марка / Модель, Тип кузова, Грузоподъёмность,
                 Объём, Действия.
  Body types observed: Тент, Контейнер, Рефрижератор, Низкая платформа
  (also Изотерм, Другое from feed-filter dropdown).

Add dialog title: «Добавить автомобиль». Fields:
  Марка, Модель, Госномер  (NOT «Номер»),
  Тип кузова (combobox, default «Тент»),
  Грузоподъёмность, кг (default 0),
  Объём, м³            (default 0),
  Дополнительные характеристики (free text, optional).
Buttons: Отмена, Создать.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from web_ui.pages._base import BasePage


class TKFleetPage(BasePage):
    path = "/fleet"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Автопарк").first

    @property
    def add_vehicle_button(self):
        return self.page.get_by_role("button", name="Добавить автомобиль")

    def row_by_plate(self, plate: str):
        return self.page.get_by_role("row").filter(has_text=plate)

    def edit_vehicle(self, plate: str) -> None:
        self.row_by_plate(plate).get_by_role("button", name="Редактировать").click()

    def click_delete_button(self, plate: str) -> None:
        """Click the row's «Удалить» icon — fires `window.confirm()`.
        Caller must install a dialog handler before this call."""
        self.row_by_plate(plate).get_by_role("button", name="Удалить").click()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)


class VehicleDialog:
    """Modal opened by «Добавить автомобиль» / «Редактировать»."""

    def __init__(self, page: Page) -> None:
        self.page = page

    @property
    def root(self):
        return self.page.get_by_role("dialog", name="Добавить автомобиль").or_(
            self.page.get_by_role("dialog", name="Редактировать автомобиль"),
        )

    @property
    def make_input(self):
        return self.root.get_by_role("textbox", name="Марка")

    @property
    def model_input(self):
        return self.root.get_by_role("textbox", name="Модель")

    @property
    def plate_input(self):
        return self.root.get_by_role("textbox", name="Госномер")

    @property
    def body_type_select(self):
        return self.root.get_by_role("combobox", name="Тип кузова")

    @property
    def capacity_kg_input(self):
        return self.root.get_by_role("textbox", name="Грузоподъёмность, кг")

    @property
    def volume_m3_input(self):
        return self.root.get_by_role("textbox", name="Объём, м³")

    @property
    def extra_input(self):
        return self.root.get_by_role(
            "textbox", name="Дополнительные характеристики",
        )

    @property
    def save_button(self):
        return self.root.get_by_role("button", name="Создать").or_(
            self.root.get_by_role("button", name="Сохранить"),
        )

    @property
    def cancel_button(self):
        return self.root.get_by_role("button", name="Отмена")

    def fill(
        self,
        *,
        make: str,
        model: str,
        plate: str,
        body_type: str = "Тент",
        capacity_kg: int = 1000,
        volume_m3: int = 10,
    ) -> None:
        self.make_input.fill(make)
        self.model_input.fill(model)
        self.plate_input.fill(plate)
        if body_type:
            self.body_type_select.click()
            self.page.get_by_role("option", name=body_type).click()
        self.capacity_kg_input.fill(str(capacity_kg))
        self.volume_m3_input.fill(str(volume_m3))

    def submit(self) -> None:
        self.save_button.click()
