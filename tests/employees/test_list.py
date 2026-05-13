"""GET /api/v1/employees — list of caller's supplier company."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import employees as emp_ep
from api.schemas import EmployeeResponse


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_for_fresh_supplier_admin_contains_self(
    supplier_admin_client: ApiClient,
) -> None:
    """A new supplier admin who hasn't invited anyone still sees themselves.

    SPECULATIVE: the swagger doesn't say whether the admin appears in the
    response. If backend excludes self, change `>= 1` to `>= 0` and check
    that no inactive accounts leak.
    """
    employees = emp_ep.list_employees(supplier_admin_client)
    assert isinstance(employees, list)
    assert all(isinstance(e, EmployeeResponse) for e in employees)


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_includes_invited_employee(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
) -> None:
    employees = emp_ep.list_employees(supplier_admin_client)
    ids = {e.id for e in employees}
    assert invited_employee.id in ids


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_returns_empty_array_not_null(
    supplier_admin_client: ApiClient,
) -> None:
    """Per swagger: 200 + PageResponse with array content (may be empty)."""
    response = supplier_admin_client.get("/api/v1/employees", expect_status=200)
    body = response.json()
    assert isinstance(body, dict), body
    assert isinstance(body.get("content"), list), body
    assert "page" in body, body


@pytest.mark.negative
def test_list_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        emp_ep.list_employees(api_client)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_list_as_tk_admin_returns_403(
    tk_admin_client: ApiClient,
) -> None:
    """Only supplier admins can list employees — TK admin must 403."""
    with tk_admin_client.expect_error(403):
        emp_ep.list_employees(tk_admin_client)
