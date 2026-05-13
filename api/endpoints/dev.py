"""Dev-only utilities — these endpoints exist only on the dev profile."""

from __future__ import annotations

from api.client import ApiClient
from api.schemas import WipeDriverRequest


def wipe_driver(client: ApiClient, body: WipeDriverRequest) -> None:
    """POST /api/v1/dev/drivers/wipe — full removal of a driver from DB + Keycloak.

    Used in test cleanup so phone numbers can be reused. Returns 204 even
    when no such driver exists (idempotent).
    """
    client.post(
        "/api/v1/dev/drivers/wipe",
        json=body.model_dump(by_alias=True),
        expect_status=204,
    )
