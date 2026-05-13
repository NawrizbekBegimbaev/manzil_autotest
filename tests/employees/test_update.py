"""PATCH /api/v1/employees/{id}."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.client import ApiClient
from api.endpoints import employees as emp_ep
from api.schemas import EmployeeResponse, UpdateEmployeeRequest

# ---------- positive --------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_full_name(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    new_name = "Updated Manager Name"
    updated = emp_ep.update_employee(
        supplier_admin_client,
        invited_employee.id,
        UpdateEmployeeRequest(full_name=new_name),
    )
    assert updated.full_name == new_name
    assert updated.id == invited_employee.id


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_update_role(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    updated = emp_ep.update_employee(
        supplier_admin_client,
        invited_employee.id,
        UpdateEmployeeRequest(role="SUPPLIER_DISPATCHER"),
    )
    assert updated.role == "SUPPLIER_DISPATCHER"


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.parametrize("status", ["ACTIVE", "BLOCKED"])
def test_update_status(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
    status: str,
) -> None:
    """Pending invitees cannot be activated/blocked before accepting invitation."""
    with supplier_admin_client.expect_error(400) as errors:
        emp_ep.update_employee(
            supplier_admin_client,
            invited_employee.id,
            UpdateEmployeeRequest(status=status),
        )
    assert errors[0].problem is not None


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_with_invalid_status_returns_400(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    """`PENDING` is set automatically — cannot be set via PATCH."""
    with supplier_admin_client.expect_error(400):
        supplier_admin_client.patch(
            f"/api/v1/employees/{invited_employee.id}",
            json={"status": "PENDING"},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_with_unknown_status_returns_400(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    with supplier_admin_client.expect_error(400):
        supplier_admin_client.patch(
            f"/api/v1/employees/{invited_employee.id}",
            json={"status": "wizard"},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_with_unknown_role_returns_400(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    with supplier_admin_client.expect_error(400):
        emp_ep.update_employee(
            supplier_admin_client,
            invited_employee.id,
            UpdateEmployeeRequest(role="overlord"),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_unknown_employee_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        emp_ep.update_employee(
            supplier_admin_client,
            uuid4(),
            UpdateEmployeeRequest(full_name="ghost"),
        )


@pytest.mark.negative
def test_update_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        emp_ep.update_employee(
            api_client,
            uuid4(),
            UpdateEmployeeRequest(full_name="X"),
        )
