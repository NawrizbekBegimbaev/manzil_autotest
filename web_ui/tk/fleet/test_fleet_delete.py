"""TK fleet delete via UI — confirm + dismiss.

Pattern: create a vehicle via UI (or API for speed), then drive the
delete from the row icon, handling the native `window.confirm()`.

Cleanup: leftover UIT-prefixed plates wiped via API in autouse teardown.
"""

from __future__ import annotations

import uuid

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient
from config.settings import Settings
from web_ui.pages._common.native_confirm import handle_next_confirm
from web_ui.pages.tk.fleet_page import TKFleetPage, VehicleDialog
from web_ui.seed.cleanup import wipe_tk_vehicles


def _ui_plate() -> str:
    return f"UIT-{uuid.uuid4().hex[:6].upper()}"


@pytest.fixture(autouse=True)
def _cleanup_after(tk_api: ApiClient):
    yield
    wipe_tk_vehicles(tk_api)


@pytest.fixture
def fleet(tk_page, settings: Settings) -> TKFleetPage:
    page = TKFleetPage(tk_page, settings.web_base_url_str)
    page.goto()
    return page


def _create_vehicle_ui(fleet: TKFleetPage, plate: str) -> None:
    fleet.add_vehicle_button.click()
    dialog = VehicleDialog(fleet.page)
    dialog.fill(
        make="Toyota",
        model="Hilux",
        plate=plate,
        body_type="Тент",
        capacity_kg=2000,
        volume_m3=12,
    )
    dialog.submit()
    expect(fleet.row_by_plate(plate)).to_be_visible(timeout=10_000)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_delete_vehicle_removes_row(fleet: TKFleetPage) -> None:
    plate = _ui_plate()
    _create_vehicle_ui(fleet, plate)

    with allure.step("Click «Удалить» — accept the native confirm"):
        with handle_next_confirm(fleet.page, accept=True) as captured:
            fleet.click_delete_button(plate)
        assert captured.appeared
        assert plate in captured.message, captured.message

    with allure.step("Row gone from the table"):
        expect(fleet.row_by_plate(plate)).to_have_count(0, timeout=10_000)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_dismissing_delete_confirm_keeps_vehicle(fleet: TKFleetPage) -> None:
    plate = _ui_plate()
    _create_vehicle_ui(fleet, plate)

    with allure.step("Click «Удалить» but DISMISS the confirm"):
        with handle_next_confirm(fleet.page, accept=False) as captured:
            fleet.click_delete_button(plate)
        assert captured.appeared

    with allure.step("Vehicle still in the table"):
        fleet.page.wait_for_timeout(500)
        expect(fleet.row_by_plate(plate)).to_be_visible()
