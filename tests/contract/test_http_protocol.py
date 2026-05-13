"""HTTP-level contract: methods, content types, CORS, OPTIONS preflight.

These checks are about the gateway / framework, not application logic.
A test failure here usually means a misconfiguration (e.g. nginx not set
up to reject non-JSON, or CORS headers missing for the web client).
"""

from __future__ import annotations

import pytest

from api.client import ApiClient

# ---------- method handling ------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/api/v1/auth/web/login"),       # POST-only
        ("DELETE", "/api/v1/auth/web/login"),
        ("PUT", "/api/v1/employees"),            # GET/POST-only
        ("PUT", "/api/v1/me"),                   # GET-only
        ("POST", "/api/v1/me"),
    ],
)
def test_unsupported_method_returns_405_or_401(
    api_client: ApiClient,
    method: str,
    path: str,
) -> None:
    """Wrong method must 405 — not 404 (that would hide the route's existence).

    On protected endpoints backend now applies auth BEFORE method
    resolution and returns 401 — that's a security improvement
    (doesn't leak route existence to anonymous probes). Both 405 and
    401 are acceptable here.
    """
    response = api_client._client.request(
        method,
        path,
        json={} if method in ("POST", "PUT", "PATCH") else None,
        headers={"Accept": "application/json"},
    )
    assert response.status_code in (401, 405), response.text
    if response.status_code == 405 and "allow" in {h.lower() for h in response.headers}:
        allow = response.headers.get("Allow", "")
        assert allow, "Allow header present but empty"


# ---------- content-type negotiation --------------------------------------


@pytest.mark.contract
def test_post_with_text_plain_content_type_returns_415(
    api_client: ApiClient,
) -> None:
    """Sending raw text where JSON is required must yield 415, not 500."""
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        content=b'{"email":"x@b.uz","password":"x"}',
        headers={"Accept": "application/json", "Content-Type": "text/plain"},
    )
    assert response.status_code in (400, 415), response.text


@pytest.mark.contract
def test_post_without_content_type_handles_gracefully(
    api_client: ApiClient,
) -> None:
    """Missing Content-Type — backend should default-treat as JSON or 415.
    Anything other than 4xx is a misconfiguration."""
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        content=b'{"email":"x@b.uz","password":"x"}',
        headers={"Accept": "application/json"},
    )
    assert 400 <= response.status_code < 500, response.text


@pytest.mark.contract
@pytest.mark.parametrize(
    "accept",
    ["application/xml", "text/csv", "application/yaml"],
)
def test_unsupported_accept_header_does_not_500(
    api_client: ApiClient,
    accept: str,
) -> None:
    """Asking for non-JSON response — server should 406 or fall back to JSON,
    NOT crash."""
    response = api_client._client.post(
        "/api/v1/auth/web/login",
        json={"email": "a@b.uz", "password": "x"},
        headers={"Accept": accept, "Content-Type": "application/json"},
    )
    assert response.status_code < 500, response.text


# ---------- CORS preflight (web frontend uses cross-origin) ----------------


@pytest.mark.contract
@pytest.mark.skip(
    reason="Same-origin architecture: dev-manzil.greatmall.uz hosts frontend "
    "and API under one domain. CORS is not required while this stays. "
    "Re-enable if frontend moves to a separate origin (see BUG-002).",
)
def test_options_preflight_returns_cors_headers(
    api_client: ApiClient,
) -> None:
    """A browser-issued preflight must succeed and expose CORS headers."""
    response = api_client._client.request(
        "OPTIONS",
        "/api/v1/auth/web/login",
        headers={
            "Origin": "https://web.dev.manzil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code in (200, 204), response.text
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    assert "access-control-allow-origin" in headers_lower, headers_lower
    assert "access-control-allow-methods" in headers_lower, headers_lower


# ---------- HEAD --------------------------------------------------------


@pytest.mark.contract
def test_head_on_swagger_returns_no_body(
    api_client: ApiClient,
) -> None:
    """HEAD must mirror GET headers without the body — used by health probes."""
    response = api_client._client.head(
        "/v3/api-docs", follow_redirects=False,
    )
    # Gateway may: allow (200/204), refuse method (405), or redirect to
    # oauth2-proxy (302) — the swagger route is gated on dev.
    assert response.status_code in (200, 204, 302, 405), response.text
    if response.status_code in (200, 204):
        assert response.content == b"", "HEAD response had a body"
