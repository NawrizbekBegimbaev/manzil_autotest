"""OTP capture for tests — pluggable backend per `OtpMode`.

Reads from settings:
- `email_otp_mode` + `email_otp` / `email_otp_endpoint` for web flows
- `telegram_otp_mode` + `telegram_otp` / `telegram_otp_endpoint` for mobile flows

This module is the single place tests look up an OTP. When backend confirms a
real capture mechanism (mailhog/test-bot/endpoint), only this file changes.
"""

from __future__ import annotations

from config.settings import OtpMode, Settings


class OtpUnavailable(RuntimeError):
    """Raised when the configured OtpMode can't deliver a code."""


def get_email_otp(settings: Settings, email: str) -> str:
    """Return the OTP delivered to `email` per the configured mode."""
    if settings.email_otp_mode is OtpMode.IMAP_GMAIL:
        from utils.gmail_otp import fetch_email_otp_via_imap
        return fetch_email_otp_via_imap(settings, email)
    return _resolve(
        mode=settings.email_otp_mode,
        fixed=settings.email_otp,
        endpoint=settings.email_otp_endpoint,
        recipient=email,
        kind="email",
    )


def get_telegram_otp(settings: Settings, phone: str) -> str:
    """Return the OTP delivered via Telegram for `phone` per the configured mode."""
    return _resolve(
        mode=settings.telegram_otp_mode,
        fixed=settings.telegram_otp,
        endpoint=settings.telegram_otp_endpoint,
        recipient=phone,
        kind="telegram",
    )


def _resolve(*, mode: OtpMode, fixed: str, endpoint: str, recipient: str, kind: str) -> str:
    if mode is OtpMode.FIXED:
        return fixed
    if mode is OtpMode.ENDPOINT:
        # TODO(open-question-2,3): wire to real endpoint once backend confirms shape.
        # Likely GET <endpoint>/{recipient} → {"code": "123456"}; defer until known.
        raise OtpUnavailable(
            f"OtpMode.ENDPOINT for {kind!r} not implemented — "
            f"endpoint URL was {endpoint!r}, recipient {recipient!r}",
        )
    if mode is OtpMode.MAILHOG:
        # TODO(open-question-2): mailhog API integration.
        raise OtpUnavailable(
            f"OtpMode.MAILHOG for {kind!r} not implemented — recipient {recipient!r}",
        )
    raise OtpUnavailable(f"Unknown OtpMode: {mode!r}")
