"""Carrier feed — TK admin (US-8) and driver (US-10)."""

from __future__ import annotations

from api.client import ApiClient
from api.schemas import FeedQuery, OrderResponse, PageResponse


def get_feed(client: ApiClient, query: FeedQuery | None = None) -> PageResponse[OrderResponse]:
    """GET /api/v1/feed — orders matched against caller's fleet bodyType.

    By default the backend filters by the caller's vehicles' body types;
    pass `bodyType` in `query` to override.
    """
    params = (query or FeedQuery()).to_query()
    response = client.get("/api/v1/feed", params=params, expect_status=200)
    return PageResponse[OrderResponse].model_validate(response.json())
