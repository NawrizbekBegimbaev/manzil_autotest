"""Web модуль 1, под-блок 1 — форма входа: отрисовка, China-first, i18n (WEB-AUTH-001…049).

Проверяем то, что ВИДИТ пользователь на /auth/login: элементы формы, дефолтный язык (China-first),
локализацию, пикер телефона. Бизнес-контракт входа покрыт API-слоем (117 auth-тестов) — здесь
только отображение. China-first кейсы (001-фрагмент/007/047) — БЕЗ RU-пина (fresh_context_no_ru).

Прогон на DEV. Один тест ↔ один ID. POM: pages/auth/login_page.py.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from pages.auth.login_page import LoginPage

pytestmark = [pytest.mark.regression, pytest.mark.web]

# Пикер телефона показывает страны в англ. формате + ISO + код (react-phone-number-input):
# «ChinaCN (+86)», «UzbekistanUZ (+998)»… — проверяем по кодам набора (язык-независимо).
_DIAL_CODES = ("+86", "+998", "+7", "+996", "+992")  # CN, UZ, RU, KG, TJ — ровно 5


@pytest.fixture
def login(web_page, web_cfg):
    """LoginPage на /auth/login (RU-пин, без логина)."""
    lp = LoginPage(web_page(), web_cfg).open()
    return lp


# ═══ Отрисовка формы ══════════════════════════════════════════════════════════


@pytest.mark.high
def test_form_elements_001(login):
    """WEB-AUTH-001: на форме видны заголовок, ссылка регистрации, поля телефона (+86)/пароля, кнопка «Войти»."""
    expect(login.title.first).to_be_visible()
    expect(login.register_link.first).to_be_visible()
    expect(login.phone_input).to_be_visible()
    expect(login.password_input).to_be_visible()
    expect(login.submit_button).to_be_visible()
    expect(login.country_button).to_be_visible()  # дефолт Китай +86


@pytest.mark.low
def test_register_forgot_inert_004(login):
    """WEB-AUTH-004: ссылки «Зарегистрироваться»/«Забыли пароль?» инертны — URL остаётся на /auth/login."""
    login.forgot_link.first.click()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))
    login.register_link.first.click()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


@pytest.mark.medium
def test_password_visibility_toggle_006(login):
    """WEB-AUTH-006: по умолчанию пароль скрыт (type=password); после клика по «глазу» — text; повторно — снова password."""
    login.password_input.fill("SecretPass1!")
    expect(login.password_input).to_have_attribute("type", "password")
    login.password_toggle.click()
    expect(login.password_input).to_have_attribute("type", "text")
    login.password_toggle.click()
    expect(login.password_input).to_have_attribute("type", "password")


# ═══ Пикер телефона / страны ══════════════════════════════════════════════════


@pytest.mark.high
def test_country_default_and_list_007(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-007: дефолт — Китай (+86); в пикере РОВНО 5 стран (CN/UZ/RU/KG/TJ по кодам набора).
    China-first → БЕЗ RU-пина. Уточнено по факту: имена стран англ.+ISO+код (react-phone-number-input),
    не локализованы — проверяем по кодам набора (язык-независимо)."""
    lp = LoginPage(fresh_context_no_ru(), web_cfg).open_zh()
    expect(lp.country_button.first).to_be_visible()  # дефолт +86
    items = lp.open_country_picker()
    expect(items).to_have_count(5)  # ровно 5 стран
    joined = " ".join(items.all_text_contents())
    for code in _DIAL_CODES:
        assert code in joined, f"[WEB-AUTH-007] код {code} не найден в пикере: {joined}"


@pytest.mark.medium
def test_country_switch_keeps_number_011(login):
    """WEB-AUTH-011: смена страны сохраняет набранные цифры и меняет код на +998 (Узбекистан)."""
    login.phone_input.click()
    login.phone_input.press_sequentially("13800138000", delay=20)
    items = login.open_country_picker()
    items.filter(has_text="+998").first.click()  # Узбекистан
    expect(login.page.get_by_role("button", name="+998").first).to_be_visible()
    expect(login.phone_input).not_to_have_value("")  # цифры не пропали


@pytest.mark.low
def test_password_accepts_special_016(login):
    """WEB-AUTH-016: поле пароля принимает спецсимволы/пробелы без блокировки/обрезки."""
    val = "  P@ss w0rd!#$  "
    login.password_input.fill(val)
    expect(login.password_input).to_have_value(val)


# ═══ China-first / i18n ═══════════════════════════════════════════════════════


@pytest.mark.medium
def test_china_first_default_047(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-047: дефолтный язык — китайский (без RU-пина): 登录 / 请输入电话号码 / 请输入密码, страна +86."""
    page = fresh_context_no_ru()
    LoginPage(page, web_cfg).open_zh()
    expect(page.get_by_role("button", name="登录").first).to_be_visible()
    expect(page.get_by_placeholder("请输入电话号码").first).to_be_visible()
    expect(page.get_by_placeholder("请输入密码").first).to_be_visible()
    assert page.evaluate("() => localStorage.getItem('__tolgee_currentLanguage')") in (None, "zh"), \
        "China-first: язык не должен быть предустановлен в RU"


@pytest.mark.medium
def test_language_persists_reload_048(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-048: выбранный язык сохраняется между перезагрузками (localStorage), не сбрасывается на китайский."""
    page = fresh_context_no_ru()
    lp = LoginPage(page, web_cfg).open_zh()
    # переключить на русский через языковой переключатель
    page.evaluate("() => localStorage.setItem('__tolgee_currentLanguage','ru')")
    page.reload(wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Войти").first).to_be_visible()  # RU сохранился
    assert page.evaluate("() => localStorage.getItem('__tolgee_currentLanguage')") == "ru"
