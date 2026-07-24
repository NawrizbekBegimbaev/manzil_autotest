"""API — Tendering: winner selection (docs/testcases/api/04_tendering_transport.json, part 2).

API-TND-050…069 — GET shipper offers + POST select. Плюс КРОСС-ГОНКИ (деньги!):
select×select (обе под локом), select×cancel (ЗАЛОЧЕННАЯ select × НЕзалоченная cancel —
потенциальная новая поверхность MNZL-275), select×offer-PATCH (редактирование оффера в
момент выбора). Порядок проверок select сверен с OfferService.selectWinner.

Один тест ↔ один ID. Прогон на DEV.
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
_CTYPE = {"SHIPPER_MANAGER": "WEB", "SHIPPER_OPERATOR": "WEB", "SHIPPER_DISPATCHER": "WEB"}


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _page(r):
    b = r.json()
    if _PAGE_SHAPE == "nested":
        assert isinstance(b, dict) and "page" in b, f"MNZL-245: ожидался вложенный page"
        return b["page"]
    return b


def _d(n):
    return "".join(random.choices(string.digits, k=n))


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def carrier(api):
    return api("transport_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def fresh_carrier(dev_api, cfg):
    created = []
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")

    def _mk():
        phone = "+99890" + _d(7)
        body = {"name": f"AT-TC-{_d(10)}", "tin": _d(9), "address": "Tashkent, Sayyod 1",
                "transportTypes": ["AUTO"], "isAll": True, "cityIds": [], "blacklistWarehouseIds": [],
                "admin": {"fullName": "AT C2", "phone": phone, "password": cfg.dev_account_password}}
        r = dev_api.request("POST", "/super-admin/transport-companies", sa, json=body)
        assert r.status_code == 201, f"fresh_carrier: {r.status_code} {r.text[:160]}"
        cid = r.json()["id"]
        created.append(cid)
        return RoleClient(dev_api, dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")), cid

    yield _mk
    for cid in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def cap(s_admin, dev_api, pwd):
    """Свежий shipper-office staff + опц. персональные гранты → залогиненный RoleClient."""
    created = []

    def _mk(role, grants=None):
        phone = "+99890" + _d(7)
        s = s_admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role})
        assert s.status_code == 201, f"cap staff: {s.status_code} {s.text[:160]}"
        sid = s.json()["id"]
        created.append(sid)
        if grants:
            r = s_admin.patch(f"/shipper/staff/{sid}",
                              json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
            assert r.status_code == 200, f"cap grant: {r.status_code} {r.text[:160]}"
        return RoleClient(dev_api, dev_api.token(phone, pwd, _CTYPE.get(role, "WEB")))

    yield _mk
    for sid in reversed(created):
        try:
            s_admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture(scope="session")
def foreign_order_id(dev_api, cfg, api_dev_roles):
    """Заказ чужой (компании B) — для tenancy/BOLA 404. Терминальный (CANCELLED), B удаляема."""
    from tests.regression.order_lifecycle import OrderFactory

    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + _d(7)
    body = {"name": f"AT-B-{_d(10)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": _d(9), "address": "Tashkent, Sayyod 1",
            "admin": {"fullName": "AT B Admin", "phone": aphone, "password": cfg.dev_account_password}}
    r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body)
    assert r.status_code in (200, 201), f"tenant B: {r.status_code} {r.text[:160]}"
    sid = r.json()["id"]
    adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
    whp = "+99890" + _d(7)
    dev_api.request("POST", "/shipper/staff", adm,
                    json={"fullName": "AT B WH", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
    whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    factory = OrderFactory(dev_api, sa, whb, adm, dev_api.token(cph, cpw, cct))
    order = factory.make("CANCELLED")
    yield order["id"]
    factory.teardown()
    dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", sa)


def _offers(s_admin, oid):
    return _content(s_admin.get(f"/shipper/orders/{oid}/offers?size=200"))


def _pending_offer_id(s_admin, oid):
    return next(o["id"] for o in _offers(s_admin, oid) if o["status"] == "PENDING")


def _select(client, oid, off_id):
    return client.post(f"/shipper/orders/{oid}/offers/{off_id}/select")


# ═══ GET /shipper/orders/{orderId}/offers (050…057) ══════════════════════════


@pytest.mark.high
def test_offers_list_050(s_admin, order_factory):
    o = order_factory.make("SELECTED")  # есть SELECTED-победитель + REJECTED прочие
    r = s_admin.get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 200, f"[API-TND-050] {r.status_code}"
    rows = _content(r)
    assert rows and rows[0].get("status") == "SELECTED", "[API-TND-050] победитель не закреплён первым"
    assert all("transportCompanyBlocked" in x for x in rows), "[API-TND-050] нет флага transportCompanyBlocked"
    assert _page(r).get("size") == 10, "[API-TND-050] size=10 по умолчанию"


@pytest.mark.low
def test_offers_empty_051(s_admin, order_factory):
    o = order_factory.make("PUBLISHED")  # ставок нет
    r = s_admin.get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 200 and _content(r) == [], f"[API-TND-051] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.capability
# GET offers гейтится SEE_PRICES (цены офферов), не TENDER_SELECT — см. ShipperTenderingController:64
def test_offers_manager_no_grant_403_052(api, order_factory):
    o = order_factory.make("QUOTED")
    r = api("shipper_manager").get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-TND-052] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_offers_manager_granted_200_053(cap, order_factory):
    o = order_factory.make("QUOTED")
    mgr = cap("SHIPPER_MANAGER", grants=["SEE_PRICES"])  # список офферов показывает цены → гейт SEE_PRICES, не TENDER_SELECT
    r = mgr.get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 200, f"[API-TND-053] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
@pytest.mark.parametrize("role", ["shipper_operator", "shipper_dispatcher"])
def test_offers_role_no_grant_403_054(api, order_factory, role):
    o = order_factory.make("QUOTED")
    r = api(role).get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-TND-054] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
@pytest.mark.parametrize("role", ["transport_admin", "shipper_warehouse", "super_admin"])
def test_offers_rbac_055(api, order_factory, role):
    o = order_factory.make("QUOTED")
    r = api(role).get(f"/shipper/orders/{o['id']}/offers")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-055] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_offers_tenancy_056(s_admin, foreign_order_id):
    r = s_admin.get(f"/shipper/orders/{foreign_order_id}/offers")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-TND-056] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_offers_not_found_057(s_admin):
    r = s_admin.get("/shipper/orders/999999999/offers")
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-TND-057] {r.status_code}/{_code(r)}"


# ═══ POST select (058…069) ═══════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_select_happy_058(s_admin, order_factory):
    o = order_factory.make("QUOTED")
    off = _pending_offer_id(s_admin, o["id"])
    r = _select(s_admin, o["id"], off)
    assert r.status_code == 200, f"[API-TND-058] {r.status_code} {r.text[:160]}"
    det = s_admin.get(f"/shipper/orders/{o['id']}").json()["order"]
    assert det["status"] == "SELECTED" and det.get("winnerOfferId") == off, f"[API-TND-058] {det.get('status')}"
    offs = {x["id"]: x["status"] for x in _offers(s_admin, o["id"])}
    assert offs[off] == "SELECTED" and all(v == "REJECTED" for k, v in offs.items() if k != off), f"[API-TND-058] статусы офферов: {offs}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_select_already_selected_059(s_admin, order_factory):
    o = order_factory.make("SELECTED")  # победитель уже выбран
    off = _offers(s_admin, o["id"])[0]["id"]
    r = _select(s_admin, o["id"], off)
    assert r.status_code == 409 and _code(r) == "error.offer.already-selected", f"[API-TND-059] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_select_not_quoted_060(s_admin, carrier, order_factory):
    o = order_factory.make("PUBLISHED")  # QUOTED-переход не случился (нет ставок)
    r = _select(s_admin, o["id"], str(uuid.uuid4()))
    assert r.status_code == 409 and _code(r) == "error.order.not-selectable", f"[API-TND-060] {r.status_code}/{_code(r)}"


# API-TND-061 (не-PENDING оффер на QUOTED-заказе → not-selectable) — automation:pending:
# состояние недостижимо чистым чёрным ящиком — первый select переводит заказ из QUOTED в SELECTED,
# а republish-REVERT восстанавливает офферы обратно в PENDING. Порядок проверки (offer!=PENDING →
# error.order.not-selectable) подтверждён по OfferService.selectWinner. См. docs/testcases NON-AUTO.


@pytest.mark.high
@pytest.mark.lifecycle
def test_select_transport_blocked_062(s_admin, fresh_carrier, order_factory, dev_api, cfg):
    o = order_factory.make("PUBLISHED")
    c2, cid = fresh_carrier()
    off = c2.post(f"/transport/orders/{o['id']}/offers", json={"price": 500}).json()["id"]
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)  # деактивируем перевозчика
    r = _select(s_admin, o["id"], off)
    assert r.status_code == 409 and _code(r) == "error.offer.transport-blocked", f"[API-TND-062] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_select_offer_other_order_063(s_admin, carrier, order_factory):
    o1 = order_factory.make("QUOTED")
    o2 = order_factory.make("QUOTED")
    off2 = _pending_offer_id(s_admin, o2["id"])  # оффер другого заказа
    r = _select(s_admin, o1["id"], off2)
    assert r.status_code == 404 and _code(r) == "error.offer.not-found", f"[API-TND-063] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_select_offer_not_found_064(s_admin, order_factory):
    o = order_factory.make("QUOTED")
    r = _select(s_admin, o["id"], str(uuid.uuid4()))
    assert r.status_code == 404 and _code(r) == "error.offer.not-found", f"[API-TND-064] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_select_tenancy_065(s_admin, foreign_order_id):
    r = _select(s_admin, foreign_order_id, str(uuid.uuid4()))
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-TND-065] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_select_manager_no_grant_403_066(cap, order_factory):
    o = order_factory.make("QUOTED")
    mgr = cap("SHIPPER_MANAGER")
    r = _select(mgr, o["id"], str(uuid.uuid4()))
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-TND-066] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_select_manager_granted_067(cap, s_admin, order_factory):
    o = order_factory.make("QUOTED")
    off = _pending_offer_id(s_admin, o["id"])
    mgr = cap("SHIPPER_MANAGER", grants=["TENDER_SELECT"])
    r = _select(mgr, o["id"], off)
    assert r.status_code == 200, f"[API-TND-067] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.rbac
@pytest.mark.parametrize("role", ["transport_admin", "shipper_warehouse", "super_admin"])
def test_select_rbac_068(api, order_factory, role):
    o = order_factory.make("QUOTED")
    r = _select(api(role), o["id"], str(uuid.uuid4()))
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-TND-068] {role}: {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_select_race_two_selects_069(s_admin, fresh_carrier, order_factory, cfg):
    """Две одновременные select разных офферов: ровно один 200, второй 409 (already-selected /
    concurrent-modification), НИКОГДА 500 и НИКОГДА два SELECTED. select под findByIdForUpdate. 12 раундов — доказательство, не везение."""
    from utils.api_client import ApiClient
    tok = s_admin.token
    seen = []
    for _ in range(12):
        o = order_factory.make("QUOTED")  # 1 оффер (dev-перевозчик)
        c2, _ = fresh_carrier()
        c2.post(f"/transport/orders/{o['id']}/offers", json={"price": 900})  # 2-й оффер
        offs = [x["id"] for x in _offers(s_admin, o["id"]) if x["status"] == "PENDING"]
        assert len(offs) == 2, f"нужно 2 PENDING-оффера, есть {len(offs)}"
        clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(2)]
        jobs = list(zip(clients, offs))

        def fire(job):
            c, off = job
            return c.request("POST", f"/shipper/orders/{o['id']}/offers/{off}/select", tok).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            rc = sorted(ex.map(fire, jobs))
        seen.extend(rc)
        assert rc.count(200) == 1, f"ровно один select должен пройти, получили {rc}"
        sel = [x for x in _offers(s_admin, o["id"]) if x["status"] == "SELECTED"]
        assert len(sel) == 1, f"должна быть ровно одна SELECTED-ставка, найдено {len(sel)}"
    assert 500 not in seen, f"[API-TND-069][race select×select] 500 недопустим (заказ под findByIdForUpdate): {seen}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_select_race_select_x_cancel(s_admin, order_factory, cfg):
    """КРОСС-ГОНКА: ЗАЛОЧЕННАЯ select × НЕзалоченная cancel на одном заказе. cancel читает без
    findByIdForUpdate (корень BUG-035/MNZL-275) — проверяем, не даёт ли пересечение 500 на новой
    поверхности. Ожидание при корректной работе: select 200; cancel — 409 not-cancellable (читал
    QUOTED) ЛИБО 200 (успел отменить уже-SELECTED); НИКОГДА 500."""
    from utils.api_client import ApiClient
    tok = s_admin.token
    cancel_codes = []
    for _ in range(12):
        o = order_factory.make("QUOTED")
        off = _pending_offer_id(s_admin, o["id"])
        cs, cc = ApiClient(cfg, base_url=cfg.dev_url), ApiClient(cfg, base_url=cfg.dev_url)

        def do_select():
            return cs.request("POST", f"/shipper/orders/{o['id']}/offers/{off}/select", tok).status_code

        def do_cancel():
            return cc.request("POST", f"/shipper/orders/{o['id']}/cancel", tok, json={"reason": "race"}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fs, fc = ex.submit(do_select), ex.submit(do_cancel)
            sc, cnl = fs.result(), fc.result()
        cancel_codes.append(cnl)
        assert sc in (200, 409), f"select дал неожиданный код {sc}"
        assert cnl in (200, 409), f"[MNZL-275?] cancel в гонке с select дал {cnl} (ожидали 200/409, не 500)"
    assert 500 not in cancel_codes, f"[race select×cancel] cancel дал 500 — новая поверхность MNZL-275: {cancel_codes}"


@pytest.mark.medium
@pytest.mark.lifecycle
def test_select_race_select_x_offer_patch(s_admin, carrier, order_factory, cfg):
    """КРОСС-ГОНКА: select оффера × PATCH цены того же оффера (редактирование в момент выбора —
    деньги). select пишет оффер БЕЗ лока оффера, PATCH берёт findByIdForUpdate(offer). Проверяем
    отсутствие 500 и что деньги не «перезаписываются» после выбора без следа."""
    from utils.api_client import ApiClient
    stok = s_admin.token
    ctok = carrier.token
    patch_codes = []
    for _ in range(12):
        o = order_factory.make("QUOTED")
        off = _pending_offer_id(s_admin, o["id"])
        cs, cp = ApiClient(cfg, base_url=cfg.dev_url), ApiClient(cfg, base_url=cfg.dev_url)

        def do_select():
            return cs.request("POST", f"/shipper/orders/{o['id']}/offers/{off}/select", stok).status_code

        def do_patch():
            return cp.request("PATCH", f"/transport/offers/{off}", ctok, json={"price": 4242}).status_code

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fs, fp = ex.submit(do_select), ex.submit(do_patch)
            sc, pc = fs.result(), fp.result()
        patch_codes.append(pc)
        assert sc in (200, 409), f"select дал {sc}"
        assert pc in (200, 409), f"[MNZL-275?] PATCH оффера в гонке с select дал {pc} (ожидали 200/409, не 500)"
    assert 500 not in patch_codes, f"[race select×patch] 500 недопустим: {patch_codes}"
