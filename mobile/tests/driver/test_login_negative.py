"""Mobile Wave 1: wrong driver password keeps the user on login."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import (
    MaestroCallable,
    assert_flow_passed,
    driver_phone_no_prefix,
)

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.negative
def test_driver_wrong_password_stays_on_login(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro(
        "driver/login/login_wrong_password_shows_error.yaml",
        {"DRIVER_PHONE_NO_PREFIX": driver_phone_no_prefix()},
    )
    assert_flow_passed(result, platform, "driver wrong-password login")
