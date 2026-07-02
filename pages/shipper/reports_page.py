"""SHIPPER ADMIN/MANAGER → Отчёты: average-price + by-company tabs."""

from __future__ import annotations

from pages.base_page import BasePage

PATH = "/shipper/reports"


class ReportsPage(BasePage):
    def __init__(self, page, cfg) -> None:
        super().__init__(page, cfg)

    def open(self) -> "ReportsPage":
        self.goto(PATH)
        return self

    def open_tab(self, name: str) -> "ReportsPage":
        self.page.get_by_role("tab", name=name).click()
        return self

    @property
    def table(self):
        return self.page.locator('[role="grid"], table').first
