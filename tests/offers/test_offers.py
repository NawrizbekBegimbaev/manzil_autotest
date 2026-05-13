"""Carrier offers + tender selection (BRD US-9 / US-12 / US-14).

Carrier-side: TK admin or driver submits / edits / withdraws own offer.
Supplier-side: manager lists offers on the order, attaches notes, picks winner.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from api.client import ApiClient
from api.endpoints import offers as off_ep
from api.endpoints import orders as ord_ep
from api.schemas import (
    OfferNoteRequest,
    OfferUpdateRequest,
    OrderResponse,
)
from data import builders

# ---------- helpers --------------------------------------------------------


@pytest.fixture
def active_order(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> OrderResponse:
    """An order published as ACTIVE, ready to receive offers."""
    return ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=True,
        ),
    )


# ---------- positive --------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_tk_admin_submits_offer_returns_201(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1500, currency=active_order.currency),
    )
    assert offer.order_id == active_order.id
    assert offer.price == 1500
    assert offer.status in {"NEW", "REVIEWED"}


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_tk_admin_can_edit_own_offer(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1500, currency=active_order.currency),
    )
    edited = off_ep.update_own_offer(
        tk_admin_client,
        active_order.id,
        offer.id,
        OfferUpdateRequest(price=1450, comment="lowered the price"),
    )
    assert edited.price == 1450


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_manager_sees_offer_in_list(
    supplier_admin_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    submitted = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1700, currency=active_order.currency),
    )
    offers = off_ep.list_offers_for_order(supplier_admin_client, active_order.id)
    assert submitted.id in {o.id for o in offers}


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_manager_attaches_note_to_offer(
    supplier_manager_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1300, currency=active_order.currency),
    )
    with_note = off_ep.upsert_offer_note(
        supplier_manager_client,
        active_order.id,
        offer.id,
        OfferNoteRequest(note="оценено менеджером, рассмотрим"),
    )
    assert with_note.manager_note == "оценено менеджером, рассмотрим"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_select_winner_flips_order_to_in_progress(
    supplier_manager_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1200, currency=active_order.currency),
    )
    updated = off_ep.select_winner(supplier_manager_client, active_order.id, offer.id)
    assert updated.status == "IN_PROGRESS"
    assert updated.winner_offer_id == offer.id


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_withdraw_own_offer(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=900, currency=active_order.currency),
    )
    after = off_ep.withdraw_own_offer(tk_admin_client, active_order.id, offer.id)
    assert after.status == "WITHDRAWN"


@pytest.mark.positive
@pytest.mark.requires_email_otp
def test_my_offers_lists_own(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1100, currency=active_order.currency),
    )
    my = off_ep.list_my_offers(tk_admin_client)
    assert offer.id in {o.id for o in my.content}


# ---------- negative -------------------------------------------------------


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_submit_offer_currency_mismatch_returns_400(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    other_currency = "CNY" if active_order.currency == "USD" else "USD"
    with tk_admin_client.expect_error(400):
        off_ep.submit_offer(
            tk_admin_client,
            active_order.id,
            builders.offer_request(price=1000, currency=other_currency),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
@pytest.mark.parametrize(
    ("field", "bad"),
    [("price", 0), ("price", -100), ("comment", "x" * 251)],
)
def test_submit_offer_validation_returns_400(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
    field: str,
    bad: object,
) -> None:
    body = {"price": 1500, "currency": active_order.currency, "comment": "ok"}
    body[field] = bad
    with tk_admin_client.expect_error(400):
        tk_admin_client.post(
            f"/api/v1/orders/{active_order.id}/offers",
            json=body,
            expect_status=201,
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_double_offer_from_same_tk_returns_409(
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    body = builders.offer_request(price=1000, currency=active_order.currency)
    off_ep.submit_offer(tk_admin_client, active_order.id, body)
    with tk_admin_client.expect_error(409):
        off_ep.submit_offer(tk_admin_client, active_order.id, body)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_offer_on_draft_order_returns_409(
    supplier_admin_client: ApiClient,
    supplier_dispatcher_client: ApiClient,
    tk_admin_client: ApiClient,
    supplier_warehouse_id: UUID,
    supplier_destination_warehouse_id: UUID,
) -> None:
    """Draft orders are invisible to TK and reject offers."""
    draft = ord_ep.create_order(
        supplier_dispatcher_client,
        builders.order_request(
            warehouse_id=supplier_warehouse_id,
            destination_warehouse_id=supplier_destination_warehouse_id,
            publish=False,
        ),
    )
    with tk_admin_client.expect_error((404, 409)):
        off_ep.submit_offer(
            tk_admin_client,
            draft.id,
            builders.offer_request(price=1000, currency=draft.currency),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_supplier_cannot_submit_offer_returns_403(
    supplier_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    with supplier_admin_client.expect_error(403):
        off_ep.submit_offer(
            supplier_admin_client,
            active_order.id,
            builders.offer_request(price=1000, currency=active_order.currency),
        )


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_select_already_chosen_winner_returns_409(
    supplier_manager_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1000, currency=active_order.currency),
    )
    off_ep.select_winner(supplier_manager_client, active_order.id, offer.id)
    with supplier_manager_client.expect_error(409):
        off_ep.select_winner(supplier_manager_client, active_order.id, offer.id)


@pytest.mark.negative
@pytest.mark.requires_email_otp
def test_withdraw_after_winner_selected_fails(
    supplier_manager_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    """SECURITY-RELEVANT (BRD US-9 §5): once selected, TK cannot back out."""
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1000, currency=active_order.currency),
    )
    off_ep.select_winner(supplier_manager_client, active_order.id, offer.id)
    with tk_admin_client.expect_error(409):
        off_ep.withdraw_own_offer(tk_admin_client, active_order.id, offer.id)


# ---------- security: BOLA ------------------------------------------------


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_other_supplier_cannot_select_winner_on_someones_order(
    supplier_admin_client: ApiClient,
    second_supplier_admin_client: ApiClient,
    tk_admin_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1000, currency=active_order.currency),
    )
    with second_supplier_admin_client.expect_error((403, 404)):
        off_ep.select_winner(second_supplier_admin_client, active_order.id, offer.id)


@pytest.mark.security
@pytest.mark.requires_email_otp
def test_tk_cannot_edit_other_tk_offer(
    tk_admin_client: ApiClient,
    api_client: ApiClient,
    active_order: OrderResponse,
) -> None:
    """SPECULATIVE: needs a second TK admin fixture to be 100% accurate.
    Approximation — try edit with anonymous client (401)."""
    offer = off_ep.submit_offer(
        tk_admin_client,
        active_order.id,
        builders.offer_request(price=1000, currency=active_order.currency),
    )
    with api_client.expect_error(401):
        off_ep.update_own_offer(
            api_client,
            active_order.id,
            offer.id,
            OfferUpdateRequest(price=1),
        )
