"""TK fleet CRUD (BRD US-3)."""

from __future__ import annotations

from uuid import UUID

from api.client import ApiClient
from api.schemas import PageResponse, VehicleRequest, VehicleResponse


def list_vehicles(
    client: ApiClient,
    *,
    page: int = 0,
    size: int = 20,
    sort: str = "createdAt,DESC",
) -> PageResponse[VehicleResponse]:
    """GET /api/v1/vehicles — paginated TK fleet."""
    response = client.get(
        "/api/v1/vehicles",
        params={"page": page, "size": size, "sort": sort},
        expect_status=200,
    )
    return PageResponse[VehicleResponse].model_validate(response.json())


def add_vehicle(client: ApiClient, body: VehicleRequest) -> VehicleResponse:
    response = client.post(
        "/api/v1/vehicles",
        json=body.model_dump(by_alias=True),
        expect_status=201,
    )
    return VehicleResponse.model_validate(response.json())


def update_vehicle(
    client: ApiClient,
    vehicle_id: UUID,
    body: VehicleRequest,
) -> VehicleResponse:
    response = client.put(
        f"/api/v1/vehicles/{vehicle_id}",
        json=body.model_dump(by_alias=True),
        expect_status=200,
    )
    return VehicleResponse.model_validate(response.json())


def remove_vehicle(client: ApiClient, vehicle_id: UUID) -> None:
    client.delete(f"/api/v1/vehicles/{vehicle_id}", expect_status=204)
