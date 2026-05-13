"""GET /api/v1/me + PATCH /api/v1/me + PATCH /api/v1/me/driver.

The new shape (2026-05-01 backend) returns a role-aware payload:
- `profile` — always present (fullName / email / phone / avatarUrl)
- `organization` — for supplier / TK staff
- `driver` + `vehicle` — for drivers
"""

from __future__ import annotations

from datetime import date
from typing import Final
from uuid import UUID

from pydantic import Field

from api.schemas._base import ApiModel

ROLES: Final[tuple[str, ...]] = (
    "SUPPLIER_ADMIN",
    "SUPPLIER_DISPATCHER",
    "SUPPLIER_MANAGER",
    "TK_ADMIN",
    "DRIVER",
)


# ---------- shared sub-blocks ---------------------------------------------


class ProfileBlock(ApiModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class OrganizationBlock(ApiModel):
    id: UUID
    type: str  # "SUPPLIER" | "TK" — backend constant
    name: str
    inn: str


class DriverLicenseBlock(ApiModel):
    number: str
    series: str | None = None
    issued_at: date
    expires_at: date


class DriverBlock(ApiModel):
    city: str | None = None
    license: DriverLicenseBlock | None = None
    geolocation_consented: bool


class DriverVehicleBlock(ApiModel):
    brand: str
    model: str
    plate: str
    body_type: str
    capacity_kg: float
    volume_m3: float
    notes: str | None = None


# ---------- response (GET /api/v1/me) -------------------------------------


class CurrentUserResponse(ApiModel):
    """Top-level /me payload. Sub-blocks are present only when relevant
    to the caller's role."""

    id: UUID
    role: str
    profile: ProfileBlock
    organization: OrganizationBlock | None = None
    driver: DriverBlock | None = None
    vehicle: DriverVehicleBlock | None = None


# ---------- request (PATCH /api/v1/me) ------------------------------------


class UpdateProfileRequest(ApiModel):
    """Self-edit available to ANY authenticated user.

    Partial — omit fields to keep current values. Empty body is a 200 no-op.
    Driver-specific fields go to PATCH /me/driver.
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()\-]{7,20}$")


# ---------- request (PATCH /api/v1/me/driver) -----------------------------


class UpdateDriverProfileRequest(ApiModel):
    """Driver self-edit. Top-level fields are partial; nested `license`
    and `vehicle` are replace-all-or-nothing."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    geolocation_consented: bool | None = None
    license: DriverLicenseBlock | None = None
    vehicle: DriverVehicleBlock | None = None
