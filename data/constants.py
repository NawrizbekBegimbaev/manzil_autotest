"""Shared test-data constants — prefixes, currencies, languages.

Anything that's a literal "magic value" in the test suite belongs here, not
inline. If a value depends on the environment, it goes into `config/settings.py`
instead.
"""

from __future__ import annotations

from typing import Final

# Used in company names so a maintenance task can find and clean them up.
E2E_PREFIX: Final[str] = "[E2E]"

# BRD §6 currencies for cargo requests
ALLOWED_CURRENCIES: Final[tuple[str, ...]] = ("USD", "CNY")

# BRD §3.5 — five UI languages. Tests don't use these yet but the list is
# centralised so an i18n suite added later can iterate over a single source.
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("ru", "uz", "ky", "zh", "ug")
DEFAULT_LANGUAGE: Final[str] = "ru"

# Employee roles/statuses per current backend contract.
EMPLOYEE_ROLES: Final[tuple[str, ...]] = (
    "SUPPLIER_ADMIN",
    "SUPPLIER_DISPATCHER",
    "SUPPLIER_MANAGER",
)
EMPLOYEE_STATUSES: Final[tuple[str, ...]] = ("ACTIVE", "BLOCKED", "PENDING")
