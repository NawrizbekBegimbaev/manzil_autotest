"""Hypothesis-driven property-based tests.

Each test asserts a *property* over a stream of generated inputs: e.g.
"the server NEVER returns 5xx for any well-typed login payload" or
"any 12-character TIN is accepted while a 19-character TIN is rejected".

This catches edge cases that hand-written parametrized tests miss — random
values stress combinations no human bothered to enumerate.

`@settings(max_examples=...)` is conservative — keep network-bound runs
small to avoid hammering dev. Tighten only for security-critical
endpoints during dedicated soak runs.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from api.client import ApiClient
from config.settings import Settings
from data.email_pool import EmailPool
from data.phone_pool import PhonePool

# Keep the example budget low to avoid network spam in normal CI runs.
_PROPERTY_SETTINGS = settings(
    max_examples=25,
    deadline=None,  # network calls vary widely; don't fail on slow ones
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)


# ---------- /api/v1/auth/web/login: server NEVER 5xx for any string ------


_PRINTABLE_BYTES = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Zs"),
        blacklist_characters="\x00",
    ),
    max_size=200,
)


@pytest.mark.property
@_PROPERTY_SETTINGS
@given(email=_PRINTABLE_BYTES, password=_PRINTABLE_BYTES)
def test_login_never_500s_for_any_string_input(
    settings: Settings,
    email: str,
    password: str,
) -> None:
    """For every well-typed (string, string) pair, /web/login responds with
    a 4xx (400/401) — never 500. Catches injection-shaped bugs in Keycloak
    and ProblemDetail formatting."""
    with ApiClient(settings) as client:
        response = client._client.post(
            "/api/v1/auth/web/login",
            json={"email": email, "password": password},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    assert response.status_code < 500, (
        f"server 5xx on login: email={email!r}, password={password!r}, "
        f"body={response.text[:200]}"
    )


# ---------- TIN regex matches backend behaviour --------------------------


_DIGIT_STRING = st.text(alphabet=string.digits, min_size=1, max_size=18)
_LONG_DIGIT_STRING = st.text(alphabet=string.digits, min_size=19, max_size=30)


@pytest.mark.property
@_PROPERTY_SETTINGS
@given(tin=_DIGIT_STRING)
def test_any_short_digit_tin_is_not_rejected_for_format(
    settings: Settings,
    tin: str,
    email_pool: EmailPool,
    phone_pool: PhonePool,
) -> None:
    """Per swagger `tin: ^[0-9]{1,18}$` — backend should NEVER reject a
    valid TIN with code='TIN_FORMAT'. (It may still 409 for collisions,
    or 400 for OTHER fields, but format on the TIN itself must pass.)"""
    with (
        email_pool.lease() as email,
        phone_pool.lease() as phone,
        ApiClient(settings) as client,
    ):
        response = client._client.post(
                "/api/v1/auth/web/registrations/suppliers",
                json={
                    "companyName": "[E2E] PropTest",
                    "tin": tin,
                    "email": email,
                    "phone": phone,
                    "fullName": "Hypothesis User",
                    "password": settings.default_test_password,
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
    if response.status_code == 400:
        body = response.json() if response.content else {}
        code = body.get("code", "")
        assert "TIN" not in code.upper(), (
            f"valid {len(tin)}-digit TIN={tin!r} rejected with TIN-format error: {body}"
        )


@pytest.mark.property
@_PROPERTY_SETTINGS
@given(tin=_LONG_DIGIT_STRING)
def test_overlong_digit_tin_is_rejected(
    settings: Settings,
    tin: str,
    email_from_pool: str,
    phone_from_pool: str,
) -> None:
    """TIN longer than 18 digits MUST be rejected (per regex `{1,18}`)."""
    with ApiClient(settings) as client:
        response = client._client.post(
            "/api/v1/auth/web/registrations/suppliers",
            json={
                "companyName": "[E2E] OverlongTIN",
                "tin": tin,
                "email": email_from_pool,
                "phone": phone_from_pool,
                "fullName": "Hypothesis User",
                "password": settings.default_test_password,
            },
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    assert response.status_code == 400, (
        f"19+-digit TIN={tin!r} accepted: {response.status_code} {response.text[:200]}"
    )


# ---------- /api/v1/me: malformed Bearer never crashes ------------------


_MALFORMED_BEARER = st.text(
    # ASCII printable only — httpx refuses to send non-latin-1 header
    # values (UnicodeEncodeError client-side, not a server property).
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=0,
    max_size=500,
).map(lambda s: f"Bearer {s}")


@pytest.mark.property
@_PROPERTY_SETTINGS
@given(authorization=_MALFORMED_BEARER)
def test_me_with_random_bearer_never_500s(
    settings: Settings,
    authorization: str,
) -> None:
    """Any string after 'Bearer ' must yield 401 — never 500."""
    if "\n" in authorization or "\r" in authorization:
        # httpx rejects newlines client-side; not a server property.
        return
    # httpx also rejects header values that end with whitespace (and
    # `Bearer ` with no token after the space is in this category) —
    # client-side, not a server property.
    if authorization.endswith((" ", "\t")) or authorization == "Bearer ":
        return
    with ApiClient(settings) as client:
        response = client._client.get(
            "/api/v1/me",
            headers={"Accept": "application/json", "Authorization": authorization},
        )
    assert response.status_code in (401, 400), (
        f"server returned {response.status_code} for random Bearer={authorization[:60]!r}"
    )


# ---------- generic: ProblemDetail stays well-formed --------------------


@pytest.mark.property
@_PROPERTY_SETTINGS
@given(payload=st.dictionaries(
    keys=st.text(alphabet=string.ascii_letters, min_size=1, max_size=20),
    values=st.one_of(st.text(max_size=50), st.integers(), st.booleans(), st.none()),
    max_size=10,
))
def test_login_returns_problemdetail_for_any_random_dict(
    settings: Settings,
    payload: dict[str, object],
) -> None:
    """Any random JSON dict to /login → 400 with ProblemDetail body. Never
    crashes Spring's deserializer with a 5xx."""
    with ApiClient(settings) as client:
        response = client._client.post(
            "/api/v1/auth/web/login",
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    assert response.status_code < 500, response.text
    if response.status_code == 400 and response.content:
        body = response.json()
        # RFC 9457 minimum + Manzil's `code`:
        assert "title" in body or "detail" in body, body
