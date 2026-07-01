"""SHIPPER MANAGER → Оператор склада (storeroom): list + order detail + actions."""

from __future__ import annotations

import re

from pages.base_page import BasePage

PATH = "/shipper/storeroom"


class StoreroomPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.dialog = page.get_by_role("dialog")

    def open(self) -> "StoreroomPage":
        self.goto(PATH)
        return self

    def filter_by_number(self, order_no: str) -> "StoreroomPage":
        box = self.page.get_by_placeholder("Номер заказа")
        if box.count():
            box.first.fill(order_no)
        return self

    def order_row(self, order_no: str):
        return self.page.get_by_role("row").filter(has_text=order_no)

    def open_order(self, order_no: str) -> "StoreroomPage":
        self.order_row(order_no).first.click()
        self.page.wait_for_url(re.compile(r"/shipper/storeroom/"))
        return self

    def cancel_order(self, order_no: str, reason: str = "Отмена по тесту") -> "StoreroomPage":
        self.filter_by_number(order_no)
        row = self.order_row(order_no).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Отменить заказ").click()
        self.dialog.wait_for(state="visible")
        ta = self.dialog.locator("textarea, input[type=text]")
        if ta.count():
            ta.first.fill(reason)
        self.dialog.get_by_role("button").last.click()
        return self

    def open_republish(self, order_no: str) -> "StoreroomPage":
        self.filter_by_number(order_no)
        row = self.order_row(order_no).first
        row.wait_for(state="visible")
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Опубликовать повторно").click()
        self.dialog.wait_for(state="visible")
        return self
