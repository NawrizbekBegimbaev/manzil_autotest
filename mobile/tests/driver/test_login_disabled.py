"""Mobile Wave 1: empty login form does not proceed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.mobile_smoke
@pytest.mark.requires_device
@pytest.mark.requires_maestro
@pytest.mark.negative
def test_login_button_does_not_submit_empty_form(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/login/login_button_disabled_when_empty.yaml", None)
    assert_flow_passed(result, platform, "empty login form")
