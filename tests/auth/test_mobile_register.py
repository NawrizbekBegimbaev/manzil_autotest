"""POST /api/v1/auth/mobile/registrations/* — driver three-step flow.

1. POST /drivers          → returns Telegram deeplink, OTP session created
2. POST /verify           → mark session verified (5-minute window)
3. POST /complete         → submit profile + license + vehicle, get tokens

Telegram OTP capture is required for the full chain — see open question #3.
Tests that don't need the real code (validation, malformed payload, etc.)
run unconditionally.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import (
    DriverRegistrationStartRequest,
    VerifyMobileOtpRequest,
)
from config.settings import Settings
from data import builders
from utils.otp import get_telegram_otp

# ---------- step 1: start --------------------------------------------------


@pytest.mark.positive
def test_start_driver_registration_returns_deeplink(
    api_client: ApiClient,
    phone_from_pool: str,
) -> None:
    response = auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    assert response.telegram_deep_link.startswith("https://t.me/")
    assert "?start=" in response.telegram_deep_link


@pytest.mark.negative
@pytest.mark.parametrize(
    "phone",
    ["", "998900000001", "+invalid", "+99890ABCDEF1", "+12345"],
    ids=["empty", "no-plus", "letters-1", "letters-2", "too-short"],
)
def test_start_driver_registration_with_malformed_phone_returns_400(
    api_client: ApiClient,
    phone: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/mobile/registrations/drivers",
            json={"phone": phone},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.requires_telegram_otp
@pytest.mark.edge_case
def test_start_for_already_registered_phone_returns_409(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
) -> None:
    """SPECULATIVE: requires fully completing a driver registration first.

    Until a fully-registered driver fixture exists (depends on Telegram OTP),
    this is a placeholder. We start once and expect either 200 (resend) or
    429 (cooldown) — and assert the SAME phone re-attempted in a fresh
    session would 409 only after /complete.
    """
    auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    # NOTE: 409 vs 200 vs 429 distinction belongs to a soak/integration test
    # once a registered driver fixture is available.


@pytest.mark.xfail(
    reason=(
        "BUG-006: backend doesn't enforce OTP-resend cooldown — no 429 "
        "(mobile/Telegram path same as web)."
    ),
    strict=False,
)
@pytest.mark.negative
@pytest.mark.edge_case
def test_immediate_resend_returns_429(
    api_client: ApiClient,
    phone_from_pool: str,
) -> None:
    """Two starts back-to-back for same phone → cooldown."""
    auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    with api_client.expect_error(429):
        auth_ep.start_driver_registration(
            api_client,
            DriverRegistrationStartRequest(phone=phone_from_pool),
        )


# ---------- step 2: verify -------------------------------------------------


@pytest.mark.positive
@pytest.mark.requires_telegram_otp
@pytest.mark.xfail(
    reason="Telegram fixed OTP no longer works on dev; needs real Telegram OTP capture.",
    strict=False,
)
def test_verify_with_correct_code_returns_204(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
) -> None:
    auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    auth_ep.verify_driver_otp(
        api_client,
        VerifyMobileOtpRequest(
            phone=phone_from_pool,
            code=get_telegram_otp(settings, phone_from_pool),
        ),
    )


@pytest.mark.negative
def test_verify_with_wrong_code_returns_400(
    api_client: ApiClient,
    phone_from_pool: str,
) -> None:
    auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    with api_client.expect_error(400):
        auth_ep.verify_driver_otp(
            api_client,
            VerifyMobileOtpRequest(phone=phone_from_pool, code="000000"),
        )


# ---------- step 3: complete -----------------------------------------------


@pytest.mark.positive
@pytest.mark.requires_telegram_otp
@pytest.mark.xfail(
    reason="Telegram fixed OTP no longer works on dev; depends on verify step.",
    strict=False,
)
def test_complete_driver_registration_returns_tokens(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
) -> None:
    auth_ep.start_driver_registration(
        api_client,
        DriverRegistrationStartRequest(phone=phone_from_pool),
    )
    auth_ep.verify_driver_otp(
        api_client,
        VerifyMobileOtpRequest(
            phone=phone_from_pool,
            code=get_telegram_otp(settings, phone_from_pool),
        ),
    )
    tokens = auth_ep.complete_driver_registration(
        api_client,
        builders.driver_complete_registration(
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    assert tokens.access_token
    assert tokens.token_type == "Bearer"


@pytest.mark.negative
def test_complete_without_verify_returns_400(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
) -> None:
    """Calling /complete with no prior /verify must fail — verified-window check."""
    with api_client.expect_error(400):
        auth_ep.complete_driver_registration(
            api_client,
            builders.driver_complete_registration(
                phone=phone_from_pool,
                password=settings.default_test_password,
            ),
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("vehicle.capacityKg", -1),
        ("vehicle.capacityKg", 0),
        ("vehicle.volumeM3", -0.5),
        ("license.expiresAt", "2000-01-01"),  # already expired
    ],
    ids=["negative-capacity", "zero-capacity", "negative-volume", "expired-license"],
)
def test_complete_with_invalid_profile_field_returns_400(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
    field: str,
    bad_value: object,
) -> None:
    """Build a baseline payload with a single invalid nested field."""
    body = builders.driver_complete_registration(
        phone=phone_from_pool,
        password=settings.default_test_password,
    ).model_dump(by_alias=True, mode="json")
    parent, _, key = field.partition(".")
    body[parent][key] = bad_value
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/mobile/registrations/complete",
            json=body,
            expect_status=200,
        )
