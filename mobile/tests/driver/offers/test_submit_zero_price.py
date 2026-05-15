"""Mobile Wave 4: zero-price offer stays on submit form."""

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
def test_submit_zero_price_does_not_close_form(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/submit_zero_price.yaml", driver_login_params())
    assert_flow_passed(result, platform, "submit zero price")
