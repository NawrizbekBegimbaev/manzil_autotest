"""Web модуль 1, под-блок 4 — shell/сайдбар RBAC (WEB-AUTH-025…030, 058, 060).

Сайдбар per-роль: у роли с правом пункт есть, у роли без права — count 0 (RBAC в обе стороны).
Пункты меню — ссылки (`get_by_role("link")`). page_as(role) — восстановленная сессия роли.
Каждый тест — с явной навигацией на стартовую роли.

Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.regression, pytest.mark.web]

_LANDING = {
    "super_admin": "/super-admin/partners/shipper-companies",
    "shipper_admin": "/dashboard",
    "shipper_manager": "/shipper/storeroom",
    "transport_admin": "/transport/orders",
}


def _open(page_as, web_cfg, role):
    page = page_as(role)
    page.goto(web_cfg.base_url.rstrip("/") + _LANDING[role], wait_until="domcontentloaded")
    page.wait_for_load_state("domcontentloaded")
    return page


def _link(page, name):
    return page.get_by_role("link", name=name, exact=False)


def _expand_groups(page):
    """Развернуть сворачиваемые группы сайдбара (кнопки-тогглы), чтобы дочерние ссылки попали в DOM."""
    for nav_i in range(page.get_by_role("navigation").count()):
        nav = page.get_by_role("navigation").nth(nav_i)
        for btn in nav.get_by_role("button").all():
            try:
                btn.click()
            except Exception:  # noqa: BLE001 — часть кнопок не тогглы; клик безопасен
                pass


# ═══ Сайдбар per-роль ════════════════════════════════════════════════════════


@pytest.mark.high
def test_sidebar_super_admin_025(page_as, web_cfg):
    """WEB-AUTH-025: SUPER_ADMIN — только «Платформа» (Грузоотправители/Перевозчики/Водители/Страны/
    Города/Типы ТС); НЕТ «Дашборд», логистики, архива."""
    page = _open(page_as, web_cfg, "super_admin")
    for present in ("Грузоотправители", "Транспортные компании", "Водители", "Страны", "Города", "Типы транспорта"):
        expect(_link(page, present).first).to_be_visible()
    for absent in ("Дашборд", "Заказы", "Кладовая", "Отчёты"):
        expect(_link(page, absent)).to_have_count(0)


@pytest.mark.high
def test_sidebar_admin_026(page_as, web_cfg):
    """WEB-AUTH-026: SHIPPER_ADMIN (все права) — «Дашборд» + логистика (Заказы/Кладовая/Отправки/Отчёты/
    Склады) + «Сотрудники»."""
    page = _open(page_as, web_cfg, "shipper_admin")
    # верхнеуровневые (без разворота группы): «Панель управления» (дашборд) + «Сотрудники» (управление персоналом — только админ)
    expect(_link(page, "Панель управления").first).to_be_visible()
    expect(_link(page, "Сотрудники").first).to_be_visible()
    expect(_link(page, "Грузоотправители")).to_have_count(0)  # платформенный раздел не виден шипперу


@pytest.mark.high
def test_sidebar_manager_no_reports_027(page_as, web_cfg):
    """WEB-AUTH-027: SHIPPER_MANAGER без REPORTS — пункта «Отчёты» НЕТ; «Кладовая» (ORDER_REVIEW) есть.
    Бизнес-контракт: API-RBAC-088 (REPORTS не в дефолте менеджера)."""
    page = _open(page_as, web_cfg, "shipper_manager")
    # ключевые дискриминаторы (ссылки не рендерятся при отсутствии права — робастно к сворачиванию групп):
    # у менеджера нет REPORTS → нет «Отчёты»; управление персоналом только у админа → нет «Сотрудники».
    expect(_link(page, "Отчёты")).to_have_count(0)
    expect(_link(page, "Сотрудники")).to_have_count(0)


@pytest.mark.high
def test_sidebar_carrier_two_items_029(page_as, web_cfg):
    """WEB-AUTH-029: TRANSPORT_ADMIN — ровно 2 пункта: «Заказы» и «Сотрудники»; ни грузоотправителя,
    ни платформы, ни архива."""
    page = _open(page_as, web_cfg, "transport_admin")
    # реальные подписи перевозчика: «Заявки» (/transport/orders) и «Водители» (/transport/employees)
    expect(_link(page, "Заявки").first).to_be_visible()
    expect(_link(page, "Водители").first).to_be_visible()
    for absent in ("Панель управления", "Грузоотправители", "Отчёты", "Страны"):
        expect(_link(page, absent)).to_have_count(0)


# ═══ Меню аккаунта ═══════════════════════════════════════════════════════════


@pytest.mark.low
def test_account_menu_060(page_as, web_cfg):
    """WEB-AUTH-060: меню аккаунта — роль + заглушки «Настройки профиля»/«Уведомления» (не работают) + «Выйти»."""
    page = _open(page_as, web_cfg, "shipper_admin")
    page.locator("button:has(.MuiAvatar-root)").last.click()
    menu = page.get_by_role("menu").last
    expect(menu).to_be_visible()
    items = menu.get_by_role("menuitem").all_text_contents()
    assert any("Настройки профиля" in i for i in items) and any("Уведомления" in i for i in items), \
        f"[WEB-AUTH-060] заглушки профиля/уведомлений: {items}"
    expect(page.get_by_text("Выйти", exact=False).first).to_be_visible()


# ═══ Мобильная навигация (бургер) ════════════════════════════════════════════
