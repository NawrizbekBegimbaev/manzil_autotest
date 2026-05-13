"""Supplier warehouses CRUD (BRD US-19).

Roles per swagger:
- create / update / delete / list — supplier admin OR dispatcher (403 otherwise)

Soft-delete: `deleted_at` is set, so historical orders that reference the
warehouse still resolve via load-address snapshot on the order row.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.client import ApiClient
from api.endpoints import warehouses as wh_ep
from api.schemas import WarehouseRequest, WarehouseResponse
from data import builders

# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_create_warehouse_returns_201_with_payload(
    supplier_admin_client: ApiClient,
) -> None:
    created = wh_ep.create_warehouse(
        supplier_admin_client,
        builders.warehouse(name="[E2E] Tashkent-North"),
    )
    assert created.name == "[E2E] Tashkent-North"
    assert created.active is True
    assert created.organization_id


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_warehouses_includes_just_created(
    supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    page = wh_ep.list_warehouses(supplier_admin_client)
    ids = {w.id for w in page.content}
    assert supplier_warehouse.id in ids
    assert page.page.size == 20
    assert page.page.page == 1  # 1-indexed in response


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_update_warehouse_replaces_fields(
    supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    updated = wh_ep.update_warehouse(
        supplier_admin_client,
        supplier_warehouse.id,
        WarehouseRequest(
            name="[E2E] Renamed",
            city="Samarkand",
            address="ул. Регистан 1",
            active=False,
        ),
    )
    assert updated.name == "[E2E] Renamed"
    assert updated.city == "Samarkand"
    assert updated.active is False


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_delete_warehouse_returns_204(
    supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    wh_ep.delete_warehouse(supplier_admin_client, supplier_warehouse.id)


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.edge_case
def test_inactive_warehouse_visible_with_active_only_false(
    supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    """`activeOnly=false` must include archived rows; default true hides them."""
    wh_ep.update_warehouse(
        supplier_admin_client,
        supplier_warehouse.id,
        WarehouseRequest(
            name=supplier_warehouse.name,
            city=supplier_warehouse.city,
            address=supplier_warehouse.address,
            active=False,
        ),
    )
    only_active = wh_ep.list_warehouses(supplier_admin_client, active_only=True)
    assert supplier_warehouse.id not in {w.id for w in only_active.content}
    full = wh_ep.list_warehouses(supplier_admin_client, active_only=False)
    assert supplier_warehouse.id in {w.id for w in full.content}


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        ({"name": "", "city": "X", "address": "Addr 1", "active": True}, "name-empty"),
        ({"name": "X", "city": "X", "address": "Addr 1", "active": True}, "name-too-short"),
        ({"name": "OK", "city": "", "address": "Addr 1", "active": True}, "city-empty"),
        ({"name": "OK", "city": "X", "address": "ab", "active": True}, "address-too-short"),
        ({"name": "OK", "city": "X", "address": "A" * 1000, "active": True}, "address-too-long"),
        ({"city": "X", "address": "Addr 1", "active": True}, "missing-name"),
    ],
)
@pytest.mark.requires_email_otp
def test_create_warehouse_validation_returns_400(
    supplier_admin_client: ApiClient,
    payload: dict[str, object],
    case_id: str,
) -> None:
    with supplier_admin_client.expect_error(400):
        supplier_admin_client.post(
            "/api/v1/warehouses",
            json=payload,
            expect_status=201,
        )


@pytest.mark.negative
def test_create_warehouse_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        wh_ep.create_warehouse(api_client, builders.warehouse())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_create_warehouse_as_tk_admin_returns_403(
    tk_admin_client: ApiClient,
) -> None:
    with tk_admin_client.expect_error(403):
        wh_ep.create_warehouse(tk_admin_client, builders.warehouse())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_unknown_warehouse_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        wh_ep.update_warehouse(supplier_admin_client, uuid4(), builders.warehouse())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_delete_unknown_warehouse_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        wh_ep.delete_warehouse(supplier_admin_client, uuid4())


# ---------- security: BOLA ------------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_cannot_update_warehouse(
    second_supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    """Cross-tenant write must 404 (not 403 — avoid existence leak)."""
    with second_supplier_admin_client.expect_error(404):
        wh_ep.update_warehouse(
            second_supplier_admin_client,
            supplier_warehouse.id,
            builders.warehouse(name="hacked"),
        )


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_cannot_delete_warehouse(
    second_supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    with second_supplier_admin_client.expect_error(404):
        wh_ep.delete_warehouse(second_supplier_admin_client, supplier_warehouse.id)


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_does_not_see_warehouse_in_list(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    supplier_warehouse: WarehouseResponse,
) -> None:
    visible = wh_ep.list_warehouses(second_supplier_admin_client)
    assert supplier_warehouse.id not in {w.id for w in visible.content}
