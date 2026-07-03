"""UAT — Менеджер / оператор склада + диспетчер (MN-01..MN-09)."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from pages.shipper.communication_page import CommunicationPage
from pages.shipper.storeroom_page import StoreroomPage

pytestmark = [pytest.mark.uat, pytest.mark.manager]



@allure.title("MN-01 Вход менеджера")
def test_mn01_login(manager_page):
    expect(manager_page).to_have_url(re.compile(r"/shipper/storeroom"))
    expect(manager_page.get_by_role("heading", name="Оператор склада").first).to_be_visible()


@allure.title("MN-02 Список заявок оператора склада")
def test_mn02_storeroom_list(manager_page, cfg):
    StoreroomPage(manager_page, cfg).open()
    expect(manager_page.get_by_role("heading", name="Оператор склада").first).to_be_visible()
    expect(manager_page.locator('[role="grid"], table').first).to_be_visible()


@allure.title("MN-03 Фильтрация заявок")
def test_mn03_filter(manager_page, cfg, seeder):
    o = seeder.order("published")
    page = StoreroomPage(manager_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_be_visible()


@allure.title("MN-04 Открытие заявки")
def test_mn04_open_order(manager_page, cfg, seeder):
    o = seeder.order("published")
    page = StoreroomPage(manager_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    page.open_order(o["displayNumber"])
    expect(manager_page).to_have_url(re.compile(r"/shipper/storeroom/"))


@allure.title("MN-05 Просмотр раздела «Диспетчер»")
def test_mn05_dispatcher(manager_page, cfg):
    CommunicationPage(manager_page, cfg).open()
    expect(manager_page.get_by_role("heading", name="Диспетчер").first).to_be_visible()


@allure.title("MN-06 Связь с водителем по заявке в работе")
def test_mn06_communication(manager_page, cfg, seeder):
    o = seeder.order("in_work")
    page = CommunicationPage(manager_page, cfg).open()
    page.open_call_status(o["displayNumber"])
    expect(page.dialog).to_be_visible()


@allure.title("MN-07 Просмотр откликов по заявке")
def test_mn07_view_offers(manager_page, cfg, seeder):
    # У менеджера в вебе нет отдельного экрана списка откликов (он только у админа).
    # Менеджер видит, что по заявке поступили ставки — статус «Цена предложена».
    o = seeder.order("quoted")
    page = StoreroomPage(manager_page, cfg).open()
    page.filter_by_number(o["displayNumber"])
    page.open_order(o["displayNumber"])
    expect(manager_page.get_by_text("Цена предложена").first).to_be_visible()


@allure.title("MN-08 Отмена заявки")
def test_mn08_cancel(manager_page, cfg, seeder):
    o = seeder.order("selected")
    page = StoreroomPage(manager_page, cfg).open()
    page.cancel_order(o["displayNumber"])
    page.filter_by_number(o["displayNumber"])
    expect(page.order_row(o["displayNumber"]).first).to_contain_text("Отмен")


@allure.title("MN-09 Повторная публикация отменённой заявки")
def test_mn09_republish(manager_page, cfg, seeder):
    o = seeder.order("selected")
    seeder.cancel(o["id"])
    page = StoreroomPage(manager_page, cfg).open()
    page.open_republish(o["displayNumber"])
    expect(page.dialog).to_be_visible()
