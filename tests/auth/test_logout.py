"""POST /api/v1/auth/logout — best-effort token revocation."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import LogoutRequest, RefreshRequest, WebLoginRequest
from tests.conftest import RegisteredAccount


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_logout_revokes_refresh_token(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """After logout, refresh with the same token must 401."""
    tokens = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    auth_ep.logout(api_client, LogoutRequest(refresh_token=tokens.refresh_token))
    with api_client.expect_error(401):
        auth_ep.refresh(api_client, RefreshRequest(refresh_token=tokens.refresh_token))


@pytest.mark.positive
def test_logout_with_unknown_token_still_returns_204(api_client: ApiClient) -> None:
    """Per swagger: unknown/already-revoked token → 204 anyway (best-effort)."""
    auth_ep.logout(api_client, LogoutRequest(refresh_token="nonexistent-token-abc"))


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
def test_logout_is_idempotent(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Two logouts in a row must both 204 — backend treats already-revoked as success."""
    tokens = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    auth_ep.logout(api_client, LogoutRequest(refresh_token=tokens.refresh_token))
    auth_ep.logout(api_client, LogoutRequest(refresh_token=tokens.refresh_token))


@pytest.mark.negative
@pytest.mark.parametrize("body", [{}, {"refreshToken": ""}, {"wrongField": "x"}])
def test_logout_with_malformed_body_returns_400(
    api_client: ApiClient,
    body: dict[str, str],
) -> None:
    with api_client.expect_error(400):
        api_client.post("/api/v1/auth/logout", json=body, expect_status=204)
