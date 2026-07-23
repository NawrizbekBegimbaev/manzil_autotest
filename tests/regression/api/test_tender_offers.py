"""API — Tendering: offers (docs/testcases/api/04_tendering_transport.json, part 1).

API-TND-001…049 — офферы: submit (bid), self-edit (PATCH), my-offers, feed, feed/{id},
feed/summary. Плюс ГОНКИ (сверх библиотеки): два бида (разные компании / одна компания),
проверка что @Version-конфликт заказа НЕ даёт 500 (bid берёт `findByIdForUpdate` —
пессимистичный лок, в отличие от BUG-035 на cancel/enter-1c).

Один тест ↔ один ID. Проверки строгие: статус + `code` + `errors[]`. Прогон на DEV.
"""

from __future__ import annotations

import concurrent.futures as cf
import random
import string
import uuid

import pytest

from config.settings import get_settings
from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api]

_PAGE_SHAPE = get_settings().page_shape


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _err_fields(r):
    try:
        return {e.get("field") for e in (r.json().get("errors") or [])}
    except Exception:  # noqa: BLE001
        return set()


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _page(r):
    b = r.json()
    if _PAGE_SHAPE == "nested":
        assert isinstance(b, dict) and "page" in b, f"MNZL-245: ожидался вложенный page: {sorted(b) if isinstance(b, dict) else type(b)}"
        return b["page"]
    return b


def _d(n):
    return "".join(random.choices(string.digits, k=n))


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def carrier(api):
    return api("transport_admin")


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def fresh_carrier(dev_api, cfg):
    """Factory → свежая транспортная компания (isAll/cityIds настраиваемы) + её TRANSPORT_ADMIN.
    Возвращает (RoleClient, company_id, phone). Удаляется на teardown."""
    created = []
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")

    def _mk(is_all=True, city_ids=None, blacklist=None):
        phone = "+99890" + _d(7)
        body = {"name": f"AT-TC-{_d(6)}", "tin": _d(9), "address": "Tashkent, Sayyod 1",
                "transportTypes": ["AUTO"], "isAll": is_all, "cityIds": city_ids or [],
                "blacklistWarehouseIds": blacklist or [],
                "admin": {"fullName": "AT Carrier2", "phone": phone, "password": cfg.dev_account_password}}
        r = dev_api.request("POST", "/super-admin/transport-companies", sa, json=body)
        assert r.status_code == 201, f"fresh_carrier: {r.status_code} {r.text[:160]}"
        cid = r.json()["id"]
        created.append(cid)
        tok = dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")
        return RoleClient(dev_api, tok), cid, phone

    yield _mk
    for cid in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


def _bid(client, order_id, price=1000, notes=None):
    body = {"price": price}
    if notes is not None:
        body["notes"] = notes
    return client.post(f"/transport/orders/{order_id}/offers", json=body)


def _order_status(s_admin, oid):
    return s_admin.get(f"/shipper/orders/{oid}").json()["order"]["status"]


# ═══ POST offers — submit / bid (001…017) ════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_bid_happy_001(carrier, s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=1234)
    assert r.status_code == 201, f"[API-TND-001] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("status") == "PENDING" and b.get("currency") == o["currency"], f"[API-TND-001] {b}"
    assert _order_status(s_admin, o["id"]) == "QUOTED", "[API-TND-001] первый бид не перевёл PUBLISHED→QUOTED"


@pytest.mark.high
@pytest.mark.lifecycle
def test_bid_on_quoted_002(fresh_carrier, s_admin, order_factory):
    o = order_factory.make("QUOTED")  # dev-перевозчик уже бидил
    carrier2, _, _ = fresh_carrier()
    r = _bid(carrier2, o["id"], price=999)
    assert r.status_code == 201 and r.json().get("status") == "PENDING", f"[API-TND-002] {r.status_code} {r.text[:160]}"
    assert _order_status(s_admin, o["id"]) == "QUOTED", "[API-TND-002] второй бид не должен менять статус"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_bid_first_offer_event_once_003(carrier, fresh_carrier, s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    assert _bid(carrier, o["id"]).status_code == 201, "[API-TND-003] первый бид"
    carrier2, _, _ = fresh_carrier()
    assert _bid(carrier2, o["id"]).status_code == 201, "[API-TND-003] второй бид"
    hist = s_admin.get(f"/shipper/orders/{o['id']}").json()["history"]
    n = sum(1 for e in hist if e.get("type") == "FIRST_OFFER_RECEIVED")
    assert n == 1, f"[API-TND-003] FIRST_OFFER_RECEIVED должно быть ровно 1, найдено {n}"


@pytest.mark.high
@pytest.mark.negative
def test_bid_already_submitted_004(carrier, order_factory):
    o = order_factory.make("QUOTED")  # dev-перевозчик (=api transport_admin) уже бидил
    r = _bid(carrier, o["id"])
    assert r.status_code == 409 and _code(r) == "error.offer.already-submitted", f"[API-TND-004] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_bid_not_open_005(fresh_carrier, order_factory):
    o = order_factory.make("SELECTED")
    carrier2, _, _ = fresh_carrier()
    r = _bid(carrier2, o["id"])
    assert r.status_code == 409 and _code(r) == "error.order.not-open-for-bids", f"[API-TND-005] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_bid_carrier_excluded_006(carrier, s_admin, order_factory):
    """Перевыпуск с изменением исключает прошлого победителя (dev-перевозчик) из нового заказа."""
    o = order_factory.make("CANCELLED")  # dev-перевозчик был победителем
    from tests.regression.order_lifecycle import _digits  # noqa
    new = s_admin.post(f"/shipper/orders/{o['id']}/republish", json={
        "cargoType": o["cargoType"], "currency": o["currency"], "loadDate": "2026-12-31",
        "vehicleTypeId": o["vehicleTypeId"], "driversCount": o["driversCount"],
        "fromWarehouseId": o["fromWarehouseId"], "toWarehouseId": o["toWarehouseId"]})
    assert new.status_code == 200, f"[API-TND-006] republish: {new.status_code} {new.text[:160]}"
    new_id = new.json().get("order", new.json()).get("id") if isinstance(new.json(), dict) else None
    new_id = new_id or new.json().get("id")
    try:
        r = _bid(carrier, new_id)
        assert r.status_code == 409 and _code(r) == "error.offer.carrier-excluded", f"[API-TND-006] {r.status_code}/{_code(r)}"
    finally:
        s_admin.delete(f"/shipper/orders/{new_id}")


@pytest.mark.medium
@pytest.mark.negative
def test_bid_order_not_found_007(carrier):
    r = _bid(carrier, 999999999)
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-TND-007] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.validation
def test_bid_price_null_008(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = carrier.post(f"/transport/orders/{o['id']}/offers", json={"notes": "no price"})
    assert r.status_code == 400 and "price" in _err_fields(r), f"[API-TND-008] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
@pytest.mark.validation
@pytest.mark.boundary
def test_bid_price_zero_009(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=0)
    assert r.status_code == 400 and "price" in _err_fields(r), f"[API-TND-009] {r.status_code} {_err_fields(r)}"


@pytest.mark.medium
@pytest.mark.validation
@pytest.mark.boundary
def test_bid_price_negative_010(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=-5)
    assert r.status_code == 400 and "price" in _err_fields(r), f"[API-TND-010] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_bid_price_min_011(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=0.01)
    assert r.status_code == 201, f"[API-TND-011] 0.01 должно приниматься: {r.status_code} {r.text[:120]}"


@pytest.mark.low
@pytest.mark.boundary
def test_bid_price_max_012(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=9999999999999.99)
    assert r.status_code == 201, f"[API-TND-012] верхняя граница цены: {r.status_code} {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.validation
@pytest.mark.boundary
def test_bid_price_over_max_013(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = carrier.post(f"/transport/orders/{o['id']}/offers", json={"price": 10000000000000})
    assert r.status_code == 400 and "price" in _err_fields(r), f"[API-TND-013] {r.status_code} {_err_fields(r)}"


@pytest.mark.low
@pytest.mark.validation
@pytest.mark.boundary
def test_bid_notes_boundary_014(carrier, fresh_carrier, order_factory):
    o1 = order_factory.make("PUBLISHED")
    ok = _bid(carrier, o1["id"], notes="n" * 250)
    assert ok.status_code == 201, f"[API-TND-014] notes=250: {ok.status_code} {ok.text[:120]}"
    o2 = order_factory.make("PUBLISHED")
    bad = _bid(carrier, o2["id"], notes="n" * 251)
    assert bad.status_code == 400 and "notes" in _err_fields(bad), f"[API-TND-014] notes=251: {bad.status_code} {_err_fields(bad)}"


@pytest.mark.high
@pytest.mark.rbac
def test_bid_rbac_shipper_admin_015(s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(s_admin, o["id"])
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-015] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
@pytest.mark.parametrize("role", ["super_admin", "shipper_manager", "shipper_operator", "shipper_dispatcher", "shipper_warehouse"])
def test_bid_rbac_other_roles_016(api, order_factory, role):
    o = order_factory.make("PUBLISHED")
    r = _bid(api(role), o["id"])
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-016] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_bid_no_token_017(dev_api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = dev_api.request("POST", f"/transport/orders/{o['id']}/offers", None, json={"price": 100})
    assert r.status_code == 401, f"[API-TND-017] {r.status_code}"


# ═══ ГОНКИ офферов (сверх библиотеки) ════════════════════════════════════════


@pytest.mark.medium
@pytest.mark.lifecycle
def test_bid_race_two_carriers_first_bid(carrier, fresh_carrier, s_admin, order_factory, cfg):
    """Два ПЕРВЫХ бида разных компаний на PUBLISHED-заказ одновременно: оба 201, заказ→QUOTED,
    НИКОГДА 500. bid берёт findByIdForUpdate (пессимистичный лок) — @Version-конфликт заказа
    сериализуется, в отличие от cancel/enter-1c (BUG-035). Подтверждаем отсутствие дефекта."""
    from utils.api_client import ApiClient
    carrier2, _, phone2 = fresh_carrier()
    tok1 = carrier.token
    tok2 = carrier2.token
    codes = []
    for _ in range(6):
        o = order_factory.make("PUBLISHED")
        c1 = ApiClient(cfg, base_url=cfg.dev_url)
        c2 = ApiClient(cfg, base_url=cfg.dev_url)
        jobs = [(c1, tok1), (c2, tok2)]

        def fire(job):
            c, t = job
            return c.request("POST", f"/transport/orders/{o['id']}/offers", t, json={"price": 500}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, jobs))
        codes.extend(rc)
        assert rc == [201, 201], f"два первых бида разных компаний должны быть 201/201, получили {rc}"
        assert _order_status(s_admin, o["id"]) == "QUOTED", "заказ должен стать QUOTED"
    assert 500 not in codes, f"[race] бид не должен давать 500 (заказ под findByIdForUpdate): {codes}"


@pytest.mark.medium
@pytest.mark.negative
def test_bid_race_same_carrier_duplicate(carrier, order_factory, cfg):
    """Два одновременных бида ОДНОЙ компании на один заказ: ровно один 201, второй 409
    already-submitted, НИКОГДА 500 (лок заказа сериализует существование-проверку)."""
    from utils.api_client import ApiClient
    tok = carrier.token
    seen = []
    for _ in range(6):
        o = order_factory.make("PUBLISHED")
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]

        def fire(c):
            return c.request("POST", f"/transport/orders/{o['id']}/offers", tok, json={"price": 700}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, clients))
        seen.extend(rc)
        assert rc.count(201) == 1, f"ровно один бид должен пройти, получили {rc}"
        assert rc.count(409) == 1, f"второй бид должен быть 409 already-submitted, получили {rc}"
    assert 500 not in seen, f"[race] дубль-бид не должен давать 500: {seen}"


# ═══ PATCH offers — self-edit (018…026) ══════════════════════════════════════


def _pending_offer(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _bid(carrier, o["id"], price=1000, notes="old")
    assert r.status_code == 201, f"setup bid: {r.status_code} {r.text[:160]}"
    return o, r.json()["id"]


@pytest.mark.high
def test_offer_patch_happy_018(carrier, order_factory):
    _, oid = _pending_offer(carrier, order_factory)
    r = carrier.patch(f"/transport/offers/{oid}", json={"price": 1450, "notes": "скидка"})
    assert r.status_code == 200, f"[API-TND-018] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert float(b["price"]) == 1450 and b["notes"] == "скидка", f"[API-TND-018] {b}"


@pytest.mark.medium
def test_offer_patch_empty_019(carrier, order_factory):
    _, oid = _pending_offer(carrier, order_factory)
    r = carrier.patch(f"/transport/offers/{oid}", json={})
    assert r.status_code == 200 and float(r.json()["price"]) == 1000 and r.json()["notes"] == "old", f"[API-TND-019] {r.text[:120]}"


@pytest.mark.low
def test_offer_patch_notes_only_020(carrier, order_factory):
    _, oid = _pending_offer(carrier, order_factory)
    r = carrier.patch(f"/transport/offers/{oid}", json={"notes": "новая заметка"})
    assert r.status_code == 200 and r.json()["notes"] == "новая заметка" and float(r.json()["price"]) == 1000, f"[API-TND-020] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_offer_patch_not_editable_021(carrier, s_admin, order_factory):
    o = order_factory.make("SELECTED")  # у dev-перевозчика оффер SELECTED
    off_id = s_admin.get(f"/shipper/orders/{o['id']}").json()["winningOffer"]["id"]
    r = carrier.patch(f"/transport/offers/{off_id}", json={"price": 5})
    assert r.status_code == 409 and _code(r) == "error.offer.not-editable", f"[API-TND-021] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_offer_patch_foreign_404_022(carrier, fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier()
    foreign_off = _bid(carrier2, o["id"]).json()["id"]
    r = carrier.patch(f"/transport/offers/{foreign_off}", json={"price": 5})
    assert r.status_code == 404 and _code(r) == "error.offer.not-found", f"[API-TND-022] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_offer_patch_not_found_023(carrier):
    r = carrier.patch(f"/transport/offers/{uuid.uuid4()}", json={"price": 5})
    assert r.status_code == 404 and _code(r) == "error.offer.not-found", f"[API-TND-023] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_offer_patch_price_validation_024(carrier, order_factory):
    _, oid = _pending_offer(carrier, order_factory)
    r0 = carrier.patch(f"/transport/offers/{oid}", json={"price": 0})
    assert r0.status_code == 400, f"[API-TND-024] price=0 → 400: {r0.status_code}"
    rbig = carrier.patch(f"/transport/offers/{oid}", json={"price": 100000000000000})
    assert rbig.status_code == 409, f"[API-TND-024] огромная цена при PATCH → 409 (не 500): {rbig.status_code} {rbig.text[:120]}"


@pytest.mark.low
@pytest.mark.validation
@pytest.mark.boundary
def test_offer_patch_notes_long_025(carrier, order_factory):
    _, oid = _pending_offer(carrier, order_factory)
    r = carrier.patch(f"/transport/offers/{oid}", json={"notes": "n" * 251})
    assert r.status_code == 400 and "notes" in _err_fields(r), f"[API-TND-025] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
@pytest.mark.rbac
def test_offer_patch_rbac_026(api):
    r = api("shipper_admin").patch(f"/transport/offers/{uuid.uuid4()}", json={"price": 5})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-026] {r.status_code}/{_code(r)}"


# ═══ GET my-offers (027…032) ═════════════════════════════════════════════════


@pytest.mark.high
def test_my_offers_list_027(carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    _bid(carrier, o["id"])
    r = carrier.get("/transport/my-offers")
    assert r.status_code == 200, f"[API-TND-027] {r.status_code}"
    assert _page(r).get("size") == 20, f"[API-TND-027] size=20 по умолчанию: {_page(r)}"


@pytest.mark.medium
def test_my_offers_filter_status_028(carrier, order_factory):
    o = order_factory.make("SELECTED")  # у dev-перевозчика SELECTED-оффер
    rows = _content(carrier.get("/transport/my-offers?status=SELECTED&size=200"))
    assert rows and all(x.get("status") == "SELECTED" for x in rows), "[API-TND-028] фильтр status протекает"


@pytest.mark.medium
def test_my_offers_filter_orderstatus_029(carrier, order_factory):
    o = order_factory.make("IN_WORK")
    rows = _content(carrier.get("/transport/my-offers?orderStatus=IN_WORK&size=200"))
    assert rows and all((x.get("orderStatus") == "IN_WORK") for x in rows), "[API-TND-029] фильтр orderStatus протекает"


@pytest.mark.low
@pytest.mark.boundary
def test_my_offers_pagination_030(carrier, order_factory):
    r = carrier.get("/transport/my-offers?page=1&size=5")
    assert r.status_code == 200 and len(_content(r)) <= 5 and _page(r).get("page") == 1, f"[API-TND-030] {r.text[:120]}"


@pytest.mark.low
def test_my_offers_empty_031(fresh_carrier):
    carrier2, _, _ = fresh_carrier()
    r = carrier2.get("/transport/my-offers")
    assert r.status_code == 200 and _content(r) == [] and _page(r).get("totalElements") == 0, f"[API-TND-031] {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.rbac
def test_my_offers_rbac_032(api):
    r = api("shipper_admin").get("/transport/my-offers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-032] {r.status_code}/{_code(r)}"


# ═══ GET feed (033…043) ══════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def two_cities(dev_api, cfg):
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    rows = dev_api.request("GET", "/super-admin/cities?size=5", sa).json()
    rows = rows.get("content", rows) if isinstance(rows, dict) else rows
    return [c["id"] for c in rows[:2]]


def _num(o):
    return o["displayNumber"].split("-")[-1]


def _in_feed(carrier, o):
    rows = _content(carrier.get(f"/transport/feed?search={_num(o)}&size=200"))
    return any(x.get("id") == o["id"] for x in rows)


@pytest.mark.high
def test_feed_happy_033(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    r = carrier2.get(f"/transport/feed?search={_num(o)}&size=200")
    assert r.status_code == 200, f"[API-TND-033] {r.status_code}"
    assert _page(r).get("size") == 200 and any(x.get("id") == o["id"] for x in _content(r)), "[API-TND-033] заказ не в ленте"


@pytest.mark.high
def test_feed_hides_already_bid_034(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    assert _in_feed(carrier2, o), "[API-TND-034] предусловие: заказ виден до бида"
    assert _bid(carrier2, o["id"]).status_code == 201
    assert not _in_feed(carrier2, o), "[API-TND-034] заказ со своим бидом должен уйти из ленты"


@pytest.mark.high
@pytest.mark.tenancy
def test_feed_city_not_served_035(fresh_carrier, order_factory, two_cities):
    o = order_factory.make("PUBLISHED")  # склады в two_cities[0]
    carrier2, _, _ = fresh_carrier(is_all=False, city_ids=[two_cities[1]])  # обслуживает другой город
    assert not _in_feed(carrier2, o), "[API-TND-035] заказ вне обслуживаемого города должен быть скрыт"


@pytest.mark.medium
def test_feed_isall_036(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    assert _in_feed(carrier2, o), "[API-TND-036] isAll=true должен видеть заказ любого города"


@pytest.mark.medium
@pytest.mark.tenancy
def test_feed_blacklist_warehouse_037(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True, blacklist=[o["fromWarehouseId"]])
    assert not _in_feed(carrier2, o), "[API-TND-037] заказ с blacklisted-складом на плече должен быть скрыт"


@pytest.mark.medium
@pytest.mark.tenancy
def test_feed_excluded_carrier_038(fresh_carrier, s_admin, order_factory):
    """Свежий перевозчик выигрывает → отмена → перевыпуск с изменением исключает его; в его ленте
    нового заказа нет, а у другого перевозчика — есть."""
    o = order_factory.make("PUBLISHED")
    winner, win_id, _ = fresh_carrier(is_all=True)
    off = _bid(winner, o["id"]).json()["id"]
    assert s_admin.post(f"/shipper/orders/{o['id']}/offers/{off}/select").status_code in (200, 201), "[API-TND-038] select"
    assert s_admin.post(f"/shipper/orders/{o['id']}/cancel", json={"reason": "x"}).status_code == 200, "[API-TND-038] cancel"
    new = s_admin.post(f"/shipper/orders/{o['id']}/republish", json={
        "cargoType": o["cargoType"], "currency": o["currency"], "loadDate": "2026-12-31",
        "vehicleTypeId": o["vehicleTypeId"], "driversCount": o["driversCount"],
        "fromWarehouseId": o["fromWarehouseId"], "toWarehouseId": o["toWarehouseId"]}).json()
    new_o = new.get("order", new)
    try:
        assert not _in_feed(winner, new_o), "[API-TND-038] исключённый бывший победитель не должен видеть перевыпущенный заказ"
        other, _, _ = fresh_carrier(is_all=True)
        assert _in_feed(other, new_o), "[API-TND-038] другой перевозчик перевыпущенный заказ видит"
    finally:
        s_admin.delete(f"/shipper/orders/{new_o['id']}")


@pytest.mark.medium
@pytest.mark.lifecycle
def test_feed_no_superseded_039(fresh_carrier, s_admin, order_factory):
    o = order_factory.make("CANCELLED")
    new = s_admin.post(f"/shipper/orders/{o['id']}/republish", json={
        "cargoType": o["cargoType"], "currency": o["currency"], "loadDate": "2026-12-31",
        "vehicleTypeId": o["vehicleTypeId"], "driversCount": o["driversCount"],
        "fromWarehouseId": o["fromWarehouseId"], "toWarehouseId": o["toWarehouseId"]}).json()
    new_o = new.get("order", new)
    carrier2, _, _ = fresh_carrier(is_all=True)
    try:
        assert not _in_feed(carrier2, o), "[API-TND-039] SUPERSEDED-заказ не должен быть в ленте"
    finally:
        s_admin.delete(f"/shipper/orders/{new_o['id']}")


@pytest.mark.medium
def test_feed_filters_040(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    rows = _content(carrier2.get(f"/transport/feed?search={_num(o)}&cargoType=AUTO&size=200"))
    assert any(x.get("id") == o["id"] for x in rows) and all(x.get("cargoType") == "AUTO" for x in rows), "[API-TND-040] фильтры ленты"


@pytest.mark.low
def test_feed_filter_status_041(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    rows = _content(carrier2.get("/transport/feed?status=PUBLISHED&size=200"))
    assert all(x.get("status") == "PUBLISHED" for x in rows), "[API-TND-041] фильтр status протекает"


@pytest.mark.low
@pytest.mark.validation
def test_feed_bad_date_042(fresh_carrier):
    carrier2, _, _ = fresh_carrier(is_all=True)
    r = carrier2.get("/transport/feed?loadFrom=31-12-2026")
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-TND-042] {r.status_code}/{_code(r)}"  # date type-mismatch → framework BAD_REQUEST


@pytest.mark.medium
@pytest.mark.rbac
def test_feed_rbac_043(api, dev_api):
    assert api("shipper_admin").get("/transport/feed").status_code == 403, "[API-TND-043] не-TND роль → 403"
    assert dev_api.request("GET", "/transport/feed", None).status_code == 401, "[API-TND-043] без токена → 401"


# ═══ GET feed/{id} (044…047) ═════════════════════════════════════════════════


@pytest.mark.high
def test_feed_detail_no_bid_044(fresh_carrier, order_factory):
    o = order_factory.make("PUBLISHED")
    carrier2, _, _ = fresh_carrier(is_all=True)
    b = carrier2.get(f"/transport/feed/{o['id']}").json()
    assert b.get("activeBidId") is None and b.get("activeBidAmount") is None, f"[API-TND-044] activeBid должен быть null: {b.get('activeBidId')}"


@pytest.mark.high
def test_feed_detail_with_bid_045(carrier, order_factory):
    o = order_factory.make("SELECTED")  # dev-перевозчик бидил и выиграл (заказ ушёл из маркетплейса)
    b = carrier.get(f"/transport/feed/{o['id']}").json()
    assert b.get("activeBidId") and b.get("activeBidAmount") is not None, f"[API-TND-045] activeBid должен быть заполнен вне PUBLISHED/QUOTED: {b}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_feed_detail_out_of_scope_404_046(fresh_carrier, order_factory):
    # detail видимость = marketplace-статус (PUBLISHED/QUOTED) ИЛИ свой бид; город/blacklist фильтруют
    # только ленту-список, не detail. Out-of-scope = не-marketplace статус без бида этой компании.
    o = order_factory.make("SELECTED")  # не-marketplace; dev-перевозчик бидил, carrier2 — нет
    carrier2, _, _ = fresh_carrier(is_all=True)
    r = carrier2.get(f"/transport/feed/{o['id']}")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-TND-046] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_feed_detail_rbac_047(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = api("shipper_admin").get(f"/transport/feed/{o['id']}")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-047] {r.status_code}/{_code(r)}"


# ═══ GET feed/summary (048…049) ══════════════════════════════════════════════


@pytest.mark.medium
def test_feed_summary_048(fresh_carrier):
    carrier2, _, _ = fresh_carrier(is_all=True)
    b = carrier2.get("/transport/feed/summary").json()
    assert isinstance(b, dict) and ("marketplace" in b and "won" in b), f"[API-TND-048] нет карт marketplace/won: {sorted(b) if isinstance(b, dict) else b}"


@pytest.mark.low
@pytest.mark.rbac
def test_feed_summary_rbac_049(api, dev_api):
    assert api("shipper_admin").get("/transport/feed/summary").status_code == 403, "[API-TND-049] не-TND → 403"
    assert dev_api.request("GET", "/transport/feed/summary", None).status_code == 401, "[API-TND-049] без токена → 401"
