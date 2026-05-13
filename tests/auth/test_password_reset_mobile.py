"""POST /api/v1/auth/mobile/password-resets + /confirm — Telegram-OTP flow."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import MobilePasswordResetConfirmRequest, MobilePasswordResetStartRequest
from config.settings import Settings


@pytest.mark.positive
def test_start_mobile_reset_with_unknown_phone_returns_204(
    api_client: ApiClient,
) -> None:
    """Enumeration defence — same as web, but for phones."""
    auth_ep.start_mobile_password_reset(
        api_client,
        MobilePasswordResetStartRequest(phone="+998900000999"),
    )


@pytest.mark.negative
@pytest.mark.parametrize(
    "phone", ["", "998900000001", "+invalid", "+99890ABCDEF1"],
    ids=["empty", "no-plus", "letters-1", "letters-2"],
)
def test_start_mobile_reset_with_malformed_phone_returns_400(
    api_client: ApiClient,
    phone: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/mobile/password-resets",
            json={"phone": phone},
            expect_status=204,
        )


@pytest.mark.negative
def test_verify_mobile_reset_with_wrong_code_returns_400(
    api_client: ApiClient,
    phone_from_pool: str,
) -> None:
    """The 2026-05-01 backend split confirm into verify+confirm. Wrong OTP
    fails at /verify, not /confirm."""
    from api.schemas import MobilePasswordResetVerifyRequest

    with api_client.expect_error(400):
        auth_ep.verify_mobile_password_reset(
            api_client,
            MobilePasswordResetVerifyRequest(phone=phone_from_pool, code="000000"),
        )


@pytest.mark.negative
def test_confirm_mobile_reset_with_bogus_token_returns_400(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    """confirm now takes a one-shot resetToken from /verify — bogus token must 400."""
    with api_client.expect_error(400):
        auth_ep.confirm_mobile_password_reset(
            api_client,
            MobilePasswordResetConfirmRequest(
                reset_token="never-issued",
                new_password=settings.default_test_password,
            ),
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    "weak_password",
    ["", "short", "lowercase1!", "Password!", "Password1"],
)
def test_confirm_mobile_reset_rejects_weak_password(
    api_client: ApiClient,
    weak_password: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/mobile/password-resets/confirm",
            json={"resetToken": "any", "newPassword": weak_password},
            expect_status=204,
        )
