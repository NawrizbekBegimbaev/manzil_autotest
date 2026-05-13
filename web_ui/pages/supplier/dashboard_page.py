"""Supplier analytics dashboard — `/dashboard`.

Landing page after Supplier login. Per matrix: visible to ADMIN and
MANAGER (DISPATCHER lands here too, but only sees their own orders in
later sections).
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class SupplierDashboardPage(BasePage):
    path = "/dashboard"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Аналитика")

    @property
    def total_orders_card(self):
        return self.page.get_by_text("Всего заявок").locator("..")

    @property
    def in_progress_card(self):
        return self.page.get_by_text("В работе", exact=True).first

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
