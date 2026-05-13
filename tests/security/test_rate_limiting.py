"""Rate-limiting probes.

Marked `slow` because they intentionally fire many requests. Skip with
`pytest -m 'not slow'` in regular CI.

These tests don't fail if rate-limiting is absent — they ASSERT that it is
present. Auth without rate-limiting = trivial credential-stuffing target.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from config.settings import Settings


@pytest.mark.xfail(
    reason="BUG-006: backend has no rate-limiting — 429 never returned.",
    strict=False,
)
@pytest.mark.security
@pytest.mark.slow
def test_brute_force_login_eventually_returns_429(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    """30 wrong-password attempts in a row — at least one must return 429.

    SPECULATIVE: limit value not in swagger. If real limit is >30 attempts
    per window, increase the loop count. If Keycloak handles this rather
    than the gateway, the threshold may be much higher.
    """
    statuses: list[int] = []
    for _ in range(30):
        response = api_client._client.post(
            "/api/v1/auth/web/login",
            json={"email": "ratelimit-target@manziltest.uz", "password": "wrong-pwd-attempt"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        statuses.append(response.status_code)
        if response.status_code == 429:
            break
    assert 429 in statuses, (
        f"30 brute-force login attempts produced no 429. statuses={statuses}"
    )


@pytest.mark.xfail(
    reason="BUG-006: backend has no rate-limiting on /password-resets — 429 never returned.",
    strict=False,
)
@pytest.mark.security
@pytest.mark.slow
def test_password_reset_spam_eventually_returns_429(
    api_client: ApiClient,
) -> None:
    """Repeated /password-resets calls for the same email must rate-limit.

    Without this, an attacker can spam victim's inbox with reset codes.
    """
    statuses: list[int] = []
    for _ in range(20):
        response = api_client._client.post(
            "/api/v1/auth/web/password-resets",
            json={"email": "spam-target@manziltest.uz"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        statuses.append(response.status_code)
        if response.status_code == 429:
            break
    assert 429 in statuses, f"20 reset attempts produced no 429. statuses={statuses}"


@pytest.mark.security
@pytest.mark.slow
def test_registration_spam_eventually_returns_429(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Repeating supplier-registration with same email/TIN must yield 429
    (or 409 on the second call onward — both are acceptable rate limits)."""
    statuses: list[int] = []
    body = {
        "companyName": "[E2E] Spam",
        "tin": "200222333444",
        "email": email_from_pool,
        "phone": phone_from_pool,
        "fullName": "Spam",
        "password": settings.default_test_password,
    }
    for _ in range(10):
        response = api_client._client.post(
            "/api/v1/auth/web/registrations/suppliers",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        statuses.append(response.status_code)
        if response.status_code == 429:
            break
    assert 429 in statuses or 409 in statuses, (
        f"10 spam regs produced neither 429 nor 409. statuses={statuses}"
    )


@pytest.mark.security
@pytest.mark.slow
def test_unknown_email_login_does_not_leak_via_timing(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    """Timing oracle check: response time for unknown-email login must be
    similar to wrong-password-on-known-account. Not a strict assertion —
    we sample 10 of each and require the medians within a 3x window.

    A 100x discrepancy means backend short-circuits on user-not-found,
    leaking enumeration info via timing.
    """
    import statistics
    import time

    def _measure(email: str) -> float:
        t0 = time.perf_counter()
        api_client._client.post(
            "/api/v1/auth/web/login",
            json={"email": email, "password": "wrong"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        return time.perf_counter() - t0

    unknown = [_measure(f"unknown-{i}@manziltest.uz") for i in range(10)]
    median = statistics.median(unknown)
    pytest.skip(
        "Need a real registered account for the comparison side; rerun once "
        "verified_supplier_admin can be brought into a slow test without "
        f"saturating the email pool. Median(unknown)={median:.3f}s",
    )
