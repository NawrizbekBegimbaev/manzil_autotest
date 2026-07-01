"""CARRIER → Заявки feed + offer submission Page Object.

The carrier sees published orders it can serve in the "Все" tab, opens one, and
submits a price offer ("Предложить цену" → dialog → "Отправить").
"""

from __future__ import annotations

import re

from pages.base_page import BasePage

PATH = "/transport/orders"


class CarrierOrdersPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.offer_button = page.get_by_role("button", name="Предложить цену")
        self.dialog = page.get_by_role("dialog")
        self.submit_button = self.dialog.get_by_role("button", name="Отправить")
        self.toast_submitted = page.get_by_text("Предложение отправлено")

    def open(self) -> "CarrierOrdersPage":
        self.goto(PATH)
        return self

    def order_row(self, order_no: str):
        return self.page.get_by_role("row").filter(has_text=order_no)

    def open_order(self, order_no: str) -> "CarrierOrdersPage":
        self.order_row(order_no).first.click()
        self.page.wait_for_url(re.compile(r"/transport/orders/"))
        return self

    def submit_offer(self, price: int, notes: str = "") -> "CarrierOrdersPage":
        self.offer_button.click()
        self.dialog.wait_for(state="visible")
        # Price is the first text input in the dialog; notes the second (optional).
        self.dialog.get_by_role("textbox").first.fill(str(price))
        if notes:
            self.dialog.get_by_role("textbox").nth(1).fill(notes)
        self.submit_button.click()
        return self

    def search(self, text: str) -> "CarrierOrdersPage":
        box = self.page.get_by_placeholder("Поиск (номер заказа)")
        if box.count():
            box.first.fill(text)
        return self

    def open_tab(self, name: str) -> "CarrierOrdersPage":
        self.page.get_by_role("tab", name=name).first.click()
        return self

    def edit_offer(self, new_price: int) -> "CarrierOrdersPage":
        self.page.get_by_role("button", name="Изменить цену").click()
        self.dialog.wait_for(state="visible")
        self.dialog.get_by_role("textbox").first.fill(str(new_price))
        self.dialog.get_by_role("button", name="Сохранить", exact=True).click()
        return self

    def assign_and_start(self, plate: str) -> "CarrierOrdersPage":
        """On a won (SELECTED) order detail: pick the first available driver + plate, start."""
        self.page.get_by_role("checkbox").first.check()
        self.page.get_by_placeholder("Гос. номер").first.fill(plate)
        self.page.get_by_role("button", name="Назначить и начать").click()
        return self
