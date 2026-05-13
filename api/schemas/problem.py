"""RFC 9457 ProblemDetail body — every 4xx/5xx returns this.

The swagger declares `properties` as an open dict for field-level errors and
similar diagnostic data. Treat it as `dict[str, Any]` and validate per call.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from api.schemas._base import ApiModel


class ProblemDetail(ApiModel):
    """RFC 9457 ProblemDetail body returned for non-2xx responses."""

    # Override base config — server emits a free-form `properties` dict that
    # may include arbitrary extras, so `extra="forbid"` is too strict here.
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    type: str | None = None
    title: str | None = None
    status: int | None = None
    detail: str | None = None
    instance: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
