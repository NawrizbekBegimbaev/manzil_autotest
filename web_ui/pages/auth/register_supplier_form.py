"""Supplier registration form — `/auth/register/supplier`.

Real labels from the live UI (verified via Playwright MCP):
  - «Название компании»
  - «ИНН / аналог»
  - «ФИО администратора»
  - «Email»
  - «Телефон»  (placeholder: «+998 90 000 00 00»)
  - «Пароль»
  - «Повторите пароль»
  - кнопка «Зарегистрироваться»

Inline error messages observed (assert these in negative tests):
  «Название не короче 2 символов»
  «ИНН от 8 до 18 символов»     ← UI says 8-18; API regex says 1-18 (BUG)
  «ФИО не короче 2 символов»
  «Неверный формат email»
  «Укажите корректный телефон»
  «Не менее 8 символов»          (password)
"""

from __future__ import annotations

from web_ui.pages._base import BasePage


class RegisterSupplierForm(BasePage):
    path = "/auth/register/supplier"

    # ---------- locators --------------------------------------------------

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Регистрация поставщика")

    @property
    def company_name_input(self):
        return self.page.get_by_role("textbox", name="Название компании")

    @property
    def tin_input(self):
        return self.page.get_by_role("textbox", name="ИНН / аналог")

    @property
    def full_name_input(self):
        return self.page.get_by_role("textbox", name="ФИО администратора")

    @property
    def email_input(self):
        return self.page.get_by_role("textbox", name="Email")

    @property
    def phone_input(self):
        return self.page.get_by_role("textbox", name="Телефон")

    @property
    def password_input(self):
        return self.page.get_by_role("textbox", name="Пароль", exact=True)

    @property
    def confirm_password_input(self):
        return self.page.get_by_role("textbox", name="Повторите пароль")

    @property
    def submit_button(self):
        return self.page.get_by_role("button", name="Зарегистрироваться")

    @property
    def back_to_login_link(self):
        return self.page.get_by_role("link", name="Войти")

    # ---------- actions ---------------------------------------------------

    def fill_all(
        self,
        *,
        company_name: str,
        tin: str,
        full_name: str,
        email: str,
        phone: str,
        password: str,
        confirm_password: str | None = None,
    ) -> None:
        self.company_name_input.fill(company_name)
        self.tin_input.fill(tin)
        self.full_name_input.fill(full_name)
        self.email_input.fill(email)
        self.phone_input.fill(phone)
        self.password_input.fill(password)
        self.confirm_password_input.fill(
            confirm_password if confirm_password is not None else password,
        )

    def submit(self) -> None:
        self.submit_button.click()

    # ---------- inline error helpers --------------------------------------
    #
    # The UI renders the error text in a sibling element under each input.
    # We match by visible text rather than DOM structure — robust to layout
    # tweaks.

    def field_error(self, message: str):
        return self.page.get_by_text(message, exact=True)
