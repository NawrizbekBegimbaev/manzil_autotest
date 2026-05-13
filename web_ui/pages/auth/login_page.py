"""Login page — `/auth/login`.

The same page handles both Supplier and TK logins. Role is determined
server-side by the user's Keycloak realm role; the UI redirects to the
correct landing page after submit:
- SUPPLIER_* → `/dashboard`
- TK_ADMIN   → `/feed`
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class LoginPage(BasePage):
    path = "/auth/login"

    # ---------- locators (kept as properties so they re-resolve each call) -

    @property
    def email_input(self):
        return self.page.get_by_role("textbox", name="Email")

    @property
    def password_input(self):
        return self.page.get_by_role("textbox", name="Пароль")

    @property
    def submit_button(self):
        return self.page.get_by_role("button", name="Войти")

    @property
    def forgot_password_link(self):
        return self.page.get_by_role("link", name="Забыли пароль")

    @property
    def register_link(self):
        return self.page.get_by_role("link", name="Зарегистрироваться")

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Войти в аккаунт")

    # ---------- actions ---------------------------------------------------

    def fill_credentials(self, *, email: str, password: str) -> None:
        self.email_input.fill(email)
        self.password_input.fill(password)

    def submit(self) -> None:
        self.submit_button.click()

    def login(self, *, email: str, password: str) -> None:
        """Fill + submit. Caller waits for the post-login URL itself."""
        self.fill_credentials(email=email, password=password)
        self.submit()

    # ---------- assertions ------------------------------------------------

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
