"""Mobile Wave 1: login screen can navigate to register entry and back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.mobile_smoke
@pytest.mark.requires_device
@pytest.mark.requires_maestro
def test_login_to_register_and_back(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/navigation/login_to_register_and_back.yaml", None)
    assert_flow_passed(result, platform, "login to register navigation")
