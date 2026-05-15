"""Mobile Wave 4: short phone does not submit login."""

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
def test_login_short_phone_disabled(maestro: MaestroCallable, platform: Platform) -> None:
    result = maestro("driver/login/login_short_phone_disabled.yaml", None)
    assert_flow_passed(result, platform, "login short phone disabled")
