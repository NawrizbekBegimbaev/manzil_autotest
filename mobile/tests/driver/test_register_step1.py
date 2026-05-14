"""Mobile Wave 1: register step 1 hands off to Telegram."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mobile.tests.driver._helpers import MaestroCallable, assert_flow_passed

if TYPE_CHECKING:
    from mobile.conftest import Platform


@pytest.mark.mobile
@pytest.mark.requires_device
@pytest.mark.requires_maestro
def test_register_step1_opens_telegram(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    result = maestro("driver/registration/register_step1_opens_telegram.yaml", None)
    assert_flow_passed(result, platform, "register step 1 Telegram handoff")
