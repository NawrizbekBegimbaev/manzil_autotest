"""Registration entry page — `/auth/register`.

Live UI: heading «Создать аккаунт», subtitle «Выберите тип организации
— регистрация занимает меньше минуты», then two links:
  - «Поставщик»                → /auth/register/supplier
  - «Транспортная компания»    → /auth/register/tk
plus a footer note «Водители регистрируются в мобильном приложении.»
and a link «Войти» back to /auth/login.
"""

from __future__ import annotations

from web_ui.pages._base import BasePage


class RegisterEntryPage(BasePage):
    path = "/auth/register"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Создать аккаунт")

    @property
    def supplier_link(self):
        return self.page.get_by_role("link", name="Поставщик")

    @property
    def tk_link(self):
        return self.page.get_by_role("link", name="Транспортная компания")

    @property
    def driver_note(self):
        return self.page.get_by_text(
            "Водители регистрируются в мобильном приложении",
        )

    @property
    def back_to_login_link(self):
        return self.page.get_by_role("link", name="Войти")

    def pick_supplier(self) -> None:
        self.supplier_link.click()

    def pick_tk(self) -> None:
        self.tk_link.click()
