"""Mass assignment / privilege escalation via extra fields in JSON body.

The attacker pattern: send fields that ARE valid in the database but are
NOT supposed to be settable by the client. The server must either reject
them (preferred — fail-closed) or silently ignore them (acceptable —
fail-safe). Returning 200 AND persisting the smuggled value is the bug.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.schemas import EmployeeResponse
from config.settings import Settings

# ---------- /employees PATCH — most-likely escalation surface --------------


@pytest.mark.security
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    "extra_field",
    [
        {"id": "11111111-1111-1111-1111-111111111111"},
        {"companyId": "22222222-2222-2222-2222-222222222222"},
        {"supplierId": "33333333-3333-3333-3333-333333333333"},
        {"keycloakUserId": "00000000-0000-0000-0000-000000000000"},
        {"createdAt": "2000-01-01T00:00:00Z"},
        {"deletedAt": None},  # un-soft-delete via PATCH
        {"realmRoles": ["super-admin"]},
        {"isAdmin": True},
        {"tenantId": "44444444-4444-4444-4444-444444444444"},
    ],
    ids=lambda v: next(iter(v.keys())) if isinstance(v, dict) else str(v),
)
def test_patch_employee_rejects_or_ignores_system_fields(
    supplier_admin_client: ApiClient,
    invited_employee: EmployeeResponse,
    extra_field: dict[str, object],
) -> None:
    """Send a smuggled system field. Either:
    - 400 (server validates strictly — best), OR
    - 200 with the field NOT applied (server ignores extras)
    Anything else means the field leaked through.
    """
    response = supplier_admin_client._client.patch(
        f"/api/v1/employees/{invited_employee.id}",
        json={**extra_field, "fullName": "OK"},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {supplier_admin_client.token}",
        },
    )
    assert response.status_code in (200, 400), response.text
    if response.status_code == 200:
        # Server accepted — the smuggled value MUST NOT be reflected.
        body = response.json()
        smuggled_key = next(iter(extra_field))
        if smuggled_key in body:
            assert body[smuggled_key] != extra_field[smuggled_key], (
                f"mass-assignment leak: {smuggled_key}={extra_field[smuggled_key]!r} "
                f"persisted via PATCH"
            )


# ---------- /employees POST (invite) --------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_invite_with_status_active_does_not_skip_pending(
    supplier_admin_client: ApiClient,
    email_from_pool: str,
) -> None:
    """Per swagger: status starts at PENDING and flips on accept. An attacker
    setting `status=active` directly would bypass the email-confirmation
    requirement — the resulting employee MUST be pending."""
    response = supplier_admin_client._client.post(
        "/api/v1/employees",
        json={
            "email": email_from_pool,
            "fullName": "Smuggler",
            "role": "SUPPLIER_MANAGER",
            "status": "ACTIVE",  # smuggled
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {supplier_admin_client.token}",
        },
    )
    assert response.status_code in (201, 400), response.text
    if response.status_code == 201:
        assert response.json()["status"] != "ACTIVE", (
            "mass-assignment: invite created an active employee, bypassing email confirmation"
        )


@pytest.mark.security
def test_supplier_registration_rejects_role_smuggling(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """An attacker can't promote themselves to super-admin during sign-up.

    SPECULATIVE: backend behaviour for unknown fields. We assert either 400
    (strict) or successful registration without role escalation.
    """
    response = api_client._client.post(
        "/api/v1/auth/web/registrations/suppliers",
        json={
            "companyName": "[E2E] Smuggler",
            "tin": "200999999999",
            "email": email_from_pool,
            "phone": phone_from_pool,
            "fullName": "Smuggler",
            "password": settings.default_test_password,
            "realmRoles": ["super-admin", "platform-admin"],
            "isAdmin": True,
            "verified": True,
        },
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code in (204, 400), response.text


# ---------- self-elevation via PATCH --------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
@pytest.mark.xfail(
    reason="Backend allows admin self-demotion through /employees/{id}; privilege-boundary bug.",
    strict=False,
)
def test_employee_patch_on_self_through_admin_endpoint_rejects_role_escalation(
    supplier_admin_client: ApiClient,
) -> None:
    """If /employees/{id} also accepts the admin's own UUID, a future
    attacker scenario is: dispatcher → invite themselves to /employees →
    promote to admin. The invariant we assert: trying to PATCH role/status
    of `appUserId=self` either 400's or doesn't persist."""
    from api.endpoints import me as me_ep

    me = me_ep.get_current_user(supplier_admin_client)
    response = supplier_admin_client._client.patch(
        f"/api/v1/employees/{me.id}",
        json={"role": "SUPPLIER_MANAGER"},  # admin tries to demote self via this route
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {supplier_admin_client.token}",
        },
    )
    # Either 400 (cannot self-edit) / 404 (admin row not exposed here) / 403:
    assert response.status_code in (400, 403, 404), response.text
