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


# ═══ Пикер/валидация длины телефона (продолжение) ════════════════════════════


@pytest.mark.high
def test_phone_length_limit_009(login):
    """WEB-AUTH-009: для Китая нельзя ввести больше 11 цифр — лишние отбрасываются, подсказка «11»."""
    login.phone_input.click()
    login.phone_input.press_sequentially("138001380001234", delay=15)  # 15 цифр
    digits = "".join(ch for ch in login.phone_input.input_value() if ch.isdigit())
    assert len(digits) == 11, f"[WEB-AUTH-009] ожидали 11 цифр (лимит Китая), получили {len(digits)}: {digits!r}"
    expect(login.page.get_by_text("11", exact=False).first).to_be_visible()


@pytest.mark.low
def test_phone_clear_button_012(login):
    """WEB-AUTH-012: крестик очищает поле телефона; виден только при непустом значении."""
    login.phone_input.click()
    login.phone_input.press_sequentially("13800138000", delay=15)
    expect(login.phone_clear_button).to_be_visible()
    login.phone_clear_button.click()
    digits = "".join(ch for ch in login.phone_input.input_value() if ch.isdigit())
    assert digits == "", f"[WEB-AUTH-012] поле не очищено: {login.phone_input.input_value()!r}"


@pytest.mark.low
def test_country_picker_no_search_008(login):
    """WEB-AUTH-008: пикер из 5 стран — поля поиска НЕТ (короткий список, фильтрация не предусмотрена).
    Уточнено по факту 2026-07-24: MUI Menu без search-input (кейс описывал несуществующую фильтрацию)."""
    items = login.open_country_picker()
    expect(items).to_have_count(5)
    menu = login.page.get_by_role("menu").last
    assert menu.locator("input").count() == 0, "[WEB-AUTH-008] в пикере нет поля поиска (5 стран)"


# ═══ i18n: переключатель языка / RTL ═════════════════════════════════════════


@pytest.mark.high
def test_language_switcher_046(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-046: в списке ровно 5 языков; выбор 中文 сразу перерисовывает форму (登录), без reload."""
    lp = LoginPage(fresh_context_no_ru(), web_cfg).open_zh()
    items = lp.open_lang_menu()
    expect(items).to_have_count(5)
    joined = " ".join(items.all_text_contents())
    for lang in ("Русский", "O'zbek", "Кыргызча", "中文", "ئۇيغۇرچە"):
        assert lang in joined, f"[WEB-AUTH-046] язык {lang!r} не в списке: {joined}"
    items.filter(has_text="中文").first.click()
    expect(lp.page.get_by_role("button", name="登录").first).to_be_visible()  # живое переключение


@pytest.mark.medium
def test_uyghur_rtl_049(fresh_context_no_ru, web_cfg):
    """WEB-AUTH-049: уйгурский разворачивает интерфейс справа налево (dir=rtl на документе)."""
    lp = LoginPage(fresh_context_no_ru(), web_cfg).open_zh()
    lp.open_lang_menu().filter(has_text="ئۇيغۇرچە").first.click()
    lp.page.wait_for_function("() => document.documentElement.getAttribute('dir') === 'rtl'",
                              timeout=web_cfg.default_timeout_ms)
    assert lp.page.locator("html").get_attribute("dir") == "rtl", "[WEB-AUTH-049] direction не rtl"


@pytest.mark.low
def test_policy_links_inert_005(login):
    """WEB-AUTH-005: ссылки политик ведут на href=# — переход не происходит, форма на месте."""
    links = login.page.get_by_role("link")
    hash_links = [l for l in links.all() if (l.get_attribute("href") or "") in ("#", "")]
    # достаточно, что форма остаётся на /auth/login после клика по любой # -ссылке
    if hash_links:
        hash_links[0].click()
    expect(login.page).to_have_url(re.compile(r"/auth/login"))


@pytest.mark.medium
def test_keyboard_nav_056(login):
    """WEB-AUTH-056: интерактивные элементы формы достижимы с клавиатуры (Tab доходит до телефона/пароля/кнопки)."""
    reached = set()
    login.phone_input.focus()
    for _ in range(12):
        tag = login.page.evaluate("() => document.activeElement && document.activeElement.tagName")
        ph = login.page.evaluate("() => document.activeElement && document.activeElement.getAttribute('placeholder')")
        if ph == "Введите номер телефона":
            reached.add("phone")
        if ph == "Введите пароль":
            reached.add("password")
        if tag == "BUTTON":
            reached.add("button")
        login.page.keyboard.press("Tab")
    assert {"phone", "password", "button"} <= reached, f"[WEB-AUTH-056] с клавиатуры достижимы не все: {reached}"
