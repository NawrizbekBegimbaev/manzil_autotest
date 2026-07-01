"""Generic page-load Page Object.

Used by page-smoke cases: open a route under an already-authenticated context
and let the test assert the page heading / URL. Lists carry their query state in
the URL, so tests match on the URL prefix and the visible heading.
"""

from __future__ import annotations

from pages.base_page import BasePage


class NavPage(BasePage):
    def open_path(self, path: str) -> "NavPage":
        self.goto(path)
        return self

    def title_text(self, text: str):
        """Locator for an exact visible page-title text (any heading level)."""
        return self.page.get_by_role("heading", name=text, exact=True)
