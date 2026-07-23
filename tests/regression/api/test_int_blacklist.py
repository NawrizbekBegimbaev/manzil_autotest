"""API — shipper driver-blacklist (06_integrations_sms_dicts.json, INT-126…151).

Чёрный список водителей грузоотправителя: добавить водителя с ЗАВЕРШЁННОГО (COMPLETED)
заказа → он больше не прикрепляется к заказам этой компании. Ключ блокировки — ТЕЛЕФОН
(snapshot телефона+имени). Контроллер: @PreAuthorize(shipper-роли) + @RequiresCapability(BLACKLIST).
BLACKLIST — admin-only-grantable (нет в дефолтах ролей): у SHIPPER_ADMIN есть (ADMIN=all),
у MANAGER/OPERATOR/DISPATCHER — только персональным грантом.

Порядок проверок в сервисе (важно для кодов): чужая компания → 404 error.order.not-found;
не COMPLETED → 409 error.order.not-completed; водитель НЕ привязан → 404
error.order.driver-not-attached; только потом lookup водителя → 404 error.driver.not-found.
Т.е. несуществующий driverId ловится ПРОВЕРКОЙ ПРИВЯЗКИ (existsByOrderIdAndDriverId) РАНЬШЕ,
чем lookup — и даёт driver-not-attached, а не driver.not-found (INT-130 уточнён по факту;
error.driver.not-found достижим лишь в orphan-состоянии attach-then-delete — чёрным ящиком не
воспроизводится). Удаление — soft: телефон снова свободен (идемпотентное повторное добавление).

Один тест ↔ один ID. Прогон на DEV. COMPLETED-заказы — через OrderFactory (company A).
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

from tests.regression.conftest import RoleClient
from tests.regression.order_lifecycle import OrderFactory

pytestmark = [pytest.mark.regression, pytest.mark.api]

_ADDR = "Tashkent"


def _d(n):
    return "".join(random.choices(string.digits, k=n))


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _add(client, order_id, driver_id, reason="AT blacklist reason"):
    body = {}
    if driver_id is not _OMIT:
        body["driverId"] = driver_id
    if reason is not _OMIT:
        body["reason"] = reason
    return client.post(f"/shipper/orders/{order_id}/blacklist", json=body)


_OMIT = object()


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def cap(s_admin, dev_api, pwd):
    """Создать shipper-staff с ролью и (опц.) персональными грантами capability."""
    created = []

    def _mk(role, grants=None):
        phone = "+99890" + _d(7)
        sid = s_admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role}).json()["id"]
        created.append(sid)
        if grants:
            s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
        return RoleClient(dev_api, dev_api.token(phone, pwd, "WEB"))

    yield _mk
    for sid in reversed(created):
        try:
            s_admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def completed(order_factory):
    """(orderId, driver{id,phone}) — COMPLETED-заказ компании A с привязанным водителем."""
    def _mk():
        o = order_factory.make("COMPLETED")
        return o["id"], order_factory.last_drivers[0]
    return _mk


@pytest.fixture
def fresh_company(dev_api, cfg, api_dev_roles):
    """Свежая shipper-компания (изоляция ЧС): admin + warehouse, умеет строить COMPLETED-заказы.
    Возвращает фабрику компаний; teardown удаляет компании (каскад записей/заказов)."""
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    carrier_tok = dev_api.token(cph, cpw, cct)
    companies = []

    class _Co:
        def __init__(self, cid, admin_tok, factory):
            self.id, self.admin, self._f = cid, admin_tok, factory

        def completed(self):
            o = self._f.make("COMPLETED")
            return o["id"], self._f.last_drivers[0]

    def _mk():
        aphone = "+99890" + _d(7)
        body = {"name": f"AT-BL-{_d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
                "tin": _d(9), "address": _ADDR, "admin": {"fullName": "AT BL Admin", "phone": aphone, "password": cfg.dev_account_password}}
        r = dev_api.request("POST", "/super-admin/shipper-companies", sa, json=body)
        assert r.status_code == 201, f"fresh company setup: {r.status_code} {r.text[:160]}"
        cid = r.json()["id"]
        companies.append(cid)
        adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
        whp = "+99890" + _d(7)
        dev_api.request("POST", "/shipper/staff", adm, json={"fullName": "AT BL Warehouse", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
        whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
        f = OrderFactory(dev_api, sa, whb, adm, carrier_tok)
        return _Co(cid, RoleClient(dev_api, adm), f)

    yield _mk
    for cid in reversed(companies):
        try:
            dev_api.request("DELETE", f"/super-admin/shipper-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


# ═══ POST blacklist — happy + доменные ошибки ════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_add_happy_126(s_admin, completed):
    """INT-126: add → 201, snapshot телефона+имени+причины; в аудит-логе ADDED."""
    oid, drv = completed()
    r = _add(s_admin, oid, drv["id"], reason="AT reason 126")
    assert r.status_code == 201, f"[API-INT-126] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("driverPhone") == drv["phone"], f"[API-INT-126] снимок телефона: {b.get('driverPhone')} != {drv['phone']}"
    assert b.get("driverFullName") and b.get("reason") == "AT reason 126" and b.get("sourceOrderId") == oid, f"[API-INT-126] тело: {b}"
    log = _content(s_admin.get("/shipper/blacklist/log"))
    assert any(x.get("action") == "ADDED" and x.get("driverPhone") == drv["phone"] for x in log), f"[API-INT-126] нет ADDED для {drv['phone']}"


@pytest.mark.high
@pytest.mark.tenancy
def test_add_foreign_order_127(s_admin, fresh_company):
    """INT-127: заказ чужой компании → 404 error.order.not-found."""
    co = fresh_company()
    oid, drv = co.completed()
    r = _add(s_admin, oid, drv["id"])
    assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-INT-127] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.negative
def test_add_not_completed_128(s_admin, order_factory):
    """INT-128: заказ не COMPLETED (SELECTED) → 409 error.order.not-completed (до проверки водителя)."""
    o = order_factory.make("SELECTED")
    r = _add(s_admin, o["id"], str(uuid.uuid4()))
    assert r.status_code == 409 and _code(r) == "error.order.not-completed", f"[API-INT-128] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_add_driver_not_attached_129(s_admin, completed, dev_api, cfg):
    """INT-129: существующий водитель, НЕ привязанный к заказу → 404 error.order.driver-not-attached."""
    oid, _ = completed()
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", sa).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    other = dev_api.request("POST", "/super-admin/drivers", sa,
                            json={"fullName": "AT Other", "phone": "+99890" + _d(7), "password": cfg.dev_account_password, "vehicleTypeId": vt})
    assert other.status_code == 201, f"[API-INT-129] driver setup: {other.status_code} {other.text[:120]}"
    try:
        r = _add(s_admin, oid, other.json()["id"])
        assert r.status_code == 404 and _code(r) == "error.order.driver-not-attached", f"[API-INT-129] {r.status_code}/{_code(r)}"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{other.json()['id']}", sa)


@pytest.mark.medium
@pytest.mark.negative
def test_add_driver_nonexistent_130(s_admin, completed):
    """INT-130: несуществующий driverId → 404 error.order.driver-not-attached.
    Уточнено по факту: проверка привязки (existsByOrderIdAndDriverId) срабатывает РАНЬШЕ lookup
    водителя, поэтому неизвестный id даёт driver-not-attached, а не driver.not-found (последний
    достижим лишь в orphan-состоянии attach-then-delete — чёрным ящиком не воспроизводится)."""
    oid, _ = completed()
    r = _add(s_admin, oid, str(uuid.uuid4()))
    assert r.status_code == 404 and _code(r) == "error.order.driver-not-attached", f"[API-INT-130] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.negative
def test_add_already_blacklisted_131(s_admin, completed):
    """INT-131: повторное добавление того же телефона → 409 error.driver.already-blacklisted."""
    oid, drv = completed()
    assert _add(s_admin, oid, drv["id"]).status_code == 201, "[API-INT-131] первое добавление"
    r = _add(s_admin, oid, drv["id"])
    assert r.status_code == 409 and _code(r) == "error.driver.already-blacklisted", f"[API-INT-131] {r.status_code}/{_code(r)}"


# ═══ POST blacklist — валидация ══════════════════════════════════════════════


@pytest.mark.medium
@pytest.mark.validation
def test_reason_too_short_132(s_admin, completed):
    """INT-132: reason 'ab' (< 3) → 400, поле reason в errors."""
    oid, drv = completed()
    r = _add(s_admin, oid, drv["id"], reason="ab")
    assert r.status_code == 400, f"[API-INT-132] {r.status_code}/{_code(r)}"
    assert "reason" in [e.get("field") for e in r.json().get("errors", [])], f"[API-INT-132] нет reason в errors: {r.json().get('errors')}"


@pytest.mark.low
@pytest.mark.boundary
def test_reason_too_long_133(s_admin, completed):
    """INT-133: reason из 501 символа (> 500) → 400."""
    oid, drv = completed()
    r = _add(s_admin, oid, drv["id"], reason="a" * 501)
    assert r.status_code == 400, f"[API-INT-133] {r.status_code}/{_code(r)}"
    assert "reason" in [e.get("field") for e in r.json().get("errors", [])], f"[API-INT-133] нет reason в errors"


@pytest.mark.medium
@pytest.mark.validation
def test_reason_null_134(s_admin, completed):
    """INT-134: reason отсутствует → 400 (обязательно, @NotNull)."""
    oid, drv = completed()
    r = _add(s_admin, oid, drv["id"], reason=_OMIT)
    assert r.status_code == 400, f"[API-INT-134] {r.status_code}/{_code(r)}"
    assert "reason" in [e.get("field") for e in r.json().get("errors", [])], f"[API-INT-134] нет reason в errors"


@pytest.mark.medium
@pytest.mark.validation
def test_driverid_null_135(s_admin, completed):
    """INT-135: driverId отсутствует → 400 (обязательно, @NotNull)."""
    oid, _ = completed()
    r = _add(s_admin, oid, _OMIT)
    assert r.status_code == 400, f"[API-INT-135] {r.status_code}/{_code(r)}"
    assert "driverId" in [e.get("field") for e in r.json().get("errors", [])], f"[API-INT-135] нет driverId в errors"


# ═══ RBAC / capability ═══════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.capability
def test_no_blacklist_cap_136(cap, completed):
    """INT-136: shipper-роль без capability BLACKLIST (OPERATOR) → 403 error.forbidden.
    BLACKLIST — admin-only-grantable; у OPERATOR по умолчанию её нет (отличие от ролевого FORBIDDEN)."""
    oid, drv = completed()
    op = cap("SHIPPER_OPERATOR")
    r = _add(op, oid, drv["id"])
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-INT-136] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_manager_granted_137(cap, completed):
    """INT-137: SHIPPER_MANAGER с персональным грантом BLACKLIST → 201."""
    oid, drv = completed()
    mgr = cap("SHIPPER_MANAGER", grants=["BLACKLIST"])
    r = _add(mgr, oid, drv["id"])
    assert r.status_code == 201, f"[API-INT-137] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.rbac
def test_transport_forbidden_138(api, completed):
    """INT-138: TRANSPORT_ADMIN → 403 FORBIDDEN (класс-гейт @PreAuthorize только для shipper-ролей)."""
    oid, drv = completed()
    r = _add(api("transport_admin"), oid, drv["id"])
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-138] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.idempotency
def test_reblacklist_after_delete_139(s_admin, completed):
    """INT-139: add → delete (soft) → add снова → 201 (телефон освобождён, ошибки «уже в ЧС» нет)."""
    oid, drv = completed()
    r1 = _add(s_admin, oid, drv["id"])
    assert r1.status_code == 201, "[API-INT-139] первое добавление"
    assert s_admin.delete(f"/shipper/blacklist/{r1.json()['id']}").status_code == 204, "[API-INT-139] удаление"
    r2 = _add(s_admin, oid, drv["id"])
    assert r2.status_code == 201, f"[API-INT-139] повторное добавление после soft-delete: {r2.status_code}/{_code(r2)}"


# ═══ GET /blacklist ══════════════════════════════════════════════════════════


@pytest.mark.high
def test_list_happy_140(s_admin, completed):
    """INT-140: список ЧС → 200, свои записи, добавленная присутствует."""
    oid, drv = completed()
    _add(s_admin, oid, drv["id"])
    rows = _content(s_admin.get("/shipper/blacklist?size=200"))
    assert isinstance(rows, list) and any(x.get("driverPhone") == drv["phone"] for x in rows), f"[API-INT-140] добавленная не в списке"


@pytest.mark.medium
def test_list_search_141(s_admin, completed):
    """INT-141: поиск по телефону → только записи с этой подстрокой."""
    oid, drv = completed()
    _add(s_admin, oid, drv["id"])
    frag = drv["phone"][-7:]
    rows = _content(s_admin.get(f"/shipper/blacklist?search={frag}&size=200"))
    assert rows and all(frag in (x.get("driverPhone", "") + x.get("driverFullName", "")) for x in rows), f"[API-INT-141] поиск вернул чужое: {rows[:1]}"


@pytest.mark.low
@pytest.mark.security
def test_list_search_escape_142(s_admin):
    """INT-142: подчёркивание в search трактуется буквально → 200, aXb не матчится по 'a_b'."""
    rows = _content(s_admin.get("/shipper/blacklist?search=a_b&size=50"))
    assert isinstance(rows, list), f"[API-INT-142] {rows}"
    assert all("a_b" in (x.get("driverPhone", "") + x.get("driverFullName", "")).lower() for x in rows) or rows == [], f"[API-INT-142] буквальный '_' нарушен: {rows[:1]}"


@pytest.mark.low
@pytest.mark.boundary
def test_list_date_range_143(s_admin):
    """INT-143: dateFrom/dateTo → 200 (границы суток по UTC)."""
    r = s_admin.get("/shipper/blacklist?dateFrom=2026-07-01&dateTo=2026-07-31")
    assert r.status_code == 200, f"[API-INT-143] {r.status_code}"


@pytest.mark.low
@pytest.mark.boundary
def test_list_empty_144(fresh_company):
    """INT-144: у свежей компании нет записей → 200, content=[]."""
    co = fresh_company()
    r = co.admin.get("/shipper/blacklist")
    assert r.status_code == 200 and _content(r) == [], f"[API-INT-144] {r.status_code} {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_list_tenancy_145(s_admin, fresh_company):
    """INT-145: записи чужой компании не видны в своём списке."""
    co = fresh_company()
    oid, drv = co.completed()
    assert _add(co.admin, oid, drv["id"]).status_code == 201, "[API-INT-145] запись компании B"
    rows = _content(s_admin.get("/shipper/blacklist?size=200"))
    assert not any(x.get("driverPhone") == drv["phone"] for x in rows), f"[API-INT-145] чужая запись видна в списке A"


# ═══ DELETE /blacklist/{id} ══════════════════════════════════════════════════


@pytest.mark.medium
def test_delete_happy_146(s_admin, completed):
    """INT-146: delete → 204; запись исчезает из списка, в логе REMOVED, телефон снова добавляем."""
    oid, drv = completed()
    eid = _add(s_admin, oid, drv["id"]).json()["id"]
    assert s_admin.delete(f"/shipper/blacklist/{eid}").status_code == 204, "[API-INT-146] удаление"
    rows = _content(s_admin.get("/shipper/blacklist?size=200"))
    assert not any(x.get("id") == eid for x in rows), "[API-INT-146] запись всё ещё в списке"
    log = _content(s_admin.get("/shipper/blacklist/log"))
    assert any(x.get("action") == "REMOVED" and x.get("driverPhone") == drv["phone"] for x in log), "[API-INT-146] нет REMOVED в логе"
    assert _add(s_admin, oid, drv["id"]).status_code == 201, "[API-INT-146] телефон должен снова добавляться"


@pytest.mark.high
@pytest.mark.tenancy
def test_delete_tenancy_147(s_admin, fresh_company):
    """INT-147: удаление чужой записи → 404 error.blacklist.not-found."""
    co = fresh_company()
    oid, drv = co.completed()
    eid = _add(co.admin, oid, drv["id"]).json()["id"]
    r = s_admin.delete(f"/shipper/blacklist/{eid}")
    assert r.status_code == 404 and _code(r) == "error.blacklist.not-found", f"[API-INT-147] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.negative
def test_delete_nonexistent_148(s_admin):
    """INT-148: удаление несуществующей записи → 404 error.blacklist.not-found."""
    r = s_admin.delete(f"/shipper/blacklist/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.blacklist.not-found", f"[API-INT-148] {r.status_code}/{_code(r)}"


# ═══ GET /blacklist/log ══════════════════════════════════════════════════════


@pytest.mark.medium
def test_log_happy_149(s_admin, completed):
    """INT-149: аудит-лог → 200, содержит ADDED и REMOVED по компании."""
    oid, drv = completed()
    eid = _add(s_admin, oid, drv["id"]).json()["id"]
    s_admin.delete(f"/shipper/blacklist/{eid}")
    log = _content(s_admin.get("/shipper/blacklist/log?size=200"))
    acts = {x.get("action") for x in log if x.get("driverPhone") == drv["phone"]}
    assert {"ADDED", "REMOVED"} <= acts, f"[API-INT-149] ожидали ADDED+REMOVED, получили {acts}"


@pytest.mark.medium
@pytest.mark.tenancy
def test_log_tenancy_150(s_admin, fresh_company):
    """INT-150: события чужой компании не попадают в свой аудит-лог."""
    co = fresh_company()
    oid, drv = co.completed()
    _add(co.admin, oid, drv["id"])
    log = _content(s_admin.get("/shipper/blacklist/log?size=200"))
    assert not any(x.get("driverPhone") == drv["phone"] for x in log), f"[API-INT-150] чужое событие в логе A"


@pytest.mark.low
@pytest.mark.rbac
def test_log_unauthenticated_151(dev_api):
    """INT-151: аудит-лог без токена → 401."""
    r = dev_api.request("GET", "/shipper/blacklist/log", None)
    assert r.status_code == 401, f"[API-INT-151] {r.status_code}"
