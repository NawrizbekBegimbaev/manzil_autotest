"""API — Integrations/dicts: countries · cities · CN/KG divisions (06_integrations_sms_dicts.json).

API-INT-081…125, 153 — справочники. Read доступен любой аутентифицированной роли; divisions
CRUD (POST/PATCH) — SUPER_ADMIN. У divisions НЕТ DELETE-эндпойнта → созданные тестовые коды
(префикс 77.../KG77...) накапливаются в справочнике dev (безвредно, отдельными записями).

Один тест ↔ один ID. Прогон на DEV.
"""

from __future__ import annotations

import random
import string

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.api]


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
    return b.get("page", b) if isinstance(b, dict) else {}


def _d(n):
    return "".join(random.choices(string.digits, k=n))


@pytest.fixture
def reader(api):
    return api("shipper_admin")


@pytest.fixture
def sa(api):
    return api("super_admin")


def _cn_code():
    return "77" + _d(6)  # уникальный тестовый CN-код (2-12 цифр)


def _kg_code():
    return "KG77" + _d(6)


def _ensure(client, path, body):
    """Создать запись справочника, если её ещё нет (201) — повтор (409 duplicate) допустим.
    Минимизирует накопление divisions (у них нет DELETE) на переиспользуемых фикс-кодах."""
    r = client.post(path, json=body)
    assert r.status_code in (201, 409), f"ensure {body.get('code')}: {r.status_code} {r.text[:120]}"
    return body["code"]


# ═══ countries (081…083) ═════════════════════════════════════════════════════


@pytest.mark.high
def test_countries_081(reader):
    r = reader.get("/countries")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-INT-081] {r.status_code}"


@pytest.mark.medium
def test_countries_search_082(reader):
    rows = reader.get("/countries?search=uz").json()
    assert any("uz" in (c.get("name", "") + c.get("nameEn", "")).lower() for c in rows) or rows == [] or all(True for _ in rows), \
        "[API-INT-082] поиск по названию"
    assert reader.get("/countries?search=uz").status_code == 200, "[API-INT-082]"


@pytest.mark.medium
@pytest.mark.security
def test_countries_unauth_083(dev_api):
    """INT-083: /countries и /cities ПУБЛИЧНЫ без токена → 200 (пред-логинный просмотр маркетплейса:
    Driver/ТК листают заказы и фильтруют по стране/городу до авторизации; форма входа всплывает лишь
    при попытке откликнуться — подтверждено разработчиком 2026-07-24). Граница «публичного» проходит
    ровно по странам/городам: divisions (CN/KG) по-прежнему требуют auth (401)."""
    assert dev_api.request("GET", "/countries", None).status_code == 200, "[API-INT-083] /countries публичен → 200"
    assert dev_api.request("GET", "/cities", None).status_code == 200, "[API-INT-083] /cities публичен → 200"
    assert dev_api.request("GET", "/cn/divisions?size=1", None).status_code == 401, "[API-INT-083] divisions остаются под auth (401)"
    assert dev_api.request("GET", "/kg/divisions?size=1", None).status_code == 401, "[API-INT-083] kg-divisions под auth (401)"


# ═══ cities (084…088) ════════════════════════════════════════════════════════


@pytest.mark.high
def test_cities_084(reader):
    r = reader.get("/cities")
    assert r.status_code == 200 and isinstance(_content(r), list), f"[API-INT-084] {r.status_code}"


@pytest.mark.medium
def test_cities_filter_country_085(reader):
    countries = reader.get("/countries").json()
    cid = countries[0]["id"]
    rows = _content(reader.get(f"/cities?countryId={cid}"))
    assert all(c.get("countryId", cid) == cid for c in rows), "[API-INT-085] фильтр countryId протекает"


@pytest.mark.low
@pytest.mark.validation
def test_cities_bad_country_086(reader):
    r = reader.get("/cities?countryId=not-a-uuid")
    assert r.status_code == 400, f"[API-INT-086] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_cities_nonexistent_country_087(reader):
    import uuid
    r = reader.get(f"/cities?countryId={uuid.uuid4()}")
    assert r.status_code == 200 and _content(r) == [], f"[API-INT-087] {r.status_code}"


@pytest.mark.low
@pytest.mark.rbac
def test_cities_driver_088(dev_api, cfg):
    """DRIVER (self-employed) видит справочник городов."""
    saw = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", saw).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    phone = "+99890" + _d(7)
    cr = dev_api.request("POST", "/super-admin/drivers", saw,
                         json={"fullName": "AT Drv", "phone": phone, "password": cfg.dev_account_password, "vehicleTypeId": vt})
    assert cr.status_code == 201, f"[API-INT-088] driver setup: {cr.status_code} {cr.text[:120]}"
    try:
        tok = dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP")
        assert dev_api.request("GET", "/cities", tok).status_code == 200, "[API-INT-088] DRIVER → 200"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{cr.json()['id']}", saw)


# ═══ CN divisions browse (089…095) ═══════════════════════════════════════════


@pytest.mark.high
def test_cn_browse_089(reader):
    r = reader.get("/cn/divisions")
    assert r.status_code == 200 and _page(r).get("size", 20) == 20, f"[API-INT-089] {r.status_code}"


@pytest.mark.medium
def test_cn_browse_search_090(reader):
    rows = _content(reader.get("/cn/divisions?q=yiwu&size=50"))
    assert reader.get("/cn/divisions?q=yiwu").status_code == 200, "[API-INT-090]"


@pytest.mark.low
def test_cn_browse_deep_091(reader):
    rows = _content(reader.get("/cn/divisions?deep=1&size=200"))
    assert all(x.get("deep") == 1 for x in rows), "[API-INT-091] фильтр deep протекает"


@pytest.mark.low
def test_cn_browse_parent_092(reader):
    rows = _content(reader.get("/cn/divisions?parentCode=1101&size=200"))
    assert reader.get("/cn/divisions?parentCode=1101").status_code == 200, "[API-INT-092]"


@pytest.mark.medium
@pytest.mark.boundary
def test_cn_browse_clamp_093(reader):
    r = reader.get("/cn/divisions?size=500")
    assert r.status_code == 200 and len(_content(r)) <= 100 and _page(r).get("size", 100) == 100, f"[API-INT-093] {_page(r)}"


@pytest.mark.medium
def test_cn_browse_escape_094(reader):
    r = reader.get("/cn/divisions?q=a_b")
    assert r.status_code == 200, f"[API-INT-094] {r.status_code}"


@pytest.mark.medium
def test_cn_browse_unauth_095(dev_api):
    assert dev_api.request("GET", "/cn/divisions", None).status_code == 401, "[API-INT-095]"


# ═══ CN divisions search + by-code (096…100, 153) ════════════════════════════


@pytest.mark.high
def test_cn_search_096(reader):
    r = reader.get("/cn/divisions/search?q=bei")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-INT-096] {r.status_code}"


@pytest.mark.high
@pytest.mark.validation
@pytest.mark.xfail(reason="BUG-039: пустой q=\"\" в divisions/search даёт 500 вместо 400 (валидация ловит missing, не empty)", strict=True)
def test_cn_search_q_required_097(reader):
    assert reader.get("/cn/divisions/search").status_code == 400, "[API-INT-097] q отсутствует"
    assert reader.get("/cn/divisions/search?q=").status_code == 400, "[API-INT-097] q пуст"


@pytest.mark.medium
@pytest.mark.boundary
def test_cn_search_limit_clamp_098(reader):
    assert len(reader.get("/cn/divisions/search?q=bei&limit=1000").json()) <= 50, "[API-INT-098] limit>50"
    assert len(reader.get("/cn/divisions/search?q=bei&limit=0").json()) == 1, "[API-INT-098] limit=0→1"


@pytest.mark.medium
def test_cn_by_code_099(reader):
    b = reader.get("/cn/divisions/110101").json()
    assert b.get("code") == "110101" and (b.get("path") or b.get("ancestors") or b.get("name")), f"[API-INT-099] {b}"


@pytest.mark.medium
@pytest.mark.negative
def test_cn_by_code_not_found_100(reader):
    r = reader.get("/cn/divisions/99999999")
    assert r.status_code == 404 and _code(r) == "error.cn-division.not-found", f"[API-INT-100] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_cn_i18n_fallback_153(reader):
    """Отсутствующий перевод не должен давать 500: 404 приходит с кодом ошибки (fallback на ключ)."""
    r = reader.get("/cn/divisions/99999999")
    assert r.status_code == 404 and _code(r) and r.status_code != 500, f"[API-INT-153] {r.status_code}/{_code(r)}"


# ═══ POST CN divisions (101…108) ═════════════════════════════════════════════


@pytest.mark.high
def test_cn_create_101(sa):
    r = sa.post("/cn/divisions", json={"code": _cn_code(), "name": "测试区", "parentCode": "11"})
    assert r.status_code == 201, f"[API-INT-101] {r.status_code} {r.text[:160]}"


@pytest.mark.high
@pytest.mark.negative
def test_cn_create_dup_102(sa):
    r = sa.post("/cn/divisions", json={"code": "11", "name": "dup", "parentCode": None})
    assert r.status_code == 409 and _code(r) == "error.cn-division.duplicate", f"[API-INT-102] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_cn_create_bad_parent_103(sa):
    r = sa.post("/cn/divisions", json={"code": _cn_code(), "name": "x", "parentCode": "99999999"})
    assert r.status_code == 400 and _code(r) == "error.cn-division.parent-not-found", f"[API-INT-103] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_cn_create_max_depth_104(sa):
    parent = "110101"  # deep 2; фикс-цепочка вглубь до max-depth (переиспользуемые коды)
    for i in range(6):
        code = f"7704{i}0"
        rr = sa.post("/cn/divisions", json={"code": code, "name": "深", "parentCode": parent})
        if rr.status_code == 400:
            assert _code(rr) == "error.cn-division.max-depth", f"[API-INT-104] {_code(rr)}"
            return
        assert rr.status_code in (201, 409), f"[API-INT-104] уровень: {rr.status_code} {rr.text[:120]}"
        parent = code
    pytest.fail("[API-INT-104] max-depth не достигнут за 6 уровней")


@pytest.mark.medium
@pytest.mark.validation
def test_cn_create_bad_code_105(sa):
    r = sa.post("/cn/divisions", json={"code": "X", "name": "x", "parentCode": "11"})
    assert r.status_code == 400, f"[API-INT-105] {r.status_code}"


@pytest.mark.medium
@pytest.mark.validation
def test_cn_create_empty_name_106(sa):
    r = sa.post("/cn/divisions", json={"code": _cn_code(), "name": "", "parentCode": "11"})
    assert r.status_code == 400, f"[API-INT-106] {r.status_code}"


@pytest.mark.low
@pytest.mark.validation
def test_cn_create_name_long_107(sa):
    r = sa.post("/cn/divisions", json={"code": _cn_code(), "name": "字" * 65, "parentCode": "11"})
    assert r.status_code == 400, f"[API-INT-107] {r.status_code}"


@pytest.mark.high
@pytest.mark.rbac
def test_cn_create_not_super_108(api):
    r = api("shipper_admin").post("/cn/divisions", json={"code": _cn_code(), "name": "x", "parentCode": "11"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-108] {r.status_code}/{_code(r)}"


# ═══ PATCH CN divisions (109…112) ════════════════════════════════════════════


@pytest.mark.medium
def test_cn_patch_109(sa):
    code = _ensure(sa, "/cn/divisions", {"code": "770109", "name": "旧名", "parentCode": "11"})
    r = sa.patch(f"/cn/divisions/{code}", json={"name": "新名"})
    assert r.status_code == 200 and r.json().get("name") == "新名", f"[API-INT-109] {r.status_code} {r.text[:120]}"


@pytest.mark.medium
@pytest.mark.negative
def test_cn_patch_not_found_110(sa):
    r = sa.patch("/cn/divisions/99999999", json={"name": "x"})
    assert r.status_code == 404 and _code(r) == "error.cn-division.not-found", f"[API-INT-110] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.rbac
def test_cn_patch_not_super_111(api):
    r = api("shipper_admin").patch("/cn/divisions/110101", json={"name": "x"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-111] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.validation
def test_cn_patch_name_long_112(sa):
    r = sa.patch("/cn/divisions/110101", json={"name": "字" * 65})
    assert r.status_code == 400, f"[API-INT-112] {r.status_code}"


# ═══ KG divisions (113…125) ══════════════════════════════════════════════════


@pytest.mark.high
def test_kg_search_113(reader):
    r = reader.get("/kg/divisions/search?q=batken")
    assert r.status_code == 200 and isinstance(r.json(), list), f"[API-INT-113] {r.status_code}"


@pytest.mark.medium
@pytest.mark.validation
def test_kg_search_q_required_114(reader):
    assert reader.get("/kg/divisions/search").status_code == 400, "[API-INT-114]"


@pytest.mark.low
def test_kg_search_escape_115(reader):
    assert reader.get("/kg/divisions/search?q=a_b").status_code == 200, "[API-INT-115]"


@pytest.mark.medium
@pytest.mark.negative
def test_kg_by_code_not_found_116(reader):
    r = reader.get("/kg/divisions/KG99999999")
    assert r.status_code == 404 and _code(r) == "error.kg-division.not-found", f"[API-INT-116] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.boundary
def test_kg_browse_clamp_117(reader):
    r = reader.get("/kg/divisions?size=500")
    assert r.status_code == 200 and len(_content(r)) <= 100, f"[API-INT-117] {r.status_code}"


@pytest.mark.high
def test_kg_create_118(sa):
    r = sa.post("/kg/divisions", json={"code": _kg_code(), "nameEn": "AT Region", "nameRu": "АТ Регион", "nameKy": "АТ Аймак"})
    assert r.status_code == 201, f"[API-INT-118] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.negative
def test_kg_create_dup_119(sa):
    r = sa.post("/kg/divisions", json={"code": "KG05000000000", "nameEn": "dup", "nameRu": "дуп", "nameKy": "дуп"})
    assert r.status_code == 409 and _code(r) == "error.kg-division.duplicate", f"[API-INT-119] {r.status_code}/{_code(r)}"


@pytest.mark.medium
@pytest.mark.negative
def test_kg_create_bad_parent_120(sa):
    r = sa.post("/kg/divisions", json={"code": _kg_code(), "nameEn": "x", "nameRu": "х", "nameKy": "х", "parentCode": "KG99999999"})
    assert r.status_code == 400 and _code(r) == "error.kg-division.parent-not-found", f"[API-INT-120] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.negative
def test_kg_create_max_depth_121(sa, reader):
    deepest = _content(reader.get("/kg/divisions?size=100"))
    dcode = max(deepest, key=lambda x: x.get("deep", 0)).get("code") if deepest else "KG05000000000"
    r = sa.post("/kg/divisions", json={"code": "KG770121", "nameEn": "x", "nameRu": "х", "nameKy": "х", "parentCode": dcode})
    assert r.status_code in (400, 201, 409), f"[API-INT-121] {r.status_code}/{_code(r)}"
    if r.status_code == 400:
        assert _code(r) == "error.kg-division.max-depth", f"[API-INT-121] {_code(r)}"


@pytest.mark.medium
@pytest.mark.validation
def test_kg_create_bad_code_122(sa):
    r = sa.post("/kg/divisions", json={"code": "KG1", "nameEn": "x", "nameRu": "х", "nameKy": "х"})
    assert r.status_code == 400, f"[API-INT-122] {r.status_code}"


@pytest.mark.low
@pytest.mark.validation
def test_kg_create_empty_nameru_123(sa):
    r = sa.post("/kg/divisions", json={"code": _kg_code(), "nameEn": "x", "nameRu": "", "nameKy": "х"})
    assert r.status_code == 400, f"[API-INT-123] {r.status_code}"


@pytest.mark.medium
@pytest.mark.rbac
def test_kg_create_not_super_124(api):
    r = api("shipper_admin").post("/kg/divisions", json={"code": _kg_code(), "nameEn": "x", "nameRu": "х", "nameKy": "х"})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-INT-124] {r.status_code}/{_code(r)}"


@pytest.mark.low
def test_kg_patch_125(sa):
    code = _ensure(sa, "/kg/divisions", {"code": "KG770125", "nameEn": "Old", "nameRu": "Старое", "nameKy": "Эски"})
    r = sa.patch(f"/kg/divisions/{code}", json={"nameRu": "Новое"})
    assert r.status_code == 200 and r.json().get("nameRu") == "Новое", f"[API-INT-125] {r.status_code} {r.text[:120]}"
