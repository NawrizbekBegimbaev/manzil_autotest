"""Cross-flow uniqueness invariants.

These aren't real concurrency tests (no threading) — they exercise the
*ordering* invariant: if A registers first, B with the same key fails. The
tests still catch most uniqueness regressions and stay deterministic.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from config.settings import Settings
from data import builders
from data.email_pool import EmailPool
from data.phone_pool import PhonePool
from utils.tin_generator import generate_tin


@pytest.mark.edge_case
def test_same_phone_blocks_second_supplier_registration(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_from_pool: str,
) -> None:
    """Two suppliers with the same phone — second must 409 (or 400 if backend
    treats phone as non-unique key for suppliers; SPECULATIVE)."""
    with email_pool.lease() as first_email:
        auth_ep.register_supplier(
            api_client,
            builders.supplier_registration(
                email=first_email,
                phone=phone_from_pool,
                password=settings.default_test_password,
            ),
        )
    with email_pool.lease() as second_email, api_client.expect_error(409):
        auth_ep.register_supplier(
            api_client,
            builders.supplier_registration(
                email=second_email,
                phone=phone_from_pool,
                password=settings.default_test_password,
            ),
        )


@pytest.mark.edge_case
def test_supplier_and_tk_cannot_share_tin(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> None:
    """One TIN, two role types — second registration must 409 (companies are
    unique by TIN regardless of role type)."""
    shared_tin = generate_tin()
    with email_pool.lease() as a_email, phone_pool.lease() as a_phone:
        auth_ep.register_supplier(
            api_client,
            builders.supplier_registration(
                email=a_email,
                phone=a_phone,
                password=settings.default_test_password,
                tin=shared_tin,
            ),
        )
    with (
        email_pool.lease() as b_email,
        phone_pool.lease() as b_phone,
        api_client.expect_error(409),
    ):
        auth_ep.register_trucking_company(
            api_client,
            builders.trucking_company_registration(
                email=b_email,
                phone=b_phone,
                password=settings.default_test_password,
                tin=shared_tin,
            ),
        )
