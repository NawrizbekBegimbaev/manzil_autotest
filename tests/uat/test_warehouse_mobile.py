"""UAT — Сотрудник склада (мобильное приложение, Maestro) (SK-01..SK-14).

Each test runs a Maestro flow against the warehouse Android app using the
provisioned warehouse account; order preconditions are API-seeded. Skipped when
no emulator/Maestro is available (so the web-only daily run still produces a
report — these show as «Не автоматизирован»).

BUG-011 (адрес) и BUG-012 (связь) — ИСПРАВЛЕНЫ. Адрес: экран Davlat + поиск города
(→ cityId), POST /warehouse/locations → 201. Связь: диалог с enum-статусами
(Tasdiqlandi/Rad etildi/Aloqasiz/Bogʻlanish), POST /communication → 204; отправка
груза («Yuk joʻnatildi» + подтверждение) → 200, заявка в «Yoʻlda». Все SK
автоматизированы и зелёные.
"""

from __future__ import annotations

import allure
import pytest

from utils.maestro import emulator_ready, run_flow

pytestmark = [pytest.mark.uat, pytest.mark.warehouse]

@pytest.fixture(autouse=True)
def _require_emulator():
    if not emulator_ready():
        pytest.skip("Нет Android-эмулятора / Maestro — мобильные кейсы пропущены")


def _wh(provisioned):
    return {"WAREHOUSE_PHONE": provisioned.warehouse_phone.removeprefix("+998"),
            "WAREHOUSE_PASSWORD": provisioned.password}


@allure.title("SK-01 Вход в приложение склада")
def test_sk01_login(provisioned):
    run_flow("01_warehouse_login.yaml", **_wh(provisioned))


@allure.title("SK-02 Список заявок и вкладки статусов")
def test_sk02_tabs(provisioned):
    run_flow("sk_tabs.yaml", **_wh(provisioned))


@allure.title("SK-03 Начать создание заявки — выбор типа транспорта")
def test_sk03_create_open(provisioned):
    run_flow("sk_create_open.yaml", **_wh(provisioned))


@allure.title("SK-04 Тип машины и число водителей")
def test_sk04_create_fill(provisioned):
    run_flow("sk_create_fill.yaml", **_wh(provisioned))


@allure.title("SK-05 Добавление адреса отправления")
def test_sk05_from_address(provisioned):
    run_flow("02_warehouse_create_order.yaml", **_wh(provisioned))


@allure.title("SK-06 Добавление адреса назначения")
def test_sk06_to_address(provisioned):
    run_flow("02_warehouse_create_order.yaml", **_wh(provisioned))


@allure.title("SK-07 Создание и публикация заявки")
def test_sk07_create_publish(provisioned):
    run_flow("02_warehouse_create_order.yaml", **_wh(provisioned))


@allure.title("SK-08 Просмотр опубликованной заявки")
def test_sk08_published(provisioned, seeder):
    o = seeder.order("published")
    run_flow("sk_find_order.yaml", TAB="Eʼlon qilindi", ORDER_NO=o["displayNumber"], **_wh(provisioned))


@allure.title("SK-09 Заявка получила отклики")
def test_sk09_quoted(provisioned, seeder):
    # У склада QUOTED отображается в той же вкладке «Eʼlon qilindi» (отдельного экрана откликов нет).
    o = seeder.order("quoted")
    run_flow("sk_find_order.yaml", TAB="Eʼlon qilindi", ORDER_NO=o["displayNumber"], **_wh(provisioned))


@allure.title("SK-10 После выбора перевозчика заявка в «Принятые»")
def test_sk10_selected(provisioned, seeder):
    o = seeder.order("selected")
    run_flow("sk_find_order.yaml", TAB="Olingan", ORDER_NO=o["displayNumber"], **_wh(provisioned))


@allure.title("SK-11 Назначенный водитель виден в заявке")
def test_sk11_driver_visible(provisioned, seeder):
    o = seeder.order("in_work")  # TK assigned a driver + started → IN_WORK (Ishda)
    run_flow("sk_order_driver.yaml", TAB="Ishda", ORDER_NO=o["displayNumber"],
             DRIVER="SANITY Driver", **_wh(provisioned))


@allure.title("SK-12 Отметка связи с водителем")
def test_sk12_communication(provisioned, seeder):
    o = seeder.order("in_work")
    run_flow("sk_communication.yaml", TAB="Ishda", ORDER_NO=o["displayNumber"], **_wh(provisioned))


@allure.title("SK-13 Отправка груза → «В пути»")
def test_sk13_goods_sent(provisioned, seeder):
    o = seeder.order("in_work")
    run_flow("sk_goods_sent.yaml", TAB="Ishda", ORDER_NO=o["displayNumber"], **_wh(provisioned))


@allure.title("SK-14 Завершённая заявка")
def test_sk14_completed(provisioned, seeder):
    o = seeder.order("in_transit")
    seeder.complete(o["id"])
    run_flow("sk_find_order.yaml", TAB="Tugallangan", ORDER_NO=o["displayNumber"], **_wh(provisioned))
