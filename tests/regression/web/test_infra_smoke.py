"""Web Фаза-0 — смоук инфры: storage_state (1 логин/роль) + RU-сторож + OrderFactory-хук.

НЕ библиотечные кейсы — проверка, что инфра Web-регрессии жива на dev:
1. Каждая web-роль получает восстановленную сессию (storage_state) и садится на свой лендинг
   на РУССКОМ (China-first не просочился).
2. storage_state = ОДИН UI-логин на роль: повторный page_as(role) переиспользует state (без
   повторного входа) — проверяем скоростью/тем, что сессия уже есть.
3. OrderFactory (dev API) готовит заказ, шиппер-админ видит его в веб-списке заказов (API-подготовка
   → UI-проверка).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.regression, pytest.mark.web]

# роль → (путь лендинга, видимая RU-строка-сторож)
_LANDING = {
    "super_admin": ("/super-admin/partners/shipper-companies", "Грузоотправители"),
    "shipper_admin": ("/dashboard", "Панель управления"),
    "shipper_manager": ("/shipper/storeroom", "Оператор склада"),
    "transport_admin": ("/transport/orders", "Заявки"),
}


@pytest.mark.parametrize("role", list(_LANDING))
def test_storage_state_and_ru_sentinel(page_as, web_cfg, expect_ru, role):
    """Инфра: восстановленная сессия роли → лендинг на RU (сторож China-first)."""
    path, ru_text = _LANDING[role]
    page = page_as(role)
    page.goto(web_cfg.base_url.rstrip("/") + path, wait_until="domcontentloaded")
    expect_ru(page, ru_text)  # ждёт видимую RU-строку (auto-wait) — заодно подтверждает, что не на логине
    assert "/auth/login" not in page.url, f"[{role}] сессия не восстановилась (редирект на вход)"


def test_storage_state_single_login_reuse(page_as, web_cfg):
    """storage_state = 1 логин/роль: два page_as(super_admin) дают восстановленную сессию оба раза
    (никакой формы входа — сразу на защищённой странице)."""
    for _ in range(2):
        page = page_as("super_admin")
        page.goto(web_cfg.base_url.rstrip("/") + "/super-admin/partners/shipper-companies",
                  wait_until="domcontentloaded")
        expect(page.get_by_text("Грузоотправители", exact=False).first).to_be_visible()
        assert "/auth/login" not in page.url, "сессия не восстановилась — потребовался вход"


def test_orderfactory_hook_api_prep(order_factory, page_as, web_cfg):
    """OrderFactory-хук: заказ готовится через API (dev), UI шиппер-админа видит его в списке.
    Заказ компании A; page_as('shipper_admin') — админ той же компании."""
    o = order_factory.make("PUBLISHED")
    num = o["displayNumber"]
    page = page_as("shipper_admin")
    page.goto(web_cfg.base_url.rstrip("/") + "/shipper/orders", wait_until="domcontentloaded")
    # номер заказа виден в списке (DataGrid); поиск по видимому тексту номера
    expect(page.get_by_text(num, exact=False).first).to_be_visible(timeout=web_cfg.nav_timeout_ms)
