"""Supplier warehouse CRUD payloads (BRD US-19).

Endpoints:
- GET    /api/v1/warehouses           paginated list
- POST   /api/v1/warehouses           create
- PUT    /api/v1/warehouses/{id}      replace mutable fields
- DELETE /api/v1/warehouses/{id}      soft-delete
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from api.schemas._base import ApiModel


class WarehouseRequest(ApiModel):
    """Used by both POST and PUT — full replacement payload."""

    name: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=3, max_length=500)
    active: bool


class WarehouseResponse(ApiModel):
    id: UUID
    organization_id: UUID
    name: str
    city: str
    address: str
    active: bool
    created_at: datetime
