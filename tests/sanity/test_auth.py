"""Login sanity — one authenticated landing per web role (phone + password)."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.sanity


@allure.title("1. Логин супер-админа (телефон+пароль) → Партнёры")
def test_super_admin_login(super_admin_page):
    expect(super_admin_page).to_have_url(re.compile(r"/super-admin/partners/shipper-companies"))
    expect(super_admin_page.get_by_role("heading", name="Грузоотправители").first).to_be_visible()


@allure.title("2. Логин админа-логиста (телефон+пароль) → Дашборд")
def test_admin_login(admin_page):
    expect(admin_page).to_have_url(re.compile(r"/dashboard"))
    expect(admin_page.get_by_role("heading", name="Панель управления").first).to_be_visible()


@allure.title("3. Логин оператора склада (телефон+пароль) → Склад")
def test_manager_login(manager_page):
    expect(manager_page).to_have_url(re.compile(r"/shipper/storeroom"))
    expect(manager_page.get_by_role("heading", name="Оператор склада").first).to_be_visible()


@allure.title("4. Логин перевозчика (телефон+пароль) → Заявки")
def test_carrier_login(carrier_page):
    expect(carrier_page).to_have_url(re.compile(r"/transport/orders"))
    expect(carrier_page.get_by_role("heading", name="Заявки").first).to_be_visible()
