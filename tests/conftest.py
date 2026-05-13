"""Shared fixtures for the Manzil API test suite.

Fixture-scope rules:
- `settings` is session-scoped — `.env` is parsed once per process.
- Pools (`phone_pool`, `email_pool`) are session-scoped — they coordinate
  via filelock, so reusing the same instance is fine.
- `api_client` is function-scoped so each test gets a clean Bearer state.
- High-level "registered/authenticated <role>" fixtures are function-scoped
  and lease their own phone/email so tests stay isolated.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from api.client import ApiClient, ApiError
from api.endpoints import auth as auth_ep
from api.endpoints import employees as emp_ep
from api.schemas import (
    AcceptInvitationRequest,
    EmployeeResponse,
    InviteEmployeeRequest,
    TokenResponse,
    VerifyWebOtpRequest,
    WebLoginRequest,
)
from config.settings import Settings
from data import builders
from data.email_pool import EmailPool
from data.phone_pool import PhonePool
from utils.gmail_otp import fetch_invitation_token_via_imap
from utils.otp import get_email_otp

# Core fixtures (settings, pools, api_client) live in the project-root
# conftest.py — both `tests/` and `web_ui/` share them.


# ---------- account fixtures (require email-OTP capture) -------------------


@dataclass
class RegisteredAccount:
    """A web-account that has finished /verify and is ready to login.

    Tests get this from `verified_supplier_admin` / `verified_tk_admin`.
    `tokens` is None until `auth_ep.web_login` is called explicitly — most
    tests want to drive login as part of the assertion, not the setup.
    """

    email: str
    phone: str
    password: str
    company_name: str
    tin: str
    full_name: str
    tokens: TokenResponse | None = None
    last_otp: str | None = None


@dataclass
class RegisteredDispatcher(RegisteredAccount):
    """Dispatcher invited and activated in a supplier admin's company."""

    inviter_admin: RegisteredAccount | None = None


def _register_supplier_with_retry(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
    *,
    max_attempts: int = 3,
) -> tuple[RegisteredAccount, str]:
    last_exc: ApiError | None = None
    for _ in range(max_attempts):
        email = email_pool.checkout()
        phone = phone_pool.checkout()
        body = builders.supplier_registration(
            email=email,
            phone=phone,
            password=settings.default_test_password,
        )
        try:
            auth_ep.register_supplier(api_client, body)
        except ApiError as exc:
            if exc.status_code != 409:
                raise
            last_exc = exc
            continue
        account = RegisteredAccount(
            email=body.email,
            phone=body.phone,
            password=body.password,
            company_name=body.company_name,
            tin=body.tin,
            full_name=body.full_name,
        )
        return account, email
    assert last_exc is not None
    raise last_exc


def _register_tk_with_retry(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
    *,
    max_attempts: int = 3,
) -> tuple[RegisteredAccount, str]:
    last_exc: ApiError | None = None
    for _ in range(max_attempts):
        email = email_pool.checkout()
        phone = phone_pool.checkout()
        body = builders.trucking_company_registration(
            email=email,
            phone=phone,
            password=settings.default_test_password,
        )
        try:
            auth_ep.register_trucking_company(api_client, body)
        except ApiError as exc:
            if exc.status_code != 409:
                raise
            last_exc = exc
            continue
        account = RegisteredAccount(
            email=body.email,
            phone=body.phone,
            password=body.password,
            company_name=body.company_name,
            tin=body.tin,
            full_name=body.full_name,
        )
        return account, email
    assert last_exc is not None
    raise last_exc


@pytest.fixture
def verified_supplier_admin(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> RegisteredAccount:
    """Register + verify a fresh supplier admin via API.

    Tests using this fixture MUST be marked `@pytest.mark.requires_email_otp`
    so the project-root collection hook auto-skips them when OTP capture
    isn't configured (`MANZIL_OTP_CAPTURE` env var). Otherwise they'd
    cascade into hundreds of setup-time ApiErrors on /verify.
    """
    account, email = _register_supplier_with_retry(
        api_client,
        settings,
        email_pool,
        phone_pool,
    )
    code = get_email_otp(settings, email)
    auth_ep.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(
            email=email,
            code=code,
        ),
    )
    account.last_otp = code
    return account


@pytest.fixture
def verified_tk_admin(
    api_client: ApiClient,
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> RegisteredAccount:
    """Register + verify a fresh TK admin via API. Same OTP gate as
    `verified_supplier_admin`."""
    account, email = _register_tk_with_retry(
        api_client,
        settings,
        email_pool,
        phone_pool,
    )
    code = get_email_otp(settings, email)
    auth_ep.verify_web_registration(
        api_client,
        VerifyWebOtpRequest(
            email=email,
            code=code,
        ),
    )
    account.last_otp = code
    return account


@pytest.fixture
def supplier_admin_client(
    settings: Settings,
    verified_supplier_admin: RegisteredAccount,
) -> Iterator[ApiClient]:
    """Independent client authenticated as a fresh supplier admin."""
    with ApiClient(settings) as client:
        tokens = auth_ep.web_login(
            client,
            WebLoginRequest(
                email=verified_supplier_admin.email,
                password=verified_supplier_admin.password,
            ),
        )
        verified_supplier_admin.tokens = tokens
        client.set_token(tokens.access_token)
        yield client


@pytest.fixture
def tk_admin_client(
    settings: Settings,
    verified_tk_admin: RegisteredAccount,
) -> Iterator[ApiClient]:
    """Independent client authenticated as a fresh TK admin."""
    with ApiClient(settings) as client:
        tokens = auth_ep.web_login(
            client,
            WebLoginRequest(
                email=verified_tk_admin.email,
                password=verified_tk_admin.password,
            ),
        )
        verified_tk_admin.tokens = tokens
        client.set_token(tokens.access_token)
        yield client


@pytest.fixture
def verified_supplier_dispatcher(
    supplier_admin_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
    email_pool: EmailPool,
    settings: Settings,
) -> RegisteredDispatcher:
    """Dispatcher invited by `verified_supplier_admin`, accepted, and logged in."""
    disp_email = email_pool.checkout()
    disp_password = settings.default_test_password
    emp_ep.invite_employee(
        supplier_admin_client,
        InviteEmployeeRequest(
            email=disp_email,
            full_name="E2E Dispatcher",
            role="SUPPLIER_DISPATCHER",
        ),
    )
    token = fetch_invitation_token_via_imap(settings, disp_email)
    with ApiClient(settings) as anon:
        auth_ep.accept_invitation(
            anon,
            AcceptInvitationRequest(token=token, password=disp_password),
        )
        tokens = auth_ep.web_login(
            anon,
            WebLoginRequest(email=disp_email, password=disp_password),
        )
    return RegisteredDispatcher(
        email=disp_email,
        phone="",
        password=disp_password,
        company_name=verified_supplier_admin.company_name,
        tin=verified_supplier_admin.tin,
        full_name="E2E Dispatcher",
        tokens=tokens,
        inviter_admin=verified_supplier_admin,
    )


@pytest.fixture
def supplier_dispatcher_client(
    settings: Settings,
    verified_supplier_dispatcher: RegisteredDispatcher,
) -> Iterator[ApiClient]:
    assert verified_supplier_dispatcher.tokens is not None
    with ApiClient(settings, token=verified_supplier_dispatcher.tokens.access_token) as client:
        yield client


@pytest.fixture
def verified_supplier_manager(
    supplier_admin_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
    email_pool: EmailPool,
    settings: Settings,
) -> RegisteredDispatcher:
    """Manager invited by `verified_supplier_admin`, accepted, and logged in."""
    manager_email = email_pool.checkout()
    manager_password = settings.default_test_password
    emp_ep.invite_employee(
        supplier_admin_client,
        InviteEmployeeRequest(
            email=manager_email,
            full_name="E2E Manager",
            role="SUPPLIER_MANAGER",
        ),
    )
    token = fetch_invitation_token_via_imap(settings, manager_email)
    with ApiClient(settings) as anon:
        auth_ep.accept_invitation(
            anon,
            AcceptInvitationRequest(token=token, password=manager_password),
        )
        tokens = auth_ep.web_login(
            anon,
            WebLoginRequest(email=manager_email, password=manager_password),
        )
    return RegisteredDispatcher(
        email=manager_email,
        phone="",
        password=manager_password,
        company_name=verified_supplier_admin.company_name,
        tin=verified_supplier_admin.tin,
        full_name="E2E Manager",
        tokens=tokens,
        inviter_admin=verified_supplier_admin,
    )


@pytest.fixture
def supplier_manager_client(
    settings: Settings,
    verified_supplier_manager: RegisteredDispatcher,
) -> Iterator[ApiClient]:
    assert verified_supplier_manager.tokens is not None
    with ApiClient(settings, token=verified_supplier_manager.tokens.access_token) as client:
        yield client


# ---------- second-tenant fixtures (for BOLA / cross-tenant) ---------------


@pytest.fixture
def second_supplier_admin(
    settings: Settings,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> Iterator[RegisteredAccount]:
    """A second, independent supplier-admin company.

    Drives BOLA tests: account A must NOT see/modify resources owned by
    account B. Uses its own ApiClient (anonymous) for setup, then leaks
    pool slots back when the test ends.
    """
    with email_pool.lease() as email, phone_pool.lease() as phone:
        with ApiClient(settings) as setup_client:
            body = builders.supplier_registration(
                email=email,
                phone=phone,
                password=settings.default_test_password,
            )
            try:
                auth_ep.register_supplier(setup_client, body)
            except ApiError as exc:
                if exc.status_code != 409:
                    raise
                account, email = _register_supplier_with_retry(
                    setup_client,
                    settings,
                    email_pool,
                    phone_pool,
                )
                body = builders.supplier_registration(
                    email=account.email,
                    phone=account.phone,
                    password=account.password,
                    company_name=account.company_name,
                    tin=account.tin,
                    full_name=account.full_name,
                )
            auth_ep.verify_web_registration(
                setup_client,
                VerifyWebOtpRequest(email=email, code=get_email_otp(settings, email)),
            )
        yield RegisteredAccount(
            email=body.email,
            phone=body.phone,
            password=body.password,
            company_name=body.company_name,
            tin=body.tin,
            full_name=body.full_name,
        )


@pytest.fixture
def employee_in_company_a(
    supplier_admin_client: ApiClient,
    email_pool: EmailPool,
) -> EmployeeResponse:
    """Invite one fresh employee in `supplier_admin_client`'s company.

    Shared across security/, contract/, employees/ tests — cheaper than
    re-leasing pool slots per file.
    """
    with email_pool.lease() as employee_email:
        return emp_ep.invite_employee(
            supplier_admin_client,
            builders.employee_invite(email=employee_email, role="SUPPLIER_MANAGER"),
        )


@pytest.fixture
def invited_employee(employee_in_company_a: EmployeeResponse) -> EmployeeResponse:
    """Legacy alias used outside tests/employees/ as well."""
    return employee_in_company_a


@pytest.fixture
def second_supplier_admin_client(
    settings: Settings,
    second_supplier_admin: RegisteredAccount,
) -> Iterator[ApiClient]:
    """Authenticated client for the second supplier admin.

    Distinct from `supplier_admin_client` — this fixture has its OWN
    ApiClient instance, so a test can hold both companies' Bearer tokens
    simultaneously.
    """
    with ApiClient(settings) as client:
        tokens = auth_ep.web_login(
            client,
            WebLoginRequest(
                email=second_supplier_admin.email,
                password=second_supplier_admin.password,
            ),
        )
        second_supplier_admin.tokens = tokens
        client.set_token(tokens.access_token)
        yield client


# ---------- domain fixtures (warehouses / orders) -------------------------
#
# These build on top of the authenticated supplier-admin client so that
# tests for tender-flow endpoints can compose without each one re-creating
# a company.

from uuid import UUID  # noqa: E402

from api.endpoints import warehouses as wh_ep  # noqa: E402
from api.schemas import WarehouseResponse  # noqa: E402


@pytest.fixture
def supplier_warehouse(
    supplier_admin_client: ApiClient,
) -> WarehouseResponse:
    """Active warehouse owned by `supplier_admin_client`'s company."""
    return wh_ep.create_warehouse(
        supplier_admin_client,
        builders.warehouse(name="[E2E] WH-pickup"),
    )


@pytest.fixture
def supplier_warehouse_id(supplier_warehouse: WarehouseResponse) -> UUID:
    """Convenience for tests that only need the ID."""
    return supplier_warehouse.id


@pytest.fixture
def supplier_destination_warehouse(
    supplier_admin_client: ApiClient,
) -> WarehouseResponse:
    """Active destination warehouse owned by `supplier_admin_client`'s company."""
    return wh_ep.create_warehouse(
        supplier_admin_client,
        builders.warehouse(
            name="[E2E] WH-destination",
            city="Almaty",
            address="Abay 45",
        ),
    )


@pytest.fixture
def supplier_destination_warehouse_id(
    supplier_destination_warehouse: WarehouseResponse,
) -> UUID:
    """Convenience for tests that only need the destination warehouse ID."""
    return supplier_destination_warehouse.id
