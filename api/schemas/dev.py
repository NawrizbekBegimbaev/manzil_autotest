"""Dev-only utilities — exist only on dev profile.

POST /api/v1/dev/drivers/wipe — full removal of a driver (DB + Keycloak).
Intended for cleanup between tests.
"""

from __future__ import annotations

from pydantic import Field

from api.schemas._base import ApiModel


class WipeDriverRequest(ApiModel):
    phone: str = Field(min_length=1, pattern=r"^\+[0-9]{10,15}$")
