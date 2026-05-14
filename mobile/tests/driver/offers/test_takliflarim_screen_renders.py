"""Mobile Wave 2: Takliflarim screen renders."""

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
def test_takliflarim_screen_renders(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/my_offer_detail_opens.yaml", driver_login_params())
    assert_flow_passed(result, platform, "takliflarim screen renders")
