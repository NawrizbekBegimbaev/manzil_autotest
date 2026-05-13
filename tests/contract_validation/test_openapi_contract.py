"""OpenAPI-spec-driven contract validation via schemathesis.

This is the closest you can get to "100% contract coverage": for every
endpoint declared in the published spec, schemathesis auto-generates
inputs (per the schema constraints), sends them, and asserts that the
responses match what the spec promises (status codes, headers,
content types, body schema).

Practical caveats:
- swagger UI is gated by oauth2-proxy on dev, so direct fetch of
  `/v3/api-docs` returns 302 — schemathesis can't introspect.
- A simple workaround is to commit a snapshot:
      curl -L https://dev-manzil.greatmall.uz/v3/api-docs > tests/contract_validation/openapi.json
  (after authenticating in the browser) — then point schemathesis at the
  file. Until that snapshot exists, the fuzz test skips with a clear
  reason.

Run on demand:
    pytest -m schemathesis -p no:cacheprovider --tb=short
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import Settings


def _try_fetch_spec(settings: Settings) -> dict[str, object] | None:
    """Attempt to fetch the OpenAPI document; return None if gated."""
    import httpx

    base = settings.api_base_url_str
    try:
        response = httpx.get(
            f"{base}/v3/api-docs",
            headers={"Accept": "application/json"},
            follow_redirects=False,
            timeout=10,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        spec = response.json()
    except ValueError:
        return None
    return spec if isinstance(spec, dict) else None


def _spec_snapshot_path(settings: Settings) -> Path:
    """Where a committed snapshot would live (gitignored if it has secrets)."""
    return settings.project_root / "tests" / "contract_validation" / "openapi.json"


@pytest.mark.schemathesis
def test_openapi_spec_is_machine_readable(settings: Settings) -> None:
    """Sanity: the spec is accessible and parseable.

    Three sources, in order:
        1. Direct fetch from `/v3/api-docs` (skips on 302 gate).
        2. Snapshot at `tests/contract_validation/openapi.json`.
        3. Skip with a clear message.
    """
    spec = _try_fetch_spec(settings)
    if spec is None:
        snapshot = _spec_snapshot_path(settings)
        if snapshot.exists():
            import json
            spec = json.loads(snapshot.read_text())
    if spec is None:
        pytest.skip(
            "OpenAPI spec not directly accessible (likely behind oauth2-proxy) "
            f"and no snapshot at {_spec_snapshot_path(settings)}. "
            "Authenticate in browser, save the JSON, and re-run.",
        )
    openapi = spec.get("openapi")
    assert isinstance(openapi, str), spec.get("openapi")
    assert openapi.startswith("3."), openapi
    paths = spec.get("paths") or {}
    assert paths, "spec has no paths"


@pytest.mark.schemathesis
@pytest.mark.slow
def test_schemathesis_fuzz_disabled_until_spec_snapshot_exists(
    settings: Settings,
) -> None:
    """Schemathesis-driven fuzzing — placeholder that explains how to enable.

    On dev the spec is gated by oauth2-proxy, so this test cannot run
    without a committed snapshot. Once `tests/contract_validation/
    openapi.json` is present, replace this body with the actual fuzz loop.

    Reference implementation (lives in git history) — uncomment after the
    snapshot lands:

        import schemathesis
        schema = schemathesis.openapi.from_path(
            _spec_snapshot_path(settings), base_url=settings.api_base_url_str,
        )
        for operation in schema.get_all_operations():
            ... fuzz, validate_response, collect failures ...
    """
    if not _spec_snapshot_path(settings).exists():
        pytest.skip(
            "OpenAPI snapshot not committed. To enable, run: "
            f"curl -L {settings.api_base_url_str}/v3/api-docs "
            f"> {_spec_snapshot_path(settings)} (after authenticating).",
        )
    pytest.skip("Snapshot found but fuzz loop not yet wired in — TODO once dev creds available.")
