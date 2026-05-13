"""TK feed — page renders + date-range filter chrome.

Live recon (2026-05-04): body-type combobox REMOVED. Filtering UI now
consists of «Дата с» / «Дата по» date pickers + «Применить» / «Очистить»
buttons. New «Валюта» column added to the table.

Body-type narrowing tests are dropped — the UI control they tested no
longer exists. If body-type filtering returns in another shape (URL
param, separate page, fleet-driven implicit filter), reintroduce.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.tk.feed_page import TKFeedPage


@pytest.fixture
def feed(tk_page, settings: Settings) -> TKFeedPage:
    page = TKFeedPage(tk_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_feed_renders_heading_and_date_filters(feed: TKFeedPage) -> None:
    expect(feed.heading).to_be_visible()
    expect(feed.date_from_input).to_be_visible()
    expect(feed.date_to_input).to_be_visible()
    expect(feed.apply_filters_button).to_be_visible()
    expect(feed.clear_filters_button).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_feed_table_columns_are_present(feed: TKFeedPage) -> None:
    # Columns now: Номер, Груз, Маршрут, Дата погрузки, Кузов, Валюта.
    # exact=True because «Груз» is a substring of «Дата погрузки» — without
    # it strict-mode resolves to 2 elements.
    for col in ("Номер", "Груз", "Маршрут", "Дата погрузки", "Кузов", "Валюта"):
        expect(
            feed.page.get_by_role("columnheader", name=col, exact=True),
        ).to_be_visible()


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_feed_has_predloghit_button_per_row(feed: TKFeedPage) -> None:
    """Every row in feed must have a «Предложить цену» button — that's
    how the TK takes action."""
    rows = feed.page.locator("tbody tr")
    rows.first.wait_for(state="visible")
    feed.page.get_by_role("button", name="Предложить цену").first.wait_for(
        state="visible",
    )
    count = rows.count()
    assert count > 0, "feed is empty — dataset issue"
    buttons = feed.page.get_by_role("button", name="Предложить цену")
    expect(buttons.first).to_be_visible()
    assert buttons.count() == count, (
        f"expected {count} «Предложить цену» buttons, got {buttons.count()}"
    )


@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_clear_filters_button_initially_disabled(feed: TKFeedPage) -> None:
    """Without any filter set, «Очистить» starts disabled — sanity for
    the new chrome."""
    expect(feed.clear_filters_button).to_be_disabled()
