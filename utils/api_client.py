"""General-purpose API client for UAT backend tests.

Unlike ``utils.api_seed.ApiSeed`` (which only *sets up* state for the web/mobile
UI tests), this client is the system-under-test: the UAT API cases assert directly
on its responses. It therefore never raises on 4xx/5xx — the *caller* asserts the
status. Auth/error bodies are ``application/problem+json`` with a ``code`` field
(e.g. ``error.invalid-credentials``); localized ``detail`` text is NOT asserted on
because staging defaults to Chinese (China-first), so tests key on ``code``.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import Settings


def _retrying_session() -> requests.Session:
    """Session that rides out transient CONNECT failures (DNS blips) common on
    this host — retries only pre-send connection errors, never read errors, so a
    request is never silently duplicated."""
    s = requests.Session()
    retry = Retry(total=5, connect=5, read=0, status=0, backoff_factor=1.0,
                  raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


class ApiClient:
    """Thin HTTP wrapper. Methods return raw ``requests.Response`` — assertions
    live in the tests."""

    def __init__(self, cfg: Settings) -> None:
        self.base = cfg.base_url.rstrip("/") + "/api/v1"
        self._session = _retrying_session()
        self._tokens: dict[str, str] = {}

    # ── raw verbs (never raise) ──
    def login(self, phone: str, password: str, client_type: str) -> requests.Response:
        return self._session.post(
            f"{self.base}/auth/login",
            json={"phone": phone, "password": password, "clientType": client_type},
            timeout=30,
        )

    def refresh(self, refresh_token) -> requests.Response:
        return self._session.post(
            f"{self.base}/auth/refresh",
            json={"refreshToken": refresh_token},
            timeout=30,
        )

    def get(self, path: str, token: str | None = None, **kw) -> requests.Response:
        return self.request("GET", path, token, **kw)

    def request(self, method: str, path: str, token: str | None = None, **kw) -> requests.Response:
        headers = kw.pop("headers", {})
        if token:
            headers = {**headers, "Authorization": f"Bearer {token}"}
        return self._session.request(method, f"{self.base}{path}", headers=headers,
                                     timeout=30, **kw)

    # ── convenience ──
    def token(self, phone: str, password: str, client_type: str) -> str:
        """Login and cache the accessToken (raises if login is not 200 — a token
        is a precondition, not the assertion)."""
        key = f"{phone}:{client_type}"
        if key not in self._tokens:
            r = self.login(phone, password, client_type)
            if r.status_code != 200:
                raise RuntimeError(f"login {phone}/{client_type}: {r.status_code} {r.text[:200]}")
            self._tokens[key] = r.json()["accessToken"]
        return self._tokens[key]
