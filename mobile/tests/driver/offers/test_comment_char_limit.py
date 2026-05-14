"""Mobile Wave 2: offer comment accepts long input without breaking the form."""

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
def test_offer_comment_char_limit_keeps_form_usable(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    params = driver_login_params() | {"LONG_TEXT": "x" * 300}
    result = maestro("driver/offers/comment_char_limit.yaml", params)
    assert_flow_passed(result, platform, "offer comment char limit")
