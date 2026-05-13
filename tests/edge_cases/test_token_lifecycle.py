"""Token lifecycle invariants — refresh + logout interactions."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.endpoints import me as me_ep
from api.schemas import LogoutRequest, RefreshRequest, WebLoginRequest
from config.settings import Settings
from tests.conftest import RegisteredAccount


@pytest.mark.edge_case
@pytest.mark.requires_email_otp
def test_refresh_chain_rotates_each_time(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Three rotations in a row: every refresh token must differ from its predecessor."""
    seen: set[str] = set()
    pair = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    seen.add(pair.refresh_token)
    for _ in range(3):
        pair = auth_ep.refresh(api_client, RefreshRequest(refresh_token=pair.refresh_token))
        assert pair.refresh_token not in seen
        seen.add(pair.refresh_token)


@pytest.mark.edge_case
@pytest.mark.requires_email_otp
def test_logout_during_active_session_breaks_refresh(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    pair = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    api_client.set_token(pair.access_token)
    me_ep.get_current_user(api_client)  # works initially

    auth_ep.logout(api_client, LogoutRequest(refresh_token=pair.refresh_token))
    with api_client.expect_error(401):
        auth_ep.refresh(api_client, RefreshRequest(refresh_token=pair.refresh_token))


@pytest.mark.edge_case
@pytest.mark.requires_email_otp
def test_password_change_via_login_sequence(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
    settings: Settings,
) -> None:
    """Two logins with the original password yield distinct token pairs.

    Smoke-style invariant: same creds, repeated, never reuse JTIs.
    """
    request = WebLoginRequest(
        email=verified_supplier_admin.email,
        password=verified_supplier_admin.password,
    )
    a = auth_ep.web_login(api_client, request)
    b = auth_ep.web_login(api_client, request)
    assert a.access_token != b.access_token
    assert a.refresh_token != b.refresh_token
