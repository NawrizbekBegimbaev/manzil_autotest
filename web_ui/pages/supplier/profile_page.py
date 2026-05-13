"""Profile settings — `/settings/profile`.

Live recon: heading «Профиль», subtitle «Ваши данные и предпочтения
интерфейса.», button «Редактировать». Shows ФИО, Email, Телефон,
Роль, Организация, ИНН as paragraphs (read-only by default).

After clicking «Редактировать»: ФИО + Телефон become editable text
inputs; Email/Роль/Организация/ИНН stay read-only. Buttons «Отмена»
+ «Сохранить» appear.

Per matrix: GET /me — all roles see; PATCH /me (ФИО, телефон) — all roles.
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class ProfilePage(BasePage):
    path = "/settings/profile"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Профиль")

    @property
    def edit_button(self):
        return self.page.get_by_role("button", name="Редактировать")

    @property
    def cancel_button(self):
        return self.page.get_by_role("button", name="Отмена")

    @property
    def save_button(self):
        return self.page.get_by_role("button", name="Сохранить")

    @property
    def full_name_input(self):
        return self.page.get_by_label("ФИО")

    @property
    def phone_input(self):
        return self.page.get_by_label("Телефон")

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
