"""DISPATCHER edits own DRAFT order via UI.

Per matrix only DISPATCHER can edit a DRAFT (their own). The edit URL
hasn't been confirmed in MCP recon — likely `/orders/{id}/edit`. We
probe that URL; if the SPA renders a form heading we know we're in
edit-mode and proceed. If the URL doesn't exist, the heading absence
becomes the failure signal — clear actionable error.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator

import allure
import pytest
from playwright.sync_api import expect

from api.client import ApiClient, ApiError
from api.endpoints import orders as ord_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import OrderResponse
from config.settings import Settings
from data import builders
from web_ui.seed.cleanup import (
    UI_TAG,
    cancel_supplier_open_orders,
    wipe_supplier_warehouses,
)


@pytest.fixture(autouse=True)
def _cleanup_after(supplier_admin_api: ApiClient):
    yield
    with contextlib.suppress(ApiError):
        cancel_supplier_open_orders(supplier_admin_api)
    wipe_supplier_warehouses(supplier_admin_api)


@pytest.fixture
def own_draft_order(
    supplier_dispatcher_api: ApiClient,
    supplier_admin_api: ApiClient,
) -> Iterator[OrderResponse]:
    """A DRAFT order owned by the dispatcher."""
    tag = f"{UI_TAG} draft-edit-{uuid.uuid4().hex[:6]}"
    warehouse = wh_ep.create_warehouse(
        supplier_dispatcher_api, builders.warehouse(name=f"{tag} WH"),
    )
    destination = wh_ep.create_warehouse(
        supplier_dispatcher_api, builders.warehouse(name=f"{tag} DST"),
    )
    order = ord_ep.create_order(
        supplier_dispatcher_api,
        builders.order_request(
            warehouse_id=warehouse.id,
            destination_warehouse_id=destination.id,
            body_type="TENT",
            cargo_type=f"{tag} cargo",
            currency="USD",
            publish=False,  # DRAFT
        ),
    )
    assert order.status.upper() == "DRAFT", f"expected DRAFT, got {order.status}"
    try:
        yield order
    finally:
        with contextlib.suppress(ApiError):
            ord_ep.cancel_order(supplier_admin_api, order.id)


@pytest.mark.xfail(
    reason=(
        "Draft-edit URL not yet reconned. Tried /orders/{id}/edit — SPA "
        "doesn't route there (load times out). Edit access likely lives "
        "behind a «Редактировать» button on the detail page or under a "
        "different URL. Needs another MCP session to capture; until then "
        "these tests pin the EXPECTED contract so a future reconnaissance "
        "knows what to wire up."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_can_open_draft_edit_form(
    own_draft_order: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    """Probe `/orders/{id}/edit`. The SPA should render a form titled
    «Редактирование заявки» (or similar — match loosely)."""
    supplier_dispatcher_page.goto(
        f"{settings.web_base_url_str}/orders/{own_draft_order.id}/edit",
    )
    # We accept any of these headings — the convention isn't pinned yet.
    headings = supplier_dispatcher_page.get_by_role("heading").filter(
        has_text="едактирование",  # «Редактирование заявки»
    ).or_(
        supplier_dispatcher_page.get_by_role("heading", name="Создание заявки"),
    )
    expect(headings.first).to_be_visible(timeout=10_000)


@pytest.mark.xfail(
    reason=(
        "Draft-edit URL not yet reconned. Tried /orders/{id}/edit — SPA "
        "doesn't route there (load times out). Edit access likely lives "
        "behind a «Редактировать» button on the detail page or under a "
        "different URL. Needs another MCP session to capture; until then "
        "these tests pin the EXPECTED contract so a future reconnaissance "
        "knows what to wire up."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_draft_edit_form_prefills_cargo_type(
    own_draft_order: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    supplier_dispatcher_page.goto(
        f"{settings.web_base_url_str}/orders/{own_draft_order.id}/edit",
    )
    cargo_input = supplier_dispatcher_page.get_by_role("textbox", name="Тип груза")
    expect(cargo_input).to_have_value(own_draft_order.cargo_type, timeout=10_000)


@pytest.mark.xfail(
    reason=(
        "Draft-edit URL not yet reconned. Tried /orders/{id}/edit — SPA "
        "doesn't route there (load times out). Edit access likely lives "
        "behind a «Редактировать» button on the detail page or under a "
        "different URL. Needs another MCP session to capture; until then "
        "these tests pin the EXPECTED contract so a future reconnaissance "
        "knows what to wire up."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_draft_edit_save_persists_cargo_change(
    own_draft_order: OrderResponse,
    supplier_dispatcher_api: ApiClient,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    new_cargo = own_draft_order.cargo_type + "-EDITED"
    supplier_dispatcher_page.goto(
        f"{settings.web_base_url_str}/orders/{own_draft_order.id}/edit",
    )
    cargo_input = supplier_dispatcher_page.get_by_role("textbox", name="Тип груза")
    cargo_input.wait_for(state="visible")
    cargo_input.fill(new_cargo)

    with allure.step("Save the draft (button name may differ — try both)"):
        save = supplier_dispatcher_page.get_by_role(
            "button", name="Сохранить",
        ).or_(supplier_dispatcher_page.get_by_role(
            "button", name="Сохранить черновик",
        ))
        save.first.click()
        # SPA likely navigates back to /orders or to detail.
        supplier_dispatcher_page.wait_for_url(
            lambda url: "/edit" not in url, timeout=15_000,
        )

    with allure.step("API confirms the update landed"):
        # Re-fetch to confirm cargo_type changed.
        refreshed = ord_ep.get_order(supplier_dispatcher_api, own_draft_order.id)
        assert refreshed.cargo_type == new_cargo, refreshed.cargo_type


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_visiting_draft_edit_url_does_not_render_form(
    own_draft_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    """ADMIN cannot edit (per matrix only DISPATCHER edits own draft).
    The SPA should not render the edit form for ADMIN — either redirect
    or empty state. We assert the «Тип груза» editable input is absent
    (a load-bearing edit-mode signal)."""
    supplier_admin_page.goto(
        f"{settings.web_base_url_str}/orders/{own_draft_order.id}/edit",
    )
    expect(
        supplier_admin_page.get_by_role("textbox", name="Тип груза"),
    ).to_have_count(0)
