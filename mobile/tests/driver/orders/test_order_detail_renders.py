"""Mobile Wave 2: order detail renders core fields."""

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
def test_order_detail_renders_core_fields(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/orders/order_detail_renders.yaml", driver_login_params())
    assert_flow_passed(result, platform, "order detail renders")
