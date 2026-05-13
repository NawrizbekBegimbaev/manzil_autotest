"""Test-data builders — produce pydantic request models with sane defaults.

Every builder accepts keyword overrides so a test can mutate one field while
the rest stays valid. Without these, tests redundantly spell out 6+ fields
just to exercise one boundary, which obscures intent.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from api.schemas import (
    CompleteDriverRegistrationRequest,
    DriverLicense,
    DriverVehicle,
    InviteEmployeeRequest,
    OfferRequest,
    OrderRequest,
    SupplierRegistrationRequest,
    TruckingCompanyRegistrationRequest,
    VehicleRequest,
    WarehouseRequest,
)
from data.constants import E2E_PREFIX
from utils.tin_generator import generate_tin


def supplier_registration(
    *,
    email: str,
    phone: str,
    password: str,
    company_name: str | None = None,
    tin: str | None = None,
    full_name: str = "E2E Supplier Admin",
    **overrides: Any,
) -> SupplierRegistrationRequest:
    payload = {
        "company_name": company_name or f"{E2E_PREFIX} Supplier {phone[-4:]}",
        "tin": tin or generate_tin(),
        "email": email,
        "phone": phone,
        "full_name": full_name,
        "password": password,
    }
    payload.update(overrides)
    return SupplierRegistrationRequest.model_validate(payload)


def trucking_company_registration(
    *,
    email: str,
    phone: str,
    password: str,
    company_name: str | None = None,
    tin: str | None = None,
    full_name: str = "E2E TK Admin",
    **overrides: Any,
) -> TruckingCompanyRegistrationRequest:
    payload = {
        "company_name": company_name or f"{E2E_PREFIX} TK {phone[-4:]}",
        "tin": tin or generate_tin(),
        "email": email,
        "phone": phone,
        "full_name": full_name,
        "password": password,
    }
    payload.update(overrides)
    return TruckingCompanyRegistrationRequest.model_validate(payload)


def employee_invite(
    *,
    email: str,
    full_name: str = "E2E Invited Employee",
    role: str = "SUPPLIER_MANAGER",
) -> InviteEmployeeRequest:
    return InviteEmployeeRequest(email=email, full_name=full_name, role=role)


def driver_complete_registration(
    *,
    phone: str,
    password: str,
    full_name: str = "E2E Driver",
    city: str = "Tashkent",
    geolocation_consented: bool = True,
    **overrides: Any,
) -> CompleteDriverRegistrationRequest:
    today = date.today()
    payload = {
        "phone": phone,
        "full_name": full_name,
        "password": password,
        "city": city,
        "geolocation_consented": geolocation_consented,
        "license": DriverLicense(
            number="AB1234567",
            series="AB",
            issued_at=today - timedelta(days=365 * 3),
            expires_at=today + timedelta(days=365 * 5),
        ),
        "vehicle": DriverVehicle(
            make="Mercedes-Benz",
            model="Actros",
            license_plate=f"01 A {phone[-3:]} BC",
            body_type="TENT",
            capacity_kg=5000,
            volume_m3=20.5,
            additional_features="refrigerator",
        ),
    }
    payload.update(overrides)
    return CompleteDriverRegistrationRequest.model_validate(payload)


# ---------- new builders for Warehouses / Vehicles / Orders / Offers ------


def warehouse(
    *,
    name: str | None = None,
    city: str = "Tashkent",
    address: str = "ул. Амира Темура, 45",
    active: bool = True,
) -> WarehouseRequest:
    return WarehouseRequest(
        name=name or f"{E2E_PREFIX} WH",
        city=city,
        address=address,
        active=active,
    )


def vehicle(
    *,
    brand: str = "Volvo",
    model: str = "FH16",
    plate: str | None = None,
    body_type: str = "TENT",
    capacity_kg: float = 20000,
    volume_m3: float = 86,
    notes: str | None = None,
) -> VehicleRequest:
    """Body type — backend enum is UPPERCASE since the 2026-05-04 release
    (TENT/REEFER/ISOTHERM/CONTAINER/LOW_PLATFORM/OTHER).
    """
    return VehicleRequest(
        brand=brand,
        model=model,
        plate=plate or "01A123BC",
        body_type=body_type,
        capacity_kg=capacity_kg,
        volume_m3=volume_m3,
        notes=notes,
    )


def order_request(
    *,
    warehouse_id: Any,
    destination_warehouse_id: Any,
    publish: bool = True,
    cargo_type: str = "Текстиль",
    weight_kg: float = 3200,
    volume_m3: float = 18,
    body_type: str = "TENT",
    loading_methods: list[str] | None = None,
    desired_date: date | None = None,
    currency: str = "USD",
    notes: str = "",
) -> OrderRequest:
    return OrderRequest(
        cargo_type=cargo_type,
        weight_kg=weight_kg,
        volume_m3=volume_m3,
        body_type=body_type,
        loading_methods=loading_methods or ["SIDE"],
        pickup_warehouse_id=warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        desired_date=desired_date or (date.today() + timedelta(days=10)),
        currency=currency,
        notes=notes,
        publish=publish,
    )


def offer_request(
    *,
    price: float = 1500,
    currency: str = "USD",
    comment: str | None = None,
) -> OfferRequest:
    return OfferRequest(price=price, currency=currency, comment=comment)
