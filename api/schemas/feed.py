"""Carrier feed query params (US-8 TK / US-10 driver).

Reuses `OrderResponse` as the content type — feed items are orders matched
against the caller's fleet bodyType.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from api.schemas._base import ApiModel


class FeedQuery(ApiModel):
    """Query parameters for GET /api/v1/feed."""

    body_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=200)
    sort: list[str] = Field(default_factory=lambda: ["desiredDateFrom,ASC"])

    def to_query(self) -> dict[str, object]:
        """Pack into httpx-friendly dict, dropping unset fields."""
        params: dict[str, object] = {"page": self.page, "size": self.size}
        if self.body_type is not None:
            params["bodyType"] = self.body_type
        if self.date_from is not None:
            params["dateFrom"] = self.date_from.isoformat()
        if self.date_to is not None:
            params["dateTo"] = self.date_to.isoformat()
        if self.sort:
            params["sort"] = self.sort
        return params
