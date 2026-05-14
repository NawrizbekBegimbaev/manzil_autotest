"""Mobile Wave 1: profile language control opens."""

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
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_language_toggle_opens_from_profile(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/profile/language_toggle_uz_to_ru.yaml", driver_login_params())
    assert_flow_passed(result, platform, "profile language toggle")
