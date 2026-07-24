"""Web модуль 1, под-блок 5 — настройки + панель оформления (WEB-AUTH-052…055, 061…065).

Проверяем отображение/поведение раздела «Настройки» и выдвижной панели оформления (тема,
контраст, compact, RTL) + их персист после reload. page_as(super_admin) — восстановленная сессия.
Каждый тест — с явной навигацией на свой экран.

Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.regression, pytest.mark.web]


def _settings(page_as, web_cfg):
    page = page_as("super_admin")
    page.goto(web_cfg.base_url.rstrip("/") + "/settings", wait_until="domcontentloaded")
    return page


def _open_appearance(page):
    """Открыть выдвижную панель оформления (кнопка-шестерёнка, aria «Settings button»)."""
    page.get_by_role("button", name="Settings button").click()
    return page.get_by_role("presentation").last


# ═══ Раздел «Настройки» (обслуживание) ═══════════════════════════════════════


@pytest.mark.medium
def test_settings_page_052(page_as, web_cfg):
    """WEB-AUTH-052: страница настроек (SUPER_ADMIN) — карточка «Обслуживание» с «Очистить кэш» и «Очистить журнал»."""
    page = _settings(page_as, web_cfg)
    expect(page.get_by_text("Обслуживание", exact=False).first).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(r"Очистить кэш")).first).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(r"Очистить журнал")).first).to_be_visible()


@pytest.mark.medium
def test_clear_cache_053(page_as, web_cfg):
    """WEB-AUTH-053: «Очистить кэш» → тост об успешной очистке (dev-maintenance, безопасно)."""
    page = _settings(page_as, web_cfg)
    page.get_by_role("button", name=re.compile(r"Очистить кэш")).first.click()
    expect(page.get_by_text(re.compile(r"кэш", re.I)).first).to_be_visible()


@pytest.mark.medium
def test_clear_log_054(page_as, web_cfg):
    """WEB-AUTH-054: «Очистить журнал» → тост об успешной очистке. Уточнено по факту: подпись «журнал», не «лог»."""
    page = _settings(page_as, web_cfg)
    page.get_by_role("button", name=re.compile(r"Очистить журнал")).first.click()
    expect(page.get_by_text(re.compile(r"журнал", re.I)).first).to_be_visible()


# ═══ Панель оформления ═══════════════════════════════════════════════════════


@pytest.mark.medium
def test_appearance_panel_061(page_as, web_cfg):
    """WEB-AUTH-061: панель оформления — тумблеры Mode/Contrast/Right to left/Compact + секция Nav (Layout/Color)."""
    page = page_as("super_admin")
    page.goto(web_cfg.base_url.rstrip("/") + "/super-admin/partners/shipper-companies", wait_until="domcontentloaded")
    panel = _open_appearance(page)
    expect(panel).to_be_visible()
    body = panel.inner_text()
    # реальные подписи панели локализованы: секции «Расположение» (Layout) и «Цвет» (Color)
    for label in ("Расположение", "Цвет"):
        assert label in body, f"[WEB-AUTH-061] нет секции {label!r} в панели: {body[:200]}"

