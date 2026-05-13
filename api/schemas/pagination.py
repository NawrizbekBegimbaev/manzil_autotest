"""Generic paginated response wrapper used by every list endpoint.

The backend returns a uniform shape:
    {"content": [...], "page": {page, size, totalElements, totalPages,
                                isFirst, isLast, isEmpty}}
where `page` is 1-indexed (per swagger note "Page numbers in the response
are 1-indexed").
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import Field

from api.schemas._base import ApiModel

T = TypeVar("T")


class PageMetadata(ApiModel):
    """Pagination metadata. `page` is 1-indexed in responses, 0-indexed in queries."""

    page: int
    size: int
    total_elements: int
    total_pages: int
    is_first: bool
    is_last: bool
    is_empty: bool


class PageResponse(ApiModel, Generic[T]):
    """Wrapper for any paginated list response."""

    content: list[T]
    page: PageMetadata = Field(alias="page")
