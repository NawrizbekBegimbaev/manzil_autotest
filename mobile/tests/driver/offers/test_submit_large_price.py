"""Mobile Wave 4: very large offer price does not crash the app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed, driver_login_params

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.mutation
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_submit_large_price_does_not_crash(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/submit_large_price.yaml", driver_login_params())
    assert_flow_passed(result, platform, "submit large price")
