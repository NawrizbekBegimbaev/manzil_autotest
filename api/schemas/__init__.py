"""Pydantic v2 models for Manzil API request/response payloads.

Field names mirror the swagger camelCase exactly — `model_config` enables
both alias-by-name and alias-by-value, so tests can construct models with
snake_case OR camelCase. JSON serialisation always emits camelCase via
`model_dump(by_alias=True)` in `api/client.py`.
"""

from api.schemas.auth import (
    AcceptInvitationRequest,
    LogoutRequest,
    MobileLoginRequest,
    RefreshRequest,
    TokenResponse,
    WebLoginRequest,
)
from api.schemas.dev import WipeDriverRequest
from api.schemas.employees import (
    EmployeeResponse,
    InviteEmployeeRequest,
    UpdateEmployeeRequest,
)
from api.schemas.feed import FeedQuery
from api.schemas.offers import (
    OFFER_STATUSES,
    OfferNoteRequest,
    OfferRequest,
    OfferResponse,
    OfferUpdateRequest,
)
from api.schemas.orders import (
    BODY_TYPES,
    CURRENCIES,
    LOADING_METHODS,
    ORDER_STATUSES,
    OrderCancelRequest,
    OrderRequest,
    OrderResponse,
    OrderUpdateRequest,
)
from api.schemas.pagination import PageMetadata, PageResponse
from api.schemas.problem import ProblemDetail
from api.schemas.registration import (
    CompleteDriverRegistrationRequest,
    DriverLicense,
    DriverRegistrationStartRequest,
    DriverRegistrationStartResponse,
    DriverVehicle,
    MobilePasswordResetConfirmRequest,
    MobilePasswordResetStartRequest,
    MobilePasswordResetVerifyRequest,
    MobilePasswordResetVerifyResponse,
    SupplierRegistrationRequest,
    TruckingCompanyRegistrationRequest,
    VerifyMobileOtpRequest,
    VerifyWebOtpRequest,
    WebPasswordResetConfirmRequest,
    WebPasswordResetStartRequest,
)
from api.schemas.user import (
    ROLES,
    CurrentUserResponse,
    DriverBlock,
    DriverLicenseBlock,
    DriverVehicleBlock,
    OrganizationBlock,
    ProfileBlock,
    UpdateDriverProfileRequest,
    UpdateProfileRequest,
)
from api.schemas.vehicles import VehicleRequest, VehicleResponse
from api.schemas.warehouses import WarehouseRequest, WarehouseResponse

__all__ = [
    "BODY_TYPES",
    "CURRENCIES",
    "LOADING_METHODS",
    "OFFER_STATUSES",
    "ORDER_STATUSES",
    "ROLES",
    "AcceptInvitationRequest",
    "CompleteDriverRegistrationRequest",
    "CurrentUserResponse",
    "DriverBlock",
    "DriverLicense",
    "DriverLicenseBlock",
    "DriverRegistrationStartRequest",
    "DriverRegistrationStartResponse",
    "DriverVehicle",
    "DriverVehicleBlock",
    "EmployeeResponse",
    "FeedQuery",
    "InviteEmployeeRequest",
    "LogoutRequest",
    "MobileLoginRequest",
    "MobilePasswordResetConfirmRequest",
    "MobilePasswordResetStartRequest",
    "MobilePasswordResetVerifyRequest",
    "MobilePasswordResetVerifyResponse",
    "OfferNoteRequest",
    "OfferRequest",
    "OfferResponse",
    "OfferUpdateRequest",
    "OrderCancelRequest",
    "OrderRequest",
    "OrderResponse",
    "OrderUpdateRequest",
    "OrganizationBlock",
    "PageMetadata",
    "PageResponse",
    "ProblemDetail",
    "ProfileBlock",
    "RefreshRequest",
    "SupplierRegistrationRequest",
    "TokenResponse",
    "TruckingCompanyRegistrationRequest",
    "UpdateDriverProfileRequest",
    "UpdateEmployeeRequest",
    "UpdateProfileRequest",
    "VehicleRequest",
    "VehicleResponse",
    "VerifyMobileOtpRequest",
    "VerifyWebOtpRequest",
    "WarehouseRequest",
    "WarehouseResponse",
    "WebLoginRequest",
    "WebPasswordResetConfirmRequest",
    "WebPasswordResetStartRequest",
    "WipeDriverRequest",
]
