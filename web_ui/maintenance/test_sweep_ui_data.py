"""Maintenance sweep: wipe leaked `[E2E-UI]` data from shared accounts.

Purpose: even with autouse cleanup fixtures, a hard-killed test run
(Ctrl-C, OOM, network drop) can leave behind:
- warehouses tagged `[E2E-UI]`
- orders with `[E2E-UI]` cargo tags (and their referencing warehouses)
- vehicles with `UIT-` plate prefix

This file runs as a regular pytest with `@pytest.mark.maintenance` so
it stays out of the default suite. Trigger manually:

    pytest -m maintenance

Suggested cron: weekly on dev (e.g. Sunday 02:00 UTC) — keeps the
shared dataset from accumulating over months.
"""

from __future__ import annotations

import pytest

from api.client import ApiClient
from web_ui.seed.cleanup import (
    cancel_supplier_open_orders,
    wipe_supplier_warehouses,
    wipe_tk_vehicles,
)


@pytest.mark.maintenance
@pytest.mark.requires_real_account
def test_sweep_supplier_warehouses_and_orders(
    supplier_admin_api: ApiClient,
) -> None:
    """Cancel any [E2E-UI]-tagged open order, then wipe warehouses."""
    cancelled = cancel_supplier_open_orders(supplier_admin_api)
    deleted = wipe_supplier_warehouses(supplier_admin_api)
    print(
        f"\nMaintenance: cancelled {cancelled} orders, "
        f"deleted {deleted} warehouses",
    )


@pytest.mark.maintenance
@pytest.mark.requires_real_account
def test_sweep_tk_vehicles(tk_api: ApiClient) -> None:
    """Wipe UIT-prefixed test vehicles from the shared TK fleet."""
    deleted = wipe_tk_vehicles(tk_api)
    print(f"\nMaintenance: deleted {deleted} test vehicles")
