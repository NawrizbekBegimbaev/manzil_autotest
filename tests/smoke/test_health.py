"""Smoke: API is reachable and serves the OpenAPI spec.

Run this first when bringing up a new environment — failure here means
nothing else will pass and the cause is environment, not code.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient


@pytest.mark.smoke
def test_openapi_spec_is_served(api_client: ApiClient) -> None:
    """`/v3/api-docs` returns a JSON OpenAPI document.

    On dev, oauth2-proxy in front of the service redirects this endpoint to
    SSO unless authenticated. We accept either 200 (open) or 302 (gated).
    """
    response = api_client._client.get(
        "/v3/api-docs",
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    if response.status_code == 302:
        pytest.skip("Swagger gated by oauth2-proxy — visit /swagger-ui in browser to authenticate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("openapi", "").startswith("3."), body
    assert body.get("paths"), "OpenAPI doc has no paths"


@pytest.mark.smoke
def test_swagger_ui_is_served(api_client: ApiClient) -> None:
    """`/swagger-ui/index.html` reachable — sanity for gateway routing."""
    response = api_client._client.get(
        "/swagger-ui/index.html",
        follow_redirects=False,
    )
    if response.status_code == 302:
        pytest.skip("Swagger UI gated by oauth2-proxy")
    assert response.status_code == 200, response.text
    assert "swagger" in response.text.lower()
