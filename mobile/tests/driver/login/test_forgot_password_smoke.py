"""Mobile Wave 4: forgot password screen renders."""

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
def test_forgot_password_screen_renders(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/login/forgot_password_screen_renders.yaml", None)
    assert_flow_passed(result, platform, "forgot password screen renders")
