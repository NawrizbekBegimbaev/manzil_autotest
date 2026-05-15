"""Mobile Wave 4: driver logout returns to login."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed, driver_login_params

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.mutation
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_driver_logout_returns_to_login(maestro: MaestroCallable, platform: Platform) -> None:
    result = maestro("driver/profile/logout.yaml", driver_login_params())
    assert_flow_passed(result, platform, "driver logout")
