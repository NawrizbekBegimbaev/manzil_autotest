"""JWT-token attacks against the resource server.

These tests do not need a real JWT-crafting library — most attacks succeed
even with structurally-broken tokens because Keycloak's middleware should
reject them at the signature check. We do NOT generate valid signed tokens
(would need the realm's private key); instead we feed:
- structurally invalid tokens (wrong segments, base64 garbage)
- tokens with `alg: none` (a classic JWT trap from the early days)
- truncated / re-signed tokens
- tokens with a bogus realm/issuer

Every one of these MUST yield 401.
"""

from __future__ import annotations

import base64
import json

import pytest

from api.client import ApiClient


def _b64url(payload: dict[str, object] | bytes) -> str:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _craft(header: dict[str, object], claims: dict[str, object], sig: bytes = b"sig") -> str:
    return f"{_b64url(header)}.{_b64url(claims)}.{_b64url(sig)}"


_BASE_CLAIMS = {
    "sub": "00000000-0000-0000-0000-000000000000",
    "preferred_username": "attacker",
    "iss": "https://wrong-issuer.example/realms/manzil",
    "aud": "manzil-app",
    "exp": 9_999_999_999,
    "iat": 1_700_000_000,
    "realm_access": {"roles": ["super-admin"]},
}


_FORGED_TOKENS: list[tuple[str, str]] = [
    ("alg-none", _craft({"alg": "none", "typ": "JWT"}, _BASE_CLAIMS, b"")),
    ("alg-hs256-fake-sig", _craft({"alg": "HS256", "typ": "JWT"}, _BASE_CLAIMS, b"x" * 32)),
    ("alg-rs256-fake-sig", _craft({"alg": "RS256", "typ": "JWT"}, _BASE_CLAIMS, b"x" * 64)),
    ("missing-sig", _craft({"alg": "RS256", "typ": "JWT"}, _BASE_CLAIMS, b"")),
    ("two-segments", _b64url({"alg": "RS256"}) + "." + _b64url(_BASE_CLAIMS)),
    ("expired", _craft({"alg": "RS256"}, {**_BASE_CLAIMS, "exp": 1_000_000_000})),
    ("wrong-issuer", _craft({"alg": "RS256"}, {**_BASE_CLAIMS, "iss": "https://evil.example/"})),
    ("garbage", "ZZZZ.YYYY.XXXX"),
]


@pytest.mark.security
@pytest.mark.parametrize(("case_id", "token"), _FORGED_TOKENS, ids=[c[0] for c in _FORGED_TOKENS])
def test_forged_token_returns_401_on_protected_route(
    api_client: ApiClient,
    case_id: str,
    token: str,
) -> None:
    """Every protected route must reject a forged token with 401."""
    response = api_client._client.get(
        "/api/v1/me",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401, (
        f"case {case_id}: forged token accepted with {response.status_code}: {response.text[:200]}"
    )
