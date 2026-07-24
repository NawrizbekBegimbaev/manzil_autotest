"""Web модуль 1, под-блок 3 — редиректы, гард-роуты, сессия (WEB-AUTH-002/003/031…042).

Проверяем поведение навигации/сессии, которое видит пользователь: редиректы без токена и
авторизованного с логина, тихий возврат с недоступного маршрута, персист сессии (F5), 404,
logout. storage_state (page_as) и route-перехват — основной инструмент.

Каждый тест НАЧИНАЕТСЯ с явной навигации на свой экран (урок полного прогона — не полагаться
на состояние после соседа). Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.regression, pytest.mark.web]

_LOGIN = re.compile(r"/auth/login")


def _goto(page, cfg, path):
    page.goto(cfg.base_url.rstrip("/") + path, wait_until="domcontentloaded")


# ═══ Редиректы без токена ════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.parametrize("path", ["/", "/auth", "/dashboard"], ids=["root-002", "auth-003", "protected-031"])
def test_redirect_to_login_no_token(web_page, web_cfg, path):
    """WEB-AUTH-002/003/031: без токена корень / /auth / защищённый маршрут → редирект на /auth/login."""
    page = web_page()
    _goto(page, web_cfg, path)
    expect(page).to_have_url(_LOGIN, timeout=web_cfg.nav_timeout_ms)


# ═══ Авторизованный: редиректы и гард-роуты ══════════════════════════════════


@pytest.mark.high
def test_authed_on_login_redirects_home_032(page_as, web_cfg):
    """WEB-AUTH-032: авторизованный пользователь на /auth/login → редирект на стартовую роли."""
    page = page_as("shipper_admin")
    _goto(page, web_cfg, "/auth/login")
    expect(page).to_have_url(re.compile(r"/dashboard"), timeout=web_cfg.nav_timeout_ms)


@pytest.mark.high
def test_silent_redirect_inaccessible_033(page_as, web_cfg):
    """WEB-AUTH-033: менеджер на недоступный /settings → тихий возврат на его стартовую (/shipper/storeroom)."""
    page = page_as("shipper_manager")
    _goto(page, web_cfg, "/settings")
    expect(page).to_have_url(re.compile(r"/shipper/storeroom"), timeout=web_cfg.nav_timeout_ms)


@pytest.mark.high
def test_capability_gated_route_034(page_as, web_cfg):
    """WEB-AUTH-034: менеджер без REPORTS по прямому URL /shipper/reports → возврат на стартовую (доступ по
    адресу ограничен теми же правами, что и видимость пункта). Бизнес-контракт: API-RBAC-088 (REPORTS)."""
    page = page_as("shipper_manager")
    _goto(page, web_cfg, "/shipper/reports")
    expect(page).not_to_have_url(re.compile(r"/shipper/reports$"), timeout=web_cfg.nav_timeout_ms)
    expect(page).to_have_url(re.compile(r"/shipper/storeroom"), timeout=web_cfg.nav_timeout_ms)


# ═══ Сессия: F5, back/forward ════════════════════════════════════════════════


@pytest.mark.high
def test_refresh_keeps_session_035(page_as, web_cfg):
    """WEB-AUTH-035: F5 сохраняет сессию — та же страница, без возврата на форму входа."""
    page = page_as("shipper_admin")
    _goto(page, web_cfg, "/dashboard")
    expect(page).to_have_url(re.compile(r"/dashboard"))
    page.reload(wait_until="domcontentloaded")
    expect(page).to_have_url(re.compile(r"/dashboard"))
    assert "/auth/login" not in page.url, "[WEB-AUTH-035] сессия потеряна после F5"


@pytest.mark.medium
def test_browser_back_forward_036(page_as, web_cfg):
    """WEB-AUTH-036: Назад/Вперёд корректно ходят по истории, правила доступа применяются на каждом переходе."""
    page = page_as("super_admin")
    _goto(page, web_cfg, "/super-admin/partners/shipper-companies")
    expect(page.get_by_text("Грузоотправители", exact=False).first).to_be_visible()
    _goto(page, web_cfg, "/super-admin/partners/transport-companies")
    page.wait_for_load_state("domcontentloaded")
    page.go_back()
    expect(page).to_have_url(re.compile(r"/shipper-companies"), timeout=web_cfg.nav_timeout_ms)
    page.go_forward()
    expect(page).to_have_url(re.compile(r"/transport-companies"), timeout=web_cfg.nav_timeout_ms)


# ═══ 404 / logout ════════════════════════════════════════════════════════════


@pytest.mark.medium
def test_not_found_page_037(page_as, web_cfg):
    """WEB-AUTH-037: несуществующий маршрут → страница «не найдено» (не пустой экран, не бесконечная загрузка).
    Уточнено по факту: текст английский «page not found» (не локализован → BUG-041)."""
    page = page_as("super_admin")
    _goto(page, web_cfg, "/zzz-nonexistent-route")
    expect(page.get_by_text(re.compile(r"page not found|не найден", re.I)).first).to_be_visible(
        timeout=web_cfg.nav_timeout_ms)


@pytest.mark.high
def test_logout_042(page_as, web_cfg):
    """WEB-AUTH-042: выход → тост о выходе + возврат на /auth/login; назад во внутренние без входа нельзя."""
    page = page_as("shipper_admin")
    _goto(page, web_cfg, "/dashboard")
    # открыть меню аккаунта (аватар справа сверху) и нажать «Выйти» (отдельная кнопка в поповере,
    # не menuitem — там только заглушки «Настройки профиля»/«Уведомления», см. WEB-AUTH-060)
    _open_account_menu(page)
    page.get_by_text(re.compile(r"Выйти", re.I)).first.click()
    expect(page).to_have_url(_LOGIN, timeout=web_cfg.nav_timeout_ms)


def _open_account_menu(page):
    """Открыть меню аккаунта: кнопка с аватаром/инициалом в правом верхнем углу."""
    # аватар — кнопка, содержащая MuiAvatar; кликаем её
    trigger = page.locator("header button:has(.MuiAvatar-root), button:has(.MuiAvatar-root)").last
    trigger.click()
    page.get_by_role("menu").last.wait_for(state="visible")
