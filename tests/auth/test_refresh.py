"""POST /api/v1/auth/refresh — rotation, expiry, reuse defence."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import RefreshRequest, WebLoginRequest
from tests.conftest import RegisteredAccount


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_refresh_returns_new_token_pair(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    initial = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    rotated = auth_ep.refresh(api_client, RefreshRequest(refresh_token=initial.refresh_token))
    assert rotated.access_token != initial.access_token
    assert rotated.refresh_token != initial.refresh_token
    assert rotated.token_type == "Bearer"
    assert rotated.expires_in > 0


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
def test_old_refresh_token_is_invalid_after_rotation(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Refresh-rotation: re-using the old token must 401 — keycloak feature."""
    initial = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    auth_ep.refresh(api_client, RefreshRequest(refresh_token=initial.refresh_token))
    with api_client.expect_error(401):
        auth_ep.refresh(api_client, RefreshRequest(refresh_token=initial.refresh_token))


@pytest.mark.negative
@pytest.mark.parametrize(
    "token",
    ["", "garbage", "a.b.c", "Bearer xyz"],
    ids=["empty", "garbage", "fake-jwt", "with-bearer-prefix"],
)
def test_refresh_with_malformed_token_returns_400_or_401(
    api_client: ApiClient,
    token: str,
) -> None:
    """Malformed tokens get either 400 (shape) or 401 (auth) — both acceptable."""
    expected = (400, 401) if token else (400,)
    response = api_client._client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": token},
        headers={"Accept": "application/json"},
    )
    assert response.status_code in expected, response.text


@pytest.mark.negative
def test_refresh_without_field_returns_400(api_client: ApiClient) -> None:
    with api_client.expect_error(400):
        api_client.post("/api/v1/auth/refresh", json={}, expect_status=200)
