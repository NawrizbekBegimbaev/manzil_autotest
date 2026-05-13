"""TK fleet CRUD payloads (BRD US-3).

Endpoints (TK admin only):
- GET    /api/v1/vehicles
- POST   /api/v1/vehicles
- PUT    /api/v1/vehicles/{id}
- DELETE /api/v1/vehicles/{id}
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from api.schemas._base import ApiModel


class VehicleRequest(ApiModel):
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    plate: str = Field(min_length=2, max_length=50)
    body_type: str  # tent / refrigerator / isotherm / container / platform / other
    capacity_kg: float = Field(gt=0)
    volume_m3: float = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class VehicleResponse(ApiModel):
    id: UUID
    organization_id: UUID
    brand: str
    model: str
    plate: str
    body_type: str
    capacity_kg: float
    volume_m3: float
    notes: str | None = None
    created_at: datetime
