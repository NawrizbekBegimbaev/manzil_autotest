"""Smoke: supplier admin can register through the web flow.

Two-step happy path:
1. POST /api/v1/auth/web/registrations/suppliers — backend persists the
   pending Keycloak user and emails the OTP.
2. POST /api/v1/auth/web/registrations/verify — submitting the captured OTP
   activates the account.

Marked `requires_email_otp` because step 2 needs a way to obtain the code.
Run with `EMAIL_OTP_MODE=fixed` and matching backend to enable.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth
from api.schemas import SupplierRegistrationRequest, VerifyWebOtpRequest
from config.settings import Settings
from data.constants import E2E_PREFIX
from utils.otp import get_email_otp
from utils.tin_generator import generate_tin


@pytest.mark.smoke
@pytest.mark.requires_email_otp
def test_supplier_registers_and_verifies(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Supplier admin completes a fresh registration end-to-end via API."""
    body = SupplierRegistrationRequest(
        company_name=f"{E2E_PREFIX} Smoke Supplier",
        tin=generate_tin(),
        email=email_from_pool,
        phone=phone_from_pool,
        full_name="E2E Supplier Admin",
        password=settings.default_test_password,
    )
    auth.register_supplier(api_client, body)

    code = get_email_otp(settings, email_from_pool)
    auth.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(email=email_from_pool, code=code),
    )
