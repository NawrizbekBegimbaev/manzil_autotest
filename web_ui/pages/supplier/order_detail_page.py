"""Supplier order detail — `/orders/{uuid}`.

Sections:
- Header: «Заявка MZL-XXXX», creator, status badge, "Назад" button.
- Груз: Тип груза, Вес, Объём, Тип кузова, Способ погрузки/разгрузки.
- Маршрут: Адрес погрузки, Адрес выгрузки, Дата, Валюта.
- Предложения: list (ADMIN+MANAGER); each card shows TK info, price,
  «Заметка» field, «Выбрать победителя» button.

Action buttons by status (per matrix):
- Active             → ADMIN/MANAGER: «Отменить»
- Active w/ winner   → ADMIN/MANAGER: «В работу» (system auto)
- В работе           → ADMIN/MANAGER: «Завершить»
- DISPATCHER on own draft → «Опубликовать», «Редактировать»
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class SupplierOrderDetailPage(BasePage):
    # Match /orders/<uuid> (UUID v4 with hyphens).
    path = re.compile(r"/orders/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

    @property
    def back_button(self):
        return self.page.get_by_role("button", name="Назад")

    @property
    def status_badge(self):
        # Header includes the status text (Активна/В работе/Завершена/etc.)
        return self.page.locator("main").get_by_text(
            re.compile(r"^(Черновик|Активна|Подтверждена|В работе|Завершена|Отменена)$"),
        ).first

    @property
    def offers_section_heading(self):
        return self.page.get_by_role("heading", name="Предложения")

    @property
    def cancel_button(self):
        return self.page.get_by_role("button", name="Отменить")

    @property
    def complete_button(self):
        return self.page.get_by_role("button", name="Завершить")

    @property
    def publish_button(self):
        return self.page.get_by_role("button", name="Опубликовать")

    @property
    def edit_button(self):
        return self.page.get_by_role("button", name="Редактировать")

    @property
    def select_winner_button(self):
        return self.page.get_by_role("button", name="Выбрать победителя")

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.offers_section_heading).to_be_visible(timeout=timeout)
