"""Carrier offers + manager actions (BRD US-9 / US-12 / US-14)."""

from __future__ import annotations

from uuid import UUID

from api.client import ApiClient
from api.schemas import (
    OfferNoteRequest,
    OfferRequest,
    OfferResponse,
    OfferUpdateRequest,
    OrderResponse,
    PageResponse,
)


def list_offers_for_order(
    client: ApiClient,
    order_id: UUID,
) -> list[OfferResponse]:
    """GET /api/v1/orders/{orderId}/offers — supplier manager sees active offers."""
    response = client.get(f"/api/v1/orders/{order_id}/offers", expect_status=200)
    body = response.json()
    if isinstance(body, list):
        return [OfferResponse.model_validate(item) for item in body]
    page = PageResponse[OfferResponse].model_validate(body)
    return page.content


def submit_offer(
    client: ApiClient,
    order_id: UUID,
    body: OfferRequest,
) -> OfferResponse:
    """POST /api/v1/orders/{orderId}/offers — TK or driver submits a price."""
    response = client.post(
        f"/api/v1/orders/{order_id}/offers",
        json=body.model_dump(by_alias=True),
        expect_status=201,
    )
    return OfferResponse.model_validate(response.json())


def update_own_offer(
    client: ApiClient,
    order_id: UUID,
    offer_id: UUID,
    body: OfferUpdateRequest,
) -> OfferResponse:
    response = client.patch(
        f"/api/v1/orders/{order_id}/offers/{offer_id}",
        json=body.model_dump(by_alias=True, exclude_none=True),
        expect_status=200,
    )
    return OfferResponse.model_validate(response.json())


def withdraw_own_offer(
    client: ApiClient,
    order_id: UUID,
    offer_id: UUID,
) -> OfferResponse:
    """POST .../withdraw — active → withdrawn (US-9 §5 / US-11 §5)."""
    response = client.post(
        f"/api/v1/orders/{order_id}/offers/{offer_id}/withdraw",
        expect_status=200,
    )
    return OfferResponse.model_validate(response.json())


def upsert_offer_note(
    client: ApiClient,
    order_id: UUID,
    offer_id: UUID,
    body: OfferNoteRequest,
) -> OfferResponse:
    """PUT .../note — manager attaches/replaces note (US-12 §6)."""
    response = client.put(
        f"/api/v1/orders/{order_id}/offers/{offer_id}/note",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return OfferResponse.model_validate(response.json())


def select_winner(
    client: ApiClient,
    order_id: UUID,
    offer_id: UUID,
) -> OrderResponse:
    """POST .../select — manager picks winner (US-14). Returns the updated order."""
    response = client.post(
        f"/api/v1/orders/{order_id}/offers/{offer_id}/select",
        expect_status=200,
    )
    return OrderResponse.model_validate(response.json())


def list_my_offers(
    client: ApiClient,
    *,
    page: int = 0,
    size: int = 20,
    sort: str = "createdAt,DESC",
) -> PageResponse[OfferResponse]:
    """GET /api/v1/my-offers — caller's own submitted offers."""
    response = client.get(
        "/api/v1/my-offers",
        params={"page": page, "size": size, "sort": sort},
        expect_status=200,
    )
    return PageResponse[OfferResponse].model_validate(response.json())
