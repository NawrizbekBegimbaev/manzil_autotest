"""UAT — Admin / Администратор грузоотправителя (AD-01..AD-19)."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from pages.shipper.orders_page import ShipperOrdersPage
from pages.shipper.reports_page import ReportsPage
from pages.shipper.staff_page import StaffPage
from pages.shipper.warehouses_page import WarehousesPage
from utils.data import StaffData

pytestmark = [pytest.mark.uat, pytest.mark.admin]

# Справочник городов на staging переводят на новую логику (глобальный справочник
# Страна/Уровень/Путь, добавление города переработано). Форма склада использует
# выбор города из этого справочника, поэтому её POM временно не соответствует UI.
# Приостановлено по решению: снять xfail и обновить POM, когда логика городов
# стабилизируется. См. docs/BUGS.md → BUG-013.
_BLOCKED_CITY_UI = (
    "Приостановлено (BUG-013): на staging меняется логика справочника городов "
    "(редизайн, добавление города переработано); выбор города в форме склада не "
    "совпадает с текущим POM. Ждём стабилизации UI."
)


@allure.title("AD-01 Вход администратора грузоотправителя")
def test_ad01_login(admin_page):
    expect(admin_page).to_have_url(re.compile(r"/dashboard"))
    expect(admin_page.get_by_role("heading", name="Панель управления").first).to_be_visible()


@allure.title("AD-02 Просмотр показателей на дашборде")
def test_ad02_dashboard(admin_page, cfg):
    from pages.common.nav_page import NavPage
    NavPage(admin_page, cfg).open_path("/dashboard")
    expect(admin_page.get_by_role("heading", name="Панель управления").first).to_be_visible()
    expect(admin_page.get_by_text("Опубликовано").first).to_be_visible()


@allure.title("AD-03 Просмотр списка заказов")
def test_ad03_orders_list(admin_page, cfg):
    ShipperOrdersPage(admin_page, cfg).open()
    expect(admin_page.get_by_role("heading", name="Админ").first).to_be_visible()
    expect(admin_page.locator('[role="grid"], table').first).to_be_visible()


@allure.title("AD-04 Фильтрация списка заказов")
def test_ad04_orders_filter(admin_page, cfg, seeder):
    o = seeder.order("published")
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("AD-05 Открытие карточки заказа")
def test_ad05_order_card(admin_page, cfg, seeder):
    o = seeder.order("published")
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    page.open_order(o["displayNumber"])
    expect(admin_page).to_have_url(re.compile(r"/shipper/orders/"))


@allure.title("AD-06 Просмотр предложений перевозчиков по заказу")
def test_ad06_view_offers(admin_page, cfg, seeder):
    o = seeder.order("quoted")
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    page.open_order(o["displayNumber"])
    expect(admin_page.get_by_role("button", name="Принять").first).to_be_visible()


@allure.title("AD-07 Выбор перевозчика-победителя")
def test_ad07_select_winner(admin_page, cfg, seeder):
    o = seeder.order("quoted")
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    page.open_order(o["displayNumber"])
    page.accept_first_offer()
    expect(page.toast_winner).to_be_visible()


@allure.title("AD-08 Просмотр списка сотрудников")
def test_ad08_staff_list(admin_page, cfg):
    StaffPage(admin_page, cfg).open()
    expect(admin_page.get_by_role("heading", name="Сотрудники").first).to_be_visible()


@allure.title("AD-09 Создание Менеджера")
def test_ad09_create_manager(admin_page, cfg):
    page = StaffPage(admin_page, cfg).open()
    data = StaffData()
    page.open_create().create(data, cfg.new_account_password, "Менеджер")
    try:
        expect(page.toast_created).to_be_visible()
        page.search(data.full_name)
        expect(page.row(data.full_name).first).to_be_visible()
    finally:
        StaffPage(admin_page, cfg).open().delete_row(data.full_name)


@allure.title("AD-10 Создание Сотрудника склада")
def test_ad10_create_warehouse_staff(admin_page, cfg):
    page = StaffPage(admin_page, cfg).open()
    data = StaffData()
    page.open_create().create(data, cfg.new_account_password, "Сотрудник склада")
    try:
        expect(page.toast_created).to_be_visible()
        page.search(data.full_name)
        expect(page.row(data.full_name).first).to_be_visible()
    finally:
        StaffPage(admin_page, cfg).open().delete_row(data.full_name)


@allure.title("AD-11 Редактирование сотрудника")
def test_ad11_edit_staff(admin_page, cfg):
    page = StaffPage(admin_page, cfg).open()
    data = StaffData()
    page.open_create().create(data, cfg.new_account_password, "Менеджер")
    expect(page.toast_created).to_be_visible()
    new_name = data.full_name + " ИЗМ"
    try:
        page.open_edit(data.full_name).set_name(new_name).save()
        page.search(new_name)
        expect(page.row(new_name).first).to_be_visible()
    finally:
        StaffPage(admin_page, cfg).open().delete_row(new_name)


@allure.title("AD-12 Удаление сотрудника")
def test_ad12_delete_staff(admin_page, cfg):
    page = StaffPage(admin_page, cfg).open()
    data = StaffData()
    page.open_create().create(data, cfg.new_account_password, "Менеджер")
    expect(page.toast_created).to_be_visible()
    page.delete_row(data.full_name)
    page.search(data.full_name)
    expect(page.row(data.full_name)).to_have_count(0)


@allure.title("AD-13 Просмотр списка складов")
def test_ad13_warehouses_list(admin_page, cfg):
    WarehousesPage(admin_page, cfg).open()
    expect(admin_page.get_by_role("heading", name="Склады").first).to_be_visible()


@allure.title("AD-14 Добавление склада")
@pytest.mark.xfail(reason=_BLOCKED_CITY_UI, strict=False, run=False)
def test_ad14_add_warehouse(admin_page, cfg):
    from utils.data import SANITY_MARKER, _letters
    page = WarehousesPage(admin_page, cfg).open()
    name = f"{SANITY_MARKER} Склад {_letters(4)}"
    page.add(name)
    try:
        page.search(name)
        expect(page.row(name).first).to_be_visible()
    finally:
        WarehousesPage(admin_page, cfg).open().delete_row(name)


@allure.title("AD-15 Редактирование и удаление склада")
@pytest.mark.xfail(reason=_BLOCKED_CITY_UI, strict=False, run=False)
def test_ad15_delete_warehouse(admin_page, cfg):
    from utils.data import SANITY_MARKER, _letters
    page = WarehousesPage(admin_page, cfg).open()
    name = f"{SANITY_MARKER} Склад {_letters(4)}"
    page.add(name)
    page.search(name)
    expect(page.row(name).first).to_be_visible()
    page.delete_row(name)
    page.search(name)
    expect(page.row(name)).to_have_count(0)


@allure.title("AD-16 Отчёт «Средняя цена»")
def test_ad16_report_avg(admin_page, cfg):
    page = ReportsPage(admin_page, cfg).open()
    page.open_tab("Средняя цена")
    expect(page.table).to_be_visible()


@allure.title("AD-17 Отчёт «По компаниям»")
def test_ad17_report_companies(admin_page, cfg):
    page = ReportsPage(admin_page, cfg).open()
    page.open_tab("По компаниям")
    expect(page.table).to_be_visible()


@allure.title("AD-18 Отмена заказа")
def test_ad18_cancel_order(admin_page, cfg, seeder):
    o = seeder.order("selected")
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.cancel_order_from_list(o["displayNumber"])
    page.filter_by_number(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_contain_text("Отмен")


@allure.title("AD-19 Завершение заказа")
def test_ad19_complete_order(admin_page, cfg, seeder):
    # В текущем веб-UI нет ручной кнопки «Завершить» (завершение идёт через 1С/API),
    # поэтому завершаем заказ через API и проверяем, что статус «Завершён» виден в списке.
    o = seeder.order("in_transit")
    seeder.complete(o["id"])
    page = ShipperOrdersPage(admin_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_contain_text("Завершён")
