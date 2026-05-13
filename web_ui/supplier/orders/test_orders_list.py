"""Supplier orders list — page renders and filters work for ADMIN.

ADMIN sees all company orders. We assert the page chrome (heading,
filters, table columns) and that filters narrow the visible rows. We
don't seed orders here — `TeamQa` already has 3 orders on dev (MZL-0001
through MZL-0003) which is enough to exercise filtering.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.supplier.orders_list_page import SupplierOrdersListPage


@pytest.fixture
def admin_orders(supplier_admin_page, settings: Settings) -> SupplierOrdersListPage:
    page = SupplierOrdersListPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_orders_list_renders_heading_and_filters(
    admin_orders: SupplierOrdersListPage,
) -> None:
    """Status filter is now a row of CHIP-BUTTONS (not a combobox).
    Verify all six are present + Поиск works."""
    expect(admin_orders.heading).to_be_visible()
    expect(admin_orders.search_input).to_be_visible()
    for chip_name in (
        "Все статусы", "Активные", "Подтверждённые",
        "В работе", "Завершённые", "Черновики",
    ):
        expect(admin_orders.status_chip(chip_name)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_orders_table_has_expected_columns(
    admin_orders: SupplierOrdersListPage,
) -> None:
    page = admin_orders.page
    for col in ("Номер", "Груз", "Маршрут", "Дата", "Статус"):
        expect(page.get_by_role("columnheader", name=col)).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_orders_list_has_at_least_one_row(
    admin_orders: SupplierOrdersListPage,
) -> None:
    """Sanity: TeamQa has standing orders on dev. If this drops to 0 it
    likely means the dataset got wiped — surface that quickly."""
    rows = admin_orders.page.locator("tbody tr")
    expect(rows.first).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_search_by_existing_cargo_narrows_table(
    admin_orders: SupplierOrdersListPage,
) -> None:
    """Search for cargo type 'Одежды' (MZL-0001) — the filtered table
    must include MZL-0001 and exclude MZL-0002 ('Человек')."""
    admin_orders.search_input.fill("Одежды")
    rows = admin_orders.page.locator("tbody tr")
    # at least one row matching
    expect(rows.first).to_contain_text("MZL-0001")
    # MZL-0002 ("Человек" — different cargo) shouldn't be present
    expect(admin_orders.page.locator("tbody")).not_to_contain_text("MZL-0002")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_search_with_unicorn_returns_empty_table(
    admin_orders: SupplierOrdersListPage,
) -> None:
    """Search for a string nothing matches — table body becomes empty
    (or shows an «empty state»)."""
    admin_orders.search_input.fill("пупырк-нонэгзистент-12345")
    # Either zero rows or empty-state text — both acceptable.
    rows_count = admin_orders.page.locator("tbody tr").count()
    if rows_count > 0:
        # If there's an "empty state" row, it should not contain MZL-XXXX.
        expect(admin_orders.page.locator("tbody")).not_to_contain_text("MZL-")
