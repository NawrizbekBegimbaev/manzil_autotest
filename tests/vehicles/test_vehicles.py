"""TK fleet CRUD (BRD US-3) — TK admin only."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.client import ApiClient
from api.endpoints import vehicles as vh_ep
from api.schemas import BODY_TYPES, VehicleRequest
from data import builders

# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_add_vehicle_returns_201(tk_admin_client: ApiClient) -> None:
    created = vh_ep.add_vehicle(tk_admin_client, builders.vehicle(plate="01A001BC"))
    assert created.brand == "Volvo"
    assert created.body_type == "TENT"
    assert created.capacity_kg == 20000


@pytest.mark.positive
@pytest.mark.requires_email_otp
@pytest.mark.parametrize("body_type", BODY_TYPES)
def test_add_vehicle_with_each_body_type(
    tk_admin_client: ApiClient,
    body_type: str,
) -> None:
    """All BRD body types must be accepted."""
    created = vh_ep.add_vehicle(
        tk_admin_client,
        builders.vehicle(plate=f"01{body_type[:1].upper()}001BC", body_type=body_type),
    )
    assert created.body_type == body_type


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_list_vehicles_includes_added(
    tk_admin_client: ApiClient,
) -> None:
    created = vh_ep.add_vehicle(tk_admin_client, builders.vehicle(plate="01L002BC"))
    page = vh_ep.list_vehicles(tk_admin_client)
    assert created.id in {v.id for v in page.content}


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_update_vehicle_replaces_fields(
    tk_admin_client: ApiClient,
) -> None:
    created = vh_ep.add_vehicle(tk_admin_client, builders.vehicle(plate="01U003BC"))
    updated = vh_ep.update_vehicle(
        tk_admin_client,
        created.id,
        VehicleRequest(
            brand="Mercedes-Benz",
            model="Actros",
            plate="01U003BC",
            body_type="REFRIGERATOR",
            capacity_kg=18000,
            volume_m3=70,
            notes="cold chain",
        ),
    )
    assert updated.brand == "Mercedes-Benz"
    assert updated.body_type == "REFRIGERATOR"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_remove_vehicle_returns_204(
    tk_admin_client: ApiClient,
) -> None:
    created = vh_ep.add_vehicle(tk_admin_client, builders.vehicle(plate="01D004BC"))
    vh_ep.remove_vehicle(tk_admin_client, created.id)


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("brand", ""),
        ("model", ""),
        ("plate", "X"),  # below min 2
        ("capacityKg", 0),
        ("capacityKg", -1),
        ("volumeM3", 0),
        ("volumeM3", -0.5),
        ("bodyType", "wizard"),
    ],
)
def test_add_vehicle_validation_returns_400(
    tk_admin_client: ApiClient,
    field: str,
    bad: object,
) -> None:
    body = builders.vehicle(plate="01V998BC").model_dump(by_alias=True)
    body[field] = bad
    with tk_admin_client.expect_error(400):
        tk_admin_client.post("/api/v1/vehicles", json=body, expect_status=201)


@pytest.mark.negative
def test_add_vehicle_without_token_returns_401(api_client: ApiClient) -> None:
    with api_client.expect_error(401):
        vh_ep.add_vehicle(api_client, builders.vehicle(plate="01N005BC"))


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_add_vehicle_as_supplier_admin_returns_403(
    supplier_admin_client: ApiClient,
) -> None:
    with supplier_admin_client.expect_error(403):
        vh_ep.add_vehicle(supplier_admin_client, builders.vehicle(plate="01F006BC"))


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_update_unknown_vehicle_returns_404(tk_admin_client: ApiClient) -> None:
    with tk_admin_client.expect_error(404):
        vh_ep.update_vehicle(tk_admin_client, uuid4(), builders.vehicle())


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_remove_unknown_vehicle_returns_404(tk_admin_client: ApiClient) -> None:
    with tk_admin_client.expect_error(404):
        vh_ep.remove_vehicle(tk_admin_client, uuid4())
