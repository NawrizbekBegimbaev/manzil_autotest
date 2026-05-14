"""Mobile Wave 1: login screen opens forgot-password flow."""

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
def test_login_to_forgot_password(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/navigation/login_to_forgot_password.yaml", None)
    assert_flow_passed(result, platform, "login to forgot-password navigation")
