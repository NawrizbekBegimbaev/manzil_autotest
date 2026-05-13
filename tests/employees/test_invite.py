"""POST /api/v1/employees — invite + acceptance flow."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import employees as emp_ep
from api.schemas import InviteEmployeeRequest
from data import builders
from data.constants import EMPLOYEE_ROLES
from data.email_pool import EmailPool


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.parametrize("role", EMPLOYEE_ROLES)
def test_invite_with_each_role_returns_201(
    supplier_admin_client: ApiClient,
    email_pool: EmailPool,
    role: str,
) -> None:
    with email_pool.lease() as employee_email:
        result = emp_ep.invite_employee(
            supplier_admin_client,
            builders.employee_invite(email=employee_email, role=role),
        )
    assert result.email.lower() == employee_email.lower()
    assert result.role == role
    assert result.status in {"PENDING", "ACTIVE"}  # status convention TBD


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_invite_with_existing_email_returns_409(
    supplier_admin_client: ApiClient,
    email_pool: EmailPool,
) -> None:
    with email_pool.lease() as employee_email:
        body = builders.employee_invite(email=employee_email)
        emp_ep.invite_employee(supplier_admin_client, body)
        with supplier_admin_client.expect_error(409):
            emp_ep.invite_employee(supplier_admin_client, body)


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        ({"email": "", "fullName": "X", "role": "SUPPLIER_MANAGER"}, "empty-email"),
        ({"email": "not-an-email", "fullName": "X", "role": "SUPPLIER_MANAGER"}, "malformed-email"),
        (
            {"email": "ok@manziltest.uz", "fullName": "", "role": "SUPPLIER_MANAGER"},
            "empty-fullname",
        ),
        ({"email": "ok@manziltest.uz", "fullName": "X", "role": ""}, "empty-role"),
        ({"email": "ok@manziltest.uz", "fullName": "X", "role": "wizard"}, "unknown-role"),
        ({"email": "ok@manziltest.uz", "role": "SUPPLIER_MANAGER"}, "missing-fullname"),
        ({"fullName": "X", "role": "SUPPLIER_MANAGER"}, "missing-email"),
        ({}, "empty-body"),
    ],
)
def test_invite_with_invalid_payload_returns_400(
    supplier_admin_client: ApiClient,
    payload: dict[str, str],
    case_id: str,
) -> None:
    with supplier_admin_client.expect_error(400) as errors:
        supplier_admin_client.post("/api/v1/employees", json=payload, expect_status=201)
    assert errors[0].problem is not None, f"case {case_id}"


@pytest.mark.negative
def test_invite_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        emp_ep.invite_employee(
            api_client,
            InviteEmployeeRequest(
                email="x@manziltest.uz", full_name="X", role="SUPPLIER_MANAGER",
            ),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_invite_as_tk_admin_returns_403(
    tk_admin_client: ApiClient,
) -> None:
    with tk_admin_client.expect_error((400, 403)):
        emp_ep.invite_employee(
            tk_admin_client,
            InviteEmployeeRequest(
                email="x@manziltest.uz", full_name="X", role="SUPPLIER_MANAGER",
            ),
        )
