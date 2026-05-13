"""POST /api/v1/auth/web/login — full coverage.

Positive:
- Verified supplier/TK admins can sign in and receive a Bearer token pair.

Negative:
- Wrong password → 401
- Unknown email → 401
- Email/password missing or empty → 400
- Email format invalid → 400 (caught server-side; client model also enforces)

The 401 path is covered by both "unknown email" and "wrong password" because
backend may treat them the same to defend against enumeration — we accept
either ProblemDetail.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.schemas import WebLoginRequest
from config.settings import Settings
from tests.conftest import RegisteredAccount

# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_supplier_admin_logs_in(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    tokens = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_supplier_admin.email,
            password=verified_supplier_admin.password,
        ),
    )
    assert tokens.token_type == "Bearer"
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_in > 0


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_tk_admin_logs_in(
    api_client: ApiClient,
    verified_tk_admin: RegisteredAccount,
) -> None:
    tokens = auth_ep.web_login(
        api_client,
        WebLoginRequest(
            email=verified_tk_admin.email,
            password=verified_tk_admin.password,
        ),
    )
    assert tokens.access_token


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_login_returns_distinct_tokens(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    """Two consecutive logins must produce different access/refresh tokens.

    Keycloak issues fresh JTIs each time — same-token reuse would indicate
    a caching bug.
    """
    request = WebLoginRequest(
        email=verified_supplier_admin.email,
        password=verified_supplier_admin.password,
    )
    first = auth_ep.web_login(api_client, request)
    second = auth_ep.web_login(api_client, request)
    assert first.access_token != second.access_token
    assert first.refresh_token != second.refresh_token


# ---------- negative: bad credentials --------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_login_with_wrong_password_returns_401(
    api_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
) -> None:
    with api_client.expect_error(401) as errors:
        auth_ep.web_login(
            api_client,
            WebLoginRequest(
                email=verified_supplier_admin.email,
                password="WrongP@ssw0rd!",
            ),
        )
    assert errors[0].problem is not None


@pytest.mark.negative
def test_login_with_unknown_email_returns_401(
    api_client: ApiClient,
    settings: Settings,
) -> None:
    with api_client.expect_error(401) as errors:
        auth_ep.web_login(
            api_client,
            WebLoginRequest(
                email="nobody-e2e@manziltest.uz",
                password=settings.default_test_password,
            ),
        )
    assert errors[0].problem is not None


# ---------- negative: malformed payload (parametrized 400 sweep) -----------


@pytest.mark.negative
@pytest.mark.parametrize(
    ("email", "password"),
    [
        pytest.param("", "P@ssw0rd!", id="empty-email"),
        pytest.param("admin@acme.uz", "", id="empty-password"),
        pytest.param("not-an-email", "P@ssw0rd!", id="malformed-email"),
        pytest.param("admin@acme.uz", " ", id="whitespace-password"),
    ],
)
def test_login_with_malformed_payload_returns_400(
    api_client: ApiClient,
    email: str,
    password: str,
) -> None:
    """Server must reject malformed credentials before hitting Keycloak."""
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/login",
            json={"email": email, "password": password},
            expect_status=200,
        )


@pytest.mark.negative
@pytest.mark.parametrize(
    "body",
    [{}, {"email": "a@b.uz"}, {"password": "x"}],
    ids=["empty-body", "no-password", "no-email"],
)
def test_login_with_missing_fields_returns_400(
    api_client: ApiClient,
    body: dict[str, str],
) -> None:
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/login",
            json=body,
            expect_status=200,
        )


# ---------- negative: blocked / unverified accounts ------------------------


@pytest.mark.negative
def test_login_before_verify_returns_401(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Account exists in Keycloak as disabled until /verify — login must fail."""
    from data import builders

    auth_ep.register_supplier(
        api_client,
        builders.supplier_registration(
            email=email_from_pool,
            phone=phone_from_pool,
            password=settings.default_test_password,
        ),
    )
    with api_client.expect_error(401):
        auth_ep.web_login(
            api_client,
            WebLoginRequest(email=email_from_pool, password=settings.default_test_password),
        )
