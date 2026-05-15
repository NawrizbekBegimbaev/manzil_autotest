"""Mobile Wave 4: profile language can switch to Russian and back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed, driver_login_params

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_profile_language_switch_to_russian(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/profile/language_switch_to_russian.yaml", driver_login_params())
    assert_flow_passed(result, platform, "profile language switch Russian")
