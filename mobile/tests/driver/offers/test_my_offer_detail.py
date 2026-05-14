"""Mobile Wave 2: my-offer card opens a detail view."""

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
def test_my_offer_detail_opens(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/my_offer_detail_opens.yaml", driver_login_params())
    assert_flow_passed(result, platform, "my offer detail opens")
