"""Account drawer (right side panel).

Opens when the avatar/account button in the top-right banner is clicked.
Contains: user name, role badge, company name, Профиль/Уведомления menu,
and the «Выйти» logout button.
"""

from __future__ import annotations

from playwright.sync_api import Page


class AccountDrawer:
    def __init__(self, page: Page) -> None:
        self.page = page

    @property
    def open_button(self):
        return self.page.get_by_role("button", name="Account button")

    @property
    def logout_button(self):
        return self.page.get_by_role("button", name="Выйти")

    @property
    def profile_menu_item(self):
        return self.page.get_by_role("menuitem", name="Профиль")

    @property
    def notifications_menu_item(self):
        return self.page.get_by_role("menuitem", name="Уведомления")

    def open(self) -> None:
        self.open_button.click()

    def logout(self) -> None:
        self.open()
        self.logout_button.click()
