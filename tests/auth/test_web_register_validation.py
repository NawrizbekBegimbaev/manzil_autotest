"""POST /api/v1/auth/web/registrations/suppliers — field-by-field 400 sweep.

Each parametrized case overrides exactly one field with an invalid value.
Same coverage applies to /trucking-companies — keep this file the canonical
source and add a thin TK file later if rules diverge.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.client import ApiClient
from config.settings import Settings


def _baseline(email: str, phone: str, password: str) -> dict[str, Any]:
    return {
        "companyName": "Acme E2E",
        "tin": "200111222333",
        "email": email,
        "phone": phone,
        "fullName": "E2E Admin",
        "password": password,
    }


# Per the 2026-05-01 swagger:
#   tin   ^[0-9]{1,18}$              — anything 1..18 digits is valid
#   phone ^\+?[0-9 ()\-]{7,20}$      — flexible, plus sign optional
#   email standard RFC + jakarta @Email
#   pwd   ^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&*\-_+=,.?/]).{8,}$
_INVALID_FIELDS: list[tuple[str, str, Any]] = [
    ("companyName-empty", "companyName", ""),
    ("companyName-only-space", "companyName", "   "),
    ("tin-empty", "tin", ""),
    ("tin-non-numeric", "tin", "20011122233A"),
    ("tin-too-long", "tin", "1234567890123456789"),  # 19 digits — over the 18 cap
    ("email-no-at", "email", "no-at-sign.uz"),
    ("email-empty", "email", ""),
    ("phone-empty", "phone", ""),
    ("phone-letters", "phone", "ABCDEFGHIJ"),
    ("phone-too-short", "phone", "+1234"),  # 5 digits — under min 7
    ("password-too-short", "password", "Ab1!"),
    ("password-no-uppercase", "password", "lowercase1!"),
    ("password-no-digit", "password", "Password!"),
    ("password-no-symbol", "password", "Password1"),
    ("fullName-empty", "fullName", ""),
    ("fullName-too-short", "fullName", "A"),  # below min 2
]


@pytest.mark.negative
@pytest.mark.parametrize(
    ("case_id", "field", "bad_value"),
    _INVALID_FIELDS,
    ids=[c[0] for c in _INVALID_FIELDS],
)
def test_supplier_registration_field_validation(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    case_id: str,
    field: str,
    bad_value: Any,
) -> None:
    """Send a single invalid field; expect 400 ProblemDetail."""
    body = _baseline(email_from_pool, phone_from_pool, settings.default_test_password)
    body[field] = bad_value
    with api_client.expect_error(400) as errors:
        api_client.post(
            "/api/v1/auth/web/registrations/suppliers",
            json=body,
            expect_status=204,
        )
    assert errors[0].problem is not None, f"case {case_id}: missing ProblemDetail"


@pytest.mark.negative
@pytest.mark.parametrize(
    "missing",
    ["companyName", "tin", "email", "phone", "fullName", "password"],
)
def test_supplier_registration_required_fields(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
    missing: str,
) -> None:
    """Drop one required field at a time — server returns 400."""
    body = _baseline(email_from_pool, phone_from_pool, settings.default_test_password)
    body.pop(missing)
    with api_client.expect_error(400):
        api_client.post(
            "/api/v1/auth/web/registrations/suppliers",
            json=body,
            expect_status=204,
        )


@pytest.mark.negative
def test_supplier_registration_handles_unknown_field(
    api_client: ApiClient,
    settings: Settings,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """Strict-mode contract: unknown fields should EITHER 400 OR be silently
    dropped. Either is acceptable. Anything else (200 with the field
    persisted, 5xx) is a defect — see BUG-011 in bug.txt."""
    body = _baseline(email_from_pool, phone_from_pool, settings.default_test_password)
    body["maliciousField"] = "<script>alert(1)</script>"
    response = api_client._client.post(
        "/api/v1/auth/web/registrations/suppliers",
        json=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert response.status_code in (204, 400), response.text
