"""Supplier warehouses — full CRUD via UI for ADMIN.

Pattern:
- Each test creates resources tagged `[E2E-UI]` so a teardown fixture
  can wipe them via the API after the test (UI delete is slower and
  itself under test). Cleanup uses the API client and tolerates 409.
- Names embed a UUID4 chunk to avoid collisions when run in parallel.

What's NOT here:
- DISPATCHER CRUD (same UI; we only have ADMIN time budget today —
  add later as a parametric run if dispatcher account stays stable).
- MANAGER negative (page hidden from sidebar — covered by RBAC suite).
"""

from __future__ import annotations

import uuid

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient
from config.settings import Settings
from web_ui.pages.supplier.warehouses_page import (
    SupplierWarehousesPage,
    WarehouseDialog,
)
from web_ui.seed.cleanup import UI_TAG, wipe_supplier_warehouses


def _ui_warehouse_name() -> str:
    return f"{UI_TAG} WH-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _cleanup_after(supplier_admin_api: ApiClient):
    """Best-effort wipe of any [E2E-UI]-named warehouse after each test."""
    yield
    wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def warehouses(
    supplier_admin_page, settings: Settings,
) -> SupplierWarehousesPage:
    page = SupplierWarehousesPage(supplier_admin_page, settings.web_base_url_str)
    page.goto()
    return page


# ---------- dialog opens, cancels, validates ------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_add_button_opens_dialog(warehouses: SupplierWarehousesPage) -> None:
    warehouses.add_warehouse_button.click()
    dialog = WarehouseDialog(warehouses.page)
    expect(dialog.title).to_have_text("Добавить склад погрузки")
    for input_locator in (
        dialog.name_input,
        dialog.city_input,
        dialog.address_input,
    ):
        expect(input_locator).to_be_visible()
    # Active checkbox is pre-checked per recon.
    expect(dialog.active_checkbox).to_be_checked()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dialog_cancel_closes_without_saving(
    warehouses: SupplierWarehousesPage,
) -> None:
    warehouses.add_warehouse_button.click()
    dialog = WarehouseDialog(warehouses.page)
    dialog.fill(name=_ui_warehouse_name(), city="X", address="Y")
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)


# ---------- create flow ---------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_create_warehouse_appears_in_table(
    warehouses: SupplierWarehousesPage,
) -> None:
    name = _ui_warehouse_name()
    with allure.step(f"Создать склад через UI: {name}"):
        warehouses.add_warehouse_button.click()
        dialog = WarehouseDialog(warehouses.page)
        dialog.fill(
            name=name,
            city="Tashkent",
            address="ул. Тестовая, 1",
        )
        dialog.submit()
    with allure.step("Новый склад виден в таблице"):
        expect(dialog.root).to_have_count(0)
        expect(warehouses.row_by_name(name)).to_be_visible()


# ---------- delete flow ---------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_delete_warehouse_removes_row(
    warehouses: SupplierWarehousesPage,
) -> None:
    """Click «Удалить» → native `window.confirm()` appears with the
    warehouse name → accept → row disappears."""
    from web_ui.pages._common.native_confirm import handle_next_confirm

    name = _ui_warehouse_name()
    warehouses.add_warehouse_button.click()
    dialog = WarehouseDialog(warehouses.page)
    dialog.fill(name=name, city="Tashkent", address="ул. Сквозная, 2")
    dialog.submit()
    expect(warehouses.row_by_name(name)).to_be_visible()

    with allure.step("Click «Удалить» — confirm appears, accept it"):
        with handle_next_confirm(warehouses.page, accept=True) as captured:
            warehouses.click_delete_button(name)
        assert captured.appeared, "expected window.confirm to appear"
        assert name in captured.message, (
            f"confirm message must mention the warehouse name, got: {captured.message!r}"
        )

    with allure.step("Row gone from the table"):
        expect(warehouses.row_by_name(name)).to_have_count(0, timeout=10_000)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dismissing_delete_confirm_keeps_warehouse(
    warehouses: SupplierWarehousesPage,
) -> None:
    """Cancel button on the native confirm — row must remain."""
    from web_ui.pages._common.native_confirm import handle_next_confirm

    name = _ui_warehouse_name()
    warehouses.add_warehouse_button.click()
    dialog = WarehouseDialog(warehouses.page)
    dialog.fill(name=name, city="Tashkent", address="ул. Тропа, 3")
    dialog.submit()
    expect(warehouses.row_by_name(name)).to_be_visible()

    with allure.step("Click «Удалить» but DISMISS the confirm"):
        with handle_next_confirm(warehouses.page, accept=False) as captured:
            warehouses.click_delete_button(name)
        assert captured.appeared

    with allure.step("Row stays — nothing was deleted"):
        # Small grace period; the API delete call should NOT have fired.
        warehouses.page.wait_for_timeout(500)
        expect(warehouses.row_by_name(name)).to_be_visible()
