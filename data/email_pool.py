"""Atomic email-address allocation across pytest-xdist workers.

Two layouts:

- Default (`e2e+{slot}@<domain>`) — used when emails just need to be
  syntactically valid + unique (e.g. mailhog / fixed-OTP modes).
- IMAP-Gmail mode (`<gmail-user>+e2e-{uuid}@gmail.com`) — when
  EMAIL_OTP_MODE=imap_gmail; plus-aliases route everything into the one
  configured Gmail inbox where the IMAP fetcher can read OTPs.

In IMAP-Gmail mode emails MUST be globally unique forever (across all
test runs ever) — backend keeps registered accounts and rejects re-use
with 409. So that mode bypasses the slot pool and uses a UUID suffix.
"""

from __future__ import annotations

import json
import uuid
from types import TracebackType

from filelock import FileLock

from config.settings import OtpMode, Settings


class EmailPoolExhausted(RuntimeError):
    """Raised when every email slot is currently checked out."""


class EmailPool:
    """Lockfile-backed FIFO of available email slots."""

    def __init__(self, settings: Settings) -> None:
        self._size = settings.email_pool_size
        self._domain = settings.email_pool_domain
        # When IMAP-Gmail mode is on, route via plus-aliases of the
        # configured Gmail account so the fetcher can read all OTPs from
        # a single inbox.
        self._gmail_user: str | None = None
        if settings.email_otp_mode is OtpMode.IMAP_GMAIL and settings.gmail_imap_user:
            self._gmail_user = settings.gmail_imap_user
        pool_dir = settings.project_root / ".pool"
        pool_dir.mkdir(exist_ok=True)
        self._state_path = pool_dir / "emails.json"
        self._lock = FileLock(str(pool_dir / "emails.lock"))

    def _load(self) -> set[int]:
        if not self._state_path.exists():
            return set()
        return set(json.loads(self._state_path.read_text()))

    def _save(self, in_use: set[int]) -> None:
        self._state_path.write_text(json.dumps(sorted(in_use)))

    def _format(self, slot: int) -> str:
        if self._gmail_user is not None:
            local, _, host = self._gmail_user.partition("@")
            return f"{local}+e2e-{slot:03d}@{host}"
        return f"e2e+{slot:03d}@{self._domain}"

    def _slot_from(self, email: str) -> int:
        """Reverse of `_format` — extract the slot number to release."""
        local = email.split("@", 1)[0]
        # Both forms have «+e2e-NNN» or «e2e+NNN» — slot is trailing digits.
        digits = "".join(ch for ch in local.split("+")[-1] if ch.isdigit())
        return int(digits)

    def checkout(self) -> str:
        # IMAP-Gmail mode: backend remembers every registered email
        # forever, so we can NEVER reuse a slot. Use a UUID hex suffix
        # instead — collision-free, no state, no lock.
        if self._gmail_user is not None:
            local, _, host = self._gmail_user.partition("@")
            return f"{local}+e2e-{uuid.uuid4().hex[:10]}@{host}"

        with self._lock:
            in_use = self._load()
            for slot in range(1, self._size + 1):
                if slot not in in_use:
                    in_use.add(slot)
                    self._save(in_use)
                    return self._format(slot)
            raise EmailPoolExhausted(
                f"All {self._size} email slots are in use; "
                "increase EMAIL_POOL_SIZE or release leases.",
            )

    def release(self, email: str) -> None:
        # In IMAP-Gmail mode there's nothing to release — emails are
        # one-shot UUIDs.
        if self._gmail_user is not None:
            return
        slot = self._slot_from(email)
        with self._lock:
            in_use = self._load()
            in_use.discard(slot)
            self._save(in_use)

    def lease(self) -> _EmailLease:
        return _EmailLease(self)


class _EmailLease:
    def __init__(self, pool: EmailPool) -> None:
        self._pool = pool
        self._email: str | None = None

    def __enter__(self) -> str:
        self._email = self._pool.checkout()
        return self._email

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._email is not None:
            self._pool.release(self._email)
            self._email = None
