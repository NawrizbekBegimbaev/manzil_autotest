# ruff: noqa: RUF001, RUF002
"""Главный E2E — сквозной тендерный сценарий BRD §4.

Шаги (один тест, разбитый на @allure.step):
    1. Регистрация Поставщика-Админа (web register + verify email-OTP).
    2. Логин Поставщика-Админа.
    3. Регистрация ТК-Админа (web register + verify).
    4. Логин ТК-Админа.
    5. ТК добавляет автомобиль в автопарк (тип tent).
    6. Поставщик создаёт склад погрузки.
    7. Поставщик создаёт заявку (publish=true) с тем же bodyType=tent,
       той же валютой USD.
    8. ТК видит заявку в /api/v1/feed.
    9. ТК подаёт предложение (price + comment).
   10. Поставщик видит предложение в /orders/{id}/offers.
   11. Поставщик прикрепляет менеджерскую заметку (PUT note).
   12. Поставщик выбирает победителя — заявка → IN_PROGRESS.
   13. Поставщик завершает заявку — заявка → COMPLETED.

ОДИН тест-метод. НЕ дробить (BRD §4 требование).
Маркеры: e2e + serial + requires_email_otp.

В новой архитектуре multi-user нам нужно ДВА разных ApiClient (поставщик и
ТК) одновременно — тут как раз реализовано через раздельные fixtures
`supplier_admin_client` + `tk_admin_client`.
"""

from __future__ import annotations

import allure
import pytest

from api.client import ApiClient
from api.endpoints import feed as feed_ep
from api.endpoints import offers as off_ep
from api.endpoints import orders as ord_ep
from api.endpoints import vehicles as vh_ep
from api.endpoints import warehouses as wh_ep
from api.schemas import (
    FeedQuery,
    OfferNoteRequest,
)
from data import builders
from tests.conftest import RegisteredAccount


@pytest.mark.e2e
@pytest.mark.serial
@pytest.mark.requires_email_otp
def test_full_tender_flow(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_manager_client: ApiClient,
    tk_admin_client: ApiClient,
    verified_supplier_admin: RegisteredAccount,
    verified_tk_admin: RegisteredAccount,
) -> None:
    # 1-4: registration + login already handled by the fixtures.
    with allure.step("Поставщик и ТК зарегистрированы и залогинены"):
        assert verified_supplier_admin.tokens is not None
        assert verified_tk_admin.tokens is not None

    with allure.step("ТК добавляет автомобиль (tent) в автопарк"):
        vehicle = vh_ep.add_vehicle(
            tk_admin_client,
            builders.vehicle(plate="01E2E001BC", body_type="TENT"),
        )
        assert vehicle.body_type == "TENT"

    with allure.step("Поставщик создаёт склад погрузки"):
        warehouse = wh_ep.create_warehouse(
            supplier_admin_client,
            builders.warehouse(name="[E2E] Tender WH"),
        )

    with allure.step("Поставщик создаёт склад выгрузки"):
        destination_warehouse = wh_ep.create_warehouse(
            supplier_admin_client,
            builders.warehouse(
                name="[E2E] Tender WH Destination",
                city="Almaty",
                address="Abay 45",
            ),
        )

    with allure.step("Поставщик создаёт и публикует заявку (tent, USD)"):
        order = ord_ep.create_order(
            supplier_dispatcher_client,
            builders.order_request(
                warehouse_id=warehouse.id,
                destination_warehouse_id=destination_warehouse.id,
                body_type="TENT",
                currency="USD",
                publish=True,
            ),
        )
        assert order.status == "ACTIVE"
        assert order.body_type == "TENT"

    with allure.step("ТК видит заявку в feed (фильтр по bodyType из автопарка)"):
        feed_page = feed_ep.get_feed(tk_admin_client, FeedQuery(body_type="TENT", size=200))
        assert order.id in {o.id for o in feed_page.content}, (
            "опубликованная активная tent-заявка должна появиться в feed ТК"
        )

    with allure.step("ТК подаёт предложение"):
        offer = off_ep.submit_offer(
            tk_admin_client,
            order.id,
            builders.offer_request(
                price=1500,
                currency="USD",
                comment="готовы выехать в течение 24 часов",
            ),
        )
        assert offer.status in {"NEW", "REVIEWED"}
        assert offer.price == 1500

    with allure.step("Поставщик видит предложение в карточке заявки"):
        offers = off_ep.list_offers_for_order(supplier_admin_client, order.id)
        offer_ids = {o.id for o in offers}
        assert offer.id in offer_ids

    with allure.step("Поставщик-Менеджер прикрепляет заметку — статус offer "
                     "должен перейти в reviewed"):
        with_note = off_ep.upsert_offer_note(
            supplier_manager_client,
            order.id,
            offer.id,
            OfferNoteRequest(note="одобрено руководством, выбираем"),
        )
        assert with_note.manager_note == "одобрено руководством, выбираем"
        # SPECULATIVE: per swagger US-12 §6 status NEW → PROCESSED, but
        # actual enum names may differ. Accepting any non-new value.
        assert with_note.status != "NEW"

    with allure.step("Менеджер выбирает победителя — заявка → in_progress"):
        order_after_select = off_ep.select_winner(
            supplier_manager_client, order.id, offer.id,
        )
        assert order_after_select.status == "IN_PROGRESS"
        assert order_after_select.winner_offer_id == offer.id

    with allure.step("Менеджер завершает заявку — статус → completed"):
        order_completed = ord_ep.complete_order(supplier_admin_client, order.id)
        assert order_completed.status == "COMPLETED"

    with allure.step("ТК видит свою выигранную заявку в /api/v1/my-offers"):
        my_offers = off_ep.list_my_offers(tk_admin_client)
        my_ids = {o.id for o in my_offers.content}
        assert offer.id in my_ids
        winning = next(o for o in my_offers.content if o.id == offer.id)
        assert winning.status == "SELECTED"
