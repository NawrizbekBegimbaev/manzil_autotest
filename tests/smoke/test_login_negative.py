"""Smoke negative: login rejects bad credentials.

These don't depend on OTP, so they run in any environment as long as the
API base URL is reachable. Keep them in `smoke/` so a broken auth pipeline
fails fast rather than waiting for the OTP-dependent suite.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth
from api.schemas import WebLoginRequest
from config.settings import Settings


@pytest.mark.smoke
@pytest.mark.negative
def test_web_login_with_unknown_email_returns_401(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    with api_client.expect_error(401) as errors:
        auth.web_login(
            api_client,
            WebLoginRequest(
                email="nobody-e2e@manziltest.uz",
                password=settings.default_test_password,
            ),
        )
    assert errors[0].problem is not None


@pytest.mark.smoke
@pytest.mark.negative
def test_web_login_with_malformed_payload_returns_400(api_client: ApiClient) -> None:
    """Empty email field — server should reject before even hitting Keycloak."""
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/login",
            json={"email": "", "password": ""},
            expect_status=200,
        )
