"""Mobile Wave 2: cancel closes submit-offer form."""

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
def test_cancel_closes_submit_offer_form(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/offers/cancel_closes_form.yaml", driver_login_params())
    assert_flow_passed(result, platform, "cancel closes submit offer form")
