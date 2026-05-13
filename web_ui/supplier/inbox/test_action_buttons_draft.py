"""Action buttons on DRAFT order detail.

Per matrix on a DRAFT order owned by the dispatcher:
  DISPATCHER (own) ✅ «Опубликовать», «Редактировать»
  ADMIN/MANAGER    — see-only (DRAFT is dispatcher's pre-publish state)
  TK               ❌ never sees DRAFT

Live recon (2026-05-03): UI doesn't render these buttons yet
(BUG-017 covers «В работе»; DRAFT actions are the same gap).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from api.schemas import OrderResponse
from config.settings import Settings
from web_ui.pages.supplier.order_detail_page import SupplierOrderDetailPage

_BUG_017 = pytest.mark.xfail(
    reason="BUG-017: DRAFT action buttons not rendered yet. Auto-lights when fixed.",
    strict=False,
)


def _open_detail(page, order: OrderResponse, settings: Settings) -> SupplierOrderDetailPage:
    page.goto(f"{settings.web_base_url_str}/orders/{order.id}")
    detail = SupplierOrderDetailPage(page, settings.web_base_url_str)
    expect(page.get_by_role("heading", name="Груз")).to_be_visible(timeout=15_000)
    return detail


# ---------- DISPATCHER (own DRAFT) — expected actions --------------------


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_sees_publish_button_on_own_draft(
    own_draft_order: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_dispatcher_page, own_draft_order, settings)
    expect(detail.publish_button).to_be_visible()


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_sees_edit_button_on_own_draft(
    own_draft_order: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_dispatcher_page, own_draft_order, settings)
    expect(detail.edit_button).to_be_visible()


# ---------- ADMIN/MANAGER on DRAFT — see-only --------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_does_not_see_publish_or_edit_on_draft(
    own_draft_order: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    """ADMIN can read the draft but never publish/edit (matrix). Pin
    that boundary."""
    detail = _open_detail(supplier_admin_page, own_draft_order, settings)
    expect(detail.publish_button).to_have_count(0)
    expect(detail.edit_button).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_does_not_see_publish_or_edit_on_draft(
    own_draft_order: OrderResponse,
    supplier_manager_page,
    settings: Settings,
) -> None:
    detail = _open_detail(supplier_manager_page, own_draft_order, settings)
    expect(detail.publish_button).to_have_count(0)
    expect(detail.edit_button).to_have_count(0)
