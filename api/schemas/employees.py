"""Supplier-employee CRUD payloads (BRD US-2).

Endpoints:
- GET    /api/v1/employees           list
- POST   /api/v1/employees           invite
- PATCH  /api/v1/employees/{id}      update name/role/status
- DELETE /api/v1/employees/{id}      soft-delete
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from api.schemas._base import ApiModel


class InviteEmployeeRequest(ApiModel):
    email: EmailStr
    full_name: str
    role: str  # validated server-side; see data/constants.EMPLOYEE_ROLES


class UpdateEmployeeRequest(ApiModel):
    full_name: str | None = None
    role: str | None = None
    status: str | None = None  # "ACTIVE" | "BLOCKED" per current backend contract


class EmployeeResponse(ApiModel):
    id: UUID
    email: str
    full_name: str
    phone: str | None = None
    role: str
    status: str
    created_at: datetime = Field(alias="createdAt")
