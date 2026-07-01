"""UAT — TK / транспортная компания (перевозчик) (TK-01..TK-14)."""

from __future__ import annotations

import random
import re
import string

import allure
import pytest
from playwright.sync_api import expect

from pages.transport.carrier_drivers_page import CarrierDriversPage
from pages.transport.carrier_orders_page import CarrierOrdersPage
from utils.data import SANITY_MARKER, _letters, unique_phone

pytestmark = [pytest.mark.uat, pytest.mark.tk]


def _plate():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


@allure.title("TK-01 Вход перевозчика")
def test_tk01_login(carrier_page):
    expect(carrier_page).to_have_url(re.compile(r"/transport/orders"))
    expect(carrier_page.get_by_role("heading", name="Заявки").first).to_be_visible()


@allure.title("TK-02 Просмотр доступных заявок (лента)")
def test_tk02_feed(carrier_page, cfg):
    CarrierOrdersPage(carrier_page, cfg).open()
    expect(carrier_page.get_by_role("table")).to_be_visible()


@allure.title("TK-03 Поиск заявки по номеру")
def test_tk03_search(carrier_page, cfg, seeder):
    o = seeder.order("published")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.search(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("TK-04 Открытие заявки из ленты")
def test_tk04_open_order(carrier_page, cfg, seeder):
    o = seeder.order("published")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.search(o["displayNumber"])
    page.open_order(o["displayNumber"])
    expect(carrier_page).to_have_url(re.compile(r"/transport/orders/"))


@allure.title("TK-05 Отправить предложение цены")
def test_tk05_submit_offer(carrier_page, cfg, seeder):
    o = seeder.order("published")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.search(o["displayNumber"])
    page.open_order(o["displayNumber"])
    page.submit_offer(4500, "по тесту")
    expect(page.toast_submitted).to_be_visible()


@allure.title("TK-06 Изменить свою цену")
def test_tk06_edit_offer(carrier_page, cfg, seeder):
    o = seeder.order("published")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.search(o["displayNumber"])
    page.open_order(o["displayNumber"])
    page.submit_offer(4500)
    expect(page.toast_submitted).to_be_visible()
    page.edit_offer(4200)
    expect(carrier_page.get_by_text("Цена обновлена")).to_be_visible()


@allure.title("TK-07 Просмотр своих предложений по статусам")
def test_tk07_my_offers(carrier_page, cfg, seeder):
    o = seeder.order("published")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.search(o["displayNumber"])
    page.open_order(o["displayNumber"])
    page.submit_offer(4500)
    expect(page.toast_submitted).to_be_visible()
    page.open().open_tab("Ставка сделана")
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("TK-08 Выигранная заявка во вкладке «Выбран»")
def test_tk08_won(carrier_page, cfg, seeder):
    o = seeder.order("selected")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.open_tab("Выбран")
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("TK-09 Просмотр списка водителей")
def test_tk09_drivers_list(carrier_page, cfg):
    CarrierDriversPage(carrier_page, cfg).open()
    expect(carrier_page.get_by_role("heading", name="Водители").first).to_be_visible()


@allure.title("TK-10 Добавление водителя")
def test_tk10_add_driver(carrier_page, cfg):
    page = CarrierDriversPage(carrier_page, cfg).open()
    name = f"{SANITY_MARKER} Driver {_letters(4)}"
    page.open_create().fill_create(name, unique_phone())
    page.submit_button.click()
    try:
        expect(page.toast_created).to_be_visible()
        page.search(name)
        expect(page.row(name).first).to_be_visible()
    finally:
        CarrierDriversPage(carrier_page, cfg).open().delete_row(name)


@allure.title("TK-11 Редактирование и удаление водителя")
def test_tk11_edit_delete_driver(carrier_page, cfg):
    page = CarrierDriversPage(carrier_page, cfg).open()
    name = f"{SANITY_MARKER} Driver {_letters(4)}"
    page.open_create().fill_create(name, unique_phone())
    page.submit_button.click()
    expect(page.toast_created).to_be_visible()
    new_name = name + " ИЗМ"
    page.open_edit(name).set_name(new_name).save()
    page.search(new_name)
    expect(page.row(new_name).first).to_be_visible()
    page.delete_row(new_name)
    page.search(new_name)
    expect(page.row(new_name)).to_have_count(0)


@allure.title("TK-12 Назначить водителя на выигранную заявку и начать")
def test_tk12_assign_start(carrier_page, cfg, seeder):
    seeder.create_driver()  # ensure the carrier has a free driver
    o = seeder.order("selected")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.open_tab("Выбран")
    page.open_order(o["displayNumber"])
    page.assign_and_start(_plate())
    expect(carrier_page.get_by_text("В работе").first).to_be_visible()


@allure.title("TK-13 Просмотр заявки в работе")
def test_tk13_in_work(carrier_page, cfg, seeder):
    o = seeder.order("in_work")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.open_tab("В работе")
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("TK-14 Замена назначенного водителя")
def test_tk14_replace_driver(carrier_page, cfg, seeder):
    seeder.create_driver()  # a spare free driver to swap in
    o = seeder.order("in_work")
    page = CarrierOrdersPage(carrier_page, cfg).open()
    page.open_tab("В работе")
    page.open_order(o["displayNumber"])
    carrier_page.get_by_role("button", name="Заменить").first.click()
    page.dialog.wait_for(state="visible")
    page.dialog.get_by_role("radio").first.check()
    page.dialog.get_by_role("textbox").first.fill(_plate())
    page.dialog.get_by_role("button", name="Заменить").click()
    expect(carrier_page.get_by_text("Водитель заменён")).to_be_visible()
