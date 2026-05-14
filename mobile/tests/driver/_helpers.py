"""Shared helpers for driver mobile flow wrappers."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from mobile.runner.maestro_runner import MaestroResult

if TYPE_CHECKING:
    from mobile.conftest import Platform

MaestroCallable = Callable[[str, dict[str, str] | None], MaestroResult]


def driver_phone_no_prefix() -> str:
    """Return the configured driver phone without the +998 prefix."""
    phone_full = os.environ.get("DRIVER_REAL_PHONE", "")
    assert phone_full.startswith("+998"), "DRIVER_REAL_PHONE must start with +998"
    return phone_full[4:]


def driver_password() -> str:
    """Return the configured driver account password."""
    password = os.environ.get("DRIVER_REAL_PASSWORD")
    assert password, "DRIVER_REAL_PASSWORD must be set in .env"
    return password


def driver_full_name() -> str:
    """Return the configured driver full name."""
    full_name = os.environ.get("DRIVER_REAL_FULL_NAME")
    assert full_name, "DRIVER_REAL_FULL_NAME must be set in .env"
    return full_name


def assert_flow_passed(result: MaestroResult, platform: Platform, flow_name: str) -> None:
    """Fail with useful Maestro logs if a flow did not pass."""
    assert result.passed, (
        f"{flow_name} failed on {platform}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def driver_login_params() -> dict[str, str]:
    """Params required by reusable post-login driver flows."""
    return {
        "DRIVER_PHONE_NO_PREFIX": driver_phone_no_prefix(),
        "DRIVER_PASSWORD": driver_password(),
        "DRIVER_FULL_NAME": driver_full_name(),
        "DRIVER_PHONE_FULL": os.environ.get("DRIVER_REAL_PHONE", ""),
    }
