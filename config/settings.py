"""Type-safe settings from .env / environment.

Single source of truth for API URL, OTP capture modes, timeouts, pools.
Tests must NEVER hardcode these values — read via the `settings` fixture.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OtpMode(StrEnum):
    """How tests obtain OTP codes (email or telegram).

    `fixed`      — accept a fixed code (no longer works on dev as of 2026-05-04)
    `mailhog`    — fetch from a mock SMTP service's HTTP API
    `endpoint`   — backend dev-endpoint exposing the last OTP per recipient
    `imap_gmail` — IMAP-fetch from a real Gmail inbox using app-password
    """

    FIXED = "fixed"
    MAILHOG = "mailhog"
    ENDPOINT = "endpoint"
    IMAP_GMAIL = "imap_gmail"


class ManzilEnv(StrEnum):
    """Which environment the suite is targeting.

    `dev`     — sandbox; safe for any test, real test accounts seeded.
    `staging` — pre-prod; same shape as dev but data may be sensitive.
                Run with care; mutating tests allowed but should be
                coordinated with the team.
    `prod`    — LIVE production. Hard guard in conftest refuses any test
                marked `requires_real_account` or `maintenance` here —
                only read-only anonymous probes (e.g. login page renders)
                are permitted.
    """

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


# Per-environment URL defaults. If the user sets API_BASE_URL or
# WEB_BASE_URL explicitly in .env they win — otherwise these resolve.
_ENV_URLS: dict[ManzilEnv, tuple[str, str]] = {
    ManzilEnv.DEV:     ("https://dev-manzil.greatmall.uz",     "https://dev-manzil.greatmall.uz"),
    ManzilEnv.STAGING: ("https://staging-manzil.greatmall.uz", "https://staging-manzil.greatmall.uz"),
    ManzilEnv.PROD:    ("https://manzil.greatmall.uz",         "https://manzil.greatmall.uz"),
}


class Settings(BaseSettings):
    """Top-level configuration loaded from .env or process env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Default to dev — switching is opt-in via env var. PROD enables
    # destructive-test guards in conftest.
    manzil_env: ManzilEnv = ManzilEnv.DEV

    # If the user sets these explicitly they win; otherwise we resolve
    # from `manzil_env` in `_resolve_urls` below.
    api_base_url: AnyHttpUrl = Field(default=AnyHttpUrl("https://dev-manzil.greatmall.uz"))
    web_base_url: AnyHttpUrl = Field(default=AnyHttpUrl("https://dev-manzil.greatmall.uz"))

    @model_validator(mode="after")
    def _resolve_urls(self) -> Settings:
        """Override URLs from `manzil_env` only if the .env didn't pin a
        non-dev value explicitly. We compare against the dev defaults to
        detect "not set" — a tiny pragmatism so callers can either set
        URLs directly or just flip MANZIL_ENV.
        """
        api_str = str(self.api_base_url).rstrip("/")
        web_str = str(self.web_base_url).rstrip("/")
        dev_url = _ENV_URLS[ManzilEnv.DEV][0]
        if api_str == dev_url and web_str == dev_url and self.manzil_env != ManzilEnv.DEV:
            api, web = _ENV_URLS[self.manzil_env]
            object.__setattr__(self, "api_base_url", AnyHttpUrl(api))
            object.__setattr__(self, "web_base_url", AnyHttpUrl(web))
        return self

    @property
    def is_prod(self) -> bool:
        return self.manzil_env == ManzilEnv.PROD

    # Pre-verified shared accounts for post-OTP UI flows. Real Keycloak users —
    # do NOT delete or change roles. Tests must clean up created data
    # (orders, warehouses, vehicles, offers) but never the accounts themselves.
    # All Supplier accounts are employees of the same company (TeamQa).
    supplier_admin_real_email: str = "nbegimbaev2006@gmail.com"
    supplier_dispatcher_real_email: str = "nbegimbaev2020@gmail.com"
    supplier_manager_real_email: str = "nbegimbaev56@gmail.com"
    tk_real_email: str = "202390415@ajou.uz"
    real_account_password: str = "Nawrizbek_20"

    # Backwards-compatibility alias (used by smoke and post-OTP fixtures
    # that don't care which sub-role they get).
    @property
    def supplier_real_email(self) -> str:
        return self.supplier_admin_real_email

    # Headed for local debug (set HEADED=1), headless on CI.
    ui_headed: bool = False
    ui_slow_mo_ms: int = 0
    ui_default_timeout_ms: int = 10_000
    # Keep traces/videos on failure to debug flakes; cheap on disk.
    ui_trace_on_failure: bool = True

    email_otp_mode: OtpMode = OtpMode.FIXED
    email_otp: str = "123456"
    email_otp_endpoint: str = ""

    # Gmail IMAP — used when email_otp_mode=imap_gmail. Tests register
    # accounts as plus-aliases of `gmail_imap_user` so all OTP letters
    # land in this single inbox while each test sees a unique recipient.
    gmail_imap_user: str = ""
    gmail_imap_app_password: str = ""
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993
    # Wait up to this many seconds for an OTP letter to arrive after
    # the registration request. Single registrations take ~5-10s, but
    # under load Manzil's mail-out pipeline + Gmail spam-filter delay
    # delivery to 60-90s. 120s is the safe upper bound for batch runs.
    gmail_imap_timeout_s: int = 180
    gmail_imap_poll_interval_s: float = 3.0

    # Master switch: when False (default), OTP-dependent tests
    # auto-skip via the pytest_collection_modifyitems hook in
    # conftest.py. Flip to True to actually run them — assumes one of
    # the OTP capture mechanisms is configured (e.g. imap_gmail).
    manzil_otp_capture: bool = False

    telegram_otp_mode: OtpMode = OtpMode.FIXED
    telegram_otp: str = "123456"
    telegram_otp_endpoint: str = ""

    phone_pool_start: int = 998900000001
    phone_pool_end: int = 998900000050
    email_pool_domain: str = "manziltest.uz"
    email_pool_size: int = 50

    tin_checksum: bool = False
    default_test_password: str = "P@ssw0rd!"

    http_timeout_s: float = 15.0
    http_verify_ssl: bool = True

    @field_validator("email_otp", "telegram_otp")
    @classmethod
    def _otp_is_six_digits(cls, value: str) -> str:
        if not (value.isdigit() and len(value) == 6):
            raise ValueError("OTP must be a 6-digit numeric string")
        return value

    @field_validator("phone_pool_end")
    @classmethod
    def _phone_pool_positive(cls, end: int) -> int:
        if end <= 0:
            raise ValueError("PHONE_POOL_END must be positive")
        return end

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def api_base_url_str(self) -> str:
        """Base URL as a plain string with no trailing slash — convenient for httpx."""
        return str(self.api_base_url).rstrip("/")

    @property
    def web_base_url_str(self) -> str:
        """Web base URL as a plain string with no trailing slash."""
        return str(self.web_base_url).rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached Settings — `.env` parsed once per process."""
    return Settings()
