"""Action buttons on «Активна» order with at least one offer.

Per matrix on an offer attached to an Active order:
  ADMIN   ✅ «Выбрать победителя», «Заметка»
  MANAGER ✅ «Выбрать победителя», «Заметка»
  TK      ❌ (only sees own offers in /offers)

Live recon (2026-05-03):
  ADMIN   sees nothing on the offer card (no «Заметка», no «Выбрать»)
  MANAGER sees only «Заметка». No «Выбрать победителя».

So:
  - «Выбрать победителя» missing for both ADMIN and MANAGER → xfail
  - ADMIN's «Заметка» missing → xfail
  - MANAGER's «Заметка» present → regular passing test
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from api.schemas import OrderResponse
from config.settings import Settings

_BUG_017 = pytest.mark.xfail(
    reason="BUG-017: missing offer-card actions in UI. Removes when frontend ships.",
    strict=False,
)


def _goto_detail(page, order: OrderResponse, settings: Settings) -> None:
    page.goto(f"{settings.web_base_url_str}/orders/{order.id}")
    expect(page.get_by_role("heading", name="Предложения")).to_be_visible(
        timeout=15_000,
    )


# ---------- «Выбрать победителя» — missing for both ADMIN and MANAGER ----


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_sees_select_winner_button_on_offer_card(
    active_order_with_offer: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    _goto_detail(supplier_admin_page, active_order_with_offer, settings)
    expect(
        supplier_admin_page.get_by_role("button", name="Выбрать победителя"),
    ).to_be_visible()


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_sees_select_winner_button_on_offer_card(
    active_order_with_offer: OrderResponse,
    supplier_manager_page,
    settings: Settings,
) -> None:
    _goto_detail(supplier_manager_page, active_order_with_offer, settings)
    expect(
        supplier_manager_page.get_by_role("button", name="Выбрать победителя"),
    ).to_be_visible()


# ---------- «Заметка» — MANAGER ✅ (current), ADMIN missing -------------


@_BUG_017
@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_sees_note_button_on_offer_card(
    active_order_with_offer: OrderResponse,
    supplier_admin_page,
    settings: Settings,
) -> None:
    _goto_detail(supplier_admin_page, active_order_with_offer, settings)
    expect(
        supplier_admin_page.get_by_role("button", name="Заметка"),
    ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_sees_note_button_on_offer_card(
    active_order_with_offer: OrderResponse,
    supplier_manager_page,
    settings: Settings,
) -> None:
    """MANAGER currently has «Заметка» (verified live). Pin it so a
    future regression (removing it) is caught."""
    _goto_detail(supplier_manager_page, active_order_with_offer, settings)
    expect(
        supplier_manager_page.get_by_role("button", name="Заметка"),
    ).to_be_visible()


# ---------- DISPATCHER negative (no actions ever) ------------------------


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_sees_no_offer_actions(
    active_order_with_offer: OrderResponse,
    supplier_dispatcher_page,
    settings: Settings,
) -> None:
    _goto_detail(supplier_dispatcher_page, active_order_with_offer, settings)
    for action in ("Выбрать победителя", "Заметка"):
        expect(
            supplier_dispatcher_page.get_by_role("button", name=action),
        ).to_have_count(0)
