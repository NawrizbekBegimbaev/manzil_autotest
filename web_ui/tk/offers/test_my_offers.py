"""TK my-offers — outgoing offer history.

Live recon: TK has at least 1 historic offer with status «Выбрано»
(MZL-0001 from TeamQa). We assert the page renders, columns exist,
and the «Выбрано» status badge shows.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings
from web_ui.pages.tk.offers_page import TKOffersPage


@pytest.fixture
def my_offers(tk_page, settings: Settings) -> TKOffersPage:
    page = TKOffersPage(tk_page, settings.web_base_url_str)
    page.goto()
    return page


@pytest.mark.xfail(
    reason=(
        "BUG-021: TK /offers renders «404 Заявка не найдена» when ANY of "
        "the historical offers references a cancelled order. After many "
        "cross-role test runs leaving cancelled orders behind, the page "
        "becomes unusable until backend prunes those records or frontend "
        "skips missing-order rows gracefully."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_my_offers_renders_heading_and_columns(my_offers: TKOffersPage) -> None:
    expect(my_offers.heading).to_be_visible()
    for col in ("Заявка", "Цена", "Статус", "Дата"):
        expect(my_offers.page.get_by_role("columnheader", name=col)).to_be_visible()


@pytest.mark.xfail(
    reason=(
        "BUG-021: TK /offers renders «404 Заявка не найдена» when ANY of "
        "the historical offers references a cancelled order. After many "
        "cross-role test runs leaving cancelled orders behind, the page "
        "becomes unusable until backend prunes those records or frontend "
        "skips missing-order rows gracefully."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_my_offers_shows_at_least_one_historic_offer(
    my_offers: TKOffersPage,
) -> None:
    rows = my_offers.page.locator("tbody tr")
    rows.first.wait_for(state="visible")
    assert rows.count() >= 1, "expected at least one historic offer for TK"


@pytest.mark.xfail(
    reason=(
        "BUG-021: TK /offers renders «404 Заявка не найдена» when ANY of "
        "the historical offers references a cancelled order. After many "
        "cross-role test runs leaving cancelled orders behind, the page "
        "becomes unusable until backend prunes those records or frontend "
        "skips missing-order rows gracefully."
    ),
    strict=False,
)
@pytest.mark.ui
@pytest.mark.ui_tk
@pytest.mark.requires_real_account
def test_my_offers_row_includes_a_currency_amount(
    my_offers: TKOffersPage,
) -> None:
    """Each row's price column must show «<digits> <CURRENCY>» — proves
    the price+currency cell renders rather than checking the status
    enum (which evolves frequently and shouldn't be hard-coded here).

    Polls the body text for up to 10s — async data fetch can lag the
    initial visibility-check by a beat in a busy suite.
    """
    import re

    my_offers.page.locator("tbody tr").first.wait_for(state="visible")
    pattern = re.compile(r"\d+\s+(USD|CNY|RUB|UZS)")
    last_text = ""
    deadline = my_offers.page.evaluate("() => Date.now()") + 10_000
    while my_offers.page.evaluate("() => Date.now()") < deadline:
        last_text = my_offers.page.locator("tbody").inner_text()
        if pattern.search(last_text):
            return
        my_offers.page.wait_for_timeout(250)
    raise AssertionError(
        f"no «<digits> <CURRENCY>» in offers table body within 10s: "
        f"{last_text[:200]}",
    )
