"""Forgot-password — `/auth/forgot-password`.

Live recon: heading «Восстановление пароля», email input
(name=email, placeholder example@mail.com), button «Отправить код».
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class ForgotPasswordPage(BasePage):
    path = "/auth/forgot-password"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Восстановление пароля")

    @property
    def email_input(self):
        return self.page.get_by_role("textbox", name="Email")

    @property
    def submit_button(self):
        return self.page.get_by_role("button", name="Отправить код")

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
