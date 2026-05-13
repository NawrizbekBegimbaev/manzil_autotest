"""Carrier feed (BRD US-8 TK / US-10 driver)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest

from api.client import ApiClient
from api.endpoints import feed as feed_ep
from api.endpoints import orders as ord_ep
from api.endpoints import vehicles as vh_ep
from api.schemas import FeedQuery
from data import builders


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_tk_feed_includes_active_order_with_matching_body_type(
    tk_admin_client: ApiClient,
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    """Add a tent vehicle to TK fleet, supplier publishes a tent order,
    feed must surface it."""
    vh_ep.add_vehicle(tk_admin_client, builders.vehicle(plate="01F100BC", body_type="TENT"))
    order = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            body_type="TENT",
            publish=True,
        ),
    )
    page = feed_ep.get_feed(tk_admin_client, FeedQuery(body_type="TENT", size=200))
    assert order.id in {o.id for o in page.content}


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_feed_filters_by_body_type_override(
    tk_admin_client: ApiClient,
) -> None:
    """`bodyType=container` returns only container orders. May be empty."""
    page = feed_ep.get_feed(tk_admin_client, FeedQuery(body_type="CONTAINER"))
    for order in page.content:
        assert order.body_type == "CONTAINER"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_feed_with_date_range_filters(
    tk_admin_client: ApiClient,
) -> None:
    """Pass dateFrom..dateTo, response only contains matching orders."""
    today = date.today()
    page = feed_ep.get_feed(
        tk_admin_client,
        FeedQuery(date_from=today, date_to=today + timedelta(days=30)),
    )
    for order in page.content:
        assert today <= order.desired_date <= today + timedelta(days=30)


@pytest.mark.negative
def test_feed_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        feed_ep.get_feed(api_client)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_feed_as_supplier_returns_403(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(403):
        feed_ep.get_feed(supplier_admin_client)
