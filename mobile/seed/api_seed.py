"""API setup helpers for mobile tests."""

from __future__ import annotations

from api.client import ApiClient
from api.endpoints import auth as auth_ep
from api.endpoints import employees as emp_ep
from api.endpoints import orders as ord_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import (
    AcceptInvitationRequest,
    InviteEmployeeRequest,
    OrderResponse,
    VerifyWebOtpRequest,
    WebLoginRequest,
)
from config.settings import Settings
from data import builders
from data.email_pool import EmailPool
from data.phone_pool import PhonePool
from utils.gmail_otp import fetch_email_otp_via_imap, fetch_invitation_token_via_imap


def make_anonymous_client(settings: Settings) -> ApiClient:
    """Create a fresh API client without an auth token."""
    return ApiClient(settings)


def seed_active_order_for_driver_feed(
    settings: Settings,
    *,
    body_type: str = "TENT",
    cargo_title_prefix: str = "[E2E-W2]",
) -> OrderResponse:
    """Create an active supplier order expected to appear in the driver feed.

    The order intentionally remains in dev backend. W2 offer tests may create
    real offers against it, so cleanup is handled by periodic maintenance.
    """
    phone_pool = PhonePool(settings)
    email_pool = EmailPool(settings)
    password = settings.default_test_password
    anonymous = make_anonymous_client(settings)

    admin_email = email_pool.checkout()
    admin_phone = phone_pool.checkout()
    auth_ep.register_supplier(
        anonymous,
        builders.supplier_registration(
            email=admin_email,
            phone=admin_phone,
            password=password,
        ),
    )
    admin_otp = fetch_email_otp_via_imap(settings, admin_email)
    auth_ep.verify_web_registration(
        anonymous,
        VerifyWebOtpRequest(email=admin_email, code=admin_otp),
    )
    admin_tokens = auth_ep.web_login(
        anonymous,
        WebLoginRequest(email=admin_email, password=password),
    )
    admin = ApiClient(settings, token=admin_tokens.access_token)

    dispatcher_email = email_pool.checkout()
    emp_ep.invite_employee(
        admin,
        InviteEmployeeRequest(
            email=dispatcher_email,
            full_name="W2 Dispatcher",
            role="SUPPLIER_DISPATCHER",
        ),
    )
    invitation_token = fetch_invitation_token_via_imap(settings, dispatcher_email)
    auth_ep.accept_invitation(
        anonymous,
        AcceptInvitationRequest(token=invitation_token, password=password),
    )
    dispatcher_tokens = auth_ep.web_login(
        anonymous,
        WebLoginRequest(email=dispatcher_email, password=password),
    )
    dispatcher = ApiClient(settings, token=dispatcher_tokens.access_token)

    pickup = wh_ep.create_warehouse(
        admin,
        builders.warehouse(name=f"{cargo_title_prefix} Pickup"),
    )
    destination = wh_ep.create_warehouse(
        admin,
        builders.warehouse(name=f"{cargo_title_prefix} Dest"),
    )
    return ord_ep.create_order(
        dispatcher,
        builders.order_request(
            warehouse_id=pickup.id,
            destination_warehouse_id=destination.id,
            cargo_type=f"{cargo_title_prefix} W2 Probe",
            body_type=body_type,
            publish=True,
        ),
    )
