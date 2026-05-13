"""Shared pydantic config for all Manzil API schemas.

API uses camelCase on the wire. We declare snake_case attributes paired with
camelCase aliases so tests can use Pythonic names while serialisation matches
the swagger contract.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base model for every request/response in the suite."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
