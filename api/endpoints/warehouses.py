"""Supplier warehouses CRUD (BRD US-19)."""

from __future__ import annotations

from uuid import UUID

from api.client import ApiClient
from api.schemas import (
    PageResponse,
    WarehouseRequest,
    WarehouseResponse,
)


def list_warehouses(
    client: ApiClient,
    *,
    active_only: bool = True,
    page: int = 0,
    size: int = 20,
    sort: str = "createdAt,DESC",
) -> PageResponse[WarehouseResponse]:
    """GET /api/v1/warehouses — paginated."""
    response = client.get(
        "/api/v1/warehouses",
        params={"activeOnly": str(active_only).lower(), "page": page, "size": size, "sort": sort},
        expect_status=200,
    )
    return PageResponse[WarehouseResponse].model_validate(response.json())


def create_warehouse(client: ApiClient, body: WarehouseRequest) -> WarehouseResponse:
    response = client.post(
        "/api/v1/warehouses",
        json=body.model_dump(by_alias=True),
        expect_status=201,
    )
    return WarehouseResponse.model_validate(response.json())


def update_warehouse(
    client: ApiClient,
    warehouse_id: UUID,
    body: WarehouseRequest,
) -> WarehouseResponse:
    response = client.put(
        f"/api/v1/warehouses/{warehouse_id}",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return WarehouseResponse.model_validate(response.json())


def delete_warehouse(client: ApiClient, warehouse_id: UUID) -> None:
    client.delete(f"/api/v1/warehouses/{warehouse_id}", expect_status=204)
