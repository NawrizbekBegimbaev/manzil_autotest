"""BasePage — minimal shared scaffolding for all Page Objects.

Every Page Object gets:
- a `page` (Playwright Page) reference,
- a `base_url` (already from settings, no trailing slash),
- `goto()` and `expect_url()` convenience helpers.

POM rules in this suite:
- One file per route (`/orders` → orders_list_page.py, `/orders/{id}` →
  order_detail_page.py).
- Selectors live ONLY inside POMs. Tests never touch raw selectors.
- Methods describe user intent ("create_warehouse", "logout"), not low-level
  clicks. Returning `Self` or another POM enables fluent chaining.
- No assertions in POMs (they describe the page; tests assert).
"""

from __future__ import annotations

import re
from typing import Literal

from playwright.sync_api import Page, expect


class BasePage:
    """All page objects inherit from this."""

    # Override in subclasses. Either an exact path string or a compiled regex.
    path: str | re.Pattern[str] = ""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    # ---------- navigation ------------------------------------------------

    def goto(
        self,
        *,
        wait_for_load_state: Literal[
            "domcontentloaded", "load", "networkidle"
        ] = "domcontentloaded",
    ) -> None:
        """Navigate to this page's `path` and wait for the URL to match."""
        if not self.path:
            raise RuntimeError(f"{type(self).__name__}.path is empty")
        target = self._resolve_path()
        self.page.goto(f"{self.base_url}{target}")
        self.page.wait_for_load_state(wait_for_load_state)
        self.expect_loaded()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        """Assert the browser landed on this page's URL.

        Subclasses can override to add element-level checks (e.g. "heading
        Заявки is visible"), but URL match is the cheapest stable signal.
        """
        path = self._resolve_path()
        if isinstance(path, re.Pattern):
            expect(self.page).to_have_url(path, timeout=timeout)
        else:
            expect(self.page).to_have_url(
                re.compile(re.escape(self.base_url + path) + r"/?(\?.*)?$"),
                timeout=timeout,
            )

    # ---------- helpers ---------------------------------------------------

    def _resolve_path(self) -> str | re.Pattern[str]:
        """Subclasses with parametric paths can override (e.g. orders/{id})."""
        return self.path
