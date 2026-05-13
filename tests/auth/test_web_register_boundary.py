"""Boundary values for /api/v1/auth/web/registrations/suppliers.

Lengths and edge formats — distinct from `test_web_register_validation.py`
which covers single-field invalidation. These tests assert the *just-valid*
side of each boundary so a server tightening (length-1) is detected.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from config.settings import Settings
from data import builders
from utils.tin_generator import generate_tin


@pytest.mark.positive
# Backend min-length aligned with UI «не короче 2 символов» on 2026-05-04 —
# 1-char names now rejected. 2 / 50 / 255 cover min, mid, near-max.
@pytest.mark.parametrize("length", [2, 50, 255], ids=["min-2", "mid-50", "near-max-255"])
def test_company_name_lengths_accepted(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    length: int,
) -> None:
    """SPECULATIVE: max length not in swagger. 255 is a common DB cap; lower if
    backend constrains differently."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
            company_name="A" * length,
        ),
    )


@pytest.mark.negative
def test_company_name_overlong_returns_400(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    body = builders.supplier_registration(
        email=email_from_pool,
        phone=phone_from_pool,
        password=settings.default_test_password,
    ).model_dump(by_alias=True)
    body["companyName"] = "A" * 1001
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/registrations/suppliers",
            json=body,
            expect_status=204,
        )


@pytest.mark.positive
def test_tin_starts_with_three(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Real Uzbek TINs may start with 3xx (sole-trader). Confirm backend
    accepts non-200 prefix (legitimate per registry rules)."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
            tin="3" + generate_tin()[1:],
        ),
    )


@pytest.mark.positive
def test_company_name_unicode_is_accepted(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Cyrillic + Chinese — both are first-class platform languages (BRD §3.5)."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
            company_name="[E2E] ООО «Пример» 中国货运",  # noqa: RUF001
        ),
    )


@pytest.mark.positive
def test_email_with_plus_tag_is_accepted(
    api_client: ApiClient,
    settings: Settings,
    phone_from_pool: str,
) -> None:
    """RFC 5322 plus-tag — `e2e+tag@manziltest.uz`. Many services strip the tag,
    but for our tests they are meaningful (unique slot)."""
    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email="e2e+boundary-001@manziltest.uz",
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
