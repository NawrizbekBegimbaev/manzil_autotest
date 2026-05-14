"""Mobile Wave 2: submit offer does not proceed with empty price."""

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
def test_submit_offer_empty_price_stays_on_form(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/submit_disabled_when_empty.yaml", driver_login_params())
    assert_flow_passed(result, platform, "submit offer empty price")
