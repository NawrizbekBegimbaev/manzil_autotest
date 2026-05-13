"""Supplier order detail — sections render, status shows, back works.

Tests open a SPECIFIC order (created/cleaned-up via API per test) instead
of clicking the first row in the list. The list is shared and mutates
when the e2e suite runs, so "click first row" was flaky — direct
navigation to a known UUID is deterministic.
"""

from __future__ import annotations

import contextlib
import re
import uuid
from collections.abc import Iterator

import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import orders as ord_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import OrderResponse
from config.settings import Settings
from data import builders
from web_ui.pages.supplier.orders_list_page import SupplierOrdersListPage
from web_ui.seed.cleanup import UI_TAG, wipe_supplier_warehouses


@pytest.fixture
def own_active_order(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
) -> Iterator[OrderResponse]:
    """A fresh published order created and cleaned up via API."""
    tag = f"{UI_TAG} {uuid.uuid4().hex[:8]}"
    warehouse = wh_ep.create_warehouse(
        supplier_dispatcher_api, builders.warehouse(name=f"{tag} WH"),
    )
    destination = wh_ep.create_warehouse(
        supplier_dispatcher_api, builders.warehouse(name=f"{tag} DST"),
    )
    order = ord_ep.create_order(
        supplier_dispatcher_api,
        builders.order_request(
            warehouse_id=warehouse.id,
            destination_warehouse_id=destination.id,
            body_type="TENT",
            currency="USD",
            cargo_type=f"{tag} cargo",
            publish=True,
        ),
    )
    try:
        yield order
    finally:
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)
        wipe_supplier_warehouses(supplier_admin_api)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_can_open_order_detail_via_url(
    own_active_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    supplier_admin_page.goto(
        f"{settings.web_base_url_str}/orders/{own_active_order.id}",
    )
    expect(supplier_admin_page).to_have_url(
        re.compile(r"/orders/[0-9a-f-]{36}"),
    )
    expect(
        supplier_admin_page.get_by_role("heading", name="Груз"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_order_detail_shows_three_sections(
    own_active_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    supplier_admin_page.goto(
        f"{settings.web_base_url_str}/orders/{own_active_order.id}",
    )
    for section in ("Груз", "Маршрут", "Предложения"):
        expect(
            supplier_admin_page.get_by_role("heading", name=section),
        ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_order_detail_shows_status_badge(
    own_active_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    supplier_admin_page.goto(
        f"{settings.web_base_url_str}/orders/{own_active_order.id}",
    )
    expect(
        supplier_admin_page.get_by_role("heading", name="Груз"),
    ).to_be_visible()
    badge = supplier_admin_page.locator("main").get_by_text(
        re.compile(r"^(Черновик|Активна|Подтверждена|В работе|Завершена|Отменена)$"),
    ).first
    expect(badge).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_back_button_returns_to_list(
    own_active_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    """«Назад» from order detail must take the user back to /orders.

    Nav into detail via the list (not via a direct URL) so SPA history
    has a real previous entry — `Назад` likely calls `history.back()`,
    which only works when the previous entry is the list.
    """
    listing = SupplierOrdersListPage(supplier_admin_page, settings.web_base_url_str)
    listing.goto()
    supplier_admin_page.goto(
        f"{settings.web_base_url_str}/orders/{own_active_order.id}",
    )
    expect(
        supplier_admin_page.get_by_role("heading", name="Груз"),
    ).to_be_visible()
    supplier_admin_page.get_by_role("button", name="Назад").click()
    supplier_admin_page.wait_for_url(
        re.compile(r".*/orders/?(\?.*)?$"), timeout=10_000,
    )
    expect(listing.heading).to_be_visible()
