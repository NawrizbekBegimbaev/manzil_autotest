"""Supplier-employee CRUD wrappers (BRD US-2).

All four endpoints require an authenticated supplier-admin Bearer token.
"""

from __future__ import annotations

from uuid import UUID

from api.client import ApiClient
from api.schemas import (
    EmployeeResponse,
    InviteEmployeeRequest,
    PageResponse,
    UpdateEmployeeRequest,
)


def list_employees(client: ApiClient) -> list[EmployeeResponse]:
    """GET /api/v1/employees."""
    response = client.get("/api/v1/employees", expect_status=200)
    page = PageResponse[EmployeeResponse].model_validate(response.json())
    return page.content


def invite_employee(client: ApiClient, body: InviteEmployeeRequest) -> EmployeeResponse:
    """POST /api/v1/employees — sends invitation email."""
    response = client.post(
        "/api/v1/employees",
        json=body.model_dump(by_alias=True),
        expect_status=201,
    )
    return EmployeeResponse.model_validate(response.json())


def update_employee(
    client: ApiClient,
    employee_id: UUID,
    body: UpdateEmployeeRequest,
) -> EmployeeResponse:
    """PATCH /api/v1/employees/{id}."""
    response = client.patch(
        f"/api/v1/employees/{employee_id}",
        json=body.model_dump(by_alias=True, exclude_none=True),
        expect_status=200,
    )
    return EmployeeResponse.model_validate(response.json())


def delete_employee(client: ApiClient, employee_id: UUID) -> None:
    """DELETE /api/v1/employees/{id} — soft-delete."""
    client.delete(f"/api/v1/employees/{employee_id}", expect_status=204)
