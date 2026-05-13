"""RBAC: each Supplier sub-role sees the right sidebar items.

Live recon (2026-05-03) per matrix:
  SUPPLIER_ADMIN       → Аналитика, Заявки, Склады, Сотрудники   (4)
  SUPPLIER_DISPATCHER  → Заявки, Склады                          (2)
  SUPPLIER_MANAGER     → Заявки                                  (1)

Landing page also differs:
  ADMIN      → /dashboard
  DISPATCHER → /orders
  MANAGER    → /orders

These two facts together ARE the role-binding test: the Keycloak realm
role determines which menu and which page the user sees. If Keycloak
ever drops a role, the wrong sidebar appears and these tests fail.
"""

from __future__ import annotations

import pytest

from config.settings import Settings
from web_ui.pages._common.sidebar import Sidebar


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_admin_lands_on_dashboard_with_admin_sidebar(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    Sidebar(supplier_admin_page).expect_supplier_admin()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_dispatcher_lands_on_orders_with_dispatcher_sidebar(
    supplier_dispatcher_page, settings: Settings,
) -> None:
    supplier_dispatcher_page.goto(f"{settings.web_base_url_str}/orders")
    Sidebar(supplier_dispatcher_page).expect_supplier_dispatcher()


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_manager_lands_on_orders_with_manager_sidebar(
    supplier_manager_page, settings: Settings,
) -> None:
    supplier_manager_page.goto(f"{settings.web_base_url_str}/orders")
    Sidebar(supplier_manager_page).expect_supplier_manager()
