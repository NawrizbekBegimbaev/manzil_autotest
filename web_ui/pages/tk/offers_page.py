"""TK my-offers — `/offers`.

Lists outgoing offers. Columns: Заявка, Цена, Статус, Дата.
Status badges seen: «Выбрано». Other expected: «На рассмотрении»,
«Отклонено», «Отозвано».
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class TKOffersPage(BasePage):
    path = "/offers"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Отклики").first

    def row_by_order_short_id(self, short_id: str):
        """Match a row by the short order ID column (e.g. "#44efdc")."""
        return self.page.get_by_role("row").filter(has_text=short_id)

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
