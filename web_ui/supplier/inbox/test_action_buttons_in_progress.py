"""Action buttons on «В работе» order detail — BUG-017 contract.

Per role matrix on a «В работе» order:
  ADMIN   ✅ «Завершить», «Отменить»
  MANAGER ✅ «Завершить», «Отменить», «Заметка» (per offer card)
  DISPATCHER ❌ (no actions even on own order)

Live recon (2026-05-03): UI renders NONE of these buttons except
MANAGER's «Заметка». BUG-017 in bug.txt.

These tests are marked `xfail(strict=False)` so:
- they DON'T fail the suite while frontend hasn't rendered the buttons
- when frontend ships, they automatically xpass — that's the signal to
  remove the xfail marker

DISPATCHER negative tests stay as regular passing tests (current state
is correct — DISPATCHER never had these actions per matrix).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from api.schemas import OrderResponse
from config.settings import Settings
from web_ui.pages.supplier.order_detail_page import SupplierOrderDetailPage

_BUG_017 = pytest.mark.xfail(
    reason=(
        "BUG-017: UI doesn't render Завершить/Отменить/Заметка/Выбрать "
        "победителя on «В работе» orders. API endpoints work — covered "
        "by API tests. Removes xfail when frontend ships the buttons."
    ),
    strict=False,
)


def _open_detail(page, order: OrderResponse, settings: Settings) -> SupplierOrderDetailPage:
    """Navigate directly to /orders/{id} and wait for content to hydrate."""
    page.goto(f"{settings.web_base_url_str}/orders/{order.id}")
    detail = SupplierOrderDetailPage(page, settings.web_base_url_str)
    expect(page.get_by_role("heading", name="Груз")).to_be_visible(timeout=15_000)
    return detail


# ---------- ADMIN expected buttons ---------------------------------------


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_sees_complete_button_on_in_progress_order(
    in_progress_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_admin_page, in_progress_order, settings)
    expect(detail.complete_button).to_be_visible()


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_sees_cancel_button_on_in_progress_order(
    in_progress_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_admin_page, in_progress_order, settings)
    expect(detail.cancel_button).to_be_visible()


# ---------- MANAGER expected buttons -------------------------------------


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_sees_complete_button_on_in_progress_order(
    in_progress_order: OrderResponse,
    supplier_manager_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_manager_page, in_progress_order, settings)
    expect(detail.complete_button).to_be_visible()


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_sees_cancel_button_on_in_progress_order(
    in_progress_order: OrderResponse,
    supplier_manager_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_manager_page, in_progress_order, settings)
    expect(detail.cancel_button).to_be_visible()


# ---------- DISPATCHER negative (current behaviour is CORRECT) -----------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_sees_no_complete_or_cancel_on_in_progress(
    in_progress_order: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    """DISPATCHER never has these actions per matrix. Sanity-pin so a
    future regression (granting them by mistake) is caught."""
    detail = _open_detail(supplier_dispatcher_page, in_progress_order, settings)
    expect(detail.complete_button).to_have_count(0)
    expect(detail.cancel_button).to_have_count(0)
