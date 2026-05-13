"""POST /api/v1/auth/web/password-resets + /confirm — email-OTP flow.

Critical security property: the *start* endpoint MUST return 204 regardless
of whether the email exists (enumeration defence). The *confirm* endpoint
fails with 400 on any bad code, so attackers can't probe codes.
"""

from __future__ import annotations

import time

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import (
    WebLoginRequest,
    WebPasswordResetConfirmRequest,
    WebPasswordResetStartRequest,
)
from config.settings import Settings
from tests.conftest import RegisteredAccount
from utils.gmail_otp import fetch_email_otp_via_imap

# ---------- start (enumeration defence) ------------------------------------


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_start_with_known_email_returns_204(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    auth_ep.start_web_password_reset(
        api_client,
        WebPasswordResetStartRequest(email=verified_supplier_admin.email),
    )


@pytest.mark.positive
def test_start_with_unknown_email_returns_204(
    api_client: ApiClient,
) -> None:
    """Enumeration defence: unknown emails MUST yield the same status as known ones."""
    auth_ep.start_web_password_reset(
        api_client,
        WebPasswordResetStartRequest(email="ghost-e2e@manziltest.uz"),
    )


@pytest.mark.negative
@pytest.mark.parametrize(
    "email",
    ["", "not-an-email", "@nodomain.uz", "user@"],
    ids=["empty", "no-at", "no-local", "no-domain"],
)
def test_start_with_malformed_email_returns_400(
    api_client: ApiClient,
    email: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/password-resets",
            json={"email": email},
            expect_status=204,
        )


# ---------- confirm --------------------------------------------------------


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_confirm_with_correct_code_resets_password(
    api_client: ApiClient,
    settings: Settings,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """End-to-end: start → fetch code → confirm → login with the new password."""
    new_password = "Rotated!Pass2025"
    reset_started_at = time.time()
    auth_ep.start_web_password_reset(
        api_client,
        WebPasswordResetStartRequest(email=verified_supplier_admin.email),
    )
    code = fetch_email_otp_via_imap(
        settings,
        verified_supplier_admin.email,
        since_epoch=reset_started_at - 30,
        exclude_codes={verified_supplier_admin.last_otp}
        if verified_supplier_admin.last_otp
        else None,
    )
    auth_ep.confirm_web_password_reset(
        api_client,
        WebPasswordResetConfirmRequest(
            email=verified_supplier_admin.email,
            code=code,
            new_password=new_password,
        ),
    )
    auth_ep.web_login(
        api_client,
        WebLoginRequest(email=verified_supplier_admin.email, password=new_password),
    )
    # Old password no longer works.
    with api_client.expect_error(401):
        auth_ep.web_login(
            api_client,
            WebLoginRequest(
                email=verified_supplier_admin.email,
                password=verified_supplier_admin.password,
            ),
        )


@pytest.mark.negative
def test_confirm_with_wrong_code_returns_400(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    with api_client.expect_error(400):
        auth_ep.confirm_web_password_reset(
            api_client,
            WebPasswordResetConfirmRequest(
                email="ghost-e2e@manziltest.uz",
                code="000000",
                new_password=settings.default_test_password,
            ),
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    "weak_password",
    ["", "short", "lowercase1!", "Password!", "Password1"],
    ids=["empty", "too-short", "no-upper", "no-digit", "no-symbol"],
)
def test_confirm_rejects_weak_password(
    api_client: ApiClient,
    weak_password: str,
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/password-resets/confirm",
            json={"email": "any@manziltest.uz", "code": "123456", "newPassword": weak_password},
            expect_status=204,
        )
