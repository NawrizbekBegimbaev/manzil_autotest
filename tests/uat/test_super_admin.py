"""UAT — Super admin (SA-01..SA-18). Maps 1:1 to manzil-uat-checklist.xlsx.

Uses the session-logged-in `super_admin_page`. Each create-case cleans up after
itself (SANITY-prefixed data).
"""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from pages.super_admin.dictionaries_page import CitiesPage, VehicleTypesPage
from pages.super_admin.drivers_page import DriversPage
from pages.super_admin.shipper_companies_page import ShipperCompaniesPage
from pages.super_admin.transport_companies_page import TransportCompaniesPage
from utils.data import CarrierData, CityData, DriverData, ShipperData, VehicleTypeData

pytestmark = [pytest.mark.uat, pytest.mark.super_admin]


@allure.title("SA-01 Вход супер-администратора")
def test_sa01_login(super_admin_page, cfg):
    # Order-independent: navigate to the role home directly and confirm the
    # authenticated super-admin lands there (not bounced to /auth/login).
    ShipperCompaniesPage(super_admin_page, cfg).open()
    expect(super_admin_page).to_have_url(re.compile(r"/super-admin/partners/shipper-companies"))
    expect(super_admin_page.get_by_role("heading", name="Грузоотправители").first).to_be_visible()


@allure.title("SA-02 Просмотр списка грузоотправителей")
def test_sa02_shippers_list(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    expect(super_admin_page.get_by_role("heading", name="Грузоотправители").first).to_be_visible()
    expect(page.page.locator('[role="grid"], table').first).to_be_visible()


@allure.title("SA-03 Поиск и фильтр грузоотправителей")
def test_sa03_shippers_search(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    try:
        page.search(data.name)
        expect(page.row(data.name).first).to_be_visible()
    finally:
        page.delete_row(data.name)


@allure.title("SA-04 Создание грузоотправителя")
def test_sa04_create_shipper(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    try:
        expect(page.toast_created).to_be_visible()
        page.search(data.name)
        expect(page.row(data.name).first).to_be_visible()
    finally:
        page.delete_row(data.name)


@allure.title("SA-05 Просмотр карточки грузоотправителя")
def test_sa05_shipper_card(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    try:
        page.open_card(data.name)
        expect(super_admin_page).to_have_url(re.compile(r"/super-admin/partners/shipper-companies/"))
        expect(super_admin_page.get_by_text(data.name).first).to_be_visible()
    finally:
        ShipperCompaniesPage(super_admin_page, cfg).open().delete_row(data.name)


@allure.title("SA-06 Редактирование грузоотправителя")
def test_sa06_edit_shipper(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    new_name = data.name + " ИЗМ"
    try:
        page.open_edit(data.name).set_name(new_name).save()
        page.search(new_name)
        expect(page.row(new_name).first).to_be_visible()
    finally:
        ShipperCompaniesPage(super_admin_page, cfg).open().delete_row(new_name)


@allure.title("SA-07 Блокировка и разблокировка грузоотправителя")
def test_sa07_block_shipper(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    try:
        page.open_edit(data.name).set_active(False).save()
        page.search(data.name)
        expect(page.row(data.name).first).to_contain_text("Заблокирован")
        page.open_edit(data.name).set_active(True).save()
        page.search(data.name)
        expect(page.row(data.name).first).to_contain_text("Активен")
    finally:
        ShipperCompaniesPage(super_admin_page, cfg).open().delete_row(data.name)


@allure.title("SA-08 Удаление грузоотправителя")
def test_sa08_delete_shipper(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    page.delete_row(data.name)
    page.search(data.name)
    expect(page.row(data.name)).to_have_count(0)


@allure.title("SA-09 Просмотр списка транспортных компаний")
def test_sa09_transport_list(super_admin_page, cfg):
    TransportCompaniesPage(super_admin_page, cfg).open()
    expect(super_admin_page.get_by_role("heading", name="Транспортные компании").first).to_be_visible()
    expect(super_admin_page.locator('[role="grid"], table').first).to_be_visible()


@allure.title("SA-10 Создание транспортной компании")
def test_sa10_create_transport(super_admin_page, cfg):
    page = TransportCompaniesPage(super_admin_page, cfg).open()
    data = CarrierData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    try:
        expect(page.toast_created).to_be_visible()
        page.search(data.name)
        expect(page.row(data.name).first).to_be_visible()
    finally:
        page.delete_row(data.name)


@allure.title("SA-11 Редактирование транспортной компании")
def test_sa11_edit_transport(super_admin_page, cfg):
    page = TransportCompaniesPage(super_admin_page, cfg).open()
    data = CarrierData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    new_name = data.name + " ИЗМ"
    try:
        page.open_edit(data.name).set_name(new_name).save()
        page.search(new_name)
        expect(page.row(new_name).first).to_be_visible()
    finally:
        TransportCompaniesPage(super_admin_page, cfg).open().delete_row(new_name)


@allure.title("SA-12 Удаление транспортной компании")
def test_sa12_delete_transport(super_admin_page, cfg):
    page = TransportCompaniesPage(super_admin_page, cfg).open()
    data = CarrierData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    page.delete_row(data.name)
    page.search(data.name)
    expect(page.row(data.name)).to_have_count(0)


@allure.title("SA-13 Просмотр списка водителей")
def test_sa13_drivers_list(super_admin_page, cfg):
    DriversPage(super_admin_page, cfg).open()
    expect(super_admin_page.get_by_role("heading", name="Водители").first).to_be_visible()


@allure.title("SA-14 Создание водителя")
def test_sa14_create_driver(super_admin_page, cfg):
    page = DriversPage(super_admin_page, cfg).open()
    data = DriverData()
    page.open_create().fill_create(data, cfg.new_account_password)
    page.submit_button.click()
    try:
        expect(page.toast_created).to_be_visible()
        page.search(data.full_name)
        expect(page.row(data.full_name).first).to_be_visible()
    finally:
        DriversPage(super_admin_page, cfg).open().delete_row(data.full_name)


@allure.title("SA-15 Редактирование и удаление водителя")
def test_sa15_edit_delete_driver(super_admin_page, cfg):
    page = DriversPage(super_admin_page, cfg).open()
    data = DriverData()
    page.open_create().fill_create(data, cfg.new_account_password)
    page.submit_button.click()
    expect(page.toast_created).to_be_visible()
    new_name = data.full_name + " ИЗМ"
    page.open_edit(data.full_name).set_name(new_name).save()
    page.search(new_name)
    expect(page.row(new_name).first).to_be_visible()
    page.delete_row(new_name)
    page.search(new_name)
    expect(page.row(new_name)).to_have_count(0)


@allure.title("SA-16 Просмотр городов и форма добавления")
def test_sa16_add_city(super_admin_page, cfg):
    # «Города» — глобальный справочник платформы без удаления по строке, поэтому
    # проверяем НЕразрушающе: страница открывается, форма «Новое административное
    # деление» (Код / Название / Пиньинь) доступна; закрываем без сохранения,
    # чтобы не засорять общий справочник.
    page = CitiesPage(super_admin_page, cfg).open()
    expect(super_admin_page.get_by_role("heading", name="Города").first).to_be_visible()
    expect(super_admin_page.locator('[role="grid"], table').first).to_be_visible()
    page.open_add()
    expect(page.dialog).to_be_visible()
    expect(page.dialog).to_contain_text("административное деление")
    expect(page.dialog.get_by_role("textbox")).to_have_count(3)
    page.cancel()


@allure.title("SA-17 Просмотр и добавление типа транспорта")
def test_sa17_add_vehicle_type(super_admin_page, cfg):
    page = VehicleTypesPage(super_admin_page, cfg).open()
    expect(super_admin_page.get_by_role("heading", name="Типы транспорта").first).to_be_visible()
    data = VehicleTypeData()
    page.add(data.name)
    try:
        expect(page.row(data.name).first).to_be_visible()
    finally:
        page.delete_row(data.name)


@allure.title("SA-18 Созданный администратор компании может войти")
def test_sa18_created_admin_can_login(super_admin_page, cfg, make_login):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()
    page.open_create().fill_create(data, cfg.new_account_password).submit()
    expect(page.toast_created).to_be_visible()
    try:
        admin = make_login(data.phone, cfg.new_account_password)
        expect(admin).to_have_url(re.compile(r"/dashboard"))
    finally:
        ShipperCompaniesPage(super_admin_page, cfg).open().delete_row(data.name)
