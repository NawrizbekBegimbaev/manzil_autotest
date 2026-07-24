"""Web-регрессия (Playwright) — инфра Фазы-0. Прогон на DEV (консистентность с API-слоем).

Отличия от tests/sanity (staging):
- base = cfg.dev_url (dev), учётки — из dev-тенанта (api_dev_roles, провижинится через API).
- **storage_state на роль**: UI-логин выполняется РАЗ на роль за прогон → сохраняется state-файл
  (localStorage: manzil.accessToken/refreshToken + __tolgee_currentLanguage=ru). Тесты получают
  СВЕЖИЙ изолированный контекст с уже восстановленной сессией — параллель-безопасно.
- **RU-сторож**: FORCE_RU через add_init_script ДО первой навигации на КАЖДОМ контексте (в т.ч.
  восстановленном) — China-first дефолт не просачивается. Проверено: tolgee остаётся 'ru' после
  restore; фикстура `expect_ru` дополнительно ассертит видимую RU-строку.
- **OrderFactory-хук**: заказ нужного статуса готовится через API (dev), UI только проверяет.

Форма входа (WEB-AUTH-*) логинится руками (без storage_state) — им нужен сам процесс входа.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from config.settings import Settings, get_settings
from pages.auth.login_page import LoginPage

# Форсировать язык RU до любого скрипта страницы (China-first дефолт SPA → zh/uz).
FORCE_RU = "try{localStorage.setItem('__tolgee_currentLanguage','ru');}catch(e){}"

# Роли, доступные в вебе (clientType WEB). Склад — mobile-only, здесь недоступен.
WEB_ROLES = ("super_admin", "shipper_admin", "shipper_manager", "transport_admin")


@pytest.fixture(scope="session")
def web_cfg(cfg: Settings) -> Settings:
    """Settings с base_url=dev — POM (base_page.goto) ходит на dev."""
    return cfg.model_copy(update={"base_url": cfg.dev_url})


@pytest.fixture(scope="session")
def web_ctx_kwargs() -> dict:
    # 1920×1080 — иначе DataGrid прячет колонку действий (грабли).
    return {"viewport": {"width": 1920, "height": 1080}, "ignore_https_errors": True}


@pytest.fixture(scope="session")
def _storage_states(browser: Browser, web_cfg: Settings, web_ctx_kwargs: dict,
                    api_dev_roles: dict, tmp_path_factory) -> dict:
    """Логин раз на роль → state-файл. Ленивая инициализация: логинится только запрошенная роль."""
    base = tmp_path_factory.mktemp("web_state")
    cache: dict[str, str] = {}

    def _ensure(role: str) -> str:
        if role not in cache:
            phone, pwd, _ = api_dev_roles[role]
            ctx = browser.new_context(**web_ctx_kwargs)
            ctx.add_init_script(FORCE_RU)
            page = ctx.new_page()
            LoginPage(page, web_cfg).login(phone, pwd)
            page.wait_for_load_state("domcontentloaded")
            path = str(base / f"{role}.json")
            ctx.storage_state(path=path)
            ctx.close()
            cache[role] = path
        return cache[role]

    return {"ensure": _ensure}


@pytest.fixture
def page_as(browser: Browser, web_cfg: Settings, web_ctx_kwargs: dict, _storage_states: dict):
    """page_as(role) → свежий контекст с восстановленной сессией роли + пере-форсированным RU.
    Контексты закрываются после теста."""
    contexts = []

    def _open(role: str) -> Page:
        assert role in WEB_ROLES, f"web-роль '{role}' недоступна (склад — mobile-only)"
        state = _storage_states["ensure"](role)
        ctx = browser.new_context(**web_ctx_kwargs, storage_state=state)
        ctx.add_init_script(FORCE_RU)  # пере-форс RU даже на восстановленной сессии
        ctx.set_default_timeout(web_cfg.default_timeout_ms)
        ctx.set_default_navigation_timeout(web_cfg.nav_timeout_ms)
        contexts.append(ctx)
        return ctx.new_page()

    yield _open
    for ctx in contexts:
        ctx.close()


@pytest.fixture
def fresh_login(browser: Browser, web_cfg: Settings, web_ctx_kwargs: dict):
    """Ручной UI-логин в свежем контексте (для WEB-AUTH-* — самой формы входа, без storage_state)."""
    contexts = []

    def _login(phone: str, password: str) -> Page:
        ctx = browser.new_context(**web_ctx_kwargs)
        ctx.add_init_script(FORCE_RU)
        page = ctx.new_page()
        LoginPage(page, web_cfg).login(phone, password)
        contexts.append(ctx)
        return page

    yield _login
    for ctx in contexts:
        ctx.close()


@pytest.fixture
def expect_ru():
    """RU-сторож: убедиться, что China-first не просочился — видимый RU-текст присутствует."""
    def _check(page: Page, ru_text: str):
        expect(page.get_by_text(ru_text, exact=False).first).to_be_visible()
        # tolgee остаётся 'ru' (не сброшен на zh на восстановленной сессии)
        lang = page.evaluate("() => localStorage.getItem('__tolgee_currentLanguage')")
        assert lang == "ru", f"RU-сторож: __tolgee_currentLanguage={lang!r} (China-first просочился)"
    return _check
