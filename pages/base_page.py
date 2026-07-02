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

    @property
    def grid(self):
        """The list container. Lists migrated from <table> to a MUI DataGrid
        (role="grid"); fall back to a plain table if some page still uses one."""
        return self.page.locator('[role="grid"], table').first

    def activate(self, locator):
        """Activate a MUI DataGrid icon button via keyboard — a plain click on an
        in-grid IconButton is swallowed by the grid in headless mode."""
        locator.focus()
        locator.press("Enter")
        return self

    def open_row_menu(self, row):
        """Open a DataGrid row's ⋮ actions menu. The MUI IconButton opens the
        menu on keyboard activation; a plain click is swallowed by the grid in
        headless mode, so we focus the button and press Enter."""
        btn = row.get_by_role("button").last
        btn.focus()
        btn.press("Enter")
        self.page.get_by_role("menu").last.wait_for(state="visible")
        return self

    def filter_search(self, placeholder: str, text: str):
        """Reveal the filters panel (search moved behind the «Фильтры» button on
        the redesigned list toolbar) and type into the search box. Idempotent:
        clicks «Фильтры» only when the box is not already visible (the collapsed
        panel may keep a hidden input in the DOM, so we check visibility)."""
        box = self.page.get_by_placeholder(placeholder).first
        if not box.is_visible():
            # Wait for the list toolbar to render (after goto it may not be ready),
            # then open the filters panel that holds the search box.
            btn = self.page.get_by_role("button", name="Фильтры").first
            btn.wait_for(state="visible")
            btn.click()
            box.wait_for(state="visible")
        box.fill(text)
        return box

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
