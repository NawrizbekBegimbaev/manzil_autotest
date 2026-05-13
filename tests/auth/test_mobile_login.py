"""POST /api/v1/auth/mobile/login — driver phone+password login."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import MobileLoginRequest
from config.settings import Settings


@pytest.mark.negative
def test_mobile_login_with_unknown_phone_returns_401(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    with api_client.expect_error(401):
        auth_ep.mobile_login(
            api_client,
            MobileLoginRequest(
                phone_number="+998900000999",
                password=settings.default_test_password,
            ),
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    ("phone", "password"),
    [
        ("", "P@ssw0rd!"),
        ("+998900000001", ""),
        ("not-a-phone", "P@ssw0rd!"),
    ],
    ids=["empty-phone", "empty-password", "malformed-phone"],
)
def test_mobile_login_with_malformed_payload_returns_400(
    api_client: ApiClient,
    phone: str,
    password: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/mobile/login",
            json={"phoneNumber": phone, "password": password},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.parametrize("body", [{}, {"phoneNumber": "+998900000001"}, {"password": "x"}])
def test_mobile_login_with_missing_fields_returns_400(
    api_client: ApiClient,
    body: dict[str, str],
) -> None:
    with api_client.expect_error(400):
        api_client.post("/api/v1/auth/mobile/login", json=body, expect_status=200)


@pytest.mark.positive
@pytest.mark.requires_telegram_otp
def test_mobile_login_after_complete_returns_tokens() -> None:
    """End-to-end driver register → login.

    SPECULATIVE: full flow needs Telegram OTP capture. Once available, this
    test should:
        1. Start + verify + complete driver registration (gets tokens A).
        2. Re-login via /mobile/login with the same phone+password.
        3. Assert tokens received (B), and they are distinct from A.
    """
    pytest.skip("Pending Telegram-OTP capture — see open question #3.")
