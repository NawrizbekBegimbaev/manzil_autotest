"""Mobile smoke: the app starts and renders an initial screen.

Wave 0 is only infrastructure. This test is collected now, but it runs only
when Maestro, app env, and a connected device or emulator are available.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from mobile.runner.maestro_runner import MaestroResult

if TYPE_CHECKING:
    from mobile.conftest import Platform

MaestroCallable = Callable[[str, dict[str, str] | None], MaestroResult]


@pytest.mark.mobile
@pytest.mark.mobile_smoke
@pytest.mark.requires_device
@pytest.mark.requires_maestro
def test_app_launches_and_shows_initial_screen(
    maestro: MaestroCallable,
    platform: Platform,
) -> None:
    """Run the smoke flow and assert Maestro completed successfully."""
    result = maestro("smoke/app_launches.yaml", None)
    assert result.passed, (
        f"smoke failed on {platform}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
