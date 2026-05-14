"""Mobile Wave 1: login with valid credentials lands on Lenta feed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import (
    MaestroCallable,
    assert_flow_passed,
    driver_login_params,
)

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.mobile_smoke
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_driver_can_login_and_sees_feed(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/login/login_with_valid_credentials.yaml", driver_login_params())
    assert_flow_passed(result, platform, "driver login")
