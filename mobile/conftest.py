"""Mobile tests: pytest fixtures for the Maestro wrapper."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Literal

import pytest
from dotenv import load_dotenv
from pluggy import Result

from mobile.runner.maestro_runner import (
    MaestroNotInstalled,
    MaestroResult,
    check_maestro_installed,
    run_flow,
)

Platform = Literal["android", "ios"]
MaestroCallable = Callable[[str, dict[str, str] | None], MaestroResult]

FLOWS_DIR = Path(__file__).parent / "flows"

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def _verify_maestro_installed() -> None:
    """Skip mobile tests once per session if Maestro is not installed."""
    try:
        version = check_maestro_installed()
        print(f"\n[maestro] using {version}")
    except MaestroNotInstalled as exc:
        pytest.skip(str(exc), allow_module_level=True)


@pytest.fixture(params=["android", "ios"], ids=["android", "ios"])
def platform(request: pytest.FixtureRequest) -> Platform:
    """Run each mobile test for both platforms, skipping unconfigured ones."""
    requested_platform = request.param
    if requested_platform not in {"android", "ios"}:
        raise ValueError(f"Unsupported mobile platform: {requested_platform}")

    platform_value: Platform = requested_platform
    if (
        platform_value == "android"
        and not os.environ.get("ANDROID_APP_ID")
        and not os.environ.get("ANDROID_APP_PATH")
    ):
        pytest.skip("ANDROID_APP_ID/ANDROID_APP_PATH is not set")
    if (
        platform_value == "ios"
        and not os.environ.get("IOS_APP_ID")
        and not os.environ.get("IOS_APP_PATH")
    ):
        pytest.skip("IOS_APP_ID/IOS_APP_PATH is not set")
    return platform_value


@pytest.fixture
def maestro_env(platform: Platform) -> dict[str, str]:
    """Environment values passed to Maestro YAML as ${APP_ID}, ${APP_PATH}, etc."""
    if platform == "android":
        return {
            "APP_ID": os.environ.get("ANDROID_APP_ID", ""),
            "APP_PATH": os.environ.get("ANDROID_APP_PATH", ""),
            "DEVICE_ID": os.environ.get("ANDROID_DEVICE_ID", ""),
            "DRIVER_FULL_NAME": os.environ.get("DRIVER_REAL_FULL_NAME", ""),
            "DRIVER_PHONE_FULL": os.environ.get("DRIVER_REAL_PHONE", ""),
        }
    return {
        "APP_ID": os.environ.get("IOS_APP_ID", ""),
        "APP_PATH": os.environ.get("IOS_APP_PATH", ""),
        "DEVICE_NAME": os.environ.get("IOS_DEVICE_NAME", "iPhone 15"),
        "PLATFORM_VERSION": os.environ.get("IOS_PLATFORM_VERSION", "17.0"),
        "DRIVER_FULL_NAME": os.environ.get("DRIVER_REAL_FULL_NAME", ""),
        "DRIVER_PHONE_FULL": os.environ.get("DRIVER_REAL_PHONE", ""),
    }


@pytest.fixture
def maestro(maestro_env: dict[str, str], platform: Platform) -> MaestroCallable:
    """Return a callback that runs a flow path relative to mobile/flows."""

    def _run(flow_rel_path: str, params: dict[str, str] | None = None) -> MaestroResult:
        flow_path = FLOWS_DIR / flow_rel_path
        return run_flow(flow_path, params=params, env=maestro_env, platform=platform)

    return _run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[object],
) -> Generator[None, Result[pytest.TestReport], None]:
    """Leave failed Maestro logs in pytest output for Allure to collect."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
