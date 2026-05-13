"""API setup helpers for mobile tests.

Wave 0 only provides the shared anonymous client factory. Driver and order
seeders will be added once the real app flows are known.
"""

from __future__ import annotations

from api.client import ApiClient
from config.settings import Settings


def make_anonymous_client(settings: Settings) -> ApiClient:
    """Create a fresh API client without an auth token."""
    return ApiClient(settings)
