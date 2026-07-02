"""API-seed helper: prepare orders in a desired status for web UAT preconditions.

Order creation is mobile/warehouse-only, so web tests that need an existing order
(offers, winner-select, cancel, ...) seed it via the API rather than driving the
mobile UI each time. Setup-only — assertions stay in the UI.

Flow per order:
  warehouse → ensure 2 personal warehouses + a vehicle type → POST /warehouse/orders
  (PUBLISHED) → [TK offer → QUOTED] → [admin select → SELECTED].

Seeded orders belong to the provisioned shipper company and are removed when that
company is deleted at session teardown, so no per-order cleanup is needed.
"""

from __future__ import annotations

import datetime
import random
import string

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import Settings
from utils.data import TenantCreds, unique_phone, unique_tin


def _retrying_session() -> requests.Session:
    """A requests session that rides out transient CONNECT failures (DNS blips,
    connection timeouts) common on this host — retries only pre-send connection
    errors (never read errors), so a POST is never silently duplicated."""
    s = requests.Session()
    retry = Retry(total=5, connect=5, read=0, status=0, backoff_factor=1.0,
                  raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def _plate() -> str:
    """Unique license plate (must be unique among active orders)."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class ApiError(RuntimeError):
    pass


class ApiSeed:
    def __init__(self, cfg: Settings, creds: TenantCreds) -> None:
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/") + "/api/v1"
        self.creds = creds
        self._tokens: dict[str, str] = {}
        self._vt_id: str | None = None
        self._wh_ids: list[str] | None = None
        self._session = _retrying_session()

    # ── low-level ──
    def _login(self, phone: str, client_type: str, password: str | None = None) -> str:
        key = f"{phone}:{client_type}"
        if key not in self._tokens:
            r = self._session.post(
                f"{self.base}/auth/login",
                json={"phone": phone, "password": password or self.creds.password,
                      "clientType": client_type},
                timeout=30,
            )
            if r.status_code != 200:
                raise ApiError(f"login {phone}/{client_type}: {r.status_code} {r.text[:200]}")
            self._tokens[key] = r.json()["accessToken"]
        return self._tokens[key]

    def _a_city_id(self) -> str:
        """Pick a valid cityId via the super-admin dictionary."""
        sa = self._login(self.cfg.super_admin_phone, "WEB", self.cfg.super_admin_password)
        data = self._req("GET", "/super-admin/cities?size=5", sa).json()
        items = data.get("content", data) if isinstance(data, dict) else data
        if not items:
            raise ApiError("no cities in dictionary to seed a warehouse")
        return items[0]["id"]

    def _h(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _req(self, method: str, path: str, token: str, **kw) -> requests.Response:
        r = self._session.request(method, f"{self.base}{path}", headers=self._h(token), timeout=30, **kw)
        if r.status_code >= 400:
            raise ApiError(f"{method} {path}: {r.status_code} {r.text[:300]}")
        return r

    # ── setup (lazy, once) ──
    def _ensure_refs(self) -> None:
        if self._vt_id and self._wh_ids:
            return
        wh = self._login(self.creds.warehouse_phone, "WAREHOUSE_APP")
        vts = self._req("GET", "/warehouse/vehicle-types", wh).json()
        vts = vts.get("content", vts) if isinstance(vts, dict) else vts
        if not vts:
            raise ApiError("no vehicle types available for warehouse")
        self._vt_id = vts[0]["id"]

        def from_ids() -> list[str]:
            data = self._req("GET", "/warehouse/locations/from", wh).json()
            data = data.get("content", data) if isinstance(data, dict) else data
            return [w["id"] for w in data]

        ids = from_ids()
        attempts = 0
        city_id = self._a_city_id()
        while len(ids) < 2 and attempts < 3:
            self._req("POST", "/warehouse/locations", wh, json={
                "cityId": city_id,
                "name": f"SANITY WH {unique_tin()}", "address": "Sayyod 1",
            })
            ids = from_ids()
            attempts += 1
        if len(ids) < 2:
            raise ApiError("could not ensure 2 warehouses for seeding")
        self._wh_ids = ids

    # ── public ──
    def order(self, status: str = "published") -> dict:
        """Seed an order; status ∈ {published, quoted, selected}. Returns dict with
        id, displayNumber, offerId (when quoted/selected)."""
        self._ensure_refs()
        wh = self._login(self.creds.warehouse_phone, "WAREHOUSE_APP")
        body = {
            "cargoType": "AUTO",
            "currency": "CNY",
            "loadDate": datetime.date.today().isoformat(),
            "vehicleTypeId": self._vt_id,
            "driversCount": 1,
            "fromWarehouseId": self._wh_ids[0],
            "toWarehouseId": self._wh_ids[1],
            "notes": "SANITY seed",
        }
        o = self._req("POST", "/warehouse/orders", wh, json=body).json()
        out = {"id": o["id"], "displayNumber": o.get("displayNumber"), "offerId": None,
               "status": o.get("status")}
        if status == "published":
            return out

        tk = self._login(self.creds.carrier_phone, "TRANSPORT_COMPANY_APP")
        offer = self._req("POST", f"/transport/orders/{out['id']}/offers", tk,
                          json={"price": 5000, "notes": "SANITY seed"}).json()
        out["offerId"] = offer["id"]
        out["status"] = "QUOTED"
        if status == "quoted":
            return out

        adm = self._login(self.creds.admin_phone, "WEB")
        self._req("POST", f"/shipper/orders/{out['id']}/offers/{out['offerId']}/select", adm)
        out["status"] = "SELECTED"
        if status == "selected":
            return out

        # in_transit: TK assigns a driver + starts → warehouse confirms + goods-sent
        tk = self._login(self.creds.carrier_phone, "TRANSPORT_COMPANY_APP")
        # NOTE: cardId is documented optional but the server 500s when it is null,
        # so we always send it.
        drv = self._req("POST", "/transport/drivers", tk,
                        json={"fullName": "SANITY Driver", "phone": unique_phone(),
                              "cardId": "AB1234567"}).json()
        self._req("POST", f"/transport/orders/{out['id']}/drivers", tk,
                  json={"drivers": [{"driverId": drv["id"], "licensePlate": _plate()}]})
        self._req("POST", f"/transport/orders/{out['id']}/start", tk)
        out["status"] = "IN_WORK"
        if status == "in_work":
            return out

        whx = self._login(self.creds.warehouse_phone, "WAREHOUSE_APP")
        self._req("POST", f"/warehouse/orders/{out['id']}/communication", whx,
                  json={"status": "CONFIRMED"})
        self._req("POST", f"/warehouse/orders/{out['id']}/goods-sent", whx)
        out["status"] = "IN_TRANSIT"
        return out

    def complete(self, order_id) -> None:
        """Complete an IN_TRANSIT order (admin API; the web UI has no manual button)."""
        adm = self._login(self.creds.admin_phone, "WEB")
        self._req("POST", f"/shipper/orders/{order_id}/complete", adm)

    def create_driver(self) -> dict:
        """Create a free TK driver (with cardId — required to avoid the 500)."""
        tk = self._login(self.creds.carrier_phone, "TRANSPORT_COMPANY_APP")
        return self._req("POST", "/transport/drivers", tk, json={
            "fullName": "SANITY Driver", "phone": unique_phone(), "cardId": "AB1234567",
        }).json()

    def cancel(self, order_id, reason: str = "SANITY seed cancel") -> None:
        """Cancel a SELECTED+ order (admin API) — used to seed a CANCELLED order."""
        adm = self._login(self.creds.admin_phone, "WEB")
        self._req("POST", f"/shipper/orders/{order_id}/cancel", adm, json={"reason": reason})
