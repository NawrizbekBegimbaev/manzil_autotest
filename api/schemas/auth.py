"""Authentication request/response models.

Endpoints covered:
- POST /api/v1/auth/web/login         (email + password)
- POST /api/v1/auth/mobile/login      (phone + password)
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- POST /api/v1/auth/invitations/accept
"""

from __future__ import annotations

from pydantic import EmailStr, Field

from api.schemas._base import ApiModel


class WebLoginRequest(ApiModel):
    email: EmailStr
    password: str


class MobileLoginRequest(ApiModel):
    phone_number: str = Field(min_length=1)
    password: str


class TokenResponse(ApiModel):
    """Returned by web/mobile login, refresh, and driver registration complete."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


class RefreshRequest(ApiModel):
    refresh_token: str


class LogoutRequest(ApiModel):
    refresh_token: str


class AcceptInvitationRequest(ApiModel):
    token: str
    password: str
