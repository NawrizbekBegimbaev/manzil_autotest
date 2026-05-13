"""GET /api/v1/me + PATCH /api/v1/me + PATCH /api/v1/me/driver."""

from __future__ import annotations

from api.client import ApiClient
from api.schemas import (
    CurrentUserResponse,
    UpdateDriverProfileRequest,
    UpdateProfileRequest,
)


def get_current_user(client: ApiClient) -> CurrentUserResponse:
    """GET /api/v1/me — role-aware payload (profile + organization OR driver+vehicle)."""
    response = client.get("/api/v1/me", expect_status=200)
    return CurrentUserResponse.model_validate(response.json())


def update_own_profile(
    client: ApiClient,
    body: UpdateProfileRequest,
) -> CurrentUserResponse:
    """PATCH /api/v1/me — partial fullName / phone update."""
    response = client.patch(
        "/api/v1/me",
        json=body.model_dump(by_alias=True, exclude_none=True),
        expect_status=200,
    )
    return CurrentUserResponse.model_validate(response.json())


def update_own_driver_profile(
    client: ApiClient,
    body: UpdateDriverProfileRequest,
) -> CurrentUserResponse:
    """PATCH /api/v1/me/driver — driver-only.

    Top-level fields are partial; nested `license` and `vehicle` blocks are
    replace-all-or-nothing per swagger.
    """
    response = client.patch(
        "/api/v1/me/driver",
        json=body.model_dump(by_alias=True, exclude_none=True),
        expect_status=200,
    )
    return CurrentUserResponse.model_validate(response.json())
