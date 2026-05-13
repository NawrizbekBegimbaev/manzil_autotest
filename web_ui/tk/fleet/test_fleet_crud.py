"""TK fleet — open dialog, create vehicle, verify in table.

Cleanup: vehicles created with plate prefix `UIT-` are removed via the
API in autouse teardown (matching `wipe_tk_vehicles` convention).

Delete-via-UI is NOT covered yet — same pattern as warehouses, the
delete icon likely opens a confirm modal we haven't reconned.
"""

from __future__ import annotations

import uuid

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient
from config.settings import Settings
from web_ui.pages.tk.fleet_page import TKFleetPage, VehicleDialog
from web_ui.seed.cleanup import wipe_tk_vehicles


def _ui_plate() -> str:
    """Plate must match `UIT-…` for `wipe_tk_vehicles` to find it."""
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


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_add_button_opens_dialog_with_expected_fields(
    fleet: TKFleetPage,
) -> None:
    fleet.add_vehicle_button.click()
    dialog = VehicleDialog(fleet.page)
    expect(dialog.root).to_be_visible()
    for input_locator in (
        dialog.make_input,
        dialog.model_input,
        dialog.plate_input,
        dialog.body_type_select,
        dialog.capacity_kg_input,
        dialog.volume_m3_input,
        dialog.extra_input,
    ):
        expect(input_locator).to_be_visible()
    # Default body type should be Тент per recon.
    expect(dialog.body_type_select).to_contain_text("Тент")


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_dialog_cancel_closes_without_creating(fleet: TKFleetPage) -> None:
    fleet.add_vehicle_button.click()
    dialog = VehicleDialog(fleet.page)
    dialog.fill(make="Honda", model="Civic", plate=_ui_plate())
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_create_vehicle_appears_in_fleet_table(
    fleet: TKFleetPage,
) -> None:
    plate = _ui_plate()
    with allure.step(f"Create vehicle via UI: plate={plate}"):
        fleet.add_vehicle_button.click()
        dialog = VehicleDialog(fleet.page)
        dialog.fill(
            make="Toyota",
            model="Hilux",
            plate=plate,
            body_type="Тент",
            capacity_kg=2500,
            volume_m3=15,
        )
        dialog.submit()
    with allure.step("New row visible in table"):
        expect(dialog.root).to_have_count(0)
        expect(fleet.row_by_plate(plate)).to_be_visible()
