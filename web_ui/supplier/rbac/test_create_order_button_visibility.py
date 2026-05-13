"""RBAC: only DISPATCHER sees «Создать заявку» on /orders.

Per matrix («Создать черновик»):
  SUPPLIER_ADMIN       → ❌
  SUPPLIER_DISPATCHER  → ✅
  SUPPLIER_MANAGER     → ❌

Hidden buttons aren't a security boundary by themselves (the API enforces
role on POST /api/v1/orders), but they ARE a UX guarantee — wrong roles
should not even be tempted to click. If this test fails, either the role
binding is wrong or the button started rendering for everyone.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings


def _create_order_link(page):
    """Match either the visible link or button — UI uses an <a> styled
    as a button."""
    return page.get_by_role("link", name="Создать заявку").or_(
        page.get_by_role("button", name="Создать заявку"),
    )


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_does_not_see_create_order(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/orders")
    expect(_create_order_link(supplier_admin_page)).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_sees_create_order_pointing_to_create_route(
    supplier_dispatcher_page, settings: Settings,
) -> None:
    supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/orders")
    link = _create_order_link(supplier_dispatcher_page)
    expect(link).to_be_visible()
    href = link.get_attribute("href") or ""
    assert href.endswith("/orders/create"), href


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_does_not_see_create_order(
    supplier_manager_page, settings: Settings,
) -> None:
    supplier_manager_page.goto(f"{settings.web_base_url_str}/orders")
    expect(_create_order_link(supplier_manager_page)).to_have_count(0)
