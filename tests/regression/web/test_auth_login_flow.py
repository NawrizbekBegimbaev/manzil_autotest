"""Web модуль 1, под-блок 2 — вход: валидация, submit, ОТОБРАЖЕНИЕ результата (WEB-AUTH-013…024).

Проверяем то, что ВИДИТ пользователь: сообщения валидации, приветственный/ошибочный тост, редирект,
состояние кнопки. Бизнес-контракт входа (401/403/wrong-app) покрыт API-слоем (API-AUTH-*) — здесь
только отображение (docstring ссылается на покрывающий API-тест).

Прогон на DEV. Один тест ↔ один ID.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from pages.auth.login_page import LoginPage

pytestmark = [pytest.mark.regression, pytest.mark.web]

_LOGIN = "**/api/v1/auth/login"


@pytest.fixture
def login(web_page, web_cfg):
    return LoginPage(web_page(), web_cfg).open()


# ═══ Валидация формы (отображение сообщений) ═════════════════════════════════


@pytest.mark.high
def test_empty_phone_message_013(login):
    """WEB-AUTH-013: пустой телефон → сообщение «Введите телефон», форма не отправляется (остаёмся на логине)."""
    login.phone_input.click()
    login.password_input.click()  # blur пустого телефона
    login.submit()
    expect(login.page.get_by_text("Введите телефон", exact=False).first).to_be_visible()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


@pytest.mark.high
def test_empty_password_message_015(login):
    """WEB-AUTH-015: пустой пароль → сообщение «Введите пароль», вход не выполняется."""
    login.phone_input.click()
    login.phone_input.press_sequentially("13800138000", delay=20)
    login.submit()
    expect(login.page.get_by_text("Введите пароль", exact=False).first).to_be_visible()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


# ═══ Submit: состояние кнопки, Enter ═════════════════════════════════════════


@pytest.mark.high
def test_loading_state_no_double_submit_017(login, web_cfg):
    """WEB-AUTH-017: на время запроса кнопка «Войти» заблокирована (защита от двойной отправки).
    Держим ответ логина «висящим» (route без continue), ловим disabled-состояние, затем unroute.
    Бизнес-контракт: API-AUTH-001."""
    holds = []
    login.page.route(_LOGIN, lambda route: holds.append(route))  # держим запрос, не отвечаем
    login.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password).submit()
    expect(login.submit_button).to_be_disabled()  # во время висящего запроса
    login.page.unroute(_LOGIN)
    for r in holds:  # отпустить, чтобы не мешать teardown
        try:
            r.abort()
        except Exception:  # noqa: BLE001
            pass


@pytest.mark.medium
def test_enter_submits_018(login, web_cfg):
    """WEB-AUTH-018: Enter отправляет форму как «Войти» (при верных данных — вход и редирект)."""
    login.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password)
    login.password_input.press("Enter")
    expect(login.page).to_have_url(re.compile(r"/super-admin/partners/shipper-companies"),
                                   timeout=web_cfg.nav_timeout_ms)


# ═══ Результат входа: тосты + редирект (отображение) ═════════════════════════


@pytest.mark.high
def test_success_toast_and_redirect_019(login, web_cfg):
    """WEB-AUTH-019: успешный вход → тост «Добро пожаловать, …» + редирект на стартовую роли.
    Бизнес-контракт: API-AUTH-001 (успешный логин)."""
    login.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password).submit()
    expect(login.page).to_have_url(re.compile(r"/super-admin/partners/shipper-companies"),
                                   timeout=web_cfg.nav_timeout_ms)
    expect(login.page.get_by_text("Добро пожаловать", exact=False).first).to_be_visible()


@pytest.mark.medium
def test_welcome_toast_localized_020(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-020: приветственный тост локализован (китайский UI → 欢迎, не по-русски). Исправлено на dev."""
    lp = LoginPage(fresh_context_no_ru(), web_cfg).open_zh()
    lp.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password).submit()
    lp.page.wait_for_url(re.compile(r"/super-admin/"), timeout=web_cfg.nav_timeout_ms)
    expect(lp.page.get_by_text("欢迎", exact=False).first).to_be_visible()


@pytest.mark.high
def test_invalid_creds_stays_021(login):
    """WEB-AUTH-021: неверные данные (401) → вход не выполняется, остаёмся на форме, поля доступны.
    Бизнес-контракт: API-AUTH-004 (error.invalid-credentials). Web проверяет отображение."""
    login.fill_creds("+998900000000", "WrongPass123!").submit()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))
    expect(login.submit_button).to_be_enabled()  # можно повторить
    expect(login.phone_input).to_be_editable()


@pytest.mark.high
def test_unsupported_account_022(login, api_dev_roles):
    """WEB-AUTH-022: учётка склада (WAREHOUSE_APP) в вебе → wrong-app → тост «не поддерживается»,
    остаёмся на логине, сессии нет. Бизнес-контракт: API-AUTH wrong-app (error.wrong-app)."""
    wh_phone, wh_pwd, _ = api_dev_roles["shipper_warehouse"]
    login.fill_creds(wh_phone, wh_pwd).submit()
    expect(login.page.get_by_text("нет доступа к этому приложению", exact=False).first).to_be_visible()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


# ═══ Сетевые/серверные ошибки входа (отображение) ════════════════════════════


@pytest.mark.medium
def test_network_error_toast_023(login, web_cfg):
    """WEB-AUTH-023: ошибка сети при входе → тост об ошибке, форма остаётся доступной."""
    login.page.route(_LOGIN, lambda route: route.abort())
    login.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password).submit()
    expect(login.page.get_by_text(re.compile(r"[Оо]шибка"), exact=False).first).to_be_visible()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


@pytest.mark.medium
def test_server_500_toast_024(login, web_cfg):
    """WEB-AUTH-024: 500 при входе → тост с текстом ошибки, кнопка «Войти» снова активна."""
    login.page.route(_LOGIN, lambda route: route.fulfill(
        status=500, content_type="application/json",
        body='{"code":"INTERNAL_SERVER_ERROR","status":500,"detail":"服务器内部错误"}'))
    login.fill_creds(web_cfg.dev_super_admin_phone, web_cfg.dev_super_admin_password).submit()
    expect(login.page.get_by_text(re.compile(r"[Оо]шибка|错误"), exact=False).first).to_be_visible()
    expect(login.submit_button).to_be_enabled()
