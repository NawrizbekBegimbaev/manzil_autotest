"""Parametrized RBAC sweep — every protected route returns 401 without a token.

Public routes (auth endpoints) are NOT included — they are tested individually.

When backend exposes more endpoints (requests, offers, vehicles…), append them
to `_PROTECTED_ROUTES` and the sweep covers them automatically.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient

# Fixed UUID — the value is irrelevant (these tests expect 401 without a token,
# so the route never reaches the resource lookup). Must be a literal so that
# every pytest-xdist worker collects identical test IDs.
_DUMMY_UUID = "00000000-0000-0000-0000-000000000001"

# (method, path, body) — body=None for GET/DELETE.
_PROTECTED_ROUTES: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "/api/v1/employees", None),
    (
        "POST",
        "/api/v1/employees",
        {"email": "x@manziltest.uz", "fullName": "X", "role": "SUPPLIER_MANAGER"},
    ),
    ("PATCH", f"/api/v1/employees/{_DUMMY_UUID}", {"fullName": "Y"}),
    ("DELETE", f"/api/v1/employees/{_DUMMY_UUID}", None),
    ("GET", "/api/v1/me", None),
]


@pytest.mark.rbac
@pytest.mark.parametrize(
    ("method", "path", "body"),
    _PROTECTED_ROUTES,
    ids=lambda v: str(v) if not isinstance(v, dict) else "body",
)
def test_protected_route_without_token_returns_401(
    api_client: ApiClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    expected = (200, 201, 204)  # any 2xx would be a leak
    response = api_client._client.request(
        method,
        path,
        json=body,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401, (
        f"route {method} {path} returned {response.status_code} without auth — expected 401, "
        f"not {expected}"
    )


@pytest.mark.rbac
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/employees"),
        ("POST", "/api/v1/employees"),
    ],
)
def test_supplier_only_route_rejects_tk_admin(
    tk_admin_client: ApiClient,
    method: str,
    path: str,
) -> None:
    """Per swagger: 403 when caller is not a supplier admin.

    Validation before authz is acceptable when the route requires a body.
    """
    body: dict[str, object] | None = None
    if method == "POST":
        body = {"email": "x@manziltest.uz", "fullName": "X", "role": "SUPPLIER_MANAGER"}
    bearer = f"Bearer {tk_admin_client.token}"
    response = tk_admin_client._client.request(
        method,
        path,
        json=body,
        headers={"Accept": "application/json", "Authorization": bearer},
    )
    expected_statuses = (400, 403) if method == "POST" else (403,)
    assert response.status_code in expected_statuses, response.text
