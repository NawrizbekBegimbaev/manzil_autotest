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
        # Инпуты — по name (язык-независимо: placeholder меняется с языком). Кнопка — по тексту.
        self.phone_input = page.locator("input[name='phone']")
        self.password_input = page.locator("input[name='password']")
        self.submit_button = page.locator("button[type='submit']")  # язык-независимо (Войти/登录/…)
        # ── элементы отображения формы (для WEB-AUTH-001/004/006/046 и т.п.) ──
        self.title = page.get_by_text("Вход в систему", exact=False)
        self.register_link = page.get_by_text("Зарегистрироваться", exact=False)
        self.forgot_link = page.get_by_text("Забыли пароль", exact=False)
        self.country_button = page.get_by_role("button", name="+86")  # дефолт Китай
        # «глаз» показа пароля — кнопка в MUI-адорнменте поля пароля.
        self.password_toggle = page.locator(
            ".MuiInputBase-root:has(input[name='password']) button"
        ).last
        # переключатель языка (aria-label «Languages button»).
        self.lang_switcher = page.get_by_role("button", name="Languages button")

    # ── действия (без assert — проверки в тестах) ──
    def open_zh(self) -> "LoginPage":
        """Открыть форму на дефолтном (китайском) языке — контекст без RU-пина."""
        self.goto(self.PATH)
        return self

    def fill_creds(self, phone: str, password: str) -> "LoginPage":
        """Заполнить телефон (посимвольно — виджет отвергает fill) и пароль, БЕЗ отправки."""
        self.phone_input.click()
        self.phone_input.press_sequentially(phone, delay=25)
        self.password_input.fill(password)
        return self

    def submit(self) -> "LoginPage":
        self.submit_button.click()
        return self

    def open_country_picker(self):
        """Открыть MUI-меню выбора страны (пункты <li> вида «UzbekistanUZ (+998)»)."""
        self.country_button.first.click()
        return self.page.get_by_role("menu").last.get_by_role("menuitem")

    def open_lang_menu(self):
        """Открыть меню языков (пункты: Русский / O'zbek / Кыргызча / 中文 / ئۇيغۇرچە)."""
        self.lang_switcher.click()
        return self.page.get_by_role("menu").last.get_by_role("menuitem")

    @property
    def phone_clear_button(self):
        """Крестик очистки поля телефона (виден только при непустом значении)."""
        return self.page.locator(
            ".MuiInputBase-root:has(input[name='phone']) button"
        ).last

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
