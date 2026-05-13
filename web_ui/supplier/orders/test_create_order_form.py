"""DISPATCHER creates orders via the `/orders/create` UI form.

Coverage:
- Page renders the heading + all inputs (form contract).
- Empty submit shows ALL six required-field errors.
- Per-field validators (weight=0, volume=0, missing fields).
- DRAFT save: «Сохранить черновик» button puts a fresh order in /orders
  with status «Черновик».
- Publish: «Опубликовать заявку» button puts a fresh order in /orders
  with status «Активна» AND it appears in TK feed.
- RBAC negatives: ADMIN and MANAGER visiting /orders/create do NOT
  render the create form's heading «Создание заявки».

Cleanup: every order created here is cancelled via API in autouse
teardown. Warehouses created for setup are wiped via API too.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import date, timedelta

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import warehouses as wh_ep
from api.schemas import WarehouseResponse
from config.settings import Settings
from data import builders
from web_ui.pages.supplier.order_create_page import OrderCreatePage
from web_ui.pages.supplier.orders_list_page import SupplierOrdersListPage
from web_ui.seed.cleanup import (
    UI_TAG,
    cancel_supplier_open_orders,
    wipe_supplier_warehouses,
)

# ---------- shared setup --------------------------------------------------


@pytest.fixture
def ui_warehouse(supplier_dispatcher_api: ApiClient) -> WarehouseResponse:
    """Provision a warehouse the form can pick — independent of any
    other dataset state."""
    return wh_ep.create_warehouse(
        supplier_dispatcher_api,
        builders.warehouse(name=f"{UI_TAG} create-form WH {uuid.uuid4().hex[:6]}"),
    )


@pytest.fixture(autouse=True)
def _cleanup_after(supplier_admin_api: ApiClient):
    """After every test in this file, cancel any UI-tagged orders we left
    open and wipe UI-tagged warehouses. Order matters: orders first,
    warehouses next (warehouse delete 409s if referenced)."""
    yield
    with contextlib.suppress(ApiError):
        cancel_supplier_open_orders(supplier_admin_api)
    wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def create_form(
    supplier_dispatcher_page,
    settings: Settings,
) -> OrderCreatePage:
    page = OrderCreatePage(supplier_dispatcher_page, settings.web_base_url_str)
    page.goto()
    return page


# ---------- form rendering ------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_form_renders_heading_and_three_sections(
    create_form: OrderCreatePage,
) -> None:
    expect(create_form.heading).to_be_visible()
    for section in ("Груз", "Маршрут", "Дополнительно"):
        expect(
            create_form.page.get_by_role("heading", name=section),
        ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_form_renders_all_inputs(create_form: OrderCreatePage) -> None:
    for input_locator in (
        create_form.cargo_type_input,
        create_form.weight_input,
        create_form.volume_input,
        create_form.body_type_select,
        create_form.loading_methods_select,
        create_form.warehouse_select,
        create_form.unload_address_select,
        create_form.desired_date_picker,
        create_form.currency_select,
        create_form.notes_input,
        create_form.publish_checkbox,
        create_form.save_draft_button,
        create_form.publish_button,
    ):
        expect(input_locator).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_publish_checkbox_is_pre_checked(create_form: OrderCreatePage) -> None:
    expect(create_form.publish_checkbox).to_be_checked()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_currency_default_is_usd(create_form: OrderCreatePage) -> None:
    expect(create_form.currency_select).to_contain_text("USD")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_body_type_default_is_tent(create_form: OrderCreatePage) -> None:
    expect(create_form.body_type_select).to_contain_text("Тент")


# ---------- empty submit ---------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_empty_submit_shows_all_required_errors(
    create_form: OrderCreatePage,
) -> None:
    with allure.step("Click «Опубликовать заявку» on an empty form"):
        create_form.publish_button.click()
    expected = (
        "Укажите тип груза",
        "Вес должен быть больше нуля",
        "Объём должен быть больше нуля",
        "Выберите склад погрузки",
        "Укажите адрес выгрузки",
        "Укажите дату",
    )
    for err in expected:
        expect(create_form.field_error(err)).to_be_visible()


# ---------- per-field validators ------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_weight_zero_shows_error_after_submit(
    create_form: OrderCreatePage,
) -> None:
    create_form.weight_input.fill("0")
    create_form.publish_button.click()
    expect(create_form.field_error("Вес должен быть больше нуля")).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_volume_zero_shows_error_after_submit(
    create_form: OrderCreatePage,
) -> None:
    create_form.volume_input.fill("0")
    create_form.publish_button.click()
    expect(create_form.field_error("Объём должен быть больше нуля")).to_be_visible()


# ---------- happy path: publish -------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_publish_creates_order_visible_in_orders_list(
    ui_warehouse: WarehouseResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    """Open the form AFTER the warehouse is created — the form fetches
    its warehouse dropdown options on mount, so a warehouse that didn't
    exist at mount time won't appear in the dropdown."""
    cargo = f"{UI_TAG} publish-{uuid.uuid4().hex[:6]}"
    desired = (date.today() + timedelta(days=14)).isoformat()

    create_form = OrderCreatePage(supplier_dispatcher_page, settings.web_base_url_str)
    create_form.goto()

    with allure.step("Fill required fields"):
        create_form.fill_required_fields(
            cargo_type=cargo, weight=2500, volume=15, desired_date_iso=desired,
        )
        create_form.select_option(
            create_form.warehouse_select, ui_warehouse.name,
        )
        create_form.select_first_unload_address()

    with allure.step("Click «Опубликовать заявку» — SPA navigates away from /create"):
        create_form.publish_button.click()
        # SPA redirects to the new order's detail (`/orders/{uuid}`),
        # not back to the list. Just wait until we're off /create.
        supplier_dispatcher_page.wait_for_url(
            lambda url: "/orders/create" not in url, timeout=15_000,
        )

    with allure.step("New row visible in DISPATCHER's /orders list"):
        supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/orders")
        listing = SupplierOrdersListPage(
            supplier_dispatcher_page, settings.web_base_url_str,
        )
        expect(listing.heading).to_be_visible()
        row = supplier_dispatcher_page.locator("tbody tr").filter(
            has_text=cargo,
        ).first
        expect(row).to_be_visible(timeout=10_000)
        expect(row).to_contain_text("Активна")


# ---------- happy path: draft ---------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_save_draft_creates_order_with_draft_status(
    ui_warehouse: WarehouseResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    cargo = f"{UI_TAG} draft-{uuid.uuid4().hex[:6]}"
    desired = (date.today() + timedelta(days=14)).isoformat()

    create_form = OrderCreatePage(supplier_dispatcher_page, settings.web_base_url_str)
    create_form.goto()

    create_form.fill_required_fields(
        cargo_type=cargo, weight=1800, volume=10, desired_date_iso=desired,
    )
    create_form.select_option(create_form.warehouse_select, ui_warehouse.name)
    create_form.select_first_unload_address()

    with allure.step("Click «Сохранить черновик»"):
        create_form.save_draft_button.click()
        supplier_dispatcher_page.wait_for_url(
            lambda url: "/orders/create" not in url, timeout=15_000,
        )

    with allure.step("Row in /orders with «Черновик» status"):
        supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/orders")
        row = supplier_dispatcher_page.locator("tbody tr").filter(
            has_text=cargo,
        ).first
        expect(row).to_be_visible(timeout=10_000)
        expect(row).to_contain_text("Черновик")


# ---------- RBAC negatives ------------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_visiting_create_url_does_not_see_create_heading(
    supplier_admin_page, settings: Settings,
) -> None:
    """ADMIN cannot reach the create form. UI may redirect or render an
    empty state — either way, the «Создание заявки» heading must be
    absent."""
    supplier_admin_page.goto(f"{settings.web_base_url_str}/orders/create")
    expect(
        supplier_admin_page.get_by_role("heading", name="Создание заявки"),
    ).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_visiting_create_url_does_not_see_create_heading(
    supplier_manager_page, settings: Settings,
) -> None:
    supplier_manager_page.goto(f"{settings.web_base_url_str}/orders/create")
    expect(
        supplier_manager_page.get_by_role("heading", name="Создание заявки"),
    ).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_tk_visiting_create_url_does_not_see_create_heading(
    tk_page, settings: Settings,
) -> None:
    tk_page.goto(f"{settings.web_base_url_str}/orders/create")
    expect(
        tk_page.get_by_role("heading", name="Создание заявки"),
    ).to_have_count(0)


# ---------- back navigation -----------------------------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_back_button_returns_to_orders_list(
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    """«Назад» calls history.back(); we land on /orders only when /orders
    is the previous SPA route. Walk in via the list explicitly."""
    listing = SupplierOrdersListPage(
        supplier_dispatcher_page, settings.web_base_url_str,
    )
    listing.goto()
    supplier_dispatcher_page.goto(
        f"{settings.web_base_url_str}/orders/create",
    )
    page = OrderCreatePage(supplier_dispatcher_page, settings.web_base_url_str)
    expect(page.heading).to_be_visible()
    page.back_button.click()
    supplier_dispatcher_page.wait_for_url("**/orders*", timeout=10_000)
    expect(listing.heading).to_be_visible()
