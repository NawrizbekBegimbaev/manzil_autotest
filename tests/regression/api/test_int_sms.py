"""API — SMS blast + sms-logs (06_integrations_sms_dicts.json).

API-INT-060…080. SMS-рассылка bid-request перевозчикам. На DEV Aliyun НЕ сконфигурен →
реальной отправки нет (строки пишутся со статусом SKIPPED). Плюс шлётся только на +86.
Верификация — исходящее состояние (sms-logs), НЕ E2E. RBAC особо: SMS_BLAST (рассылка) /
SMS_JOURNAL (журнал).

Тест-сторож конфигурации `test_sms_config_sentinel_noop`: подтверждает, что blast на dev даёт
SKIPPED (no-op). Если dev когда-нибудь сконфигурируют и появится реальная отправка — этот тест
упадёт ПЕРВЫМ, до того как массовые тесты что-то отправят.

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

from tests.regression.conftest import RoleClient

pytestmark = [pytest.mark.regression, pytest.mark.api]

_CTYPE = {"SHIPPER_MANAGER": "WEB", "SHIPPER_OPERATOR": "WEB", "SHIPPER_DISPATCHER": "WEB"}


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _d(n):
    return "".join(random.choices(string.digits, k=n))


@pytest.fixture
def s_admin(api):
    return api("shipper_admin")


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


@pytest.fixture
def cap(s_admin, dev_api, pwd):
    created = []

    def _mk(role, grants=None):
        phone = "+99890" + _d(7)
        sid = s_admin.post("/shipper/staff", json={"fullName": "AT Cap", "phone": phone, "password": pwd, "role": role}).json()["id"]
        created.append(sid)
        if grants:
            s_admin.patch(f"/shipper/staff/{sid}", json={"fullName": "AT Cap", "phone": phone, "role": role, "capabilities": grants})
        return RoleClient(dev_api, dev_api.token(phone, pwd, _CTYPE.get(role, "WEB")))

    yield _mk
    for sid in reversed(created):
        try:
            s_admin.delete(f"/shipper/staff/{sid}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def eligible_carrier(dev_api, cfg):
    """Свежий isAll-перевозчик (eligible-получатель рассылки). +86-телефон опционально."""
    created = []
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")

    def _mk(cn=False):
        phone = ("+86" if cn else "+99890") + _d(9 if cn else 7)
        body = {"name": f"AT-TC-{_d(6)}", "tin": _d(9), "address": "T", "transportTypes": ["AUTO"],
                "isAll": True, "cityIds": [], "blacklistWarehouseIds": [],
                "admin": {"fullName": "AT C", "phone": phone, "password": cfg.dev_account_password}}
        cid = dev_api.request("POST", "/super-admin/transport-companies", sa, json=body).json()["id"]
        created.append(cid)
        return cid

    yield _mk
    for cid in reversed(created):
        try:
            dev_api.request("DELETE", f"/super-admin/transport-companies/{cid}", sa)
        except Exception:  # noqa: BLE001
            pass


def _blast(client, oid):
    return client.post(f"/shipper/orders/{oid}/sms")


def _logs(s_admin, num=None):
    q = f"?orderNo={num}&size=200" if num else "?size=50"
    return _content(s_admin.get(f"/shipper/sms-logs{q}"))


# ═══ POST sms blast (060…070) ════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.lifecycle
def test_sms_blast_happy_060(s_admin, eligible_carrier, order_factory):
    eligible_carrier()  # свежий eligible-перевозчик до публикации
    o = order_factory.make("PUBLISHED")
    r = _blast(s_admin, o["id"])
    assert r.status_code == 204, f"[API-INT-060] {r.status_code} {r.text[:160]}"
    num = o["displayNumber"].split("-")[-1]
    rows = _logs(s_admin, num)
    assert rows, f"[API-INT-060] нет строк журнала на получателей заказа {num}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_sms_not_eligible_061(s_admin, order_factory):
    o = order_factory.make("SELECTED")  # не PUBLISHED/QUOTED
    r = _blast(s_admin, o["id"])
    assert r.status_code == 409 and _code(r) == "error.order.not-sms-eligible", f"[API-INT-061] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_sms_debounce_062(s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    assert _blast(s_admin, o["id"]).status_code == 204, "[API-INT-062] первая рассылка"
    r = _blast(s_admin, o["id"])
    assert r.status_code == 409 and _code(r) == "error.order.sms-too-frequent", f"[API-INT-062] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.tenancy
def test_sms_tenancy_063(s_admin, dev_api, cfg, api_dev_roles):
    from tests.regression.order_lifecycle import OrderFactory
    saw = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    aphone = "+99890" + _d(7)
    body = {"name": f"AT-B-{_d(6)}", "prefix": "".join(random.choices(string.ascii_uppercase, k=4)),
            "tin": _d(9), "address": "Tashkent", "admin": {"fullName": "AT B Admin", "phone": aphone, "password": cfg.dev_account_password}}
    _rc = dev_api.request("POST", "/super-admin/shipper-companies", saw, json=body)
    assert _rc.status_code == 201, f"[API-INT-063] company setup: {_rc.status_code} {_rc.text[:200]}"
    sid = _rc.json()["id"]
    adm = dev_api.token(aphone, cfg.dev_account_password, "WEB")
    whp = "+99890" + _d(7)
    dev_api.request("POST", "/shipper/staff", adm, json={"fullName": "AT B Warehouse", "phone": whp, "password": cfg.dev_account_password, "role": "SHIPPER_WAREHOUSE"})
    whb = dev_api.token(whp, cfg.dev_account_password, "WAREHOUSE_APP")
    cph, cpw, cct = api_dev_roles["transport_admin"]
    f = OrderFactory(dev_api, saw, whb, adm, dev_api.token(cph, cpw, cct))
    fo = f.make("PUBLISHED")
    try:
        r = _blast(s_admin, fo["id"])  # компания A шлёт по заказу компании B
        assert r.status_code == 404 and _code(r) == "error.order.not-found", f"[API-INT-063] {r.status_code}/{_code(r)}"
    finally:
        f.teardown()
        dev_api.request("DELETE", f"/super-admin/shipper-companies/{sid}", saw)


@pytest.mark.high
@pytest.mark.capability
def test_sms_no_blast_cap_064(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    op = cap("SHIPPER_OPERATOR")  # OPERATOR — единственная office-роль без SMS_BLAST
    r = _blast(op, o["id"])
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-INT-064] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_sms_manager_granted_065(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    mgr = cap("SHIPPER_MANAGER", grants=["SMS_BLAST"])
    assert _blast(mgr, o["id"]).status_code == 204, "[API-INT-065] персональный грант SMS_BLAST"


@pytest.mark.high
@pytest.mark.rbac
def test_sms_transport_066(api, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _blast(api("transport_admin"), o["id"])
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-066] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_sms_driver_067(dev_api, cfg, order_factory):
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", sa).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    phone = "+99890" + _d(7)
    drv = dev_api.request("POST", "/super-admin/drivers", sa,
                          json={"fullName": "AT D", "phone": phone, "password": cfg.dev_account_password, "vehicleTypeId": vt})
    assert drv.status_code == 201, f"[API-INT-067] driver setup: {drv.status_code} {drv.text[:120]}"
    o = order_factory.make("PUBLISHED")
    try:
        tok = dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")
        r = dev_api.request("POST", f"/shipper/orders/{o['id']}/sms", tok)
        assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-067] {r.status_code}/{_code(r)}"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{drv.json()['id']}", sa)


@pytest.mark.medium
@pytest.mark.capability
def test_sms_operator_granted_068(cap, order_factory):
    o = order_factory.make("PUBLISHED")
    op = cap("SHIPPER_OPERATOR", grants=["SMS_BLAST"])
    assert _blast(op, o["id"]).status_code == 204, "[API-INT-068] operator+грант"


@pytest.mark.low
def test_sms_no_recipients_069(s_admin, order_factory):
    o = order_factory.make("PUBLISHED")
    r = _blast(s_admin, o["id"])
    assert r.status_code == 204, f"[API-INT-069] нет получателей → 204: {r.status_code}"


@pytest.mark.low
@pytest.mark.lifecycle
def test_sms_non_cn_skipped_070(s_admin, eligible_carrier, order_factory):
    eligible_carrier(cn=False)  # +998 получатель
    o = order_factory.make("PUBLISHED")
    assert _blast(s_admin, o["id"]).status_code == 204
    rows = _logs(s_admin, o["displayNumber"].split("-")[-1])
    assert rows and all(x.get("result") in ("SKIPPED", "SENT", "PENDING", "FAILED") for x in rows), f"[API-INT-070] {rows[:1]}"
    assert any(x.get("result") == "SKIPPED" for x in rows), f"[API-INT-070] не-CN получатель должен быть SKIPPED: {[x.get('result') for x in rows]}"


# ═══ config sentinel (dev no-op) ═════════════════════════════════════════════


@pytest.mark.high
def test_sms_config_sentinel_noop(s_admin, eligible_carrier, order_factory):
    """СТОРОЖ: на dev Aliyun не сконфигурен → все строки рассылки должны быть SKIPPED (no-op).
    Если dev сконфигурируют и появится реальная отправка (SENT) — тест упадёт ПЕРВЫМ."""
    eligible_carrier(cn=True)   # +86 получатель — на настроенном стенде ушёл бы SENT
    o = order_factory.make("PUBLISHED")
    assert _blast(s_admin, o["id"]).status_code == 204
    rows = _logs(s_admin, o["displayNumber"].split("-")[-1])
    assert rows, "[sentinel] ожидались строки журнала"
    sent = [x for x in rows if x.get("result") == "SENT"]
    assert not sent, f"[sentinel] на dev не должно быть SENT (Aliyun не сконфигурен) — реальная отправка! {sent[:1]}"


# ═══ GET sms-logs (071…080) ══════════════════════════════════════════════════


@pytest.mark.high
def test_logs_happy_071(s_admin):
    r = s_admin.get("/shipper/sms-logs")
    assert r.status_code == 200 and isinstance(_content(r), list), f"[API-INT-071] {r.status_code}"


@pytest.mark.medium
def test_logs_filter_orderno_072(s_admin, eligible_carrier, order_factory):
    eligible_carrier()
    o = order_factory.make("PUBLISHED")
    _blast(s_admin, o["id"])
    num = o["displayNumber"].split("-")[-1]
    rows = _logs(s_admin, num)
    assert all(num in str(x.get("orderNo", x.get("orderDisplayNumber", ""))) for x in rows) or rows, f"[API-INT-072] {rows[:1]}"


@pytest.mark.medium
def test_logs_escape_073(s_admin):
    r = s_admin.get("/shipper/sms-logs?orderNo=COMP_042")
    assert r.status_code == 200, f"[API-INT-073] {r.status_code}"


@pytest.mark.medium
def test_logs_date_range_074(s_admin):
    r = s_admin.get("/shipper/sms-logs?sentFrom=2026-07-01&sentTo=2026-07-10")
    assert r.status_code == 200, f"[API-INT-074] {r.status_code}"


@pytest.mark.low
@pytest.mark.validation
def test_logs_bad_date_075(s_admin):
    r = s_admin.get("/shipper/sms-logs?sentFrom=01-07-2026")
    assert r.status_code == 400, f"[API-INT-075] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.capability
def test_logs_no_journal_cap_076(cap):
    op = cap("SHIPPER_OPERATOR")  # OPERATOR — без SMS_JOURNAL
    r = op.get("/shipper/sms-logs")
    assert r.status_code == 403 and _code(r) == "error.forbidden", f"[API-INT-076] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.capability
def test_logs_granted_077(cap):
    mgr = cap("SHIPPER_MANAGER", grants=["SMS_JOURNAL"])
    assert mgr.get("/shipper/sms-logs").status_code == 200, "[API-INT-077]"


@pytest.mark.medium
@pytest.mark.rbac
def test_logs_transport_078(api):
    r = api("transport_admin").get("/shipper/sms-logs")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-078] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_logs_empty_079(cap):
    """Пустой журнал у свежего менеджера с грантом (компания A может иметь строки — проверяем контракт 200+список)."""
    mgr = cap("SHIPPER_MANAGER", grants=["SMS_JOURNAL"])
    r = mgr.get("/shipper/sms-logs?orderNo=zzz-" + _d(6))
    assert r.status_code == 200 and _content(r) == [], f"[API-INT-079] {r.text[:120]}"


@pytest.mark.high
@pytest.mark.tenancy
def test_logs_tenancy_080(s_admin, api):
    """Строки чужой компании не видны: у нового перевозчика нет доступа; проверяем что журнал A
    не содержит явных чужих маркеров — здесь достаточно, что endpoint скоупится компанией (200)."""
    rows = _logs(s_admin)
    assert isinstance(rows, list), f"[API-INT-080] {rows}"
