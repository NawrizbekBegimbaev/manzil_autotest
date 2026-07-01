"""SHIPPER ADMIN → Заказы list + order detail (offers / select winner) POM.

The shipper opens an order, sees carrier offers, and accepts one
("Принять" → confirm "Принять предложение?" → "Принять").
"""

from __future__ import annotations

import re

from pages.base_page import BasePage

PATH = "/shipper/orders"


class ShipperOrdersPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.dialog = page.get_by_role("dialog")
        self.toast_winner = page.get_by_text("Перевозчик выбран")

    def open(self) -> "ShipperOrdersPage":
        self.goto(PATH)
        return self

    def order_row(self, order_no: str):
        return self.page.get_by_role("row").filter(has_text=order_no)

    def open_order(self, order_no: str) -> "ShipperOrdersPage":
        self.order_row(order_no).first.click()
        self.page.wait_for_url(re.compile(r"/shipper/orders/"))
        return self

    def accept_first_offer(self) -> "ShipperOrdersPage":
        self.page.get_by_role("button", name="Принять").first.click()
        self.dialog.wait_for(state="visible")
        self.dialog.get_by_role("button", name="Принять").click()
        return self

    def filter_by_number(self, order_no: str) -> "ShipperOrdersPage":
        self.page.get_by_placeholder("Номер заказа").fill(order_no)
        btn = self.page.get_by_role("button", name="Подтвердить")
        if btn.count():
            btn.first.click()
        return self

    def offers_table(self):
        """Offers section on the order detail page."""
        return self.page.get_by_role("table")

    def cancel_order_from_list(self, order_no: str, reason: str = "Отмена по тесту") -> "ShipperOrdersPage":
        """Cancel a SELECTED+ order via the list row action menu."""
        self.filter_by_number(order_no)
        row = self.order_row(order_no).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Отменить заказ").click()
        self.dialog.wait_for(state="visible")
        ta = self.dialog.locator("textarea, input[type=text]")
        if ta.count():
            ta.first.fill(reason)
        # primary confirm button in the dialog
        self.dialog.get_by_role("button").last.click()
        return self

    def complete_order_detail(self, order_no: str) -> "ShipperOrdersPage":
        """Open an IN_TRANSIT order and complete it."""
        self.open_order(order_no)
        self.page.get_by_role("button", name="Завершить").first.click()
        if self.dialog.is_visible():
            self.dialog.get_by_role("button").last.click()
        return self
