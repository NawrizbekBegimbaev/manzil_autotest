"""Login page — phone + password, no OTP (all roles use this single step)."""

from __future__ import annotations

import re

from playwright.sync_api import Page

from config.settings import Settings
from pages.base_page import BasePage

# Matches any URL that is NOT the login route — used to detect a successful login.
_NOT_LOGIN = re.compile(r"^(?!.*/auth/login).*$")


class LoginPage(BasePage):
    PATH = "/auth/login"

    def __init__(self, page: Page, cfg: Settings) -> None:
        super().__init__(page, cfg)
        # data-testid is not available; target form fields by placeholder / role.
        self.phone_input = page.get_by_placeholder("Введите номер телефона")
        self.password_input = page.get_by_placeholder("Введите пароль")
        self.submit_button = page.get_by_role("button", name="Войти")

    def open(self) -> "LoginPage":
        self.goto(self.PATH)
        return self

    def login(self, phone: str, password: str) -> "LoginPage":
        """Fill credentials, submit, and wait until we leave the login route.

        The phone field is a react-phone-number-input control: `fill()` is
        rejected, so we type the full international number key-by-key — the
        widget then auto-detects the country (+998) and formats the national part.
        """
        self.open()
        self.phone_input.click()
        self.phone_input.press_sequentially(phone, delay=30)
        self.password_input.fill(password)
        self.submit_button.click()
        self.page.wait_for_url(_NOT_LOGIN, timeout=self.cfg.nav_timeout_ms)
        return self
