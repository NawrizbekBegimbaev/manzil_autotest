"""Email-OTP verification screen.

We deliberately STOP here in pre-OTP coverage — we don't have a way to
read the real Gmail inbox in tests. The presence of this screen after
form submit IS the assertion: it proves the backend accepted the form
and started the OTP session.

Selectors are placeholders; refine on first real run.
"""

from __future__ import annotations

from web_ui.pages._base import BasePage


class VerifyOtpPage(BasePage):
    # The path varies by flow (supplier vs tk). We match by visible content
    # rather than URL — see `expect_loaded`.
    path = "/auth/verify"

    @property
    def heading(self):
        return self.page.get_by_role("heading").filter(has_text="код")

    @property
    def code_input(self):
        return self.page.get_by_role("textbox", name="Код").or_(
            self.page.get_by_label("Код"),
        )

    @property
    def submit_button(self):
        return self.page.get_by_role("button", name="Подтвердить").or_(
            self.page.get_by_role("button", name="Verify"),
        )

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        # We rely on visible OTP UI cues, not URL path, since the live URL
        # may differ between supplier/tk flows.
        from playwright.sync_api import expect
        expect(self.code_input.or_(self.heading)).to_be_visible(timeout=timeout)
