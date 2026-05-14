"""Mobile Wave 1: logged-in driver can navigate bottom tabs."""

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
def test_post_login_bottom_tabs_render(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/navigation/post_login_bottom_tabs.yaml", driver_login_params())
    assert_flow_passed(result, platform, "post-login bottom tabs")
