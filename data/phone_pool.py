"""Atomic phone-number allocation across pytest-xdist workers.

Uses a single lockfile + index file in `.pool/` to give every concurrent test
a unique phone from the configured range. Phones are released on session end
via the `phone_from_pool` fixture, so the same range can be reused.

Phone format follows BRD §3.1 — `+998xxxxxxxxx`.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Self

from filelock import FileLock

from config.settings import Settings


class PhonePoolExhausted(RuntimeError):
    """Raised when every phone in the configured range is currently checked out."""


class PhonePool:
    """Lockfile-backed FIFO of available phone numbers.

    Exposes context-manager `acquire` for one-shot leases. Storage lives in
    `<project_root>/.pool/phones.json`; the file is created on first use.
    """

    def __init__(self, settings: Settings) -> None:
        self._start = settings.phone_pool_start
        self._end = settings.phone_pool_end
        pool_dir = settings.project_root / ".pool"
        pool_dir.mkdir(exist_ok=True)
        self._state_path = pool_dir / "phones.json"
        self._lock = FileLock(str(pool_dir / "phones.lock"))

    def _load(self) -> set[int]:
        if not self._state_path.exists():
            return set()
        return set(json.loads(self._state_path.read_text()))

    def _save(self, in_use: set[int]) -> None:
        self._state_path.write_text(json.dumps(sorted(in_use)))

    def checkout(self) -> str:
        """Reserve a free phone and return it formatted as `+998xxxxxxxxx`."""
        with self._lock:
            in_use = self._load()
            for candidate in range(self._start, self._end + 1):
                if candidate not in in_use:
                    in_use.add(candidate)
                    self._save(in_use)
                    return f"+{candidate}"
            raise PhonePoolExhausted(
                f"All phones {self._start}..{self._end} are in use; "
                "increase PHONE_POOL_END or release leases.",
            )

    def release(self, phone: str) -> None:
        """Mark a phone as DONE — but do NOT return it to the pool.

        Backend remembers every registered phone forever; if a slot is
        re-used the next registration 409s. So we keep the slot in
        `in_use` permanently. With a 99k-slot range that's enough for
        years of test runs; bump `PHONE_POOL_START` if the high-water
        mark gets close to `PHONE_POOL_END`.
        """
        # No-op: never release, never reuse.

    def lease(self) -> _PhoneLease:
        """Context-manager that auto-releases on exit."""
        return _PhoneLease(self)


class _PhoneLease:
    def __init__(self, pool: PhonePool) -> None:
        self._pool = pool
        self._phone: str | None = None

    def __enter__(self) -> str:
        self._phone = self._pool.checkout()
        return self._phone

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._phone is not None:
            self._pool.release(self._phone)
            self._phone = None

    def __aenter__(self) -> Self:
        raise NotImplementedError("Use sync `with`, not `async with`.")
