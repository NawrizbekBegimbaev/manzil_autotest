"""BOLA — Broken Object Level Authorization.

OWASP API Top-1. The fact that `/employees/{id}` accepts ANY UUID and the
caller's company is implicit (Bearer token) makes this the highest-risk
class of bug for Manzil's API. Every employee operation MUST be scoped by
the caller's company on the server side.

Each test creates two independent supplier admins (companies A and B),
operates on A's data with B's token, and asserts the response indicates
"not found" rather than "forbidden" — to avoid leaking existence of
foreign UUIDs (404 over 403 is the correct security choice).
"""

from __future__ import annotations

import contextlib
from uuid import uuid4

import pytest

from api.client import ApiClient
from api.endpoints import employees as emp_ep
from api.schemas import (
    EmployeeResponse,
    InviteEmployeeRequest,
    UpdateEmployeeRequest,
)

# ---------- read isolation -------------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_cannot_see_company_a_employee_in_list(
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    """B's /employees must not contain A's employees."""
    visible = emp_ep.list_employees(second_supplier_admin_client)
    assert employee_in_company_a.id not in {e.id for e in visible}


# ---------- write isolation: PATCH ----------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_patch_on_a_employee_returns_404(
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    """SECURITY-CRITICAL: must be 404 (not 403) — 403 leaks existence."""
    with second_supplier_admin_client.expect_error(404):
        emp_ep.update_employee(
            second_supplier_admin_client,
            employee_in_company_a.id,
            UpdateEmployeeRequest(full_name="hacked-name"),
        )


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_patch_does_not_modify_a_employee(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    """Even if backend accidentally returns 200, the data must not change."""
    with contextlib.suppress(Exception):
        emp_ep.update_employee(
            second_supplier_admin_client,
            employee_in_company_a.id,
            UpdateEmployeeRequest(full_name="hacked-name", role="SUPPLIER_ADMIN"),
        )
    fresh = next(
        e for e in emp_ep.list_employees(supplier_admin_client)
        if e.id == employee_in_company_a.id
    )
    assert fresh.full_name != "hacked-name"
    assert fresh.role != "SUPPLIER_ADMIN"


# ---------- write isolation: DELETE ---------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_delete_on_a_employee_returns_404(
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    with second_supplier_admin_client.expect_error(404):
        emp_ep.delete_employee(second_supplier_admin_client, employee_in_company_a.id)


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_delete_does_not_remove_a_employee(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    """Idempotency-safe: even if delete returned 204 by mistake, the row stays."""
    with contextlib.suppress(Exception):
        emp_ep.delete_employee(second_supplier_admin_client, employee_in_company_a.id)
    visible = emp_ep.list_employees(supplier_admin_client)
    assert employee_in_company_a.id in {e.id for e in visible}


# ---------- random UUID guessing -------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_random_uuid_patch_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    """Sanity: a UUID that doesn't exist anywhere must 404, not 200/500."""
    with supplier_admin_client.expect_error(404):
        emp_ep.update_employee(
            supplier_admin_client,
            uuid4(),
            UpdateEmployeeRequest(full_name="ghost"),
        )


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_random_uuid_delete_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        emp_ep.delete_employee(supplier_admin_client, uuid4())


# ---------- invite-as-other-tenant ----------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_company_b_cannot_invite_employee_already_in_a(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
) -> None:
    """SPECULATIVE: backend may treat the email as globally unique (409) or
    company-scoped (allow). Either is defensible — but if it's 409 across
    companies, an attacker can probe membership of a known email."""
    with second_supplier_admin_client.expect_error((400, 409)):
        emp_ep.invite_employee(
            second_supplier_admin_client,
            InviteEmployeeRequest(
                email=employee_in_company_a.email,
                full_name="X",
                role="SUPPLIER_MANAGER",
            ),
        )


# ---------- /me sanity ----------------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_a_token_and_b_token_resolve_to_different_app_users(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
) -> None:
    """Two simultaneous tokens must point to different `appUserId` values
    — sanity check that fixture isolation actually works."""
    from api.endpoints import me as me_ep

    a_me = me_ep.get_current_user(supplier_admin_client)
    b_me = me_ep.get_current_user(second_supplier_admin_client)
    assert a_me.id != b_me.id
    assert a_me.profile.email != b_me.profile.email
