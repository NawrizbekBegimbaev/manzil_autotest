"""DELETE /api/v1/employees/{id} — soft-delete."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.client import ApiClient
from api.endpoints import employees as emp_ep
from api.endpoints import me as me_ep
from api.schemas import EmployeeResponse

# ---------- positive --------------------------------------------------------


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_delete_employee_returns_204(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    emp_ep.delete_employee(supplier_admin_client, invited_employee.id)


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_deleted_employee_disappears_from_list(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    emp_ep.delete_employee(supplier_admin_client, invited_employee.id)
    remaining = emp_ep.list_employees(supplier_admin_client)
    assert all(e.id != invited_employee.id for e in remaining)


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
def test_email_can_be_reinvited_after_delete(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    """Per swagger: delete frees the email for re-invitation."""
    emp_ep.delete_employee(supplier_admin_client, invited_employee.id)
    from api.schemas import InviteEmployeeRequest

    fresh = emp_ep.invite_employee(
        supplier_admin_client,
        InviteEmployeeRequest(
            email=invited_employee.email,
            full_name="Re-invited",
            role="SUPPLIER_MANAGER",
        ),
    )
    assert fresh.email.lower() == invited_employee.email.lower()
    assert fresh.role == "SUPPLIER_MANAGER"


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_admin_cannot_delete_self_returns_400(
    supplier_admin_client: ApiClient,
) -> None:
    """Server protects the admin from deleting their own account — 400."""
    me = me_ep.get_current_user(supplier_admin_client)
    with supplier_admin_client.expect_error(400):
        emp_ep.delete_employee(supplier_admin_client, me.id)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_delete_unknown_employee_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        emp_ep.delete_employee(supplier_admin_client, uuid4())


@pytest.mark.negative
def test_delete_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        emp_ep.delete_employee(api_client, uuid4())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_double_delete_returns_404(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    """After soft-delete, the row is no longer visible — second delete → 404."""
    emp_ep.delete_employee(supplier_admin_client, invited_employee.id)
    with supplier_admin_client.expect_error(404):
        emp_ep.delete_employee(supplier_admin_client, invited_employee.id)
