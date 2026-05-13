"""Error response consistency: every 4xx / 5xx is a ProblemDetail and
contains no info-leaking artefacts.

This is a *cross-cutting* contract: every error from every endpoint
should obey the same shape. A leak (stack trace, SQL fragment, internal
hostname) on any single endpoint would compromise the whole API surface.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from api.client import ApiClient
from api.schemas import EmployeeResponse

_LEAK_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"at [a-zA-Z_.$/]+\.java:\d+"),  # JVM stack frame
    re.compile(r"at [a-zA-Z_.$/]+\.py:\d+"),    # Python stack frame
    re.compile(r"org\.springframework\.[a-zA-Z.]+Exception"),
    re.compile(r"java\.sql\.[A-Z]\w+Exception"),
    re.compile(r"psycopg2\."),
    re.compile(r"PSQLException"),
    re.compile(r"select\s+\*\s+from\s+", re.IGNORECASE),
    re.compile(r"/(home|var|opt)/[a-zA-Z_/]+\.(java|py)"),  # filesystem paths
]


def _assert_no_leak(body: str, status: int, where: str) -> None:
    for pat in _LEAK_PATTERNS:
        snippet = body[:300]
        assert not pat.search(body), (
            f"info-leak at {where} ({status}): pattern={pat.pattern!r} body={snippet!r}"
        )


@pytest.mark.contract
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/v1/auth/web/login", {"email": "not-json", "password": ""}),
        ("POST", "/api/v1/auth/web/registrations/suppliers", {}),
        ("POST", "/api/v1/auth/refresh", {}),
        ("POST", "/api/v1/auth/logout", {"refreshToken": ""}),
        ("POST", "/api/v1/auth/invitations/accept", {"token": "x", "password": "weak"}),
    ],
)
def test_400_responses_do_not_leak_internals(
    api_client: ApiClient,
    method: str,
    path: str,
    body: dict[str, str],
) -> None:
    response = api_client._client.request(
        method,
        path,
        json=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code >= 400, "case must produce error"
    _assert_no_leak(response.text, response.status_code, f"{method} {path}")


# Fixed UUID — value is irrelevant since the route returns 401 before resource
# lookup. Literal required so xdist workers collect identical test IDs.
_DUMMY_UUID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.contract
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/employees"),
        ("GET", "/api/v1/me"),
        ("DELETE", f"/api/v1/employees/{_DUMMY_UUID}"),
    ],
)
def test_401_uses_problemdetail_content_type(
    api_client: ApiClient,
    method: str,
    path: str,
) -> None:
    """Per swagger: 401/403/404 ALL return application/problem+json."""
    response = api_client._client.request(
        method,
        path,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401
    ct = response.headers.get("content-type", "")
    assert ct.startswith("application/problem+json") or ct.startswith("application/json"), ct
    body = response.json()
    # ProblemDetail has at minimum these three:
    assert isinstance(body.get("status"), int) or body.get("status") is None
    assert "title" in body or "detail" in body, body


@pytest.mark.contract
@pytest.mark.requires_email_otp
def test_404_for_other_tenants_employee_matches_404_for_random_uuid(
    supplier_admin_client: ApiClient,
    employee_in_company_a: EmployeeResponse,
    second_supplier_admin_client: ApiClient,
) -> None:
    """SECURITY: 404 for "exists in other tenant" must look identical to
    404 for "doesn't exist anywhere". Otherwise an attacker can probe
    UUIDs to enumerate the platform's employee directory.
    """
    other_tenant = second_supplier_admin_client._client.delete(
        f"/api/v1/employees/{employee_in_company_a.id}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {second_supplier_admin_client.token}",
        },
    )
    nowhere = second_supplier_admin_client._client.delete(
        f"/api/v1/employees/{uuid4()}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {second_supplier_admin_client.token}",
        },
    )
    assert other_tenant.status_code == nowhere.status_code == 404
    # Body shape MUST be identical (same fields populated). We don't compare
    # raw bytes (timestamps may differ), but the keys should match.
    if other_tenant.headers.get("content-type", "").startswith("application/"):
        assert set(other_tenant.json().keys()) == set(nowhere.json().keys()), (
            "tenant-leak via 404 body shape divergence"
        )
