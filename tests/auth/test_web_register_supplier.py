"""POST /api/v1/auth/web/registrations/suppliers — happy path + duplicates + cooldown.

Verify-step coverage lives in `test_web_register_verify.py`.
Generic field-validation lives in `test_web_register_validation.py`.
Length/range boundary cases live in `test_web_register_boundary.py`.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from config.settings import Settings
from data import builders
from data.email_pool import EmailPool
from data.phone_pool import PhonePool

# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
def test_register_supplier_returns_204(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Backend persists pending account + dispatches OTP. No JWT yet."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )


# ---------- negative: duplicates -------------------------------------------


@pytest.mark.xfail(
    reason="BUG-004: backend returns 204 on duplicate email instead of 409.",
    strict=False,
)
@pytest.mark.negative
def test_register_supplier_with_duplicate_email_returns_409(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    phone_pool: PhonePool,
) -> None:
    """Same email cannot be reused — second attempt returns 409."""
    first = builders.supplier_registration(
        email=email_from_pool,
        phone=phone_from_pool,
        password=settings.default_test_password,
    )
    auth_ep.register_supplier(api_client, first)

    with phone_pool.lease() as another_phone, api_client.expect_error(409) as errors:
        second = builders.supplier_registration(
            email=email_from_pool,  # same email
            phone=another_phone,
            password=settings.default_test_password,
        )
        auth_ep.register_supplier(api_client, second)
    assert errors[0].problem is not None


@pytest.mark.negative
def test_register_supplier_with_duplicate_tin_returns_409(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    phone_pool: PhonePool,
    email_pool: EmailPool,
) -> None:
    """TIN is the company key — same TIN twice → 409."""
    shared_tin = builders.supplier_registration(
        email=email_from_pool,
        phone=phone_from_pool,
        password=settings.default_test_password,
    ).tin
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
            tin=shared_tin,
        ),
    )

    with (
        email_pool.lease() as another_email,
        phone_pool.lease() as another_phone,
        api_client.expect_error(409) as errors,
    ):
        auth_ep.register_supplier(
            api_client,
            builders.supplier_registration(
                email=another_email,
                phone=another_phone,
                password=settings.default_test_password,
                tin=shared_tin,  # collision
            ),
        )
    assert errors[0].problem is not None


# ---------- negative: resend cooldown (429) --------------------------------


@pytest.mark.xfail(
    reason="BUG-006: backend doesn't enforce OTP-resend cooldown — no 429.",
    strict=False,
)
@pytest.mark.negative
@pytest.mark.edge_case
def test_register_supplier_immediate_resend_returns_429(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Two starts in a row for the same email — second hits cooldown.

    Backend declares 429 on the swagger; the cooldown duration is unspecified
    (open question). If backend's cooldown is too short to catch reliably,
    backend should provide a test-mode header — track in open question #2.
    """
    body = builders.supplier_registration(
        email=email_from_pool,
        phone=phone_from_pool,
        password=settings.default_test_password,
    )
    auth_ep.register_supplier(api_client, body)
    with api_client.expect_error(429):
        auth_ep.register_supplier(api_client, body)
