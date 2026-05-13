"""POST /api/v1/auth/web/registrations/trucking-companies.

Same shape as supplier registration — see also test_web_register_supplier.py.
We keep separate files because the routes diverge in a few negatives (e.g.
TIN collision MAY be allowed across role boundaries — backend hasn't said).
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from config.settings import Settings
from data import builders
from data.phone_pool import PhonePool


@pytest.mark.smoke
@pytest.mark.positive
def test_register_trucking_company_returns_204(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    auth_ep.register_trucking_company(
        api_client,
        builders.trucking_company_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )


@pytest.mark.xfail(
    reason="BUG-004: backend returns 204 on duplicate email instead of 409 (TK side).",
    strict=False,
)
@pytest.mark.negative
def test_register_trucking_company_with_duplicate_email_returns_409(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    phone_pool: PhonePool,
) -> None:
    auth_ep.register_trucking_company(
        api_client,
        builders.trucking_company_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    with phone_pool.lease() as another_phone, api_client.expect_error(409):
        auth_ep.register_trucking_company(
            api_client,
            builders.trucking_company_registration(
                email=email_from_pool,
                phone=another_phone,
                password=settings.default_test_password,
            ),
        )


@pytest.mark.negative
@pytest.mark.edge_case
def test_email_taken_by_supplier_blocks_tk_registration(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    phone_pool: PhonePool,
) -> None:
    """A supplier-admin email cannot also register as TK admin (same Keycloak user)."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    with phone_pool.lease() as another_phone, api_client.expect_error(409):
        auth_ep.register_trucking_company(
            api_client,
            builders.trucking_company_registration(
                email=email_from_pool,
                phone=another_phone,
                password=settings.default_test_password,
            ),
        )
