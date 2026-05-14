"""Mobile Wave 2: driver submits a valid offer."""

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
@pytest.mark.maintenance
@pytest.mark.mutation
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.requires_real_account
def test_submit_valid_offer(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/submit_valid_offer.yaml", driver_login_params())
    assert_flow_passed(result, platform, "submit valid offer")
