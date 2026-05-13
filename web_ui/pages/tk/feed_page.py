"""TK feed — `/feed`.

Landing page after TK_ADMIN login. Active orders matching the company's
автопарк (per matrix).

Live recon (2026-05-04):
- Body-type combobox filter REMOVED. Filtering now happens via «Дата с»
  / «Дата по» pickers + buttons «Применить» / «Очистить».
- Table got a new «Валюта» column (USD/CNY).
- Pagination added: «Строк на странице» combobox (10 default), prev/next.

Each row has a «Предложить цену» button which opens `SubmitOfferDialog`.
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class TKFeedPage(BasePage):
    path = "/feed"

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Лента активных заявок").first

    @property
    def date_from_input(self):
        return self.page.get_by_role("group", name="Дата с").locator("input")

    @property
    def date_to_input(self):
        return self.page.get_by_role("group", name="Дата по").locator("input")

    @property
    def apply_filters_button(self):
        return self.page.get_by_role("button", name="Применить")

    @property
    def clear_filters_button(self):
        return self.page.get_by_role("button", name="Очистить")

    @property
    def page_size_select(self):
        return self.page.get_by_role("combobox", name="Строк на странице")

    def row_by_number(self, mzl_number: str):
        return self.page.get_by_role("row").filter(has_text=mzl_number)

    def submit_offer_for(self, mzl_number: str) -> None:
        self.row_by_number(mzl_number).get_by_role(
            "button", name="Предложить цену",
        ).click()

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)


class SubmitOfferDialog:
    """Modal opened by «Предложить цену» on a feed row.

    Live recon (2026-05-04): currency is now READ-ONLY — fixed to the
    order's currency at submission time. UI shows a disabled input plus
    a small note «Валюта зафиксирована при подаче и не редактируется.».
    Comment field is a `<textarea>` (placeholder «Необязательно, до 250
    символов»).
    """

    def __init__(self, page) -> None:
        self.page = page

    @property
    def root(self):
        return self.page.get_by_role("dialog", name="Предложить цену")

    @property
    def price_input(self):
        return self.root.locator('input[name="price"]')

    @property
    def currency_input(self):
        """Read-only display field showing the order's currency."""
        return self.root.get_by_label("Валюта")

    @property
    def currency_locked_note(self):
        return self.root.get_by_text("Валюта зафиксирована")

    @property
    def comment_input(self):
        return self.root.locator('textarea[name="comment"]')

    @property
    def submit_button(self):
        return self.root.get_by_role("button", name="Отправить")

    @property
    def cancel_button(self):
        return self.root.get_by_role("button", name="Отмена")

    def fill(self, *, price: str, comment: str = "") -> None:
        """Fill price (and optional comment). Currency is no longer
        user-controlled — backend uses the order's currency."""
        self.price_input.fill(price)
        if comment:
            self.comment_input.fill(comment)

    def submit(self) -> None:
        self.submit_button.click()
