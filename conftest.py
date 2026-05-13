"""Project-root conftest — shared fixtures used by both `tests/` and `web_ui/`.

Anything that is not strictly API-only or strictly UI-only lives here:
- `settings` (parsed once per process)
- shared pools (phone, email) that coordinate via filelock and are safe
  to share across both API and UI test runs in the same xdist worker.
- Production safety guard (collection hook): when `MANZIL_ENV=prod` we
  refuse to run any test marked `requires_real_account`, `maintenance`,
  or any UI-write operation that would mutate live data.

Subdirectory `conftest.py` files extend this with their own role/page/
client fixtures.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from api.client import ApiClient
from config.settings import ManzilEnv, Settings, get_settings
from data.email_pool import EmailPool
from data.phone_pool import PhonePool

# ---------- prod safety guard --------------------------------------------
#
# Markers that MUST NOT run against production. A run with `MANZIL_ENV=prod`
# is intended for pre-launch sanity (e.g. health probes, login page
# renders) — never for anything that touches state or uses shared fixture
# accounts.
_PROD_FORBIDDEN_MARKERS = frozenset({
    "requires_real_account",
    "requires_email_otp",
    "requires_telegram_otp",
    "maintenance",
})

# OTP-dependent tests are auto-skipped on every environment unless the
# operator explicitly enables them (set `MANZIL_OTP_CAPTURE=1`). Reason:
# dev backend stopped accepting the fixed dev-code `123456`, and we have
# no other capture mechanism wired in (open Q1 in bug.txt). When email/
# telegram OTP capture lands, set the env var to re-enable.
_OTP_MARKERS = frozenset({"requires_email_otp", "requires_telegram_otp"})


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    settings = get_settings()
    is_prod = settings.manzil_env == ManzilEnv.PROD
    has_otp_capture = settings.manzil_otp_capture

    skip_prod = pytest.mark.skip(
        reason=(
            "Refused on MANZIL_ENV=prod: this test mutates state or uses "
            "shared real accounts. Re-run against dev or staging."
        ),
    )
    skip_otp = pytest.mark.skip(
        reason=(
            "OTP capture not configured: dev backend stopped accepting the "
            "fixed dev-code; tests requiring email/telegram OTP are "
            "auto-skipped. Set MANZIL_OTP_CAPTURE=1 to enable when a real "
            "OTP source (mailhog / endpoint / fixed-code) is wired in."
        ),
    )

    for item in items:
        item_marker_names = {m.name for m in item.iter_markers()}
        if is_prod and item_marker_names & _PROD_FORBIDDEN_MARKERS:
            item.add_marker(skip_prod)
            continue  # already skipped, no need for further markers
        if not has_otp_capture and item_marker_names & _OTP_MARKERS:
            item.add_marker(skip_otp)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def phone_pool(settings: Settings) -> PhonePool:
    return PhonePool(settings)


@pytest.fixture(scope="session")
def email_pool(settings: Settings) -> EmailPool:
    return EmailPool(settings)


@pytest.fixture
def phone_from_pool(phone_pool: PhonePool) -> Iterator[str]:
    with phone_pool.lease() as phone:
        yield phone


@pytest.fixture
def email_from_pool(email_pool: EmailPool) -> Iterator[str]:
    with email_pool.lease() as email:
        yield email


@pytest.fixture
def api_client(settings: Settings) -> Iterator[ApiClient]:
    """Anonymous (no Bearer token) httpx-based API client."""
    with ApiClient(settings) as client:
        yield client
