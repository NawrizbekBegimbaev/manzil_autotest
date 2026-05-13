r"""Cargo shipping orders (BRD US-6, US-7).

Lifecycle: draft → active → confirmed → in_progress → completed
                       \_______ cancelled (from any non-terminal)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final
from uuid import UUID

from pydantic import Field

from api.schemas._base import ApiModel

# ---------- enums (informational; backend validates) ----------------------

ORDER_STATUSES: Final[tuple[str, ...]] = (
    "DRAFT", "ACTIVE", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED",
)
BODY_TYPES: Final[tuple[str, ...]] = (
    "TENT", "REFRIGERATOR", "CONTAINER", "LOW_PLATFORM", "OTHER",
)
LOADING_METHODS: Final[tuple[str, ...]] = ("SIDE", "REAR", "TOP")
CURRENCIES: Final[tuple[str, ...]] = ("USD", "CNY")


# ---------- request models ------------------------------------------------


class OrderRequest(ApiModel):
    """POST /api/v1/orders — dispatcher creates an order (US-6)."""

    cargo_type: str = Field(min_length=1, max_length=255)
    weight_kg: float = Field(gt=0)
    volume_m3: float = Field(gt=0)
    body_type: str
    loading_methods: list[str] = Field(min_length=1)
    pickup_warehouse_id: UUID
    destination_warehouse_id: UUID
    desired_date: date
    currency: str
    notes: str = Field(default="", max_length=1000)
    publish: bool


class OrderUpdateRequest(ApiModel):
    """PATCH /api/v1/orders/{id} — partial draft edit (US-6 line 298)."""

    cargo_type: str | None = Field(default=None, min_length=1, max_length=255)
    weight_kg: float | None = Field(default=None, gt=0)
    volume_m3: float | None = Field(default=None, gt=0)
    body_type: str | None = None
    loading_methods: list[str] | None = Field(default=None, min_length=1)
    pickup_warehouse_id: UUID | None = None
    destination_warehouse_id: UUID | None = None
    desired_date: date | None = None
    currency: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class OrderCancelRequest(ApiModel):
    """POST /api/v1/orders/{id}/cancel — optional reason."""

    reason: str | None = Field(default=None, max_length=500)


# ---------- response model ------------------------------------------------


class OrderResponse(ApiModel):
    id: UUID
    number: str
    organization_id: UUID
    created_by: UUID
    created_by_name: str | None = None
    status: str
    cargo_type: str
    weight_kg: float
    volume_m3: float
    body_type: str
    loading_methods: list[str]
    warehouse_id: UUID | None = None
    # Backend (release 2026-05-04+) дополняет OrderResponse полями маршрута.
    # Эти поля приходят в /feed и в list/get /orders. Optional — для backwards-compat.
    pickup_warehouse_id: UUID | None = None
    destination_warehouse_id: UUID | None = None
    load_city: str | None = None
    unload_city: str | None = None
    load_address: str | None = None
    unload_address: str
    desired_date: date
    currency: str
    notes: str | None = None
    winner_offer_id: UUID | None = None
    # Backend started emitting `offersCount` (number of offers attached
    # to the order) after the 2026-05-01 release. Optional for backwards
    # compatibility.
    offers_count: int | None = None
    created_at: datetime
    updated_at: datetime
