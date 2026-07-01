"""Page-load smoke per provisioned role (ADMIN / MANAGER / CARRIER).

Each page opens under the right role and shows its title — proves routing + RBAC
(no redirect to /auth/login or a forbidden page) for the provisioned accounts.
"""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from pages.common.nav_page import NavPage

pytestmark = pytest.mark.sanity

ADMIN_PAGES = [
    ("12", "/dashboard", "Панель управления"),
    ("13", "/shipper/orders", "Админ"),
    ("14", "/shipper/warehouses", "Склады"),
    ("15", "/shipper/reports", "Отчёты"),
    ("16", "/shipper/staff", "Сотрудники"),
    ("17", "/shipper/departures", "Список отправлений"),
]
MANAGER_PAGES = [
    ("18", "/shipper/storeroom", "Оператор склада"),
    ("19", "/shipper/communication", "Диспетчер"),
]
CARRIER_PAGES = [
    ("20", "/transport/orders", "Заявки"),
    ("21", "/transport/employees", "Водители"),
]


def _check(page, cfg, path, title):
    nav = NavPage(page, cfg).open_path(path)
    expect(page).to_have_url(re.compile(re.escape(path)))
    expect(nav.title_text(title).first).to_be_visible()


@pytest.mark.smoke
@allure.title("{case_no}. ADMIN: {title}")
@pytest.mark.parametrize("case_no,path,title", ADMIN_PAGES, ids=[p[1] for p in ADMIN_PAGES])
def test_admin_pages(admin_page, cfg, case_no, path, title):
    _check(admin_page, cfg, path, title)


@pytest.mark.smoke
@allure.title("{case_no}. MANAGER: {title}")
@pytest.mark.parametrize("case_no,path,title", MANAGER_PAGES, ids=[p[1] for p in MANAGER_PAGES])
def test_manager_pages(manager_page, cfg, case_no, path, title):
    _check(manager_page, cfg, path, title)


@pytest.mark.smoke
@allure.title("{case_no}. CARRIER: {title}")
@pytest.mark.parametrize("case_no,path,title", CARRIER_PAGES, ids=[p[1] for p in CARRIER_PAGES])
def test_carrier_pages(carrier_page, cfg, case_no, path, title):
    _check(carrier_page, cfg, path, title)
