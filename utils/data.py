"""Unique test-data generators for entities the workflow creates on staging.

Names carry the SANITY marker so created rows are recognisable and cleanable.
The admin `full_name` is kept to plain letters + spaces: brackets there break
Keycloak user provisioning server-side (a 500), so we avoid them. Phones are
unique per run (login username), hence randomised.
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass, field

SANITY_MARKER = "SANITY"
# UZ mobile operator codes (national, after +998).
_UZ_CODES = ["90", "91", "93", "94", "95", "97", "98", "99"]


def _stamp() -> str:
    return time.strftime("%m%d%H%M%S")


def _letters(n: int) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=n))


def unique_phone() -> str:
    code = random.choice(_UZ_CODES)
    rest = "".join(random.choices(string.digits, k=7))
    return f"+998{code}{rest}"


def unique_prefix() -> str:
    return _letters(4)


def unique_tin() -> str:
    return "".join(random.choices(string.digits, k=9))


def _admin_name() -> str:
    # Plain letters + spaces only — safe for Keycloak provisioning.
    return f"{SANITY_MARKER} Admin {_letters(4)}"


@dataclass
class ShipperData:
    name: str = field(default_factory=lambda: f"{SANITY_MARKER} Shipper {_stamp()}")
    prefix: str = field(default_factory=unique_prefix)
    tin: str = field(default_factory=unique_tin)
    address: str = "Tashkent, Sayyod st. 1"
    full_name: str = field(default_factory=_admin_name)
    phone: str = field(default_factory=unique_phone)


@dataclass
class CarrierData:
    name: str = field(default_factory=lambda: f"{SANITY_MARKER} Carrier {_stamp()}")
    tin: str = field(default_factory=unique_tin)
    address: str = "Tashkent, Sayyod st. 2"
    full_name: str = field(default_factory=_admin_name)
    phone: str = field(default_factory=unique_phone)


@dataclass
class StaffData:
    full_name: str = field(default_factory=lambda: f"{SANITY_MARKER} Manager {_letters(4)}")
    phone: str = field(default_factory=unique_phone)


@dataclass
class DriverData:
    full_name: str = field(default_factory=lambda: f"{SANITY_MARKER} Driver {_letters(4)}")
    phone: str = field(default_factory=unique_phone)


@dataclass
class CityData:
    name: str = field(default_factory=lambda: f"{SANITY_MARKER}City{_letters(5)}")
    country: str = "Uzbekistan"


@dataclass
class VehicleTypeData:
    name: str = field(default_factory=lambda: f"{SANITY_MARKER}-VT-{_letters(5)}")


@dataclass
class TenantCreds:
    """Credentials of the accounts the suite provisions for a run."""

    password: str
    admin_phone: str
    carrier_phone: str
    manager_phone: str
    shipper_name: str
    carrier_name: str
    warehouse_phone: str = ""
