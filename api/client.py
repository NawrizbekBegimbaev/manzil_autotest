"""HTTP client wrapping httpx with Manzil-specific concerns.

Responsibilities:
- Compose requests against `settings.api_base_url`.
- Inject `Authorization: Bearer <jwt>` when a token is configured on the
  client instance.
- Raise `ApiError` containing the parsed RFC 9457 ProblemDetail on non-2xx.
- Allure-step decoration of every call so traces in the report are useful.

Tests should NOT instantiate `httpx.Client` directly — they get an
`ApiClient` from a fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any

import allure
import httpx

from api.schemas.problem import ProblemDetail
from config.settings import Settings


class ApiError(RuntimeError):
    """Non-2xx response from the API.

    Carries the parsed ProblemDetail when the server emitted one (any
    `application/problem+json` body), the raw status, and the request URL —
    enough for tests to assert on without re-fetching the response.
    """

    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        method: str,
        problem: ProblemDetail | None,
        raw_body: str,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.method = method
        self.problem = problem
        self.raw_body = raw_body
        title = problem.title if problem else raw_body[:120]
        super().__init__(f"{method} {url} → {status_code}: {title}")


class ApiClient:
    """Thin wrapper over `httpx.Client` carrying Manzil defaults.

    The client is reusable across requests in a single test; for separate
    sessions (e.g. two roles in the same test) instantiate two clients.
    """

    def __init__(self, settings: Settings, *, token: str | None = None) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.api_base_url_str,
            timeout=settings.http_timeout_s,
            verify=settings.http_verify_ssl,
            headers={"Accept": "application/json"},
        )
        self._token: str | None = token

    # ----- token management ------------------------------------------------

    def set_token(self, token: str | None) -> None:
        """Set or clear the Bearer token used for subsequent requests."""
        self._token = token

    @property
    def token(self) -> str | None:
        return self._token

    # ----- request entrypoints --------------------------------------------

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        expect_status: int | tuple[int, ...] = 200,
    ) -> httpx.Response:
        return self._request("GET", path, params=params, expect_status=expect_status)

    def post(
        self,
        path: str,
        *,
        json: Any = None,
        expect_status: int | tuple[int, ...] = (200, 201, 204),
    ) -> httpx.Response:
        return self._request("POST", path, json=json, expect_status=expect_status)

    def patch(
        self,
        path: str,
        *,
        json: Any = None,
        expect_status: int | tuple[int, ...] = 200,
    ) -> httpx.Response:
        return self._request("PATCH", path, json=json, expect_status=expect_status)

    def put(
        self,
        path: str,
        *,
        json: Any = None,
        expect_status: int | tuple[int, ...] = 200,
    ) -> httpx.Response:
        return self._request("PUT", path, json=json, expect_status=expect_status)

    def delete(
        self,
        path: str,
        *,
        expect_status: int | tuple[int, ...] = 204,
    ) -> httpx.Response:
        return self._request("DELETE", path, expect_status=expect_status)

    # ----- expected-failure helper ----------------------------------------

    @contextmanager
    def expect_error(
        self,
        status: int | tuple[int, ...],
    ) -> Iterator[list[ApiError]]:
        """Context manager that captures an ApiError matching `status`.

        `status` can be a single code or a tuple of acceptable codes. Use a
        tuple when backend behaviour is genuinely ambiguous (e.g. 404 vs 409
        on a draft order — different roles see different errors).

        Usage in negative tests:

            with client.expect_error(409) as errors:
                client.post("/api/v1/auth/web/registrations/suppliers", json=...)
            assert errors[0].problem.detail == "TIN already in use"
        """
        allowed = (status,) if isinstance(status, int) else status
        captured: list[ApiError] = []
        try:
            yield captured
        except ApiError as err:
            if err.status_code not in allowed:
                raise AssertionError(
                    f"expected status {allowed}, got {err.status_code}: {err}",
                ) from err
            captured.append(err)
            return
        raise AssertionError(f"expected status {allowed}, request succeeded")

    # ----- internals ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        expect_status: int | tuple[int, ...],
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"

        with allure.step(f"{method} {path}"):
            response = self._client.request(
                method,
                path,
                json=json,
                params=params,
                headers=headers or None,
            )
            allure.attach(
                str(response.status_code),
                name="status",
                attachment_type=allure.attachment_type.TEXT,
            )
            if response.content:
                allure.attach(
                    response.text,
                    name="response",
                    attachment_type=allure.attachment_type.JSON
                    if response.headers.get("content-type", "").startswith(
                        ("application/json", "application/problem+json"),
                    )
                    else allure.attachment_type.TEXT,
                )

        allowed = (expect_status,) if isinstance(expect_status, int) else expect_status
        if response.status_code not in allowed:
            raise self._build_error(method=method, response=response)
        return response

    @staticmethod
    def _build_error(*, method: str, response: httpx.Response) -> ApiError:
        problem: ProblemDetail | None = None
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(("application/problem+json", "application/json")):
            try:
                problem = ProblemDetail.model_validate(response.json())
            except (ValueError, httpx.DecodingError):
                problem = None
        return ApiError(
            status_code=response.status_code,
            url=str(response.request.url),
            method=method,
            problem=problem,
            raw_body=response.text,
        )

    # ----- lifecycle ------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
