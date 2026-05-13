"""Carrier offers and tender selection (BRD US-9 / US-11 / US-12 / US-14)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Final
from uuid import UUID

from pydantic import Field

from api.schemas._base import ApiModel

# BRD-defined statuses; backend validates against its enum.
OFFER_STATUSES: Final[tuple[str, ...]] = (
    "NEW", "REVIEWED", "SELECTED", "NOT_SELECTED", "WITHDRAWN",
)


class OfferRequest(ApiModel):
    """POST /api/v1/orders/{orderId}/offers — submit a price."""

    price: float = Field(gt=0)
    currency: str  # must match the order's currency
    comment: str | None = Field(default=None, max_length=250)


class OfferUpdateRequest(ApiModel):
    """PATCH /api/v1/orders/{orderId}/offers/{offerId} — self-edit while active."""

    price: float | None = Field(default=None, gt=0)
    comment: str | None = Field(default=None, max_length=250)


class OfferNoteRequest(ApiModel):
    """PUT /api/v1/orders/{orderId}/offers/{offerId}/note — manager note (US-12 §6)."""

    note: str = Field(min_length=1, max_length=500)


class OfferResponse(ApiModel):
    id: UUID
    order_id: UUID
    organization_id: UUID
    organization_name: str | None = None
    contact_phone: str | None = None
    status: str
    price: float
    currency: str
    comment: str | None = None
    manager_note: str | None = None
    manager_note_author: str | None = None
    # Backend now denormalizes order context into offer rows/details.
    order_number: str | None = None
    order_status: str | None = None
    pickup_city: str | None = None
    destination_city: str | None = None
    desired_date: date | None = None
    created_at: datetime
    updated_at: datetime
