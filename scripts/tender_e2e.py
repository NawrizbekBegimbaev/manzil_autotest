#!/usr/bin/env python3
"""Cross-role tender E2E: mobile publishes an order → web carrier offers → web
shipper selects the winner.

Orchestrates Playwright (web) + Maestro (Android) in one run:
  1. SUPER_ADMIN provisions shipper A (admin login) + carrier B (login);
     shipper A's admin creates a "Сотрудник склада" staff (mobile warehouse login).
  2. Maestro publishes an order from the warehouse app (mobile-only step).
  3. Carrier B finds the order in the web feed and submits a price offer.
  4. Shipper A's admin accepts the offer (selects the winner).
  5. The provisioned tenants are deleted (cleanup), even on failure.

Requires: a running Android emulator/device with the staging warehouse APK, the
Maestro CLI + adb on PATH, and SUPER_ADMIN creds + NEW_ACCOUNT_PASSWORD in .env.
Run via scripts/run_tender_e2e.sh (sets the Android/Java/Maestro env).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from config.settings import get_settings  # noqa: E402
from pages.auth.login_page import LoginPage  # noqa: E402
from pages.shipper.orders_page import ShipperOrdersPage  # noqa: E402
from pages.shipper.staff_page import StaffPage  # noqa: E402
from pages.super_admin.shipper_companies_page import ShipperCompaniesPage  # noqa: E402
from pages.super_admin.transport_companies_page import TransportCompaniesPage  # noqa: E402
from pages.transport.carrier_orders_page import CarrierOrdersPage  # noqa: E402
from utils.data import CarrierData, ShipperData, StaffData  # noqa: E402

FORCE_RU = "try{localStorage.setItem('__tolgee_currentLanguage','ru');}catch(e){}"
APP_ID = os.environ.get("APP_ID", "uz.logos.manzil.warehouse.staging")
ADB = os.environ.get("ADB", "adb")
CREATE_FLOW = "mobile/flows/02_warehouse_create_order.yaml"
OFFER_PRICE = 5_000_000


def _ctx(browser, cfg):
    c = browser.new_context(
        locale="ru-RU", timezone_id=cfg.timezone, ignore_https_errors=True,
        viewport={"width": 1440, "height": 900},
    )
    c.add_init_script(FORCE_RU)
    c.set_default_timeout(cfg.default_timeout_ms)
    c.set_default_navigation_timeout(cfg.nav_timeout_ms)
    return c


def _provision(browser, cfg):
    pwd = cfg.new_account_password
    sa = _ctx(browser, cfg).new_page()
    LoginPage(sa, cfg).login(*cfg.creds("super_admin"))

    sp = ShipperCompaniesPage(sa, cfg).open()
    shipper = ShipperData()
    sp.open_create().fill_create(shipper, pwd)
    with sa.expect_response(lambda r: r.request.method == "POST" and "shipper-companies" in r.url) as r1:
        sp.submit()
    assert r1.value.status in (200, 201), f"shipper provision {r1.value.status}"

    cp = TransportCompaniesPage(sa, cfg).open()
    carrier = CarrierData()
    cp.open_create().fill_create(carrier, pwd)
    with sa.expect_response(lambda r: r.request.method == "POST" and "transport-companies" in r.url) as r2:
        cp.submit()
    assert r2.value.status in (200, 201), f"carrier provision {r2.value.status}"

    adm = _ctx(browser, cfg).new_page()
    LoginPage(adm, cfg).login(shipper.phone, pwd)
    staff = StaffPage(adm, cfg).open().open_create()
    wh = StaffData()
    with adm.expect_response(lambda r: r.request.method == "POST" and r.url.rstrip("/").endswith("/shipper/staff")) as r3:
        staff.create(wh, pwd, "Сотрудник склада")
    assert r3.value.status in (200, 201), f"warehouse provision {r3.value.status}"
    adm.context.close()

    return {
        "password": pwd,
        "admin_phone": shipper.phone,
        "carrier_phone": carrier.phone,
        "warehouse_national": wh.phone.removeprefix("+998"),
        "shipper_name": shipper.name,
        "carrier_name": carrier.name,
        "prefix": shipper.prefix,
        "_sa_page": sa,
    }


def _publish_order_mobile(creds) -> str:
    subprocess.run(
        ["maestro", "test", CREATE_FLOW,
         "-e", f"APP_ID={APP_ID}",
         "-e", f"WAREHOUSE_PHONE={creds['warehouse_national']}",
         "-e", f"WAREHOUSE_PASSWORD={creds['password']}"],
        check=True,
    )
    time.sleep(1)
    subprocess.run([ADB, "shell", "uiautomator", "dump"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dump = subprocess.run([ADB, "shell", "cat", "/sdcard/window_dump.xml"],
                          capture_output=True, text=True).stdout
    nums = re.findall(rf"{creds['prefix']}-\d{{3,6}}", dump)
    if not nums:
        raise RuntimeError("Could not read the published order number from the app screen")
    return sorted(set(nums))[0]


def _carrier_offers(browser, cfg, creds, order_no):
    page = _ctx(browser, cfg).new_page()
    LoginPage(page, cfg).login(creds["carrier_phone"], creds["password"])
    co = CarrierOrdersPage(page, cfg).open()
    expect(co.order_row(order_no).first).to_be_visible()
    co.open_order(order_no)
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.rstrip("/").endswith("/offers")) as ri:
        co.submit_offer(OFFER_PRICE, "sanity offer")
    assert ri.value.status in (200, 201), f"offer {ri.value.status}: {ri.value.text()[:200]}"
    expect(co.toast_submitted).to_be_visible()
    page.context.close()


def _shipper_selects(browser, cfg, creds, order_no):
    page = _ctx(browser, cfg).new_page()
    LoginPage(page, cfg).login(creds["admin_phone"], creds["password"])
    so = ShipperOrdersPage(page, cfg).open()
    expect(so.order_row(order_no).first).to_be_visible()
    so.open_order(order_no)
    with page.expect_response(lambda r: r.request.method == "POST" and "/select" in r.url) as ri:
        so.accept_first_offer()
    assert ri.value.status in (200, 201), f"select {ri.value.status}: {ri.value.text()[:200]}"
    expect(so.toast_winner).to_be_visible()
    page.context.close()


def _cleanup(cfg, creds):
    sa = creds.get("_sa_page")
    if sa is None:
        return
    for klass, name in ((ShipperCompaniesPage, creds["shipper_name"]),
                        (TransportCompaniesPage, creds["carrier_name"])):
        try:
            klass(sa, cfg).open().delete_row(name)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


def main() -> int:
    cfg = get_settings()
    if not cfg.has_creds("super_admin") or not cfg.new_account_password:
        print("Need SUPER_ADMIN creds + NEW_ACCOUNT_PASSWORD in .env", file=sys.stderr)
        return 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        creds = _provision(browser, cfg)
        try:
            order_no = _publish_order_mobile(creds)
            print(f"[mobile] published order {order_no}")
            _carrier_offers(browser, cfg, creds, order_no)
            print("[web] carrier submitted offer")
            _shipper_selects(browser, cfg, creds, order_no)
            print("[web] shipper selected winner")
            print(f"TENDER E2E PASSED for {order_no}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"TENDER E2E FAILED: {exc}", file=sys.stderr)
            return 1
        finally:
            _cleanup(cfg, creds)
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
