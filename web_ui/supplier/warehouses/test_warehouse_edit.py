"""Edit warehouse via UI — same dialog as create, pre-filled.

Recon: clicking the «Редактировать» icon opens a dialog titled
«Редактировать склад» with the same fields as create (Название, Город,
Адрес, Активен), pre-filled with the row's values. Submit button text
is «Сохранить» (vs. «Создать» on the add dialog).
"""

from __future__ import annotations

import contextlib
import uuid

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import warehouses as wh_ep
from config.settings import Settings
from data import builders
from web_ui.pages.supplier.warehouses_page import (
    SupplierWarehousesPage,
    WarehouseDialog,
)
from web_ui.seed.cleanup import UI_TAG, wipe_supplier_warehouses


def _ui_warehouse_name() -> str:
    return f"{UI_TAG} edit-{uuid.uuid4().hex[:6]}"


@pytest.fixture(autouse=True)
def _cleanup_after(supplier_admin_api: ApiClient):
    yield
    with contextlib.suppress(ApiError):
        wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def warehouses(
    supplier_admin_page, settings: Settings,
) -> SupplierWarehousesPage:
    page = SupplierWarehousesPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.fixture
def existing_warehouse(supplier_admin_api: ApiClient):
    """Create via API for speed; tests then drive the EDIT through UI."""
    return wh_ep.create_warehouse(
        supplier_admin_api,
        builders.warehouse(
            name=_ui_warehouse_name(),
            city="Tashkent",
            address="ул. Эдит, 1",
        ),
    )


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_edit_dialog_opens_with_prefilled_values(
    existing_warehouse, warehouses: SupplierWarehousesPage,
) -> None:
    """Click row's «Редактировать» icon → dialog opens with current
    values populated."""
    # Force a reload to pick up the API-created warehouse.
    warehouses.page.reload()
    warehouses.edit_warehouse(existing_warehouse.name)
    dialog = WarehouseDialog(warehouses.page)
    expect(dialog.title).to_have_text("Редактировать склад")
    expect(dialog.name_input).to_have_value(existing_warehouse.name)
    expect(dialog.city_input).to_have_value(existing_warehouse.city)
    expect(dialog.address_input).to_have_value(existing_warehouse.address)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_edit_warehouse_persists_changes(
    existing_warehouse, warehouses: SupplierWarehousesPage,
) -> None:
    new_name = _ui_warehouse_name() + "-updated"
    warehouses.page.reload()

    with allure.step("Edit and save"):
        warehouses.edit_warehouse(existing_warehouse.name)
        dialog = WarehouseDialog(warehouses.page)
        dialog.name_input.fill(new_name)
        dialog.city_input.fill("Самарканд")
        dialog.address_input.fill("ул. Регистан, 99")
        dialog.submit()

    with allure.step("New name visible in table; old gone"):
        expect(dialog.root).to_have_count(0)
        expect(warehouses.row_by_name(new_name)).to_be_visible(timeout=10_000)
        expect(warehouses.row_by_name(existing_warehouse.name)).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_edit_dialog_cancel_keeps_original_values(
    existing_warehouse, warehouses: SupplierWarehousesPage,
) -> None:
    warehouses.page.reload()
    warehouses.edit_warehouse(existing_warehouse.name)
    dialog = WarehouseDialog(warehouses.page)
    dialog.name_input.fill("[E2E-UI] discarded")
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)
    # Row name unchanged.
    expect(warehouses.row_by_name(existing_warehouse.name)).to_be_visible()
    expect(warehouses.row_by_name("[E2E-UI] discarded")).to_have_count(0)
