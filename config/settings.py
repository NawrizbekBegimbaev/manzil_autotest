"""Runtime configuration — everything comes from .env, nothing hardcoded.

URLs, credentials, timeouts and Telegram config are read from the project-root
.env via pydantic-settings. Tests and fixtures consume `get_settings()`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Web roles as the frontend ACL sees them. The post-login landing route differs
# per role; sanity asserts the context landed where it should.
ROLE_LANDING: dict[str, str] = {
    "super_admin": "/super-admin/partners/shipper-companies",
    "admin": "/dashboard",
    "manager": "/shipper/storeroom",
    "carrier": "/transport/orders",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── Target ────────────────────────────────────────────────────────────
    base_url: str = "https://staging-manzil.greatmall.uz"

    # ─── Credentials (phone + password, no OTP for any role) ───────────────
    super_admin_phone: str = ""
    super_admin_password: str = Field(default="", repr=False)
    admin_phone: str = ""
    admin_password: str = Field(default="", repr=False)
    manager_phone: str = ""
    manager_password: str = Field(default="", repr=False)
    carrier_phone: str = ""
    carrier_password: str = Field(default="", repr=False)
    # Password assigned to accounts the workflow creates on the fly.
    new_account_password: str = Field(default="", repr=False)

    # ─── Browser context ───────────────────────────────────────────────────
    locale: str = "ru-RU"
    timezone: str = "Asia/Tashkent"
    default_timeout_ms: int = 15000
    nav_timeout_ms: int = 30000

    # ─── Telegram report delivery (optional; empty = skip send) ────────────
    tg_bot_token: str = Field(default="", repr=False)
    tg_chat_id: str = ""
    tg_report_env: str = "STAGING"

    # ─── DEV target — regression suite only (tests/regression); staging UAT
    #     is never pointed here. Fresh tenant provisioned per run via API. ────
    dev_url: str = "https://dev-manzil.greatmall.uz"
    dev_super_admin_phone: str = ""
    dev_super_admin_password: str = Field(default="", repr=False)
    # Password assigned to the throwaway accounts the regression suite creates
    # on DEV (must satisfy the policy). Never a real/existing credential.
    dev_account_password: str = Field(default="", repr=False)
    # Dedicated throwaway phones for ratelimit (429) cases — never real accounts.
    ratelimit_phone_1: str = ""
    ratelimit_phone_2: str = ""
    # 1С inbound webhook shared secret (X-Webhook-Token) for DEV. Empty → 1С happy-path
    # tests skip (endpoint fail-closed). Never commit the value — .env only, repo public.
    onec_webhook_secret: str = Field(default="", repr=False)
    # Pagination response shape of the regression target. DEV (MNZL-245) nests page
    # metadata under `page`; staging still returns it flat (top-level). Strict, not
    # auto-detected — a mismatch is a real signal, not something to tolerate.
    page_shape: str = "nested"  # "nested" (dev) | "flat" (staging)

    def creds(self, role: str) -> tuple[str, str]:
        """Return (phone, password) for a web role key. Empty when not set."""
        phone = getattr(self, f"{role}_phone", "")
        password = getattr(self, f"{role}_password", "")
        return phone, password

    def has_creds(self, role: str) -> bool:
        phone, password = self.creds(role)
        return bool(phone and password)

    def landing(self, role: str) -> str:
        return ROLE_LANDING[role]


@lru_cache
def get_settings() -> Settings:
    return Settings()
