"""Cargo shipping orders (BRD US-6, US-7)."""

from __future__ import annotations

from uuid import UUID

from api.client import ApiClient
from api.schemas import (
    OrderCancelRequest,
    OrderRequest,
    OrderResponse,
    OrderUpdateRequest,
    PageResponse,
)


def list_orders(
    client: ApiClient,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 0,
    size: int = 20,
    sort: str = "createdAt,DESC",
) -> PageResponse[OrderResponse]:
    """GET /api/v1/orders."""
    params: dict[str, object] = {"page": page, "size": size, "sort": sort}
    if status is not None:
        params["status"] = status
    if search is not None:
        params["search"] = search
    response = client.get("/api/v1/orders", params=params, expect_status=200)
    return PageResponse[OrderResponse].model_validate(response.json())


def create_order(client: ApiClient, body: OrderRequest) -> OrderResponse:
    """POST /api/v1/orders — dispatcher only."""
    response = client.post(
        "/api/v1/orders",
        json=body.model_dump(by_alias=True, mode="json"),
        expect_status=201,
    )
    return OrderResponse.model_validate(response.json())


def get_order(client: ApiClient, order_id: UUID) -> OrderResponse:
    response = client.get(f"/api/v1/orders/{order_id}", expect_status=200)
    return OrderResponse.model_validate(response.json())


def update_draft_order(
    client: ApiClient,
    order_id: UUID,
    body: OrderUpdateRequest,
) -> OrderResponse:
    """PATCH /api/v1/orders/{id} — dispatcher edits own DRAFT."""
    response = client.patch(
        f"/api/v1/orders/{order_id}",
        json=body.model_dump(by_alias=True, mode="json", exclude_none=True),
        expect_status=200,
    )
    return OrderResponse.model_validate(response.json())


def publish_order(client: ApiClient, order_id: UUID) -> OrderResponse:
    """POST /api/v1/orders/{id}/publish — DRAFT → ACTIVE."""
    response = client.post(f"/api/v1/orders/{order_id}/publish", expect_status=200)
    return OrderResponse.model_validate(response.json())


def cancel_order(
    client: ApiClient,
    order_id: UUID,
    body: OrderCancelRequest | None = None,
) -> OrderResponse:
    """POST /api/v1/orders/{id}/cancel — supplier-side cancel before delivery."""
    payload = body.model_dump(by_alias=True, exclude_none=True) if body else None
    response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json=payload,
        expect_status=200,
    )
    return OrderResponse.model_validate(response.json())


def complete_order(client: ApiClient, order_id: UUID) -> OrderResponse:
    """POST /api/v1/orders/{id}/complete — IN_PROGRESS → COMPLETED."""
    response = client.post(f"/api/v1/orders/{order_id}/complete", expect_status=200)
    return OrderResponse.model_validate(response.json())
