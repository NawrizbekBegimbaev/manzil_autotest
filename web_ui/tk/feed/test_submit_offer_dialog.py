"""TK submit-offer dialog — opens, fields render, cancel works.

We test dialog plumbing only. Actually submitting an offer mutates
shared state (creates a real offer row that other tests / future runs
will see; offers are de-duped per (order, TK) so re-running would 409).
The cross-role e2e suite is the right place for end-to-end submission,
where it owns the full create→offer→complete cycle and cleans up.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.tk.feed_page import SubmitOfferDialog, TKFeedPage


@pytest.fixture
def feed(tk_page, settings: Settings) -> TKFeedPage:
    page = TKFeedPage(tk_page, settings.web_base_url_str)
    page.goto()
    return page


def _open_first_offer_dialog(feed: TKFeedPage) -> SubmitOfferDialog:
    feed.page.locator("tbody tr").first.wait_for(state="visible")
    feed.page.get_by_role("button", name="Предложить цену").first.click()
    return SubmitOfferDialog(feed.page)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_dialog_opens_with_expected_fields(feed: TKFeedPage) -> None:
    dialog = _open_first_offer_dialog(feed)
    expect(dialog.root).to_be_visible()
    expect(dialog.price_input).to_be_visible()
    # Currency is now a read-only display, not a combobox.
    expect(dialog.currency_input).to_be_visible()
    expect(dialog.comment_input).to_be_visible()
    expect(dialog.submit_button).to_be_visible()
    expect(dialog.cancel_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_currency_is_locked_with_explanatory_note(feed: TKFeedPage) -> None:
    """Currency in the offer dialog is fixed at submission time —
    backend uses the order's currency. UI shows the note
    «Валюта зафиксирована при подаче и не редактируется.»."""
    dialog = _open_first_offer_dialog(feed)
    expect(dialog.currency_locked_note).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_dialog_cancel_closes_without_creating_offer(feed: TKFeedPage) -> None:
    dialog = _open_first_offer_dialog(feed)
    dialog.price_input.fill("12345")
    dialog.cancel_button.click()
    expect(dialog.root).to_have_count(0)


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_comment_input_accepts_text(feed: TKFeedPage) -> None:
    dialog = _open_first_offer_dialog(feed)
    dialog.comment_input.fill("Готовы выехать в течение 24 часов")
    expect(dialog.comment_input).to_have_value("Готовы выехать в течение 24 часов")
    dialog.cancel_button.click()
