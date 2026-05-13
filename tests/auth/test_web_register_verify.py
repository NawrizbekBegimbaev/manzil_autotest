"""POST /api/v1/auth/web/registrations/verify — OTP confirmation."""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import VerifyWebOtpRequest
from config.settings import Settings
from data import builders
from utils.otp import get_email_otp


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_verify_with_correct_code_returns_204(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    auth_ep.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(
            email=email_from_pool,
            code=get_email_otp(settings, email_from_pool),
        ),
    )


@pytest.mark.negative
def test_verify_with_wrong_code_returns_400(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    with api_client.expect_error(400):
        auth_ep.verify_web_registration(
            api_client,
            VerifyWebOtpRequest(email=email_from_pool, code="000000"),
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    "code",
    ["12345", "1234567", "abcdef", "12 34 56", ""],
    ids=["too-short", "too-long", "letters", "with-spaces", "empty"],
)
def test_verify_with_malformed_code_returns_400(
    api_client: ApiClient,
    email_from_pool: str,
    code: str,
) -> None:
    """Malformed code never reaches OTP storage — server validates shape first."""
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/registrations/verify",
            json={"email": email_from_pool, "code": code},
            expect_status=204,
        )


@pytest.mark.negative
def test_verify_for_unknown_email_returns_400(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    """No pending registration for this email → 400 (no enumeration leakage)."""
    with api_client.expect_error(400):
        auth_ep.verify_web_registration(
            api_client,
            VerifyWebOtpRequest(email="nonexistent-e2e@manziltest.uz", code="123456"),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
def test_verify_twice_with_same_code_returns_400_on_second(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """OTP is single-use — second verify call must fail even with the right code."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    code = get_email_otp(settings, email_from_pool)
    auth_ep.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(email=email_from_pool, code=code),
    )
    with api_client.expect_error(400):
        auth_ep.verify_web_registration(
            api_client,
            VerifyWebOtpRequest(email=email_from_pool, code=code),
        )
