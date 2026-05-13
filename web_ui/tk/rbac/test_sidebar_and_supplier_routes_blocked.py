"""RBAC: TK_ADMIN sees only TK sidebar items, can't reach Supplier pages.

Sidebar items (live recon):
  TK_ADMIN → Лента заявок, Автопарк, Отклики (3 items)
  None of the supplier routes (/dashboard, /orders, /warehouses, /employees)
  should render their respective admin chrome for a TK user — the SPA
  must redirect or show an empty state. Either is acceptable; what's
  NOT acceptable is rendering supplier-only widgets like the
  «Добавить сотрудника» button.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages._common.sidebar import Sidebar


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_lands_on_feed_with_tk_sidebar(
    tk_page, settings: Settings,
) -> None:
    tk_page.goto(f"{settings.web_base_url_str}/feed")
    Sidebar(tk_page).expect_tk()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
@pytest.mark.parametrize(
    ("supplier_route", "supplier_widget_name"),
    [
        ("/employees", "Добавить сотрудника"),
        ("/warehouses", "Добавить склад"),
        ("/orders", "Создать заявку"),
    ],
)
def test_tk_does_not_render_supplier_widgets_on_supplier_routes(
    tk_page, settings: Settings,
    supplier_route: str, supplier_widget_name: str,
) -> None:
    tk_page.goto(f"{settings.web_base_url_str}{supplier_route}")
    expect(
        tk_page.get_by_role("button", name=supplier_widget_name),
    ).to_have_count(0)
    expect(
        tk_page.get_by_role("link", name=supplier_widget_name),
    ).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_visiting_dashboard_does_not_show_supplier_analytics_heading(
    tk_page, settings: Settings,
) -> None:
    """Supplier /dashboard heading is «Аналитика» — TK must not see it."""
    tk_page.goto(f"{settings.web_base_url_str}/dashboard")
    expect(
        tk_page.get_by_role("heading", name="Аналитика"),
    ).to_have_count(0)
