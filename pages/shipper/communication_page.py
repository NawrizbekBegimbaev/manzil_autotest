"""SHIPPER MANAGER → Диспетчер (communication): list + driver-call status."""

from __future__ import annotations

from pages.base_page import BasePage

PATH = "/shipper/communication"


class CommunicationPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)
        self.dialog = page.get_by_role("dialog")

    def open(self) -> "CommunicationPage":
        self.goto(PATH)
        return self

    def filter_by_number(self, order_no: str) -> "CommunicationPage":
        self.filter_search("Номер заказа", order_no)
        return self

    def order_row(self, order_no: str):
        return self.page.get_by_role("row").filter(has_text=order_no)

    def open_call_status(self, order_no: str) -> "CommunicationPage":
        self.filter_by_number(order_no)
        row = self.order_row(order_no).first
        row.wait_for(state="visible")
        self.open_row_menu(row)
        self.page.get_by_role("menuitem", name="Связь с водителем").click()
        return self
