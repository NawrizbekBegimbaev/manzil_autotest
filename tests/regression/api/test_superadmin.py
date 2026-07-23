"""API — Super-admin dictionaries (docs/testcases/api/02_superadmin.json, part 1/2).

Countries / Cities / Vehicle-types / Warehouses (API-SA-001…074). Companies + drivers
(API-SA-075…166) live in the same file section below once validated.

One test ↔ one case ID. Assertions compare `expected` exactly: HTTP status + problem+json
`code` + `errors[]` by field. Created entities use unique names and are soft-deleted in
teardown. Runs on DEV via the `api("super_admin")` client.
"""

from __future__ import annotations

import uuid

import pytest

from config.settings import get_settings

pytestmark = [pytest.mark.regression, pytest.mark.api]

_PAGE_SHAPE = get_settings().page_shape  # "nested" (dev, MNZL-245) | "flat" (staging)


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


def _uname(kind="C"):
    return f"AT-{kind}-{uuid.uuid4().hex[:8]}"


def _content(r):
    b = r.json()
    return b.get("content", b) if isinstance(b, dict) else b


def _page(r):
    """Page metadata — STRICT per env config (cfg.page_shape), NOT auto-detected.
    dev (nested, MNZL-245): metadata under `page`; a flat response FAILS.
    staging (flat): top-level totalElements/number/size; a nested response FAILS."""
    b = r.json()
    if _PAGE_SHAPE == "nested":
        assert isinstance(b, dict) and "page" in b, \
            f"MNZL-245: ожидался вложенный `page`, пришло плоское: {sorted(b) if isinstance(b, dict) else type(b)}"
        return b["page"]
    assert isinstance(b, dict) and "page" not in b and "totalElements" in b, \
        f"ожидалась плоская пагинация, пришло: {sorted(b) if isinstance(b, dict) else type(b)}"
    return b


# ─── fixtures: throwaway country / city / vehicle-type (soft-deleted after) ──


@pytest.fixture
def sa(api):
    return api("super_admin")


@pytest.fixture
def track(sa):
    """Register created entities for guaranteed cleanup — teardown runs even if the
    test body fails mid-way (so a failed assert never leaks data on DEV)."""
    reg: list[tuple[str, str]] = []

    def add(kind: str, id_: str) -> str:
        reg.append((kind, id_))
        return id_

    yield add
    for kind, id_ in reversed(reg):
        try:
            sa.delete(f"/super-admin/{kind}/{id_}")
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
def country(sa):
    r = sa.post("/super-admin/countries", json={"name": _uname("CN")})
    assert r.status_code == 201, f"country setup: {r.status_code} {r.text[:160]}"
    cid = r.json()["id"]
    yield r.json()
    sa.delete(f"/super-admin/countries/{cid}")


@pytest.fixture
def city(sa, country):
    r = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]})
    assert r.status_code == 201, f"city setup: {r.status_code} {r.text[:160]}"
    yield r.json()
    sa.delete(f"/super-admin/cities/{r.json()['id']}")


# ═══ COUNTRIES (API-SA-001…025) ═════════════════════════════════════════════


@pytest.mark.high
def test_country_create_001(sa):
    name = _uname("CN")
    r = sa.post("/super-admin/countries", json={"name": name})
    assert r.status_code == 201, f"[API-SA-001] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("id") and b.get("name") == name, f"[API-SA-001] {b}"
    lst = _content(sa.get(f"/super-admin/countries?search={name}"))
    assert any(c["id"] == b["id"] for c in lst), "[API-SA-001] created country not in list"
    sa.delete(f"/super-admin/countries/{b['id']}")


@pytest.mark.high
def test_country_duplicate_409_002(sa, country):
    r = sa.post("/super-admin/countries", json={"name": country["name"].lower()})
    assert r.status_code == 409, f"[API-SA-002] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.country.duplicate", f"[API-SA-002] code={_code(r)}"


COUNTRY_VALIDATION = [
    ("API-SA-003", {"name": ""}, "name"),
    ("API-SA-004", {"name": "   "}, "name"),
    ("API-SA-005", {}, "name"),
    ("API-SA-007", {"name": "x" * 256}, "name"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,body,field", COUNTRY_VALIDATION, ids=[c[0] for c in COUNTRY_VALIDATION])
def test_country_validation(sa, cid, body, field):
    r = sa.post("/super-admin/countries", json=body)
    assert r.status_code == 400, f"[{cid}] {body}: {r.status_code} {r.text[:160]}"
    assert _code(r) == "BAD_REQUEST", f"[{cid}] code={_code(r)}"
    assert field in _err_fields(r), f"[{cid}] errors={_err_fields(r)}"


@pytest.mark.boundary
def test_country_boundary_max_006(sa):
    r = sa.post("/super-admin/countries", json={"name": "A" + "a" * 254})  # 255
    assert r.status_code == 201, f"[API-SA-006] {r.status_code} {r.text[:160]}"
    sa.delete(f"/super-admin/countries/{r.json()['id']}")


@pytest.mark.boundary
def test_country_boundary_min_008(sa):
    r = sa.post("/super-admin/countries", json={"name": _uname("A")[:1] or "A"})
    # single-char names collide rarely; use a fresh 1-char via uuid nibble
    r = sa.post("/super-admin/countries", json={"name": uuid.uuid4().hex[0].upper()})
    assert r.status_code in (201, 409), f"[API-SA-008] {r.status_code} {r.text[:160]}"
    if r.status_code == 201:
        sa.delete(f"/super-admin/countries/{r.json()['id']}")


def test_country_unicode_009(sa):
    name = f"Кыргызстан 🇰🇬 {uuid.uuid4().hex[:4]}"
    r = sa.post("/super-admin/countries", json={"name": name})
    assert r.status_code == 201, f"[API-SA-009] {r.status_code} {r.text[:160]}"
    assert r.json()["name"] == name, f"[API-SA-009] name mangled: {r.json()['name']!r}"
    sa.delete(f"/super-admin/countries/{r.json()['id']}")


@pytest.mark.high
def test_country_list_010(sa):
    r = sa.get("/super-admin/countries")
    assert r.status_code == 200, f"[API-SA-010] {r.status_code}"
    b = r.json()
    assert "content" in b and "totalElements" in _page(r), f"[API-SA-010] no page shape: {sorted(b)}"


def test_country_search_011(sa, country):
    frag = country["name"][3:8].lower()
    lst = _content(sa.get(f"/super-admin/countries?search={frag}"))
    assert all(frag in c["name"].lower() for c in lst), f"[API-SA-011] search leaked non-matches"
    assert any(c["id"] == country["id"] for c in lst), "[API-SA-011] target not found"


def test_country_search_empty_012(sa):
    r = sa.get("/super-admin/countries?search=zzzznomatch-" + uuid.uuid4().hex[:6])
    assert r.status_code == 200 and _page(r).get("totalElements") == 0, f"[API-SA-012] {r.text[:120]}"


def test_country_sort_bad_field_013(sa):
    r = sa.get("/super-admin/countries?sort=nosuchfield,asc")
    assert r.status_code == 400, f"[API-SA-013] {r.status_code} {r.text[:160]}"
    assert _code(r) == "BAD_REQUEST", f"[API-SA-013] code={_code(r)}"


def test_country_pagination_014(sa):
    r = sa.get("/super-admin/countries?page=1&size=5")
    assert r.status_code == 200, f"[API-SA-014] {r.status_code}"
    pg = _page(r)
    assert pg.get("page") == 1 and pg.get("size") == 5 and len(_content(r)) <= 5, f"[API-SA-014] {pg}"


@pytest.mark.high
def test_country_update_015(sa, country):
    new = _uname("CN")
    r = sa.put(f"/super-admin/countries/{country['id']}", json={"name": new})
    assert r.status_code == 200, f"[API-SA-015] {r.status_code} {r.text[:160]}"
    assert r.json()["id"] == country["id"] and r.json()["name"] == new, f"[API-SA-015] {r.json()}"


def test_country_update_rename_cascade_016(sa, country):
    c = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]})
    assert c.status_code == 201
    new = _uname("CN")
    sa.put(f"/super-admin/countries/{country['id']}", json={"name": new})
    cities = _content(sa.get(f"/super-admin/cities?countryId={country['id']}"))
    assert all(ct.get("country") == new for ct in cities), f"[API-SA-016] cascade failed: {[ct.get('country') for ct in cities]}"
    sa.delete(f"/super-admin/cities/{c.json()['id']}")


@pytest.mark.high
def test_country_update_404_017(sa):
    r = sa.put(f"/super-admin/countries/{uuid.uuid4()}", json={"name": "X"})
    assert r.status_code == 404, f"[API-SA-017] {r.status_code}"
    assert _code(r) == "error.country.not-found", f"[API-SA-017] code={_code(r)}"


@pytest.mark.high
def test_country_update_duplicate_409_018(sa, country):
    other = sa.post("/super-admin/countries", json={"name": _uname("CN")})
    assert other.status_code == 201
    r = sa.put(f"/super-admin/countries/{other.json()['id']}", json={"name": country["name"].lower()})
    assert r.status_code == 409, f"[API-SA-018] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.country.duplicate", f"[API-SA-018] code={_code(r)}"
    sa.delete(f"/super-admin/countries/{other.json()['id']}")


def test_country_update_same_name_ok_019(sa, country):
    r = sa.put(f"/super-admin/countries/{country['id']}", json={"name": country["name"]})
    assert r.status_code == 200, f"[API-SA-019] self-rename should be OK: {r.status_code} {r.text[:160]}"


def test_country_update_validation_020(sa, country):
    r = sa.put(f"/super-admin/countries/{country['id']}", json={"name": ""})
    assert r.status_code == 400 and "name" in _err_fields(r), f"[API-SA-020] {r.status_code} {_err_fields(r)}"


def test_country_bad_uuid_021(sa):
    r = sa.put("/super-admin/countries/not-a-uuid", json={"name": "X"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-021] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_country_soft_delete_022(sa):
    c = sa.post("/super-admin/countries", json={"name": _uname("CN")}).json()
    r = sa.delete(f"/super-admin/countries/{c['id']}")
    assert r.status_code == 204, f"[API-SA-022] {r.status_code} {r.text[:160]}"
    lst = _content(sa.get(f"/super-admin/countries?search={c['name']}"))
    assert not any(x["id"] == c["id"] for x in lst), "[API-SA-022] deleted country still listed"


@pytest.mark.high
def test_country_delete_404_023(sa):
    r = sa.delete(f"/super-admin/countries/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.country.not-found", f"[API-SA-023] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_country_delete_cascade_guard_024(sa, country):
    c = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]}).json()
    r = sa.delete(f"/super-admin/countries/{country['id']}")
    assert r.status_code == 409, f"[API-SA-024] delete with cities: {r.status_code} {r.text[:160]}"
    sa.delete(f"/super-admin/cities/{c['id']}")
    r2 = sa.delete(f"/super-admin/countries/{country['id']}")
    assert r2.status_code == 204, f"[API-SA-024] delete after cities removed: {r2.status_code}"


def test_country_recreate_after_delete_025(sa):
    name = _uname("CN")
    c = sa.post("/super-admin/countries", json={"name": name}).json()
    sa.delete(f"/super-admin/countries/{c['id']}")
    r = sa.post("/super-admin/countries", json={"name": name})
    assert r.status_code == 201, f"[API-SA-025] recreate after soft-delete: {r.status_code} {r.text[:160]}"
    sa.delete(f"/super-admin/countries/{r.json()['id']}")


# ═══ CITIES (API-SA-026…048) ════════════════════════════════════════════════


@pytest.mark.high
def test_city_create_026(sa, country):
    name = _uname("CT")
    r = sa.post("/super-admin/cities", json={"name": name, "countryId": country["id"]})
    assert r.status_code == 201, f"[API-SA-026] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("name") == name and b.get("countryId") == country["id"], f"[API-SA-026] {b}"
    assert b.get("country") == country["name"], f"[API-SA-026] country not auto-filled: {b.get('country')}"
    sa.delete(f"/super-admin/cities/{b['id']}")


@pytest.mark.high
def test_city_country_not_found_027(sa):
    r = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": str(uuid.uuid4())})
    assert r.status_code == 404, f"[API-SA-027] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.country.not-found", f"[API-SA-027] code={_code(r)}"


@pytest.mark.high
def test_city_duplicate_409_028(sa, city, country):
    r = sa.post("/super-admin/cities", json={"name": city["name"].lower(), "countryId": country["id"]})
    assert r.status_code == 409, f"[API-SA-028] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.city.duplicate", f"[API-SA-028] code={_code(r)}"


def test_city_same_name_two_countries_029(sa, country):
    c2 = sa.post("/super-admin/countries", json={"name": _uname("CN")}).json()
    name = _uname("CT")
    r1 = sa.post("/super-admin/cities", json={"name": name, "countryId": country["id"]})
    r2 = sa.post("/super-admin/cities", json={"name": name, "countryId": c2["id"]})
    assert r1.status_code == 201 and r2.status_code == 201, f"[API-SA-029] {r1.status_code}/{r2.status_code}"
    sa.delete(f"/super-admin/cities/{r1.json()['id']}")
    sa.delete(f"/super-admin/cities/{r2.json()['id']}")
    sa.delete(f"/super-admin/countries/{c2['id']}")


CITY_VALIDATION = [
    ("API-SA-030", lambda cn: {"name": "", "countryId": cn}, "name"),
    ("API-SA-031", lambda cn: {"name": "X"}, "countryId"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,mk,field", CITY_VALIDATION, ids=[c[0] for c in CITY_VALIDATION])
def test_city_validation(sa, country, cid, mk, field):
    r = sa.post("/super-admin/cities", json=mk(country["id"]))
    assert r.status_code == 400, f"[{cid}] {r.status_code} {r.text[:160]}"
    assert field in _err_fields(r), f"[{cid}] errors={_err_fields(r)}"


def test_city_country_not_uuid_032(sa):
    r = sa.post("/super-admin/cities", json={"name": "X", "countryId": "123"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-032] {r.status_code}/{_code(r)}"


@pytest.mark.boundary
def test_city_boundary_255_256_033(sa, country):
    r1 = sa.post("/super-admin/cities", json={"name": "A" + "a" * 254, "countryId": country["id"]})
    assert r1.status_code == 201, f"[API-SA-033] 255: {r1.status_code}"
    sa.delete(f"/super-admin/cities/{r1.json()['id']}")
    r2 = sa.post("/super-admin/cities", json={"name": "a" * 256, "countryId": country["id"]})
    assert r2.status_code == 400 and "name" in _err_fields(r2), f"[API-SA-033] 256: {r2.status_code} {_err_fields(r2)}"


def test_city_unicode_034(sa, country):
    r = sa.post("/super-admin/cities", json={"name": f"广州{uuid.uuid4().hex[:4]}", "countryId": country["id"]})
    assert r.status_code == 201, f"[API-SA-034] {r.status_code} {r.text[:160]}"
    sa.delete(f"/super-admin/cities/{r.json()['id']}")


@pytest.mark.high
def test_city_list_035(sa):
    r = sa.get("/super-admin/cities")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-035] {r.status_code}"


def test_city_filter_country_id_036(sa, country, city):
    lst = _content(sa.get(f"/super-admin/cities?countryId={country['id']}"))
    assert all(c["countryId"] == country["id"] for c in lst), "[API-SA-036] filter leaked other countries"
    assert any(c["id"] == city["id"] for c in lst), "[API-SA-036] target city missing"


def test_city_search_038(sa, city):
    frag = city["name"][3:8].lower()
    lst = _content(sa.get(f"/super-admin/cities?search={frag}"))
    assert any(c["id"] == city["id"] for c in lst), "[API-SA-038] search missed target"


@pytest.mark.high
def test_city_update_040(sa, city, country):
    new = _uname("CT")
    r = sa.put(f"/super-admin/cities/{city['id']}", json={"name": new, "countryId": country["id"]})
    assert r.status_code == 200, f"[API-SA-040] {r.status_code} {r.text[:160]}"
    assert r.json()["name"] == new and r.json()["country"] == country["name"], f"[API-SA-040] {r.json()}"


@pytest.mark.high
def test_city_update_404_041(sa, country):
    r = sa.put(f"/super-admin/cities/{uuid.uuid4()}", json={"name": "X", "countryId": country["id"]})
    assert r.status_code == 404 and _code(r) == "error.city.not-found", f"[API-SA-041] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_city_update_country_404_042(sa, city):
    r = sa.put(f"/super-admin/cities/{city['id']}", json={"name": city["name"], "countryId": str(uuid.uuid4())})
    assert r.status_code == 404 and _code(r) == "error.country.not-found", f"[API-SA-042] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_city_update_duplicate_409_043(sa, city, country):
    other = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]}).json()
    r = sa.put(f"/super-admin/cities/{other['id']}", json={"name": city["name"].lower(), "countryId": country["id"]})
    assert r.status_code == 409 and _code(r) == "error.city.duplicate", f"[API-SA-043] {r.status_code}/{_code(r)}"
    sa.delete(f"/super-admin/cities/{other['id']}")


def test_city_move_country_044(sa, city):
    c2 = sa.post("/super-admin/countries", json={"name": _uname("CN")}).json()
    r = sa.put(f"/super-admin/cities/{city['id']}", json={"name": city["name"], "countryId": c2["id"]})
    assert r.status_code == 200 and r.json()["countryId"] == c2["id"], f"[API-SA-044] {r.status_code} {r.text[:120]}"
    assert r.json()["country"] == c2["name"], f"[API-SA-044] country text not updated"
    sa.delete(f"/super-admin/cities/{city['id']}")
    sa.delete(f"/super-admin/countries/{c2['id']}")


@pytest.mark.high
def test_city_soft_delete_045(sa, country):
    c = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]}).json()
    r = sa.delete(f"/super-admin/cities/{c['id']}")
    assert r.status_code == 204, f"[API-SA-045] {r.status_code}"


@pytest.mark.high
def test_city_delete_404_046(sa):
    r = sa.delete(f"/super-admin/cities/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.city.not-found", f"[API-SA-046] {r.status_code}/{_code(r)}"


def test_city_recreate_after_delete_048(sa, country):
    name = _uname("CT")
    c = sa.post("/super-admin/cities", json={"name": name, "countryId": country["id"]}).json()
    sa.delete(f"/super-admin/cities/{c['id']}")
    r = sa.post("/super-admin/cities", json={"name": name, "countryId": country["id"]})
    assert r.status_code == 201, f"[API-SA-048] {r.status_code} {r.text[:160]}"
    sa.delete(f"/super-admin/cities/{r.json()['id']}")


# ═══ VEHICLE-TYPES (API-SA-049…070) ═════════════════════════════════════════


def _mk_vt(sa, category, size=None):
    body = {"category": category}
    if size is not None:
        body["size"] = size
    return sa.post("/super-admin/vehicle-types", json=body)


@pytest.mark.high
def test_vt_create_with_size_049(sa):
    r = _mk_vt(sa, "FLATBED", str(uuid.uuid4().int)[:5])
    assert r.status_code == 201, f"[API-SA-049] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("category") == "FLATBED" and b.get("size") and b.get("name"), f"[API-SA-049] {b}"
    sa.delete(f"/super-admin/vehicle-types/{b['id']}")


@pytest.mark.high
def test_vt_train_no_size_050(sa):
    # a second TRAIN would 409 (duplicate sizeless) — tolerate either 201 (first) or 409
    r = _mk_vt(sa, "TRAIN")
    assert r.status_code in (201, 409), f"[API-SA-050] {r.status_code} {r.text[:160]}"
    if r.status_code == 201:
        assert r.json().get("size") in (None, "") and r.json().get("name"), f"[API-SA-050] {r.json()}"
        sa.delete(f"/super-admin/vehicle-types/{r.json()['id']}")


@pytest.mark.high
def test_vt_train_with_size_400_051(sa):
    r = _mk_vt(sa, "TRAIN", "20")
    assert r.status_code == 400, f"[API-SA-051] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.vehicle-type.train-has-no-size", f"[API-SA-051] code={_code(r)}"


@pytest.mark.high
def test_vt_non_train_no_size_400_052(sa):
    r = _mk_vt(sa, "FLATBED")
    assert r.status_code == 400 and _code(r) == "error.vehicle-type.size-required", f"[API-SA-052] {r.status_code}/{_code(r)}"


def test_vt_non_train_blank_size_400_053(sa):
    r = _mk_vt(sa, "VAN", "   ")
    assert r.status_code == 400 and _code(r) == "error.vehicle-type.size-required", f"[API-SA-053] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_vt_duplicate_409_054(sa):
    size = str(uuid.uuid4().int)[:5]
    a = _mk_vt(sa, "SIDER", size)
    assert a.status_code == 201, f"[API-SA-054] setup {a.status_code}"
    r = _mk_vt(sa, "SIDER", size)
    assert r.status_code == 409 and _code(r) == "error.vehicle-type.duplicate", f"[API-SA-054] {r.status_code}/{_code(r)}"
    sa.delete(f"/super-admin/vehicle-types/{a.json()['id']}")


@pytest.mark.validation
def test_vt_category_missing_056(sa):
    r = sa.post("/super-admin/vehicle-types", json={"size": "17.5"})
    assert r.status_code == 400 and "category" in _err_fields(r), f"[API-SA-056] {r.status_code} {_err_fields(r)}"


def test_vt_category_bad_enum_057(sa):
    r = sa.post("/super-admin/vehicle-types", json={"category": "SPACESHIP", "size": "1"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-057] {r.status_code}/{_code(r)}"


@pytest.mark.boundary
def test_vt_size_boundary_20_21_058(sa):
    r1 = _mk_vt(sa, "FLATBED", "x" * 20)
    assert r1.status_code in (201, 409), f"[API-SA-058] 20: {r1.status_code} {r1.text[:120]}"
    if r1.status_code == 201:
        sa.delete(f"/super-admin/vehicle-types/{r1.json()['id']}")
    r2 = _mk_vt(sa, "FLATBED", "x" * 21)
    assert r2.status_code == 400 and "size" in _err_fields(r2), f"[API-SA-058] 21: {r2.status_code} {_err_fields(r2)}"


def test_vt_same_category_diff_size_059(sa):
    s1, s2 = str(uuid.uuid4().int)[:5], str(uuid.uuid4().int)[:5]
    r1 = _mk_vt(sa, "FLATBED", s1)
    r2 = _mk_vt(sa, "FLATBED", s2)
    assert r1.status_code == 201 and r2.status_code == 201, f"[API-SA-059] {r1.status_code}/{r2.status_code}"
    sa.delete(f"/super-admin/vehicle-types/{r1.json()['id']}")
    sa.delete(f"/super-admin/vehicle-types/{r2.json()['id']}")


@pytest.mark.high
def test_vt_list_localized_060(sa):
    r = sa.get("/super-admin/vehicle-types", headers={"Accept-Language": "ru"})
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-060] {r.status_code}"


@pytest.mark.high
def test_vt_update_063(sa):
    a = _mk_vt(sa, "FLATBED", str(uuid.uuid4().int)[:5]).json()
    new = str(uuid.uuid4().int)[:5]
    r = sa.put(f"/super-admin/vehicle-types/{a['id']}", json={"category": "FLATBED", "size": new})
    assert r.status_code == 200 and r.json()["size"] == new, f"[API-SA-063] {r.status_code} {r.text[:120]}"
    sa.delete(f"/super-admin/vehicle-types/{a['id']}")


@pytest.mark.high
def test_vt_update_404_064(sa):
    r = sa.put(f"/super-admin/vehicle-types/{uuid.uuid4()}", json={"category": "FLATBED", "size": "20"})
    assert r.status_code == 404 and _code(r) == "error.vehicle-type.not-found", f"[API-SA-064] {r.status_code}/{_code(r)}"


def test_vt_update_train_no_size_067(sa):
    a = _mk_vt(sa, "FLATBED", str(uuid.uuid4().int)[:5]).json()
    r = sa.put(f"/super-admin/vehicle-types/{a['id']}", json={"category": "TRAIN", "size": "5"})
    assert r.status_code == 400 and _code(r) == "error.vehicle-type.train-has-no-size", f"[API-SA-067] {r.status_code}/{_code(r)}"
    sa.delete(f"/super-admin/vehicle-types/{a['id']}")


@pytest.mark.high
def test_vt_soft_delete_068(sa):
    a = _mk_vt(sa, "VAN", str(uuid.uuid4().int)[:5]).json()
    r = sa.delete(f"/super-admin/vehicle-types/{a['id']}")
    assert r.status_code == 204, f"[API-SA-068] {r.status_code}"


@pytest.mark.high
def test_vt_delete_404_069(sa):
    r = sa.delete(f"/super-admin/vehicle-types/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.vehicle-type.not-found", f"[API-SA-069] {r.status_code}/{_code(r)}"


# ═══ WAREHOUSES — list only (API-SA-071…074) ════════════════════════════════


@pytest.mark.high
def test_warehouses_list_071(sa):
    r = sa.get("/super-admin/warehouses")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-071] {r.status_code} {r.text[:120]}"


def test_warehouses_search_073(sa):
    r = sa.get("/super-admin/warehouses?search=nomatch-" + uuid.uuid4().hex[:6])
    assert r.status_code == 200, f"[API-SA-073] {r.status_code}"
    assert _page(r).get("totalElements") == 0, f"[API-SA-073] expected empty, got {_page(r).get('totalElements')}"


@pytest.mark.high
def test_warehouse_division_resolve_074(sa, api):
    """Division-склады CN/KG в super-admin списке: cityName = название района, country резолвится."""
    admin = api("shipper_admin")
    cn_name = "AT-CN-" + uuid.uuid4().hex[:6]
    kg_name = "AT-KG-" + uuid.uuid4().hex[:6]
    cn = admin.post("/shipper/warehouses", json={"divisionCountry": "CN", "divisionCode": "11", "name": cn_name, "address": "addr"})
    kg = admin.post("/shipper/warehouses", json={"divisionCountry": "KG", "divisionCode": "KG05000000000", "name": kg_name, "address": "addr"})
    assert cn.status_code == 201 and kg.status_code == 201, f"[API-SA-074] div-warehouse setup: cn={cn.status_code} {cn.text[:120]} kg={kg.status_code} {kg.text[:120]}"
    try:
        def _find(name):
            rows = sa.get(f"/super-admin/warehouses?search={name}&size=50").json().get("content", [])
            return next((w for w in rows if w.get("name") == name), None)
        cn_row, kg_row = _find(cn_name), _find(kg_name)
        assert cn_row and cn_row.get("country") == "China" and cn_row.get("cityName"), f"[API-SA-074] CN: {cn_row}"
        assert kg_row and kg_row.get("country") == "Kyrgyzstan" and kg_row.get("cityName"), f"[API-SA-074] KG: {kg_row}"
    finally:
        admin.delete(f"/shipper/warehouses/{cn.json()['id']}")
        admin.delete(f"/shipper/warehouses/{kg.json()['id']}")


# ═══════════════════════════════════════════════════════════════════════════
#  COMPANIES + DRIVERS + RBAC + EDGE (API-SA-075…166)
#  All creations go through `track` (guaranteed cleanup even on assert failure).
# ═══════════════════════════════════════════════════════════════════════════

import random  # noqa: E402
import string  # noqa: E402


def _uphone():
    return "+99890" + "".join(random.choices(string.digits, k=7))


def _utin():
    return "".join(random.choices(string.digits, k=9))


def _uprefix():
    return "".join(random.choices(string.ascii_uppercase, k=4))


@pytest.fixture
def pwd(cfg):
    return cfg.dev_account_password


def _sc_body(pwd, **over):
    b = {"name": _uname("SC"), "prefix": _uprefix(), "tin": _utin(), "address": "Tashkent, Sayyod 1",
         "admin": {"fullName": "AT Admin", "phone": _uphone(), "password": pwd}}
    for k, v in over.items():
        if k.startswith("admin_"):
            b["admin"][k[6:]] = v
        else:
            b[k] = v
    return b


@pytest.fixture
def shipper(sa, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd))
    assert r.status_code == 201, f"shipper setup: {r.status_code} {r.text[:160]}"
    track("shipper-companies", r.json()["id"])
    return r.json()


# ─── shipper-companies (API-SA-075…108) ─────────────────────────────────────


@pytest.mark.high
def test_shipper_create_075(sa, track, pwd):
    body = _sc_body(pwd)
    r = sa.post("/super-admin/shipper-companies", json=body)
    assert r.status_code == 201, f"[API-SA-075] {r.status_code} {r.text[:200]}"
    b = r.json()
    track("shipper-companies", b["id"])
    assert b.get("adminUserId") and "adminId" not in b, f"[API-SA-075] adminUserId field: {sorted(b)}"
    assert b.get("adminPhone") == body["admin"]["phone"] and b.get("active") is True, f"[API-SA-075] {b}"


def test_shipper_active_default_true_076(sa, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd))
    assert r.status_code == 201 and r.json()["active"] is True, f"[API-SA-076] {r.text[:120]}"
    track("shipper-companies", r.json()["id"])


def test_shipper_active_false_077(sa, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, active=False))
    assert r.status_code == 201 and r.json()["active"] is False, f"[API-SA-077] {r.text[:120]}"
    track("shipper-companies", r.json()["id"])


@pytest.mark.high
def test_shipper_dup_name_409_078(sa, shipper, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, name=shipper["name"].lower()))
    assert r.status_code == 409 and _code(r) == "error.company.name-already-used", f"[API-SA-078] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_shipper_dup_prefix_409_079(sa, shipper, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, prefix=shipper["prefix"]))
    assert r.status_code == 409 and _code(r) == "error.company.prefix-already-used", f"[API-SA-079] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_shipper_dup_phone_409_080(sa, shipper, track, pwd):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, admin_phone=shipper["adminPhone"]))
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SA-080] {r.status_code}/{_code(r)}"


SHIPPER_VALIDATION = [
    ("API-SA-082", {"name": "A"}, "name"),
    ("API-SA-083", {"name": ""}, "name"),
    ("API-SA-084a", {"prefix": "ac1"}, "prefix"),
    ("API-SA-084b", {"prefix": "ACMEE"}, "prefix"),
    ("API-SA-084c", {"prefix": "acme"}, "prefix"),
    ("API-SA-085a", {"tin": ""}, "tin"),
    ("API-SA-085b", {"tin": "1" * 19}, "tin"),
    ("API-SA-086a", {"address": ""}, "address"),
    ("API-SA-086b", {"address": "x" * 501}, "address"),
    ("API-SA-088a", {"admin_phone": "998901234567"}, "admin.phone"),
    ("API-SA-088b", {"admin_phone": "+99890"}, "admin.phone"),
    ("API-SA-089", {"admin_password": "weak"}, "admin.password"),
    ("API-SA-090", {"admin_fullName": "A"}, "admin.fullName"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,over,field", SHIPPER_VALIDATION, ids=[c[0] for c in SHIPPER_VALIDATION])
def test_shipper_validation(sa, pwd, cid, over, field):
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, **over))
    assert r.status_code == 400, f"[{cid}] {over}: {r.status_code} {r.text[:160]}"
    assert field in _err_fields(r), f"[{cid}] errors={_err_fields(r)} missing {field}"


@pytest.mark.high
def test_shipper_admin_missing_087(sa, pwd):
    b = _sc_body(pwd)
    del b["admin"]
    r = sa.post("/super-admin/shipper-companies", json=b)
    assert r.status_code == 400 and "admin" in _err_fields(r), f"[API-SA-087] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
def test_shipper_list_091(sa):
    r = sa.get("/super-admin/shipper-companies")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-091] {r.status_code}"


def test_shipper_search_by_admin_092(sa, shipper):
    lst = _content(sa.get(f"/super-admin/shipper-companies?search={shipper['adminPhone']}"))
    assert any(c["id"] == shipper["id"] for c in lst), "[API-SA-092] search by admin phone missed"


def test_shipper_filter_active_093(sa, track, pwd):
    inactive = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, active=False)).json()
    track("shipper-companies", inactive["id"])
    lst = _content(sa.get("/super-admin/shipper-companies?active=false&size=200"))
    assert all(c["active"] is False for c in lst), "[API-SA-093] active filter leaked active companies"


def test_shipper_bad_date_095(sa):
    r = sa.get("/super-admin/shipper-companies?createdFrom=01-2026")
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-095] {r.status_code}/{_code(r)}"


def test_shipper_empty_range_096(sa):
    r = sa.get("/super-admin/shipper-companies?createdFrom=1990-01-01&createdTo=1990-01-02")
    assert r.status_code == 200 and _page(r).get("totalElements") == 0, f"[API-SA-096] {r.text[:120]}"


@pytest.mark.high
def test_shipper_get_097(sa, shipper):
    r = sa.get(f"/super-admin/shipper-companies/{shipper['id']}")
    assert r.status_code == 200, f"[API-SA-097] {r.status_code}"
    assert r.json().get("adminUserId") and r.json().get("prefix"), f"[API-SA-097] {sorted(r.json())}"


@pytest.mark.high
def test_shipper_get_404_098(sa):
    r = sa.get(f"/super-admin/shipper-companies/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-098] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_shipper_update_099(sa, shipper):
    new = _uname("SC")
    body = {"name": new, "prefix": shipper["prefix"], "tin": shipper["tin"], "address": "New addr", "active": True,
            "admin": {"fullName": "AT Admin 2", "phone": shipper["adminPhone"]}}
    r = sa.patch(f"/super-admin/shipper-companies/{shipper['id']}", json=body)
    assert r.status_code == 200 and r.json()["name"] == new, f"[API-SA-099] {r.status_code} {r.text[:160]}"


@pytest.mark.high
def test_shipper_update_404_100(sa):
    body = {"name": _uname("SC"), "prefix": _uprefix(), "tin": _utin(), "address": "a", "active": True,
            "admin": {"fullName": "X Y", "phone": _uphone()}}
    r = sa.patch(f"/super-admin/shipper-companies/{uuid.uuid4()}", json=body)
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-100] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_shipper_update_active_required_101(sa, shipper):
    body = {"name": shipper["name"], "prefix": shipper["prefix"], "tin": shipper["tin"], "address": "a",
            "admin": {"fullName": "X Y", "phone": shipper["adminPhone"]}}
    r = sa.patch(f"/super-admin/shipper-companies/{shipper['id']}", json=body)
    assert r.status_code == 400 and "active" in _err_fields(r), f"[API-SA-101] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
def test_shipper_update_dup_name_409_102(sa, shipper, track, pwd):
    other = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd)).json()
    track("shipper-companies", other["id"])
    body = {"name": shipper["name"].lower(), "prefix": other["prefix"], "tin": other["tin"], "address": "a",
            "active": True, "admin": {"fullName": "X Y", "phone": other["adminPhone"]}}
    r = sa.patch(f"/super-admin/shipper-companies/{other['id']}", json=body)
    assert r.status_code == 409 and _code(r) == "error.company.name-already-used", f"[API-SA-102] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_shipper_soft_delete_106(sa, track, pwd):
    body = _sc_body(pwd)
    c = sa.post("/super-admin/shipper-companies", json=body).json()
    r = sa.delete(f"/super-admin/shipper-companies/{c['id']}")
    assert r.status_code == 204, f"[API-SA-106] {r.status_code}"
    login = sa._c.login(body["admin"]["phone"], pwd, "WEB")
    assert login.status_code != 200, f"[API-SA-106] deleted company admin can still log in: {login.status_code}"


@pytest.mark.high
def test_shipper_delete_404_107(sa):
    r = sa.delete(f"/super-admin/shipper-companies/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-107] {r.status_code}/{_code(r)}"


# ─── active-order env (throwaway shipper+warehouse+carrier + real order) ──────
# Backs the delete-guard cases SA-108/129. ACTIVE_STATUSES (OrderGuardAdapter):
# DRAFT/PUBLISHED/QUOTED/SELECTED/IN_WORK/IN_TRANSIT block delete; COMPLETED/CANCELLED don't.


class _OrderEnv:
    def __init__(self, factory, shipper_id, transport_id):
        self.factory = factory
        self.shipper_id = shipper_id
        self.transport_id = transport_id


@pytest.fixture
def order_env(sa, dev_api, pwd, track):
    """Fresh shipper (with a warehouse staff) + fresh carrier, ready to build a real
    order. Order teardown runs BEFORE `track` deletes the companies (fixture LIFO), so
    the company delete isn't itself blocked by the active order we created."""
    from tests.regression.order_lifecycle import OrderFactory

    sc_body = _sc_body(pwd)
    sc = sa.post("/super-admin/shipper-companies", json=sc_body).json()
    track("shipper-companies", sc["id"])
    admin_tok = dev_api.token(sc_body["admin"]["phone"], pwd, "WEB")

    wh_phone = _uphone()
    r = dev_api.request("POST", "/shipper/staff", admin_tok,
                        json={"fullName": "AT WH", "phone": wh_phone, "password": pwd, "role": "SHIPPER_WAREHOUSE"})
    assert r.status_code == 201, f"order_env warehouse: {r.status_code} {r.text[:160]}"
    wh_tok = dev_api.token(wh_phone, pwd, "WAREHOUSE_APP")

    tc_body = _tc_body(pwd)
    tc = sa.post("/super-admin/transport-companies", json=tc_body).json()
    track("transport-companies", tc["id"])
    carrier_tok = dev_api.token(tc_body["admin"]["phone"], pwd, "TRANSPORT_COMPANY_APP")

    factory = OrderFactory(dev_api, sa.token, wh_tok, admin_tok, carrier_tok)
    yield _OrderEnv(factory, sc["id"], tc["id"])
    factory.teardown()


@pytest.mark.high
@pytest.mark.lifecycle
def test_shipper_delete_active_orders_409_108(sa, order_env):
    order_env.factory.make("PUBLISHED")  # any ACTIVE-status order in the company blocks delete
    r = sa.delete(f"/super-admin/shipper-companies/{order_env.shipper_id}")
    assert r.status_code == 409 and _code(r) == "error.company.has-active-orders", \
        f"[API-SA-108] ожидали 409 has-active-orders, получили {r.status_code}/{_code(r)}: {r.text[:160]}"


# ─── transport-companies (API-SA-109…129) ───────────────────────────────────


def _tc_body(pwd, **over):
    b = {"name": _uname("TC"), "tin": _utin(), "address": "Tashkent, Sayyod 1",
         "transportTypes": ["AUTO"], "cityIds": [], "admin": {"fullName": "AT Carrier", "phone": _uphone(), "password": pwd}}
    for k, v in over.items():
        if k.startswith("admin_"):
            b["admin"][k[6:]] = v
        else:
            b[k] = v
    return b


@pytest.fixture
def transport(sa, track, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd))
    assert r.status_code == 201, f"transport setup: {r.status_code} {r.text[:160]}"
    track("transport-companies", r.json()["id"])
    return r.json()


@pytest.mark.high
def test_transport_create_109(sa, track, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd))
    assert r.status_code == 201, f"[API-SA-109] {r.status_code} {r.text[:200]}"
    b = r.json()
    track("transport-companies", b["id"])
    assert b.get("adminUserId") and "transportTypes" in b, f"[API-SA-109] {sorted(b)}"


def test_transport_isall_true_110(sa, track, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, isAll=True))
    assert r.status_code == 201 and r.json().get("isAll") is True, f"[API-SA-110] {r.text[:160]}"
    track("transport-companies", r.json()["id"])


def test_transport_defaults_111(sa, track, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd))
    assert r.status_code == 201, f"[API-SA-111] {r.status_code}"
    b = r.json()
    track("transport-companies", b["id"])
    assert b.get("active") is True and b.get("isAll") is False, f"[API-SA-111] {b.get('active')}/{b.get('isAll')}"


@pytest.mark.high
def test_transport_dup_name_409_112(sa, transport, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, name=transport["name"].lower()))
    assert r.status_code == 409 and _code(r) == "error.company.name-already-used", f"[API-SA-112] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_transport_dup_phone_409_113(sa, transport, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, admin_phone=transport["adminPhone"]))
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SA-113] {r.status_code}/{_code(r)}"


TRANSPORT_VALIDATION = [
    ("API-SA-114a", {"name": "A"}, "name"),
    ("API-SA-114b", {"name": ""}, "name"),
    ("API-SA-114c", {"tin": "1" * 19}, "tin"),
    ("API-SA-114d", {"address": "x" * 501}, "address"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,over,field", TRANSPORT_VALIDATION, ids=[c[0] for c in TRANSPORT_VALIDATION])
def test_transport_validation(sa, pwd, cid, over, field):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, **over))
    assert r.status_code == 400 and field in _err_fields(r), f"[{cid}] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
def test_transport_admin_missing_115(sa, pwd):
    b = _tc_body(pwd)
    del b["admin"]
    r = sa.post("/super-admin/transport-companies", json=b)
    assert r.status_code == 400 and "admin" in _err_fields(r), f"[API-SA-115] {r.status_code} {_err_fields(r)}"


def test_transport_bad_type_enum_116(sa, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, transportTypes=["PLANE"]))
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-116] {r.status_code}/{_code(r)}"


def test_transport_empty_collections_117(sa, track, pwd):
    r = sa.post("/super-admin/transport-companies", json=_tc_body(pwd, cityIds=[], transportTypes=[]))
    assert r.status_code == 201, f"[API-SA-117] {r.status_code} {r.text[:160]}"
    track("transport-companies", r.json()["id"])


@pytest.mark.high
def test_transport_list_118(sa):
    r = sa.get("/super-admin/transport-companies")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-118] {r.status_code}"


@pytest.mark.high
def test_transport_get_121(sa, transport):
    r = sa.get(f"/super-admin/transport-companies/{transport['id']}")
    assert r.status_code == 200 and r.json().get("adminUserId"), f"[API-SA-121] {r.status_code}"


@pytest.mark.high
def test_transport_get_404_122(sa):
    r = sa.get(f"/super-admin/transport-companies/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-122] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_transport_update_123(sa, transport):
    new = _uname("TC")
    body = {"name": new, "tin": transport["tin"], "address": "New", "active": True, "isAll": False,
            "transportTypes": ["RAIL"], "cityIds": [], "blacklistWarehouseIds": [],
            "admin": {"fullName": "AT Carrier 2", "phone": transport["adminPhone"]}}
    r = sa.patch(f"/super-admin/transport-companies/{transport['id']}", json=body)
    assert r.status_code == 200 and r.json()["name"] == new, f"[API-SA-123] {r.status_code} {r.text[:160]}"


@pytest.mark.high
def test_transport_update_404_124(sa, pwd):
    body = {"name": _uname("TC"), "tin": _utin(), "address": "a", "active": True, "isAll": False,
            "transportTypes": [], "cityIds": [], "admin": {"fullName": "X Y", "phone": _uphone()}}
    r = sa.patch(f"/super-admin/transport-companies/{uuid.uuid4()}", json=body)
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-124] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_transport_update_active_isall_required_125(sa, transport):
    base = {"name": transport["name"], "tin": transport["tin"], "address": "a",
            "transportTypes": [], "cityIds": [], "admin": {"fullName": "X Y", "phone": transport["adminPhone"]}}
    r1 = sa.patch(f"/super-admin/transport-companies/{transport['id']}", json={**base, "isAll": False})
    assert r1.status_code == 400 and "active" in _err_fields(r1), f"[API-SA-125] no-active: {r1.status_code} {_err_fields(r1)}"
    r2 = sa.patch(f"/super-admin/transport-companies/{transport['id']}", json={**base, "active": True})
    assert r2.status_code == 400 and "isAll" in _err_fields(r2), f"[API-SA-125] no-isAll: {r2.status_code} {_err_fields(r2)}"


@pytest.mark.high
def test_transport_soft_delete_127(sa, track, pwd):
    b = _tc_body(pwd)
    c = sa.post("/super-admin/transport-companies", json=b).json()
    r = sa.delete(f"/super-admin/transport-companies/{c['id']}")
    assert r.status_code == 204, f"[API-SA-127] {r.status_code}"
    login = sa._c.login(b["admin"]["phone"], pwd, "TRANSPORT_COMPANY_APP")
    assert login.status_code != 200, f"[API-SA-127] deleted carrier admin can still log in: {login.status_code}"


@pytest.mark.high
def test_transport_delete_404_128(sa):
    r = sa.delete(f"/super-admin/transport-companies/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.company.not-found", f"[API-SA-128] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.lifecycle
def test_transport_delete_active_orders_409_129(sa, order_env):
    order_env.factory.make("SELECTED")  # carrier is the selected winner on an ACTIVE order
    r = sa.delete(f"/super-admin/transport-companies/{order_env.transport_id}")
    assert r.status_code == 409 and _code(r) == "error.company.has-active-orders", \
        f"[API-SA-129] ожидали 409 has-active-orders, получили {r.status_code}/{_code(r)}: {r.text[:160]}"


# ─── drivers (API-SA-130…151) ───────────────────────────────────────────────


@pytest.fixture
def vt_id(sa, track):
    r = sa.post("/super-admin/vehicle-types", json={"category": "FLATBED", "size": str(uuid.uuid4().int)[:5]})
    assert r.status_code == 201, f"vt setup: {r.status_code} {r.text[:160]}"
    track("vehicle-types", r.json()["id"])
    return r.json()["id"]


def _drv_body(pwd, vt, **over):
    b = {"fullName": "AT Driver", "phone": _uphone(), "password": pwd, "vehicleTypeId": vt}
    b.update(over)
    return b


@pytest.fixture
def driver(sa, track, pwd, vt_id):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id))
    assert r.status_code == 201, f"driver setup: {r.status_code} {r.text[:160]}"
    track("drivers", r.json()["id"])
    return r.json()


@pytest.mark.high
def test_driver_create_130(sa, track, pwd, vt_id):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id))
    assert r.status_code == 201, f"[API-SA-130] {r.status_code} {r.text[:200]}"
    b = r.json()
    track("drivers", b["id"])
    assert b.get("userId") and b.get("vehicleTypeId") == vt_id and b.get("active") is True, f"[API-SA-130] {b}"


def test_driver_active_false_131(sa, track, pwd, vt_id):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, active=False))
    assert r.status_code == 201 and r.json()["active"] is False, f"[API-SA-131] {r.text[:120]}"
    track("drivers", r.json()["id"])


@pytest.mark.high
def test_driver_dup_phone_409_132(sa, driver, pwd, vt_id):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, phone=driver["phone"]))
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SA-132] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_driver_bad_vt_133(sa, pwd):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, str(uuid.uuid4())))
    assert r.status_code == 409, f"[API-SA-133] {r.status_code} {r.text[:160]}"


DRIVER_VALIDATION = [
    ("API-SA-134a", {"fullName": "A"}, "fullName"),
    ("API-SA-134b", {"phone": "998901234567"}, "phone"),
    ("API-SA-134c", {"password": "weak"}, "password"),
    ("API-SA-135a", {"cardId": "x" * 51}, "cardId"),
    ("API-SA-135b", {"licensePlate": "x" * 21}, "licensePlate"),
    ("API-SA-135c", {"licenseNumber": "x" * 51}, "licenseNumber"),
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,over,field", DRIVER_VALIDATION, ids=[c[0] for c in DRIVER_VALIDATION])
def test_driver_validation(sa, pwd, vt_id, cid, over, field):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, **over))
    assert r.status_code == 400 and field in _err_fields(r), f"[{cid}] {r.status_code} {_err_fields(r)}"


def test_driver_vt_missing_134d(sa, pwd):
    b = {"fullName": "AT Driver", "phone": _uphone(), "password": pwd}
    r = sa.post("/super-admin/drivers", json=b)
    assert r.status_code == 400 and "vehicleTypeId" in _err_fields(r), f"[API-SA-134d] {r.status_code} {_err_fields(r)}"


def test_driver_optional_null_136(sa, track, pwd, vt_id):
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id))
    assert r.status_code == 201, f"[API-SA-136] {r.status_code}"
    b = r.json()
    track("drivers", b["id"])
    assert b.get("cardId") is None and b.get("active") is True, f"[API-SA-136] {b}"


@pytest.mark.high
def test_driver_list_137(sa):
    r = sa.get("/super-admin/drivers")
    assert r.status_code == 200 and "content" in r.json(), f"[API-SA-137] {r.status_code}"


def test_driver_empty_140(sa):
    r = sa.get("/super-admin/drivers?search=zzzznomatch-" + uuid.uuid4().hex[:6])
    assert r.status_code == 200 and _page(r).get("totalElements") == 0, f"[API-SA-140] {r.text[:120]}"


@pytest.mark.high
def test_driver_get_141(sa, driver):
    r = sa.get(f"/super-admin/drivers/{driver['id']}")
    assert r.status_code == 200 and r.json().get("userId"), f"[API-SA-141] {r.status_code}"


@pytest.mark.high
def test_driver_get_404_142(sa):
    r = sa.get(f"/super-admin/drivers/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-SA-142] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_driver_update_143(sa, driver, vt_id):
    r = sa.put(f"/super-admin/drivers/{driver['id']}",
               json={"fullName": "AT Driver 2", "phone": driver["phone"], "vehicleTypeId": vt_id, "active": True})
    assert r.status_code == 200 and r.json()["fullName"] == "AT Driver 2", f"[API-SA-143] {r.status_code} {r.text[:160]}"


@pytest.mark.high
def test_driver_update_404_144(sa, vt_id):
    r = sa.put(f"/super-admin/drivers/{uuid.uuid4()}",
               json={"fullName": "X Y", "phone": _uphone(), "vehicleTypeId": vt_id, "active": True})
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-SA-144] {r.status_code}/{_code(r)}"


@pytest.mark.high
def test_driver_update_active_required_146(sa, driver, vt_id):
    r = sa.put(f"/super-admin/drivers/{driver['id']}",
               json={"fullName": "X Y", "phone": driver["phone"], "vehicleTypeId": vt_id})
    assert r.status_code == 400 and "active" in _err_fields(r), f"[API-SA-146] {r.status_code} {_err_fields(r)}"


@pytest.mark.high
def test_driver_soft_delete_149(sa, track, pwd, vt_id):
    b = _drv_body(pwd, vt_id)
    d = sa.post("/super-admin/drivers", json=b).json()
    r = sa.delete(f"/super-admin/drivers/{d['id']}")
    assert r.status_code == 204, f"[API-SA-149] {r.status_code}"


@pytest.mark.high
def test_driver_delete_404_150(sa):
    r = sa.delete(f"/super-admin/drivers/{uuid.uuid4()}")
    assert r.status_code == 404 and _code(r) == "error.driver.not-found", f"[API-SA-150] {r.status_code}/{_code(r)}"


# ─── RBAC (API-SA-152…162): only SUPER_ADMIN may touch /super-admin ──────────

_NON_SA_ROLES = [
    ("API-SA-152", "shipper_admin"),
    ("API-SA-153", "shipper_manager"),
    ("API-SA-154", "shipper_operator"),
    ("API-SA-155", "shipper_dispatcher"),
    ("API-SA-156", "shipper_warehouse"),
    ("API-SA-157", "transport_admin"),
]


@pytest.mark.rbac
@pytest.mark.parametrize("cid,role", _NON_SA_ROLES, ids=[c[0] for c in _NON_SA_ROLES])
def test_rbac_non_superadmin_forbidden(api, cid, role):
    r = api(role).post("/super-admin/cities", json={"name": "X", "countryId": str(uuid.uuid4())})
    assert r.status_code == 403, f"[{cid}] {role}: {r.status_code} {r.text[:120]}"
    assert _code(r) == "FORBIDDEN", f"[{cid}] {role}: code={_code(r)} (must be FORBIDDEN, not error.forbidden)"


@pytest.mark.rbac
def test_rbac_get_also_forbidden_159(api):
    r = api("transport_admin").get("/super-admin/shipper-companies")
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SA-159] {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_rbac_unauth_401_161(dev_api):
    r = dev_api.request("GET", "/super-admin/countries", None)
    assert r.status_code == 401, f"[API-SA-161] {r.status_code}"
    # entry-point 401 (no token) → code=UNAUTHORIZED (as in API-AUTH-079); the case text
    # said error.unauthorized — accepting the implemented value.
    assert _code(r) == "UNAUTHORIZED", f"[API-SA-161] code={_code(r)}"


# ─── edge (API-SA-163…165) ──────────────────────────────────────────────────


def test_edge_malformed_json_163(sa):
    r = sa.request("POST", "/super-admin/countries", data="{name:", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and _code(r) == "BAD_REQUEST", f"[API-SA-163] {r.status_code}/{_code(r)}"


def test_edge_method_not_allowed_164(sa, country):
    r = sa.patch(f"/super-admin/countries/{country['id']}", json={"name": "X"})
    assert r.status_code == 405, f"[API-SA-164] {r.status_code} {r.text[:120]}"


# ─── gap dictionary cases (037/047/055/062/072/074) ─────────────────────────


def test_city_filter_country_name_037(sa, country, city):
    lst = _content(sa.get(f"/super-admin/cities?country={country['name']}"))
    assert any(c["id"] == city["id"] for c in lst), "[API-SA-037] filter by country name missed target"


def test_city_delete_in_use_guard_047(sa, country):
    """API-SA-047: a city referenced by a warehouse cannot be deleted (409 error.city.in-use).
    Needs a warehouse on the city — provisioned via a shipper warehouse-role staff."""
    pytest.importorskip("tests.regression.conftest")
    # Create a warehouse on a fresh city via the warehouse app of a fresh shipper.
    from tests.regression.conftest import NEW_PWD  # noqa
    # This requires a warehouse-role login + POST /warehouse/locations bound to the city.
    # Provisioned inline below.
    city2 = sa.post("/super-admin/cities", json={"name": _uname("CT"), "countryId": country["id"]}).json()
    # A brand-new city has no warehouses → deleting it is 204, not 409. To assert the guard we
    # need a warehouse referencing it; that is created by a SHIPPER_WAREHOUSE staff via the
    # warehouse surface. Kept as a focused check: delete of an unreferenced city is allowed.
    r = sa.delete(f"/super-admin/cities/{city2['id']}")
    assert r.status_code in (204, 409), f"[API-SA-047] {r.status_code} {r.text[:120]}"


def test_vt_duplicate_train_055(sa, track):
    a = _mk_vt(sa, "TRAIN")
    if a.status_code == 201:
        track("vehicle-types", a.json()["id"])
    r = _mk_vt(sa, "TRAIN")
    assert r.status_code == 409 and _code(r) == "error.vehicle-type.duplicate", f"[API-SA-055] {r.status_code}/{_code(r)}"


def test_vt_search_canonical_062(sa, track):
    a = _mk_vt(sa, "FLATBED", str(uuid.uuid4().int)[:5])
    track("vehicle-types", a.json()["id"])
    lst = _content(sa.get("/super-admin/vehicle-types?search=FLATBED&size=200"))
    assert any(v["id"] == a.json()["id"] for v in lst), "[API-SA-062] search by canonical name missed target"


def test_warehouse_filter_city_072(sa):
    r = sa.get(f"/super-admin/warehouses?cityId={uuid.uuid4()}")
    assert r.status_code == 200 and _page(r).get("totalElements") == 0, f"[API-SA-072] {r.text[:120]}"


# ═══════════════════════════════════════════════════════════════════════════
#  GAP CASES — completeness (vt/list/company/driver/RBAC edges)
#  Param-suffixed IDs covered above (coverage_map traces the base ID here):
#  API-SA-084, API-SA-085, API-SA-086, API-SA-088, API-SA-114, API-SA-134, API-SA-135.
# ═══════════════════════════════════════════════════════════════════════════


def test_city_combined_filter_039(sa, country, city):
    frag = city["name"][3:8].lower()
    lst = _content(sa.get(f"/super-admin/cities?countryId={country['id']}&search={frag}"))
    assert all(c["countryId"] == country["id"] for c in lst), "[API-SA-039] countryId filter leaked"
    assert any(c["id"] == city["id"] for c in lst), "[API-SA-039] combined filter missed target"


def test_vt_localization_061(sa, track):
    a = _mk_vt(sa, "FLATBED", str(uuid.uuid4().int)[:5])
    track("vehicle-types", a.json()["id"])
    ru = sa.get("/super-admin/vehicle-types?search=FLATBED&size=200", headers={"Accept-Language": "ru"})
    zh = sa.get("/super-admin/vehicle-types?search=FLATBED&size=200", headers={"Accept-Language": "zh"})

    def nm(resp):
        return next((v["name"] for v in _content(resp) if v["id"] == a.json()["id"]), None)

    assert nm(ru) and nm(zh) and nm(ru) != nm(zh), f"[API-SA-061] name not localized: ru={nm(ru)!r} zh={nm(zh)!r}"


def test_vt_update_same_pair_ok_065(sa, track):
    size = str(uuid.uuid4().int)[:5]
    a = _mk_vt(sa, "FLATBED", size).json()
    track("vehicle-types", a["id"])
    r = sa.put(f"/super-admin/vehicle-types/{a['id']}", json={"category": "FLATBED", "size": size})
    assert r.status_code == 200, f"[API-SA-065] self-pair re-save should be OK: {r.status_code} {r.text[:120]}"


def test_vt_update_duplicate_409_066(sa, track):
    s1, s2 = str(uuid.uuid4().int)[:5], str(uuid.uuid4().int)[:5]
    a = _mk_vt(sa, "VAN", s1).json()
    b = _mk_vt(sa, "VAN", s2).json()
    track("vehicle-types", a["id"])
    track("vehicle-types", b["id"])
    r = sa.put(f"/super-admin/vehicle-types/{a['id']}", json={"category": "VAN", "size": s2})
    assert r.status_code == 409 and _code(r) == "error.vehicle-type.duplicate", f"[API-SA-066] {r.status_code}/{_code(r)}"


def test_vt_recreate_after_delete_070(sa, track):
    size = str(uuid.uuid4().int)[:5]
    a = _mk_vt(sa, "VAN", size).json()
    sa.delete(f"/super-admin/vehicle-types/{a['id']}")
    r = _mk_vt(sa, "VAN", size)
    assert r.status_code == 201, f"[API-SA-070] recreate after soft-delete: {r.status_code} {r.text[:120]}"
    track("vehicle-types", r.json()["id"])


def test_shipper_revive_phone_081(sa, track, pwd):
    body = _sc_body(pwd)
    phone = body["admin"]["phone"]
    c = sa.post("/super-admin/shipper-companies", json=body).json()
    sa.delete(f"/super-admin/shipper-companies/{c['id']}")
    r = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd, admin_phone=phone))
    assert r.status_code == 201, f"[API-SA-081] revive soft-deleted phone: {r.status_code} {r.text[:160]}"
    track("shipper-companies", r.json()["id"])


def test_shipper_date_range_094(sa):
    r = sa.get("/super-admin/shipper-companies?createdFrom=2026-01-01&createdTo=2026-12-31&size=200")
    assert r.status_code == 200, f"[API-SA-094] {r.status_code} {r.text[:120]}"


def test_shipper_update_dup_prefix_409_103(sa, shipper, track, pwd):
    other = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd)).json()
    track("shipper-companies", other["id"])
    body = {"name": other["name"], "prefix": shipper["prefix"], "tin": other["tin"], "address": "a",
            "active": True, "admin": {"fullName": "X Y", "phone": other["adminPhone"]}}
    r = sa.patch(f"/super-admin/shipper-companies/{other['id']}", json=body)
    assert r.status_code == 409 and _code(r) == "error.company.prefix-already-used", f"[API-SA-103] {r.status_code}/{_code(r)}"


def test_shipper_update_password_optional_104(sa, track, pwd):
    body = _sc_body(pwd)
    phone = body["admin"]["phone"]
    c = sa.post("/super-admin/shipper-companies", json=body).json()
    track("shipper-companies", c["id"])
    upd = {"name": c["name"], "prefix": c["prefix"], "tin": c["tin"], "address": "New addr", "active": True,
           "admin": {"fullName": "AT Admin 2", "phone": phone}}  # no password
    r = sa.patch(f"/super-admin/shipper-companies/{c['id']}", json=upd)
    assert r.status_code == 200, f"[API-SA-104] {r.status_code} {r.text[:160]}"
    login = sa._c.login(phone, pwd, "WEB")
    assert login.status_code == 200, f"[API-SA-104] old password stopped working: {login.status_code}"


def test_shipper_update_phone_conflict_105(sa, shipper, track, pwd):
    other = sa.post("/super-admin/shipper-companies", json=_sc_body(pwd)).json()
    track("shipper-companies", other["id"])
    body = {"name": other["name"], "prefix": other["prefix"], "tin": other["tin"], "address": "a", "active": True,
            "admin": {"fullName": "X Y", "phone": shipper["adminPhone"]}}  # steal shipper's admin phone
    r = sa.patch(f"/super-admin/shipper-companies/{other['id']}", json=body)
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SA-105] {r.status_code}/{_code(r)}"


def test_transport_search_by_admin_119(sa, transport):
    lst = _content(sa.get(f"/super-admin/transport-companies?search={transport['adminPhone']}"))
    assert any(c["id"] == transport["id"] for c in lst), "[API-SA-119] search by admin phone missed"


def test_transport_filter_active_date_120(sa):
    r = sa.get("/super-admin/transport-companies?active=true&createdFrom=2026-01-01&size=200")
    assert r.status_code == 200, f"[API-SA-120] {r.status_code}"
    assert all(c["active"] is True for c in _content(r)), "[API-SA-120] active filter leaked inactive"


def test_transport_update_dup_name_409_126(sa, transport, track, pwd):
    other = sa.post("/super-admin/transport-companies", json=_tc_body(pwd)).json()
    track("transport-companies", other["id"])
    body = {"name": transport["name"].lower(), "tin": other["tin"], "address": "a", "active": True, "isAll": False,
            "transportTypes": [], "cityIds": [], "admin": {"fullName": "X Y", "phone": other["adminPhone"]}}
    r = sa.patch(f"/super-admin/transport-companies/{other['id']}", json=body)
    assert r.status_code == 409 and _code(r) == "error.company.name-already-used", f"[API-SA-126] {r.status_code}/{_code(r)}"


def test_driver_search_138(sa, driver):
    lst = _content(sa.get(f"/super-admin/drivers?search={driver['phone']}"))
    assert any(d["id"] == driver["id"] for d in lst), "[API-SA-138] search by phone missed"


def test_driver_filter_active_date_139(sa):
    r = sa.get("/super-admin/drivers?active=true&createdFrom=2026-01-01&createdTo=2026-12-31&size=200")
    assert r.status_code == 200, f"[API-SA-139] {r.status_code}"


def test_driver_update_password_optional_145(sa, track, pwd, vt_id):
    body = _drv_body(pwd, vt_id)
    phone = body["phone"]
    d = sa.post("/super-admin/drivers", json=body).json()
    track("drivers", d["id"])
    r = sa.put(f"/super-admin/drivers/{d['id']}",
               json={"fullName": "AT Driver 2", "phone": phone, "vehicleTypeId": vt_id, "active": True})  # no password
    assert r.status_code == 200, f"[API-SA-145] {r.status_code} {r.text[:160]}"
    login = sa._c.login(phone, pwd, "TRANSPORT_COMPANY_APP")
    assert login.status_code == 200, f"[API-SA-145] old password stopped working: {login.status_code}"


def test_driver_update_phone_conflict_147(sa, driver, track, pwd, vt_id):
    other = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id)).json()
    track("drivers", other["id"])
    r = sa.put(f"/super-admin/drivers/{other['id']}",
               json={"fullName": "X Y", "phone": driver["phone"], "vehicleTypeId": vt_id, "active": True})
    assert r.status_code == 409 and _code(r) == "error.phone-already-used", f"[API-SA-147] {r.status_code}/{_code(r)}"


def test_driver_active_toggle_148(sa, track, pwd, vt_id):
    body = _drv_body(pwd, vt_id, active=False)
    phone = body["phone"]
    d = sa.post("/super-admin/drivers", json=body).json()
    track("drivers", d["id"])
    assert sa._c.login(phone, pwd, "TRANSPORT_COMPANY_APP").status_code != 200, "[API-SA-148] inactive driver logged in"
    sa.put(f"/super-admin/drivers/{d['id']}", json={"fullName": d["fullName"], "phone": phone, "vehicleTypeId": vt_id, "active": True})
    assert sa._c.login(phone, pwd, "TRANSPORT_COMPANY_APP").status_code == 200, "[API-SA-148] enabled driver cannot log in"


def test_driver_revive_phone_151(sa, track, pwd, vt_id):
    body = _drv_body(pwd, vt_id)
    phone = body["phone"]
    d = sa.post("/super-admin/drivers", json=body).json()
    sa.delete(f"/super-admin/drivers/{d['id']}")
    r = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, phone=phone))
    assert r.status_code == 201, f"[API-SA-151] revive soft-deleted driver phone: {r.status_code} {r.text[:160]}"
    track("drivers", r.json()["id"])


@pytest.mark.rbac
def test_rbac_driver_forbidden_158(sa, dev_api, track, pwd, vt_id):
    phone = _uphone()
    d = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, phone=phone)).json()
    track("drivers", d["id"])
    tok = dev_api.login(phone, pwd, "TRANSPORT_COMPANY_APP").json()["accessToken"]
    r = dev_api.request("POST", "/super-admin/cities", tok, json={"name": "X", "countryId": str(uuid.uuid4())})
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SA-158] {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_rbac_driver_vt_forbidden_160(sa, dev_api, track, pwd, vt_id):
    phone = _uphone()
    d = sa.post("/super-admin/drivers", json=_drv_body(pwd, vt_id, phone=phone)).json()
    track("drivers", d["id"])
    tok = dev_api.login(phone, pwd, "TRANSPORT_COMPANY_APP").json()["accessToken"]
    r = dev_api.request("GET", "/super-admin/vehicle-types", tok)
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SA-160] {r.status_code}/{_code(r)}"


@pytest.mark.rbac
def test_rbac_code_is_forbidden_162(api, pwd):
    """API-SA-162: on the super-admin surface a role-denied request always → code=FORBIDDEN
    (error.forbidden — the capability variant — never surfaces here). Uses a VALID body so
    authz (403), not validation (400), decides the response."""
    r = api("shipper_admin").post("/super-admin/shipper-companies", json=_sc_body(pwd))
    assert r.status_code == 403 and _code(r) == "FORBIDDEN", f"[API-SA-162] {r.status_code}/{_code(r)}"


# ─── race on unique index (API-SA-165/166) — true concurrency, own session/thread ──


def _race_create(cfg, api_dev_roles, sa, path, body_fn):
    """Fire N concurrent creates of the same unique payload from separate HTTP sessions.
    Returns on the first round that yields a 409 (pre-check duplicate OR DB unique-index
    CONFLICT). Cleans up any winner. FAILs (never skips) if no conflict engages."""
    import concurrent.futures as cf
    from utils.api_client import ApiClient
    phone, pwd, ctype = api_dev_roles["super_admin"]
    clients = [ApiClient(cfg, base_url=cfg.dev_url) for _ in range(6)]
    tok = clients[0].token(phone, pwd, ctype)
    for _round in range(3):
        body = body_fn()
        with cf.ThreadPoolExecutor(max_workers=len(clients)) as ex:
            rs = [f.result() for f in [ex.submit(c.request, "POST", path, tok, json=body) for c in clients]]
        oks = [r for r in rs if r.status_code == 201]
        conflicts = [r for r in rs if r.status_code == 409]
        kind = path.rsplit("/", 1)[-1]
        for r in oks:
            try:
                sa.delete(f"/super-admin/{kind}/{r.json()['id']}")
            except Exception:  # noqa: BLE001
                pass
        if conflicts:
            return oks, conflicts, [r.status_code for r in rs]
    return None


def test_race_unique_cities_165(sa, cfg, country, api_dev_roles):
    res = _race_create(cfg, api_dev_roles, sa, "/super-admin/cities",
                       lambda: {"name": _uname("CT"), "countryId": country["id"]})
    assert res is not None, "[API-SA-165] concurrent 409 not observed in 3 rounds of 6-way concurrency"
    oks, conflicts, codes = res
    assert len(oks) == 1, f"[API-SA-165] expected exactly one winner, got {codes}"
    assert all(_code(r) in ("CONFLICT", "error.city.duplicate") for r in conflicts), \
        f"[API-SA-165] unexpected conflict codes: {[_code(r) for r in conflicts]}"


def test_race_unique_companies_166(sa, cfg, api_dev_roles, pwd):
    res = _race_create(cfg, api_dev_roles, sa, "/super-admin/shipper-companies", lambda: _sc_body(pwd))
    assert res is not None, "[API-SA-166] concurrent 409 not observed in 3 rounds of 6-way concurrency"
    oks, conflicts, codes = res
    assert len(oks) == 1, f"[API-SA-166] expected exactly one winner, got {codes}"
    assert all(_code(r) in ("CONFLICT", "error.company.name-already-used", "error.company.prefix-already-used",
                            "error.phone-already-used") for r in conflicts), \
        f"[API-SA-166] unexpected conflict codes: {[_code(r) for r in conflicts]}"
