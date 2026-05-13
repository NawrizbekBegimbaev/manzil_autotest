"""Fetch the OTP code from a real Gmail inbox via IMAP.

Used when `EMAIL_OTP_MODE=imap_gmail`. Tests register accounts as
plus-aliases of the configured Gmail address (e.g.
`you+e2e-001@gmail.com`); Manzil sends the OTP letter there; this
module IMAP-polls Gmail and parses the 6-digit code.

Why we search «All Mail» and not «INBOX»: Manzil is a new SMTP sender,
so Gmail's spam filter routes its first letters into Spam. «All Mail»
(special-use `\\All`) is a virtual folder that contains everything except
Trash — including Spam. We always search there.

Properties (intentional):
- `readonly=True` — cannot mark as seen, cannot delete.
- Searches by recipient and recency only — never reads unrelated email.
- Polls with back-off, gives up after `gmail_imap_timeout_s`.
- Robust to multipart MIME (text/plain + text/html) — checks both.

Generate the App Password at https://myaccount.google.com/apppasswords
(requires 2FA on the Google account). Never use the real Gmail
password — Google blocks plain-password IMAP since 2022.
"""

from __future__ import annotations

import atexit
import contextlib
import email
import email.utils
import imaplib
import re
import ssl
import threading
import time
from collections.abc import Callable
from email.message import Message
from urllib.parse import parse_qs, urlparse

from config.settings import Settings

# Six-digit OTP, surrounded by word boundaries.
# Negative-lookbehind on `#` excludes hex-color values like `#111827`
# embedded in CSS (Manzil's email template uses these heavily).
_OTP_REGEX = re.compile(r"(?<![#\w])(\d{6})(?!\d)")
# Tag-stripper: text-only view of an HTML body to defang CSS/markup.
_TAG_REGEX = re.compile(r"<[^>]+>")
_STYLE_REGEX = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_URL_REGEX = re.compile(r"https?://[^\s\"'<>]+")

_IMAP_LOCK = threading.Lock()
_IMAP_CONN: imaplib.IMAP4_SSL | None = None


class GmailOtpUnavailable(RuntimeError):
    """Raised when the Gmail IMAP fetcher can't find an OTP in time."""


def fetch_email_otp_via_imap(
    settings: Settings,
    recipient: str,
    *,
    since_epoch: float | None = None,
    exclude_codes: set[str] | None = None,
) -> str:
    """Block until an OTP letter for `recipient` appears in the inbox.

    Polls every `gmail_imap_poll_interval_s` up to `gmail_imap_timeout_s`.
    Only accepts letters delivered AFTER `since_epoch` (the moment this
    function was called) — ignores stale emails from earlier test runs
    that re-used the same email-pool slot.

    Raises `GmailOtpUnavailable` on timeout / config errors.
    """
    if not settings.gmail_imap_user or not settings.gmail_imap_app_password:
        raise GmailOtpUnavailable(
            "Gmail IMAP not configured: set GMAIL_IMAP_USER and "
            "GMAIL_IMAP_APP_PASSWORD in .env (use a Google App Password, "
            "not your real Gmail password).",
        )

    since_epoch = time.time() - 30 if since_epoch is None else since_epoch
    deadline = time.monotonic() + settings.gmail_imap_timeout_s
    last_error: Exception | None = None
    excluded = exclude_codes or set()

    def extract_non_excluded(message: Message) -> str | None:
        code = _extract_otp(message)
        if code in excluded:
            return None
        return code

    while time.monotonic() < deadline:
        try:
            code = _try_fetch_once(
                settings,
                recipient,
                since_epoch=since_epoch,
                extractor=extract_non_excluded,
            )
            if code is not None:
                return code
        except (imaplib.IMAP4.error, ssl.SSLError, OSError) as err:
            last_error = err  # transient — try again
        time.sleep(settings.gmail_imap_poll_interval_s)

    msg = (
        f"Gmail IMAP timeout after {settings.gmail_imap_timeout_s}s "
        f"waiting for OTP letter to {recipient!r}."
    )
    if last_error is not None:
        msg += f" Last error: {last_error!r}"
    raise GmailOtpUnavailable(msg)


def fetch_invitation_token_via_imap(settings: Settings, recipient: str) -> str:
    """Block until an invitation email for `recipient` appears and return its token."""
    if not settings.gmail_imap_user or not settings.gmail_imap_app_password:
        raise GmailOtpUnavailable(
            "Gmail IMAP not configured: set GMAIL_IMAP_USER and "
            "GMAIL_IMAP_APP_PASSWORD in .env.",
        )

    since_epoch = time.time() - 30
    deadline = time.monotonic() + settings.gmail_imap_timeout_s
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            token = _try_fetch_once(
                settings,
                recipient,
                since_epoch=since_epoch,
                extractor=_extract_invitation_token,
            )
            if token is not None:
                return token
        except (imaplib.IMAP4.error, ssl.SSLError, OSError) as err:
            last_error = err
            _reset_imap()
        time.sleep(settings.gmail_imap_poll_interval_s)

    msg = (
        f"Gmail IMAP timeout after {settings.gmail_imap_timeout_s}s "
        f"waiting for invitation letter to {recipient!r}."
    )
    if last_error is not None:
        msg += f" Last error: {last_error!r}"
    raise GmailOtpUnavailable(msg)


def _try_fetch_once(
    settings: Settings,
    recipient: str,
    *,
    since_epoch: float,
    extractor: Callable[[Message], str | None],
) -> str | None:
    """One IMAP round-trip. Returns the OTP code if found, else None.

    Searches both «All Mail» (\\All) and «Spam» (\\Junk) — Manzil is a new
    SMTP sender so Gmail routes most letters into Spam. Gmail's «All Mail»
    is misleadingly named: it does NOT include Spam, only Inbox + archived.

    Only accepts letters dated AFTER `since_epoch` — pool slots are
    reused across runs so the same recipient may have stale emails with
    expired OTP codes.
    """
    with _IMAP_LOCK:
        imap = _get_imap(settings)
        folders = _gmail_search_folders(imap)
        for folder in folders:
            code = _search_in_folder(
                imap,
                folder,
                recipient,
                since_epoch=since_epoch,
                extractor=extractor,
            )
            if code is not None:
                return code
    return None


def _get_imap(settings: Settings) -> imaplib.IMAP4_SSL:
    global _IMAP_CONN
    if _IMAP_CONN is not None and _is_alive(_IMAP_CONN):
        return _IMAP_CONN
    _reset_imap()
    _IMAP_CONN = imaplib.IMAP4_SSL(
        host=settings.gmail_imap_host,
        port=settings.gmail_imap_port,
    )
    _IMAP_CONN.login(settings.gmail_imap_user, settings.gmail_imap_app_password)
    return _IMAP_CONN


def _is_alive(imap: imaplib.IMAP4_SSL) -> bool:
    try:
        status, _ = imap.noop()
    except (imaplib.IMAP4.error, OSError, ssl.SSLError):
        return False
    return status == "OK"


def _reset_imap() -> None:
    global _IMAP_CONN
    if _IMAP_CONN is not None:
        with contextlib.suppress(imaplib.IMAP4.error, OSError, ssl.SSLError):
            _IMAP_CONN.logout()
    _IMAP_CONN = None


atexit.register(_reset_imap)


def _search_in_folder(
    imap: imaplib.IMAP4_SSL,
    folder: str,
    recipient: str,
    *,
    since_epoch: float,
    extractor: Callable[[Message], str | None],
) -> str | None:
    """SELECT a folder, search by recipient, parse first match dated
    after `since_epoch`."""
    status, _ = imap.select(f'"{folder}"', readonly=True)
    if status != "OK":
        return None

    today = time.strftime("%d-%b-%Y", time.gmtime())
    status, data = imap.search(None, f'(TO "{recipient}") (SINCE "{today}")')
    if status != "OK" or not data or not data[0]:
        return None

    # Newest ID is at the end. Walk backwards — most-recent letter wins.
    msg_ids = data[0].split()
    for msg_id in reversed(msg_ids):
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            continue
        raw = msg_data[0][1]
        assert isinstance(raw, bytes)
        message = email.message_from_bytes(raw)
        if not _is_fresh(message, since_epoch=since_epoch):
            continue
        code = extractor(message)
        if code is not None:
            return code
    return None


def _is_fresh(message: Message, *, since_epoch: float) -> bool:
    """True if the message's Date header is at or after `since_epoch`."""
    raw = message.get("Date")
    if not raw:
        return True  # no date — accept (rare)
    parsed = email.utils.parsedate_to_datetime(raw)
    if parsed is None:
        return True
    return parsed.timestamp() >= since_epoch


def _gmail_search_folders(imap: imaplib.IMAP4_SSL) -> list[str]:
    """Folders to search for an OTP letter, in priority order.

    Looks for Gmail's special-use flags: `\\All` (All Mail) and `\\Junk`
    (Spam). Folder names are locale-dependent — flags aren't.
    """
    status, listing = imap.list()
    if status != "OK" or not listing:
        return ["[Gmail]/All Mail", "[Gmail]/Spam"]  # safe fallbacks

    by_flag: dict[str, str] = {}
    for entry in listing:
        if isinstance(entry, bytes):
            decoded = entry.decode("utf-8", errors="replace")
        elif isinstance(entry, str):
            decoded = entry
        else:
            continue
        # Format: `(\Flag1 \Flag2) "/" "folder/name"`
        parts = decoded.rsplit('"', 2)
        if len(parts) < 2:
            continue
        name = parts[-2]
        for flag in ("\\All", "\\Junk"):
            if flag in decoded and flag not in by_flag:
                by_flag[flag] = name

    # Spam first — it's where most fresh-sender mail lands. Then All Mail.
    return [
        by_flag.get("\\Junk", "[Gmail]/Spam"),
        by_flag.get("\\All", "[Gmail]/All Mail"),
    ]


def _extract_otp(message: Message) -> str | None:
    """Search for a 6-digit code in the message body (text + html).

    Prefers `text/plain` parts; for `text/html` parts we strip <style>,
    <script>, and ALL tags, then run the regex. This avoids matching
    hex CSS colors like `#111827` that appear in styled email templates.
    """
    plain_bodies: list[str] = []
    html_bodies: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                plain_bodies.append(_decode_part(part))
            elif ct == "text/html":
                html_bodies.append(_decode_part(part))
    else:
        ct = message.get_content_type()
        body = _decode_part(message)
        (html_bodies if ct == "text/html" else plain_bodies).append(body)

    # Plain-text first (cleanest signal), then HTML stripped of tags.
    for body in plain_bodies:
        match = _OTP_REGEX.search(body)
        if match:
            return match.group(1)
    for raw_html in html_bodies:
        stripped = _STYLE_REGEX.sub(" ", raw_html)
        stripped = _TAG_REGEX.sub(" ", stripped)
        match = _OTP_REGEX.search(stripped)
        if match:
            return match.group(1)
    return None


def _extract_invitation_token(message: Message) -> str | None:
    """Extract invitation token from text/html links in an invite email."""
    for body in _message_bodies(message):
        stripped = _STYLE_REGEX.sub(" ", body)
        stripped = _TAG_REGEX.sub(" ", stripped)
        for candidate in (body, stripped):
            for match in _URL_REGEX.finditer(candidate):
                parsed = urlparse(match.group(0))
                params = parse_qs(parsed.query)
                for key in ("invite_token", "invitation_token", "token"):
                    values = params.get(key)
                    if values and values[0]:
                        return values[0]
        # Fallback for templates that render just `token=...` text.
        token_match = re.search(
            r"(?:invite_token|invitation_token|token)=([A-Za-z0-9._~+/=-]+)",
            body,
        )
        if token_match:
            return token_match.group(1)
    return None


def _message_bodies(message: Message) -> list[str]:
    bodies: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() in {"text/plain", "text/html"}:
                bodies.append(_decode_part(part))
    else:
        bodies.append(_decode_part(message))
    return bodies


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")
