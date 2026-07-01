"""SUPER_ADMIN page-load smoke — each platform page opens with its title."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from pages.common.nav_page import NavPage

pytestmark = pytest.mark.sanity

# (case_no, path, exact RU heading from public/i18n/ru.json)
PAGES = [
    ("5", "/super-admin/partners/shipper-companies", "Грузоотправители"),
    ("6", "/super-admin/partners/transport-companies", "Транспортные компании"),
    ("7", "/super-admin/partners/drivers", "Водители"),
    ("8", "/super-admin/cities", "Города"),
    ("9", "/super-admin/vehicle-types", "Типы транспорта"),
]


@pytest.mark.smoke
@allure.title("{case_no}. Страница супер-админа: {title}")
@pytest.mark.parametrize("case_no,path,title", PAGES, ids=[p[1] for p in PAGES])
def test_super_admin_page_loads(super_admin_page, cfg, case_no, path, title):
    nav = NavPage(super_admin_page, cfg).open_path(path)
    expect(super_admin_page).to_have_url(re.compile(re.escape(path)))
    expect(nav.title_text(title).first).to_be_visible()
