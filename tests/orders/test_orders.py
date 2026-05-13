"""Cargo orders CRUD + lifecycle (BRD US-6, US-7).

Lifecycle covered:
    POST → DRAFT → publish → ACTIVE → cancel → CANCELLED
                                    → (after offer-select) IN_PROGRESS → complete → COMPLETED

Roles:
- dispatcher: create / edit-draft / publish, only own orders
- manager / admin: list-all, cancel any non-terminal, complete IN_PROGRESS, select winner
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from api.client import ApiClient
from api.endpoints import orders as ord_ep
from api.schemas import (
    OrderCancelRequest,
    OrderUpdateRequest,
)
from data import builders

# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_create_order_as_draft(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    """SPECULATIVE: dispatcher role required per swagger; supplier admin
    is an admin, but not a dispatcher. If 403 here, see BUG report —
    backend either needs to allow admin to create orders or these tests
    need a dispatcher fixture (depends on full employee invite cycle)."""
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    assert created.status == "DRAFT"
    assert created.cargo_type == "Текстиль"
    assert created.pickup_warehouse_id == supplier_warehouse_id
    assert created.destination_warehouse_id == supplier_destination_warehouse_id
    assert created.load_address, "loadAddress must be snapshot from warehouse"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_create_order_with_publish_true_goes_active(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=True,
        ),
    )
    assert created.status == "ACTIVE"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_get_order_returns_full_payload(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    fetched = ord_ep.get_order(supplier_admin_client, created.id)
    assert fetched.id == created.id
    assert fetched.number == created.number


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_patch_draft_order_updates_fields(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    updated = ord_ep.update_draft_order(
        supplier_dispatcher_client,
        created.id,
        OrderUpdateRequest(cargo_type="Электроника", weight_kg=4500),
    )
    assert updated.cargo_type == "Электроника"
    assert updated.weight_kg == 4500


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_publish_draft_order_flips_to_active(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    published = ord_ep.publish_order(supplier_dispatcher_client, created.id)
    assert published.status == "ACTIVE"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_cancel_draft_order_with_reason(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    cancelled = ord_ep.cancel_order(
        supplier_dispatcher_client,
        created.id,
        OrderCancelRequest(reason="ИФ-тест: отмена"),
    )
    assert cancelled.status == "CANCELLED"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_orders_includes_just_created(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    page = ord_ep.list_orders(supplier_admin_client, status="DRAFT")
    assert created.id in {o.id for o in page.content}


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_orders_search_finds_by_number(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    page = ord_ep.list_orders(supplier_admin_client, search=created.number)
    assert created.id in {o.id for o in page.content}


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("cargoType", ""),
        ("weightKg", 0),
        ("weightKg", -100),
        ("volumeM3", 0),
        ("volumeM3", -1.0),
        ("bodyType", "wizard"),
        ("loadingMethods", []),
        ("currency", "RUB"),  # only USD/CNY per BRD §6 — SPECULATIVE
        ("destinationWarehouseId", ""),
    ],
)
def test_create_order_validation(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
    field: str,
    bad: object,
) -> None:
    body = builders.order_request(
        warehouse_id=supplier_warehouse_id,
        destination_warehouse_id=supplier_destination_warehouse_id,
    ).model_dump(
        by_alias=True, mode="json",
    )
    body[field] = bad
    with supplier_dispatcher_client.expect_error(400):
        supplier_dispatcher_client.post("/api/v1/orders", json=body, expect_status=201)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_create_order_with_unknown_warehouse_returns_404(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_destination_warehouse_id: UUID,
) -> None:
    body = builders.order_request(
        warehouse_id=uuid4(),
        destination_warehouse_id=supplier_destination_warehouse_id,
    ).model_dump(by_alias=True, mode="json")
    with supplier_dispatcher_client.expect_error(404):
        supplier_dispatcher_client.post("/api/v1/orders", json=body, expect_status=201)


@pytest.mark.negative
def test_create_order_without_token_returns_401(
    api_client: ApiClient,
) -> None:
    with api_client.expect_error(401):
        api_client.post(
            "/api/v1/orders",
            json={"cargoType": "x", "weightKg": 1, "volumeM3": 1},
            expect_status=201,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_publish_already_active_returns_409(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=True,
        ),
    )
    with supplier_dispatcher_client.expect_error(409):
        ord_ep.publish_order(supplier_dispatcher_client, created.id)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_patch_active_order_returns_409(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=True,
        ),
    )
    with supplier_dispatcher_client.expect_error(409):
        ord_ep.update_draft_order(
            supplier_dispatcher_client, created.id, OrderUpdateRequest(weight_kg=999),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_cancel_unknown_order_returns_404(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(404):
        ord_ep.cancel_order(supplier_admin_client, uuid4())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_double_cancel_returns_409(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    ord_ep.cancel_order(supplier_dispatcher_client, created.id)
    with supplier_dispatcher_client.expect_error(409):
        ord_ep.cancel_order(supplier_dispatcher_client, created.id)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_complete_order_not_in_progress_returns_409(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    with supplier_admin_client.expect_error(409):
        ord_ep.complete_order(supplier_admin_client, created.id)


# ---------- security -------------------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_cannot_get_order(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    """BOLA: cross-tenant order fetch must 404."""
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    with second_supplier_admin_client.expect_error(404):
        ord_ep.get_order(second_supplier_admin_client, created.id)


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_cannot_cancel_order(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    created = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    with second_supplier_admin_client.expect_error(404):
        ord_ep.cancel_order(second_supplier_admin_client, created.id)
