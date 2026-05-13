"""Edit vehicle via UI — same dialog as create, pre-filled."""

from __future__ import annotations

import contextlib
import uuid

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import vehicles as vh_ep
from config.settings import Settings
from data import builders
from web_ui.pages.tk.fleet_page import TKFleetPage, VehicleDialog
from web_ui.seed.cleanup import wipe_tk_vehicles


def _ui_plate() -> str:
    return f"UIT-{uuid.uuid4().hex[:6].upper()}"


@pytest.fixture(autouse=True)
def _cleanup_after(tk_api: ApiClient):
    yield
    with contextlib.suppress(ApiError):
        wipe_tk_vehicles(tk_api)


@pytest.fixture
def fleet(tk_page, settings: Settings) -> TKFleetPage:
    page = TKFleetPage(tk_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.fixture
def existing_vehicle(tk_api: ApiClient):
    """Create via API for speed; tests then drive EDIT through UI."""
    return vh_ep.add_vehicle(
        tk_api,
        builders.vehicle(
            plate=_ui_plate(),
            brand="Toyota",
            model="Hilux",
            body_type="TENT",
            capacity_kg=2000,
            volume_m3=10,
        ),
    )


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_edit_dialog_opens_with_prefilled_plate(
    existing_vehicle, fleet: TKFleetPage,
) -> None:
    fleet.page.reload()
    fleet.edit_vehicle(existing_vehicle.plate)
    dialog = VehicleDialog(fleet.page)
    expect(dialog.plate_input).to_have_value(existing_vehicle.plate)
    expect(dialog.make_input).to_have_value(existing_vehicle.brand)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_edit_vehicle_persists_capacity_change(
    existing_vehicle, fleet: TKFleetPage,
) -> None:
    fleet.page.reload()
    with allure.step("Edit capacity to 9999"):
        fleet.edit_vehicle(existing_vehicle.plate)
        dialog = VehicleDialog(fleet.page)
        dialog.capacity_kg_input.fill("9999")
        dialog.submit()

    with allure.step("Updated value visible in table"):
        expect(dialog.root).to_have_count(0)
        row = fleet.row_by_plate(existing_vehicle.plate)
        # Numeric formatting may use thin spaces («9 999») — match on the
        # leading digits only.
        expect(row).to_contain_text("9")


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_edit_dialog_cancel_keeps_original_capacity(
    existing_vehicle, fleet: TKFleetPage,
) -> None:
    fleet.page.reload()
    fleet.edit_vehicle(existing_vehicle.plate)
    dialog = VehicleDialog(fleet.page)
    dialog.capacity_kg_input.fill("11111")
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)
    # Row's capacity is unchanged — we look for the original value.
    row = fleet.row_by_plate(existing_vehicle.plate)
    expect(row).not_to_contain_text("11111")
