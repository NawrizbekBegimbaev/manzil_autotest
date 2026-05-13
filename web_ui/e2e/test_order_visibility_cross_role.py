"""Cross-role visibility invariants.

These tests drive both Supplier and TK contexts in the same Python
process. Pattern:

  setup  : create an order via API (fast, deterministic)
  action : observe in the OTHER role's UI
  assert : the right thing appears (or disappears)
  teardown: cancel the order + delete the warehouse via API

Why API for setup and not UI? Two reasons:
1. UI flows take 5–15s each — with cross-role we need 4+ flows per test
   (supplier login + warehouse create + order create + TK open feed),
   total ≥ 30s without setup-via-API. API setup keeps each test under
   10s.
2. We're testing CROSS-ROLE behaviour, not the create-via-UI path
   (already covered by Layer 1/2). The invariant is "order visible in
   role A's view because role B did X" — independent of whether B did
   it through UI or API.

Body type = «tent» throughout — TeamQa fleet has a tent vehicle so the
matching invariant holds; tests don't accidentally fail due to fleet
mismatch.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import orders as ord_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import OrderResponse
from config.settings import Settings
from data import builders
from web_ui.pages.tk.feed_page import TKFeedPage
from web_ui.seed.cleanup import UI_TAG, wipe_supplier_warehouses

# ---------- shared setup --------------------------------------------------


@pytest.fixture
def fresh_published_tent_order(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
) -> Iterator[OrderResponse]:
    """Create a real published `tent`-bodyType order on the Supplier side.

    Uses the DISPATCHER role (only one allowed to create per matrix).
    Cleanup: the order is cancelled, then a warehouse sweep removes
    the [E2E-UI] warehouse. ADMIN cleanup runs on its own client to
    avoid coupling teardown to the dispatcher's permissions.
    """
    # UUID suffix → unique per test run AND per test, so leftover orders
    # from a previously-failed run can't trigger ambiguous matches.
    tag = f"{UI_TAG} {uuid.uuid4().hex[:8]}"
    warehouse = wh_ep.create_warehouse(
        supplier_dispatcher_api,
        builders.warehouse(name=f"{tag} WH"),
    )
    destination = wh_ep.create_warehouse(
        supplier_dispatcher_api,
        builders.warehouse(name=f"{tag} DST"),
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
        # ADMIN cancels (DISPATCHER can't — only ADMIN/MANAGER per
        # matrix; backend returns 409 if dispatcher tries). 409 still
        # tolerated because the test may have selected a winner →
        # in_progress, which is then non-cancellable.
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)
        wipe_supplier_warehouses(supplier_admin_api)


def _tk_open_feed(tk_page, settings: Settings) -> TKFeedPage:
    feed = TKFeedPage(tk_page, settings.web_base_url_str)
    feed.goto()
    feed.page.locator("tbody tr").first.wait_for(state="visible")
    return feed


def _feed_includes(feed: TKFeedPage, order: OrderResponse, *, timeout: int = 10_000) -> bool:
    """True if the feed table contains a row matching `order` within
    timeout.

    Match by `cargo_type` (we always tag it with `[E2E-UI]` + a random
    chunk so it's unique across the whole feed). MZL numbers are NOT
    globally unique — the feed mixes orders from many supplier
    companies, each with its own MZL counter, so two visible rows can
    share the same «MZL-0012».
    """
    from playwright.sync_api import TimeoutError as PWTimeout
    locator = feed.page.locator("tbody tr").filter(has_text=order.cargo_type)
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except PWTimeout:
        return False


# ---------- visibility tests ---------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_cross
@pytest.mark.requires_real_account
def test_published_tent_order_appears_in_tk_feed(
    fresh_published_tent_order: OrderResponse,
    tk_page,
    settings: Settings,
) -> None:
    """A published order created by Dispatcher must appear in TK_Admin's
    feed (TK has a tent vehicle so the bodyType filter passes)."""
    with allure.step("TK opens /feed and sees the new order"):
        feed = _tk_open_feed(tk_page, settings)
        assert _feed_includes(feed, fresh_published_tent_order), (
            f"order {fresh_published_tent_order.id} not visible in TK feed "
            f"after publish"
        )


@pytest.mark.ui
@pytest.mark.ui_cross
@pytest.mark.requires_real_account
def test_cancelled_order_disappears_from_tk_feed(
    supplier_admin_api: ApiClient,
    fresh_published_tent_order: OrderResponse,
    tk_page,
    settings: Settings,
) -> None:
    """After Supplier-Admin cancels, TK must NOT see the order in /feed.

    NOTE: the ADMIN client is used for cancellation because the
    DISPATCHER client returned 409 from POST /orders/{id}/cancel — per
    matrix only ADMIN/MANAGER can cancel; DISPATCHER cannot.
    """
    with allure.step("Verify the order IS visible before cancel"):
        feed = _tk_open_feed(tk_page, settings)
        assert _feed_includes(feed, fresh_published_tent_order)

    with allure.step("Supplier-Admin cancels via API"):
        ord_ep.cancel_order(supplier_admin_api, fresh_published_tent_order.id)

    with allure.step("TK reloads /feed — order is gone"):
        tk_page.reload()
        feed.page.locator("tbody tr").first.wait_for(state="visible")
        assert not _feed_includes(
            feed, fresh_published_tent_order, timeout=2_000,
        ), "cancelled order should disappear from TK feed"


@pytest.mark.ui
@pytest.mark.ui_cross
@pytest.mark.requires_real_account
def test_published_order_appears_in_supplier_admin_orders_list(
    fresh_published_tent_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    """Order created by Dispatcher (a colleague) must show up in
    SUPPLIER_ADMIN's full-company list."""
    from web_ui.pages.supplier.orders_list_page import SupplierOrdersListPage

    listing = SupplierOrdersListPage(
        supplier_admin_page, settings.web_base_url_str,
    )
    listing.goto()
    supplier_admin_page.locator("tbody tr").first.wait_for(state="visible")
    # In Supplier's own list the MZL number IS unique (per company), but
    # using cargo_type stays consistent with the cross-role helper.
    expect(
        supplier_admin_page.locator("tbody tr").filter(
            has_text=fresh_published_tent_order.cargo_type,
        ),
    ).to_be_visible()
