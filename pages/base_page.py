"""Base Page Object.

Page Objects expose actions and getters only — NO assertions. Assertions live
in tests via Playwright's auto-retrying `expect(...)`. We never use
`wait_for_load_state("networkidle")`: this SPA holds live connections, so
networkidle never fires. Navigation waits on `domcontentloaded`; readiness is
asserted in the test against a stable element.
"""

from __future__ import annotations

from playwright.sync_api import Page

from config.settings import Settings


class BasePage:
    def __init__(self, page: Page, cfg: Settings) -> None:
        self.page = page
        self.cfg = cfg

    def goto(self, path: str) -> "BasePage":
        url = self.cfg.base_url.rstrip("/") + path
        self.page.goto(url, wait_until="domcontentloaded")
        return self

    @property
    def heading(self):
        """First level-1 heading on the page (page title)."""
        return self.page.get_by_role("heading", level=1)

    @staticmethod
    def fill_phone(locator, e164: str) -> None:
        """Type a phone into a react-phone-number-input field defaulted to +998.

        `fill()` is rejected and re-typing the +998 prefix makes the widget drop
        digits, so we clear and type the NATIONAL part only, key-by-key.
        """
        locator.click()
        locator.press("ControlOrMeta+a")
        locator.press("Backspace")
        locator.press_sequentially(e164.removeprefix("+998"), delay=60)

    @staticmethod
    def fill_phone_intl(locator, e164: str) -> None:
        """Type a full international phone into a field whose default country is NOT UZ
        (e.g. login / carrier-driver default to +86). Typing the full +998… number
        auto-switches the widget's country."""
        locator.click()
        locator.press("ControlOrMeta+a")
        locator.press("Backspace")
        locator.press_sequentially(e164, delay=50)
