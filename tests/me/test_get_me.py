"""GET /api/v1/me + PATCH /api/v1/me + PATCH /api/v1/me/driver.

The 2026-05-01 backend revamps /me into a role-aware payload:
    {id, role, profile{...}, organization{...}, driver{...}, vehicle{...}}
Sub-blocks are present only when relevant to the caller's role.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import me as me_ep
from api.schemas import UpdateProfileRequest
from tests.conftest import RegisteredAccount

# ---------- positive --------------------------------------------------------


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_supplier_admin_me_payload(
    supplier_admin_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    me = me_ep.get_current_user(supplier_admin_client)
    assert me.role == "SUPPLIER_ADMIN"
    assert me.profile.email == verified_supplier_admin.email
    assert me.profile.full_name == verified_supplier_admin.full_name
    assert me.organization is not None, "supplier admin must have organization block"
    assert me.organization.type == "SUPPLIER"
    assert me.organization.inn == verified_supplier_admin.tin
    assert me.driver is None, "supplier admin must not have driver block"
    assert me.vehicle is None


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_tk_admin_me_payload(
    tk_admin_client: ApiClient,
    verified_tk_admin: RegisteredAccount,
) -> None:
    me = me_ep.get_current_user(tk_admin_client)
    assert me.role == "TK_ADMIN"
    assert me.profile.email == verified_tk_admin.email
    assert me.organization is not None
    assert me.organization.type == "TK"
    assert me.driver is None
    assert me.vehicle is None


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_patch_me_updates_full_name(
    supplier_admin_client: ApiClient,
) -> None:
    new_name = "Updated By PATCH"
    updated = me_ep.update_own_profile(
        supplier_admin_client,
        UpdateProfileRequest(full_name=new_name),
    )
    assert updated.profile.full_name == new_name


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_patch_me_with_empty_body_is_noop(
    supplier_admin_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Per swagger: an empty body is a successful 200 no-op."""
    before = me_ep.get_current_user(supplier_admin_client)
    after = me_ep.update_own_profile(supplier_admin_client, UpdateProfileRequest())
    assert after.profile.full_name == before.profile.full_name


# ---------- negative --------------------------------------------------------


@pytest.mark.negative
def test_me_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        me_ep.get_current_user(api_client)


@pytest.mark.negative
@pytest.mark.parametrize(
    "header_value",
    ["Bearer not-a-jwt", "NoBearer xyz", "Bearer a.b.c"],
    ids=["bearer-garbage", "wrong-scheme", "fake-jwt"],
)
def test_me_with_malformed_bearer_returns_401(
    api_client: ApiClient,
    header_value: str,
) -> None:
    response = api_client._client.get(
        "/api/v1/me",
        headers={"Accept": "application/json", "Authorization": header_value},
    )
    assert response.status_code == 401, response.text


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_patch_me_with_invalid_phone_returns_400(
    supplier_admin_client: ApiClient,
) -> None:
    """Phone must match `^\\+?[0-9 ()\\-]{7,20}$`."""
    with supplier_admin_client.expect_error(400):
        supplier_admin_client.patch(
            "/api/v1/me",
            json={"phone": "ABC123"},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_patch_me_driver_as_non_driver_returns_403(
    supplier_admin_client: ApiClient,
) -> None:
    """Per swagger: non-driver cannot patch driver profile."""
    with supplier_admin_client.expect_error((403, 404)):
        supplier_admin_client.patch(
            "/api/v1/me/driver",
            json={"city": "Tashkent"},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
@pytest.mark.xfail(
    reason="Backend does not online-revoke access tokens on logout; token remains valid until exp.",
    strict=False,
)
def test_me_with_revoked_token_behavior(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Logout must invalidate the access token's ability to call /me.

    SPECULATIVE: Keycloak access tokens are typically not online-revoked;
    they expire when `expiresIn` runs out. If backend does NOT enforce
    online revocation, /me succeeds and this test should be xfail'd.
    """
    from api.endpoints import auth as auth_ep
    from api.schemas import LogoutRequest, WebLoginRequest

    tokens = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    api_client.set_token(tokens.access_token)
    auth_ep.logout(api_client, LogoutRequest(refresh_token=tokens.refresh_token))
    with api_client.expect_error(401):
        me_ep.get_current_user(api_client)
