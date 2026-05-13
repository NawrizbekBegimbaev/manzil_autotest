"""Real concurrency invariants — runs requests in parallel threads.

Distinct from `tests/edge_cases/test_concurrent_registration.py`, which is
sequential. These tests use `ThreadPoolExecutor` to actually fire requests
at the same moment so backend's uniqueness constraints are stress-tested.

A correctly-implemented backend uses DB unique-constraint + retryable
transactions to ensure exactly one request wins. A broken backend either:
- accepts duplicates (no constraint), or
- 500s on the loser (constraint check is bare INSERT without handling).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.endpoints import employees as emp_ep
from api.schemas import (
    InviteEmployeeRequest,
    LogoutRequest,
    WebLoginRequest,
)
from config.settings import Settings
from data import builders
from data.email_pool import EmailPool
from data.phone_pool import PhonePool
from tests.conftest import RegisteredAccount


@pytest.mark.concurrency
def test_parallel_supplier_registration_with_same_email_yields_one_winner(
    settings: Settings,
    email_from_pool: str,
    phone_pool: PhonePool,
) -> None:
    """Two threads, two phones, same email → exactly one 204, one 409."""

    def attempt(phone: str) -> int:
        with ApiClient(settings) as client:
            response = client._client.post(
                "/api/v1/auth/web/registrations/suppliers",
                json=builders.supplier_registration(
                    email=email_from_pool,
                    phone=phone,
                    password=settings.default_test_password,
                ).model_dump(by_alias=True),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            return response.status_code

    with (
        phone_pool.lease() as phone_a,
        phone_pool.lease() as phone_b,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        statuses = list(pool.map(attempt, [phone_a, phone_b]))

    success = sum(1 for s in statuses if s == 204)
    conflict = sum(1 for s in statuses if s == 409)
    assert success == 1, f"expected exactly 1 success; got {statuses}"
    assert conflict == 1, f"expected exactly 1 conflict; got {statuses}"


@pytest.mark.xfail(
    reason="BUG-005: backend doesn't reject duplicate TIN — race produces multiple winners.",
    strict=False,
)
@pytest.mark.concurrency
def test_parallel_supplier_registration_with_same_tin_yields_one_winner(
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> None:
    """Same TIN, different emails+phones, two threads."""
    from utils.tin_generator import generate_tin

    shared_tin = generate_tin()

    def attempt(creds: tuple[str, str]) -> int:
        email, phone = creds
        with ApiClient(settings) as client:
            response = client._client.post(
                "/api/v1/auth/web/registrations/suppliers",
                json=builders.supplier_registration(
                    email=email,
                    phone=phone,
                    password=settings.default_test_password,
                    tin=shared_tin,
                ).model_dump(by_alias=True),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            return response.status_code

    with (
        email_pool.lease() as ea,
        email_pool.lease() as eb,
        phone_pool.lease() as pa,
        phone_pool.lease() as pb,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        statuses = list(pool.map(attempt, [(ea, pa), (eb, pb)]))

    assert statuses.count(204) == 1, statuses
    assert statuses.count(409) == 1, statuses


@pytest.mark.concurrency
@pytest.mark.requires_email_otp
def test_parallel_invite_with_same_email_yields_one_winner(
    settings: Settings,
    supplier_admin_client: ApiClient,
    email_from_pool: str,
) -> None:
    """Same admin invites same email twice in parallel — one 201, one 409."""

    def attempt(_: int) -> int:
        # Re-use the SAME authenticated client across threads — backend must
        # serialise on the email key, not on the connection.
        try:
            emp_ep.invite_employee(
                supplier_admin_client,
                InviteEmployeeRequest(
                    email=email_from_pool,
                    full_name="Race",
                    role="SUPPLIER_MANAGER",
                ),
            )
            return 201
        except Exception as exc:
            return getattr(exc, "status_code", 500)

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, [0, 1]))

    assert statuses.count(201) == 1, statuses
    assert statuses.count(409) == 1, statuses


@pytest.mark.concurrency
@pytest.mark.requires_email_otp
@pytest.mark.xfail(
    reason="Backend currently allows two concurrent refreshes with the same token.",
    strict=False,
)
def test_parallel_refresh_with_same_token_yields_one_winner(
    settings: Settings,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Refresh-token rotation under race: two threads call /refresh with
    the SAME refresh token. Exactly one must succeed (200), other 401."""
    with ApiClient(settings) as login_client:
        tokens = auth_ep.web_login(
            login_client,
            WebLoginRequest(
                email=verified_supplier_admin.email,
                password=verified_supplier_admin.password,
            ),
        )

    def attempt(_: int) -> int:
        with ApiClient(settings) as client:
            response = client._client.post(
                "/api/v1/auth/refresh",
                json={"refreshToken": tokens.refresh_token},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, [0, 1]))

    assert statuses.count(200) == 1, statuses
    assert statuses.count(401) == 1, statuses


@pytest.mark.concurrency
@pytest.mark.requires_email_otp
def test_parallel_logout_is_idempotent(
    settings: Settings,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Two simultaneous logouts with the same refresh token — both 204
    (per swagger: best-effort, never fails)."""
    with ApiClient(settings) as client:
        tokens = auth_ep.web_login(
            client,
            WebLoginRequest(
                email=verified_supplier_admin.email,
                password=verified_supplier_admin.password,
            ),
        )

    def attempt(_: int) -> int:
        with ApiClient(settings) as worker:
            try:
                auth_ep.logout(
                    worker,
                    LogoutRequest(refresh_token=tokens.refresh_token),
                )
                return 204
            except Exception as exc:
                return getattr(exc, "status_code", 500)

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, [0, 1]))

    assert statuses == [204, 204], statuses
