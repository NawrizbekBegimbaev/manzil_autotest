"""Mobile Wave 3: profile vehicle mutation with revert."""

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
@pytest.mark.mutation
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_profile_vehicle_can_be_edited_and_reverted(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/profile/edit_vehicle.yaml", driver_login_params())
    assert_flow_passed(result, platform, "profile edit vehicle")
