"""Cleanup helpers — wipe `[E2E-UI-…]`-tagged data via the API.

UI tests run against the real shared accounts. To keep them stable across
runs we tag everything we create with a recognisable prefix and remove
matching items in test teardown. The API is faster, more reliable, and
already covered by its own tests, so we use it instead of clicking
«Удалить» in the UI.

Tagging convention:
    UI_TAG = "[E2E-UI]"

Anything whose name/title starts with this tag is fair game to delete.
"""

from __future__ import annotations

from api.client import ApiClient, ApiError
from api.endpoints import orders as ord_ep
from api.endpoints import vehicles as vh_ep
from api.endpoints import warehouses as wh_ep

UI_TAG = "[E2E-UI]"


def tagged_name(suffix: str) -> str:
    """Build a UI-test-tagged name. e.g. `tagged_name("WH 1")` →
    `"[E2E-UI] WH 1"`.
    """
    return f"{UI_TAG} {suffix}"


# ---------- Supplier-side cleanup -----------------------------------------


def wipe_supplier_warehouses(supplier_api: ApiClient) -> int:
    """Delete every warehouse owned by the caller whose name starts with
    UI_TAG. Returns the count deleted.
    """
    deleted = 0
    page = wh_ep.list_warehouses(supplier_api, page=0, size=100)
    for wh in page.content:
        if wh.name.startswith(UI_TAG):
            try:
                wh_ep.delete_warehouse(supplier_api, wh.id)
                deleted += 1
            except ApiError:
                # 409 expected when the warehouse is referenced by an active
                # order — leave it; the order cleanup pass should handle it.
                continue
    return deleted


def cancel_supplier_open_orders(supplier_api: ApiClient) -> int:
    """Cancel any non-terminal order whose cargo type starts with UI_TAG.

    Cargo type carries our tag; `status` filter on `list_orders` is
    backend-side, so we batch-cancel the small set we created.
    """
    deleted = 0
    page = ord_ep.list_orders(supplier_api, page=0, size=100)
    for order in page.content:
        cargo = getattr(order, "cargo_type", "") or ""
        if not cargo.startswith(UI_TAG):
            continue
        if order.status in {"completed", "cancelled"}:
            continue
        try:
            ord_ep.cancel_order(supplier_api, order.id)
            deleted += 1
        except ApiError:
            # 409 if status transition is invalid (e.g. already terminal);
            # skip — we tried our best.
            continue
    return deleted


# ---------- TK-side cleanup -----------------------------------------------


def wipe_tk_vehicles(tk_api: ApiClient) -> int:
    """Delete vehicles whose plate starts with the UI_TAG-mapped pattern."""
    deleted = 0
    page = vh_ep.list_vehicles(tk_api, page=0, size=100)
    for vehicle in page.content:
        # Plates are short — we use a plate-prefix marker UI_TAG_PLATE_PREFIX
        # set when creating in tests (e.g. "UIT-…"). Adjust here if the
        # marker convention changes.
        if vehicle.plate.startswith("UIT-"):
            try:
                vh_ep.remove_vehicle(tk_api, vehicle.id)
                deleted += 1
            except ApiError:
                continue
    return deleted
