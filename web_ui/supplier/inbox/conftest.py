"""Shared fixtures for inbox tests — orders in specific statuses.

All setup goes through the API (well-tested, fast). UI just observes
the resulting state. Cleanup tolerates 409 because some tests may
advance the order past the cancellable phase.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator

import pytest

from api.client import ApiClient, ApiError
from api.endpoints import offers as off_ep
from api.endpoints import orders as ord_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import OrderResponse
from data import builders
from web_ui.seed.cleanup import UI_TAG, wipe_supplier_warehouses


def _ui_tag() -> str:
    return f"{UI_TAG} inbox-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def in_progress_order(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
    supplier_manager_api: ApiClient,
    tk_api: ApiClient,
) -> Iterator[OrderResponse]:
    """An order in the «В работе» status, owned by TeamQa.

    Setup: DISPATCHER publishes → TK submits offer → MANAGER selects
    winner (BUG-015: ADMIN gets 403 on /select; MANAGER works).
    """
    tag = _ui_tag()
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
    offer = off_ep.submit_offer(
        tk_api,
        order.id,
        builders.offer_request(price=999, currency="USD", comment=tag),
    )
    advanced = off_ep.select_winner(supplier_manager_api, order.id, offer.id)
    assert advanced.status in {"in_progress", "IN_PROGRESS"}, advanced.status
    try:
        yield advanced
    finally:
        # «В работе» orders may not be cancellable depending on flow;
        # tolerate 409 either way.
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)
        wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def active_order_with_offer(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
    tk_api: ApiClient,
) -> Iterator[OrderResponse]:
    """An «Активна» order with one TK offer attached (no winner yet)."""
    tag = _ui_tag()
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
    off_ep.submit_offer(
        tk_api,
        order.id,
        builders.offer_request(price=777, currency="USD", comment=tag),
    )
    try:
        yield order
    finally:
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)
        wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def own_draft_order(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
) -> Iterator[OrderResponse]:
    """A DRAFT order owned by the dispatcher."""
    tag = _ui_tag()
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
            publish=False,
        ),
    )
    assert order.status.upper() == "DRAFT", order.status
    try:
        yield order
    finally:
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)
        wipe_supplier_warehouses(supplier_admin_api)
