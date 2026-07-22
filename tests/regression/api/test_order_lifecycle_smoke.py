"""Smoke — order-lifecycle provisioning (tests/regression/order_lifecycle.py).

NOT a case suite — one assertion per status confirming the factory really lands an
order in the requested state (built via the honest API chain, no DB edits). The ~140
shipper orders/lifecycle cases build on `order_factory`; this proves the helper first.

Run twice back-to-back — teardown must leave DEV clean (2nd run sees no 1st-run debris).
"""

from __future__ import annotations

import pytest

from tests.regression.order_lifecycle import OrderFactory

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.lifecycle]


_ACTIVE = ("PUBLISHED", "QUOTED", "SELECTED", "IN_WORK", "IN_TRANSIT")


@pytest.mark.parametrize("status", OrderFactory.STATUSES)
def test_factory_lands_status(order_factory, status):
    o = order_factory.make(status)
    assert o.get("status") == status, f"[lifecycle-smoke] {status}: got status={o.get('status')} — {o}"
    assert o.get("id"), f"[lifecycle-smoke] {status}: no order id in {o}"
    assert o.get("displayNumber"), f"[lifecycle-smoke] {status}: no displayNumber — {o}"


def test_teardown_leaves_no_active_debris(api):
    """Runs after all factory teardowns — company A must carry no active orders."""
    rows = api("shipper_admin").get("/shipper/orders?size=200").json().get("content", [])
    active = [(o.get("id"), o.get("status")) for o in rows if o.get("status") in _ACTIVE]
    assert not active, f"[lifecycle-smoke] teardown left active debris: {active}"
