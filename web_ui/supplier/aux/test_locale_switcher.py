"""Locale switcher in the top banner.

Live recon options: Русский / O'zbek / Кыргызча / 中文 / ئۇيغۇرچە (5 langs).
Default is Русский (RU shown in the button).

We test:
- Click the switcher — popover lists ALL 5 languages.
- Picking a non-default language changes UI strings (e.g. sidebar
  «Заявки» → «Buyurtmalar» for O'zbek). We then click again to flip
  back to Русский so subsequent tests see the expected RU labels.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from config.settings import Settings

EXPECTED_LANGUAGES = ("Русский", "O'zbek", "Кыргызча", "中文", "ئۇيغۇرچە")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_locale_switcher_lists_all_5_languages(
    supplier_admin_page, settings: Settings,
) -> None:
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    supplier_admin_page.locator('button[aria-label="Languages button"]').click()
    for lang in EXPECTED_LANGUAGES:
        expect(supplier_admin_page.get_by_text(lang, exact=True)).to_be_visible()
    supplier_admin_page.keyboard.press("Escape")


@pytest.mark.ui
@pytest.mark.ui_supplier
@pytest.mark.requires_real_account
def test_switching_to_uzbek_changes_sidebar_label(
    supplier_admin_page, settings: Settings,
) -> None:
    """Switch to O'zbek; sidebar «Заявки» becomes the Uzbek
    translation. Then switch back to Русский so other tests don't get
    confused by leftover language."""
    supplier_admin_page.goto(f"{settings.web_base_url_str}/dashboard")
    supplier_admin_page.locator('button[aria-label="Languages button"]').click()
    supplier_admin_page.get_by_text("O'zbek", exact=True).click()
    # «Заявки» must NOT be present anymore.
    expect(
        supplier_admin_page.get_by_role("link", name="Заявки"),
    ).to_have_count(0, timeout=5_000)

    # Restore RU so the next test's storage_state-loaded session sees
    # the expected labels.
    supplier_admin_page.locator('button[aria-label="Languages button"]').click()
    supplier_admin_page.get_by_text("Русский", exact=True).click()
    expect(
        supplier_admin_page.get_by_role("link", name="Заявки"),
    ).to_be_visible(timeout=5_000)
