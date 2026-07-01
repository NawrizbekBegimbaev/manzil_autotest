"""Cross-role workflow sanity.

SUPER_ADMIN provisions the tenants (shipper + carrier), each with its own login,
then the suite logs in as those fresh accounts in separate contexts. Order
creation itself is mobile-only (Maestro track), so the web workflow proves
tenant provisioning + auth + role landing end-to-end.
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from pages.super_admin.shipper_companies_page import ShipperCompaniesPage
from pages.super_admin.transport_companies_page import TransportCompaniesPage
from utils.data import CarrierData, ShipperData

pytestmark = pytest.mark.sanity


def _attach_and_assert(resp, what: str) -> None:
    allure.attach(
        f"{resp.status}\n{resp.text()}",
        name=f"POST {resp.url.split('/api/')[-1]}",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert resp.status in (200, 201), f"{what} вернуло {resp.status}: {resp.text()[:300]}"


def _is_create_shipper(resp) -> bool:
    return (
        resp.request.method == "POST"
        and resp.url.rstrip("/").endswith("/super-admin/shipper-companies")
    )


@pytest.mark.workflow
@allure.title("10. SUPER_ADMIN создаёт грузоотправителя (с логином)")
def test_create_shipper_company(super_admin_page, cfg):
    page = ShipperCompaniesPage(super_admin_page, cfg).open()
    data = ShipperData()

    page.open_create().fill_create(data, cfg.new_account_password)
    with super_admin_page.expect_response(_is_create_shipper) as resp_info:
        page.submit()
    resp = resp_info.value
    created = resp.status in (200, 201)
    try:
        _attach_and_assert(resp, "Создание грузоотправителя")
        expect(page.toast_created).to_be_visible()
        page.search(data.name)
        expect(page.row(data.name).first).to_be_visible()
    finally:
        if created:
            try:
                page.delete_row(data.name)
            except Exception:  # noqa: BLE001 - cleanup must not mask the result
                pass


def _is_create_carrier(resp) -> bool:
    return (
        resp.request.method == "POST"
        and resp.url.rstrip("/").endswith("/super-admin/transport-companies")
    )


@pytest.mark.workflow
@allure.title("11. SUPER_ADMIN создаёт транспортную компанию (с логином)")
def test_create_transport_company(super_admin_page, cfg):
    page = TransportCompaniesPage(super_admin_page, cfg).open()
    data = CarrierData()

    page.open_create().fill_create(data, cfg.new_account_password)
    with super_admin_page.expect_response(_is_create_carrier) as resp_info:
        page.submit()
    resp = resp_info.value
    created = resp.status in (200, 201)
    try:
        _attach_and_assert(resp, "Создание транспортной компании")
        expect(page.toast_created).to_be_visible()
        page.search(data.name)
        expect(page.row(data.name).first).to_be_visible()
    finally:
        if created:
            try:
                page.delete_row(data.name)
            except Exception:  # noqa: BLE001 - cleanup must not mask the result
                pass
