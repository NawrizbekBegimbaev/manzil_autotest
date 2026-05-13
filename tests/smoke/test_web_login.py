"""Smoke: registered supplier admin can log in and call /api/v1/me.

Depends on `test_web_register.py` succeeding logically — but stays
self-contained: it registers a fresh user, verifies, then signs in. We
deliberately do NOT share state with the register test because `pytest -n`
schedules them on different workers.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth, me
from api.schemas import (
    SupplierRegistrationRequest,
    VerifyWebOtpRequest,
    WebLoginRequest,
)
from config.settings import Settings
from data.constants import E2E_PREFIX
from utils.otp import get_email_otp
from utils.tin_generator import generate_tin


@pytest.mark.smoke
@pytest.mark.requires_email_otp
def test_supplier_can_login_and_fetch_me(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    auth.register_supplier(
        api_client,
        SupplierRegistrationRequest(
            company_name=f"{E2E_PREFIX} Smoke Login Supplier",
            tin=generate_tin(),
            email=email_from_pool,
            phone=phone_from_pool,
            full_name="E2E Login Admin",
            password=settings.default_test_password,
        ),
    )
    auth.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(
            email=email_from_pool,
            code=get_email_otp(settings, email_from_pool),
        ),
    )

    tokens = auth.web_login(
        api_client,
        WebLoginRequest(email=email_from_pool, password=settings.default_test_password),
    )
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in > 0

    api_client.set_token(tokens.access_token)
    current = me.get_current_user(api_client)
    assert current.profile.email == email_from_pool
    assert current.role, "expected /me to expose role string"


@pytest.mark.smoke
def test_unauthenticated_me_is_rejected(api_client: ApiClient) -> None:
    """`/api/v1/me` without Bearer must return 401 with a ProblemDetail."""
    with api_client.expect_error(401) as errors:
        me.get_current_user(api_client)
    assert errors[0].problem is not None
