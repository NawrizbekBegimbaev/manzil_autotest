"""Registration and password-reset payloads.

Web flows (supplier admin / TK admin) use email + 6-digit email OTP.
Mobile flow (driver) uses phone + Telegram deeplink + 6-digit Telegram OTP +
final profile submit.
"""

from __future__ import annotations

from datetime import date

from pydantic import EmailStr, Field

from api.schemas._base import ApiModel

# ---------- Web registration (supplier + trucking-company) ----------------


class _WebRegistrationBase(ApiModel):
    """Shared body for both web registration variants — same shape per swagger."""

    company_name: str = Field(min_length=1)
    tin: str = Field(min_length=12, max_length=12, pattern=r"^\d{12}$")
    email: EmailStr
    phone: str
    full_name: str
    password: str


class SupplierRegistrationRequest(_WebRegistrationBase):
    """POST /api/v1/auth/web/registrations/suppliers."""


class TruckingCompanyRegistrationRequest(_WebRegistrationBase):
    """POST /api/v1/auth/web/registrations/trucking-companies."""


class VerifyWebOtpRequest(ApiModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# ---------- Web password reset --------------------------------------------


class WebPasswordResetStartRequest(ApiModel):
    email: EmailStr


class WebPasswordResetConfirmRequest(ApiModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str


# ---------- Mobile (driver) registration ----------------------------------


class DriverRegistrationStartRequest(ApiModel):
    phone: str


class DriverRegistrationStartResponse(ApiModel):
    telegram_deep_link: str


class VerifyMobileOtpRequest(ApiModel):
    phone: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class DriverLicense(ApiModel):
    number: str
    series: str
    issued_at: date
    expires_at: date


class DriverVehicle(ApiModel):
    make: str
    model: str
    license_plate: str
    body_type: str
    capacity_kg: int = Field(gt=0)
    volume_m3: float = Field(gt=0)
    additional_features: str | None = None


class CompleteDriverRegistrationRequest(ApiModel):
    phone: str
    full_name: str
    password: str
    city: str
    geolocation_consented: bool
    license: DriverLicense
    vehicle: DriverVehicle


# ---------- Mobile password reset (3-step) --------------------------------


class MobilePasswordResetStartRequest(ApiModel):
    phone: str


class MobilePasswordResetVerifyRequest(ApiModel):
    """POST /api/v1/auth/mobile/password-resets/verify — exchanges OTP for a
    one-shot reset token (~10 min TTL)."""

    phone: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MobilePasswordResetVerifyResponse(ApiModel):
    reset_token: str


class MobilePasswordResetConfirmRequest(ApiModel):
    """POST /api/v1/auth/mobile/password-resets/confirm — replays the reset
    token from /verify together with the new password. Note: per the new
    contract this no longer takes phone+code directly."""

    reset_token: str
    new_password: str
