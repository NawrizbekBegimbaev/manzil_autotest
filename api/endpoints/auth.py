"""Authentication + registration + password-reset endpoint wrappers.

Each function takes an `ApiClient`, builds the request from typed pydantic
models, and returns the parsed response model (or `None` for 204 endpoints).

All endpoints in this module are public (no Bearer token required) EXCEPT
where noted.
"""

from __future__ import annotations

from api.client import ApiClient
from api.schemas import (
    AcceptInvitationRequest,
    CompleteDriverRegistrationRequest,
    DriverRegistrationStartRequest,
    DriverRegistrationStartResponse,
    LogoutRequest,
    MobileLoginRequest,
    MobilePasswordResetConfirmRequest,
    MobilePasswordResetStartRequest,
    MobilePasswordResetVerifyRequest,
    MobilePasswordResetVerifyResponse,
    RefreshRequest,
    SupplierRegistrationRequest,
    TokenResponse,
    TruckingCompanyRegistrationRequest,
    VerifyMobileOtpRequest,
    VerifyWebOtpRequest,
    WebLoginRequest,
    WebPasswordResetConfirmRequest,
    WebPasswordResetStartRequest,
)

# ---------- Web login ------------------------------------------------------


def web_login(client: ApiClient, body: WebLoginRequest) -> TokenResponse:
    """POST /api/v1/auth/web/login — supplier/TK admins, dispatchers, managers."""
    response = client.post(
        "/api/v1/auth/web/login",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return TokenResponse.model_validate(response.json())


def mobile_login(client: ApiClient, body: MobileLoginRequest) -> TokenResponse:
    """POST /api/v1/auth/mobile/login — drivers (phone + password)."""
    response = client.post(
        "/api/v1/auth/mobile/login",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return TokenResponse.model_validate(response.json())


def refresh(client: ApiClient, body: RefreshRequest) -> TokenResponse:
    """POST /api/v1/auth/refresh — rotates the refresh token."""
    response = client.post(
        "/api/v1/auth/refresh",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return TokenResponse.model_validate(response.json())


def logout(client: ApiClient, body: LogoutRequest) -> None:
    """POST /api/v1/auth/logout — revokes the refresh token. Always 204."""
    client.post(
        "/api/v1/auth/logout",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def accept_invitation(client: ApiClient, body: AcceptInvitationRequest) -> None:
    """POST /api/v1/auth/invitations/accept — set initial password from invite."""
    client.post(
        "/api/v1/auth/invitations/accept",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


# ---------- Web registration ----------------------------------------------


def register_supplier(client: ApiClient, body: SupplierRegistrationRequest) -> None:
    """POST /api/v1/auth/web/registrations/suppliers — sends email OTP. 204."""
    client.post(
        "/api/v1/auth/web/registrations/suppliers",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def register_trucking_company(
    client: ApiClient,
    body: TruckingCompanyRegistrationRequest,
) -> None:
    """POST /api/v1/auth/web/registrations/trucking-companies — sends email OTP. 204."""
    client.post(
        "/api/v1/auth/web/registrations/trucking-companies",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def verify_web_registration(client: ApiClient, body: VerifyWebOtpRequest) -> None:
    """POST /api/v1/auth/web/registrations/verify — finalises web sign-up. 204."""
    client.post(
        "/api/v1/auth/web/registrations/verify",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


# ---------- Web password reset --------------------------------------------


def start_web_password_reset(
    client: ApiClient,
    body: WebPasswordResetStartRequest,
) -> None:
    """POST /api/v1/auth/web/password-resets — always 204 (enumeration defence)."""
    client.post(
        "/api/v1/auth/web/password-resets",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def confirm_web_password_reset(
    client: ApiClient,
    body: WebPasswordResetConfirmRequest,
) -> None:
    """POST /api/v1/auth/web/password-resets/confirm — sets new password. 204."""
    client.post(
        "/api/v1/auth/web/password-resets/confirm",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


# ---------- Mobile (driver) registration ----------------------------------


def start_driver_registration(
    client: ApiClient,
    body: DriverRegistrationStartRequest,
) -> DriverRegistrationStartResponse:
    """POST /api/v1/auth/mobile/registrations/drivers — returns Telegram deeplink."""
    response = client.post(
        "/api/v1/auth/mobile/registrations/drivers",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return DriverRegistrationStartResponse.model_validate(response.json())


def verify_driver_otp(client: ApiClient, body: VerifyMobileOtpRequest) -> None:
    """POST /api/v1/auth/mobile/registrations/verify — 204 on success."""
    client.post(
        "/api/v1/auth/mobile/registrations/verify",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def complete_driver_registration(
    client: ApiClient,
    body: CompleteDriverRegistrationRequest,
) -> TokenResponse:
    """POST /api/v1/auth/mobile/registrations/complete — issues tokens."""
    response = client.post(
        "/api/v1/auth/mobile/registrations/complete",
        json=body.model_dump(by_alias=True, mode="json"),
        expect_status=200,
    )
    return TokenResponse.model_validate(response.json())


# ---------- Mobile password reset -----------------------------------------


def start_mobile_password_reset(
    client: ApiClient,
    body: MobilePasswordResetStartRequest,
) -> None:
    """POST /api/v1/auth/mobile/password-resets — always 204."""
    client.post(
        "/api/v1/auth/mobile/password-resets",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )


def verify_mobile_password_reset(
    client: ApiClient,
    body: MobilePasswordResetVerifyRequest,
) -> MobilePasswordResetVerifyResponse:
    """POST /api/v1/auth/mobile/password-resets/verify — exchanges OTP for
    a one-shot reset token (~10 min TTL)."""
    response = client.post(
        "/api/v1/auth/mobile/password-resets/verify",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return MobilePasswordResetVerifyResponse.model_validate(response.json())


def confirm_mobile_password_reset(
    client: ApiClient,
    body: MobilePasswordResetConfirmRequest,
) -> None:
    """POST /api/v1/auth/mobile/password-resets/confirm — 204. Replays the
    reset token from /verify together with the new password."""
    client.post(
        "/api/v1/auth/mobile/password-resets/confirm",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )
