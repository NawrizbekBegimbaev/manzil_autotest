"""Mobile Wave 1: feed renders structural order-card labels."""

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
def test_feed_renders_order_cards(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/feed/feed_renders_orders.yaml", driver_login_params())
    assert_flow_passed(result, platform, "feed order cards")
