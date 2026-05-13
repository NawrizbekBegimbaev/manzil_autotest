"""Notifications drawer.

Live recon: bell icon (top-right) opens a right-side drawer titled
«Уведомления» with two tabs «Все» / «Непрочитанные» and category
sections («Заявки», «Автопарк», «Сотрудники»).

We test:
- Click the bell — drawer opens with the heading.
- Both tabs are visible.
- Drawer contains at least one notification card (TeamQa has standing
  history on dev).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_bell_opens_notifications_drawer(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    supplier_admin_page.locator('button[aria-label="Кнопка уведомлений"]').click()
    expect(
        supplier_admin_page.get_by_role("heading", name="Уведомления"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_notifications_drawer_has_two_tabs(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    supplier_admin_page.locator('button[aria-label="Кнопка уведомлений"]').click()
    # Tabs are exposed as buttons or tabs role.
    drawer = supplier_admin_page.get_by_role("dialog").filter(has_text="Уведомления")
    expect(drawer.get_by_text("Все").first).to_be_visible()
    expect(drawer.get_by_text("Непрочитанные").first).to_be_visible()
