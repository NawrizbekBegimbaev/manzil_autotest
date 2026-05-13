"""TK (Транспортная компания) registration form — `/auth/register/tk`.

Identical layout to the Supplier form except:
  - Heading: «Регистрация транспортной компании»
  - Company name label: «Название ТК» (vs. «Название компании»)
"""

from __future__ import annotations

from web_ui.pages._base import BasePage


class RegisterTKForm(BasePage):
    path = "/auth/register/tk"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Регистрация транспортной компании")

    @property
    def company_name_input(self):
        return self.page.get_by_role("textbox", name="Название ТК")

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

    def field_error(self, message: str):
        return self.page.get_by_text(message, exact=True)
