"""Order-lifecycle provisioning — build an order in any status via the HONEST API chain.

Every transition is a real public-API call under the correct role (never a DB edit):

    status       actor              call
    ─────────────────────────────────────────────────────────────────────────────
    PUBLISHED    SHIPPER_WAREHOUSE  POST /warehouse/orders (no scheduledPublishDate)
    QUOTED       TRANSPORT_ADMIN    POST /transport/orders/{id}/offers {price}
    SELECTED     SHIPPER_ADMIN      POST /shipper/orders/{id}/offers/{offerId}/select
    IN_WORK      TRANSPORT_ADMIN    POST /transport/drivers ; /orders/{id}/drivers ; /orders/{id}/start
    IN_TRANSIT   SHIPPER_WAREHOUSE  POST /warehouse/orders/{id}/communication {CONFIRMED} ; /goods-sent
    COMPLETED    SHIPPER_ADMIN      POST /shipper/orders/{id}/complete
    CANCELLED    SHIPPER_ADMIN      POST /shipper/orders/{id}/cancel {reason}  (built to SELECTED first)

Teardown drives every created order to a terminal state and deletes it:
DRAFT/PUBLISHED/QUOTED/COMPLETED/CANCELLED are DELETE-able directly; SELECTED/IN_WORK/IN_TRANSIT
return 409 on delete → cancel first, then delete. So DEV never accumulates active orders (which
would otherwise skew list/stats tests).
"""

from __future__ import annotations

import datetime
import random
import string


def _digits(n: int) -> str:
    return "".join(random.choices(string.digits, k=n))


# Refs (vehicle type + 2 warehouse locations) are reusable across ALL orders of a company —
# cache them per warehouse token so a whole run reuses ONE set (else each test creates new
# locations and hits `error.warehouse.personal-limit`).
_REFS_CACHE: dict = {}


class OrderFactory:
    STATUSES = ("PUBLISHED", "QUOTED", "SELECTED", "IN_WORK", "IN_TRANSIT", "COMPLETED", "CANCELLED")

    def __init__(self, dev_api, sa_token, wh_token, admin_token, carrier_token):
        self.api = dev_api
        self.sa = sa_token          # SUPER_ADMIN — refs (vehicle type)
        self.wh = wh_token          # SHIPPER_WAREHOUSE — create, communication, goods-sent
        self.admin = admin_token    # SHIPPER_ADMIN — select, complete, cancel, delete
        self.carrier = carrier_token  # TRANSPORT_ADMIN — bid, drivers, start
        self._refs = None
        self._orders: list = []
        # Водители, привязанные последним make() с драйверами (для blacklist-тестов и т.п.).
        self.last_drivers: list[dict] = []  # [{id, phone}]

    # ── low-level ──
    def _req(self, method, path, token, ok=None, **kw):
        r = self.api.request(method, path, token, **kw)
        if ok is not None and r.status_code not in ok:
            raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:200]}")
        return r

    def _ensure_refs(self):
        if self._refs:
            return self._refs
        cached = _REFS_CACHE.get(self.wh)
        if cached:
            self._refs = cached
            return cached
        vt = self._req("POST", "/super-admin/vehicle-types", self.sa, ok=(201,),
                       json={"category": "FLATBED", "size": _digits(9)}).json()["id"]
        cities = self._req("GET", "/super-admin/cities?size=5", self.sa, ok=(200,)).json()
        cid = (cities.get("content", cities) if isinstance(cities, dict) else cities)[0]["id"]
        locs = []
        for _ in range(2):
            loc = self._req("POST", "/warehouse/locations", self.wh, ok=(200, 201),
                            json={"cityId": cid, "name": "AT-WH-" + _digits(5), "address": "Tashkent, Sayyod 1"}).json()
            locs.append(loc["id"])
        self._refs = (vt, locs)
        _REFS_CACHE[self.wh] = self._refs
        return self._refs

    def _get(self, oid):
        r = self.api.request("GET", f"/shipper/orders/{oid}", self.admin)
        if r.status_code == 200:
            b = r.json()
            assert isinstance(b, dict) and "order" in b, \
                f"order detail must be wrapped in {{order,winningOffer,history}}, got keys={sorted(b) if isinstance(b, dict) else type(b)}"
            return b["order"]
        lst = self.api.request("GET", "/shipper/orders?size=200", self.admin).json()
        rows = lst.get("content", lst) if isinstance(lst, dict) else lst
        return next((o for o in rows if str(o.get("id")) == str(oid)), {"id": oid})

    # ── build ──
    def make(self, status: str = "PUBLISHED", drivers_count: int = 1, plate: str | None = None) -> dict:
        """plate: госномер привязываемых водителей (для 1С-вебхука по номеру). None → уникальный
        на каждого водителя. Один и тот же plate на двух IN_TRANSIT-заказах даёт ambiguous-plate."""
        assert status in self.STATUSES, f"unknown status {status}"
        vt, locs = self._ensure_refs()
        o = self._req("POST", "/warehouse/orders", self.wh, ok=(201,), json={
            "cargoType": "AUTO", "currency": "CNY", "loadDate": datetime.date.today().isoformat(),
            "vehicleTypeId": vt, "driversCount": drivers_count, "fromWarehouseId": locs[0], "toWarehouseId": locs[1],
            "notes": "AT lifecycle"}).json()
        oid = o["id"]
        self._orders.append(oid)
        if status == "PUBLISHED":
            return self._get(oid)

        offer = self._req("POST", f"/transport/orders/{oid}/offers", self.carrier, ok=(200, 201),
                          json={"price": 5000}).json()
        if status == "QUOTED":
            return self._get(oid)

        self._req("POST", f"/shipper/orders/{oid}/offers/{offer['id']}/select", self.admin, ok=(200, 201))
        if status == "SELECTED":
            return self._get(oid)
        if status == "CANCELLED":
            self._req("POST", f"/shipper/orders/{oid}/cancel", self.admin, ok=(200, 204),
                      json={"reason": "AT lifecycle teardown"})
            return self._get(oid)

        assignments = []
        self.last_drivers = []
        for _ in range(drivers_count):
            phone = "+99890" + _digits(7)
            lp = plate or ("01A" + _digits(6))  # уникальный по умолчанию (низкая коллизия в резолвере по номеру)
            drv = self._req("POST", "/transport/drivers", self.carrier, ok=(201,),
                            json={"fullName": "AT Driver", "phone": phone}).json()
            assignments.append({"driverId": drv["id"], "licensePlate": lp, "cardId": _digits(18)})
            self.last_drivers.append({"id": drv["id"], "phone": phone, "plate": lp})
        self._req("POST", f"/transport/orders/{oid}/drivers", self.carrier, ok=(200, 201),
                  json={"drivers": assignments})
        self._req("POST", f"/transport/orders/{oid}/start", self.carrier, ok=(200, 201))
        if status == "IN_WORK":
            return self._get(oid)

        self._req("POST", f"/warehouse/orders/{oid}/communication", self.wh, ok=(200, 201, 204),
                  json={"status": "CONFIRMED"})
        self._req("POST", f"/warehouse/orders/{oid}/goods-sent", self.wh, ok=(200, 201, 204))
        if status == "IN_TRANSIT":
            return self._get(oid)

        self._req("POST", f"/shipper/orders/{oid}/complete", self.admin, ok=(200, 201, 204))
        return self._get(oid)

    # ── cleanup ──
    def teardown(self):
        for oid in reversed(self._orders):
            try:
                r = self.api.request("DELETE", f"/shipper/orders/{oid}", self.admin)
                if r.status_code == 409:  # active (SELECTED/IN_WORK/IN_TRANSIT) → cancel then delete
                    self.api.request("POST", f"/shipper/orders/{oid}/cancel", self.admin,
                                     json={"reason": "AT teardown"})
                    self.api.request("DELETE", f"/shipper/orders/{oid}", self.admin)
            except Exception:  # noqa: BLE001
                pass
        self._orders = []
