"""UAT — backend API: аутентификация, /me и RBAC-гейты.

Первый инкремент API-набора (источник: docs/testcases/api/01_auth_me_devices.json,
07_rbac_capabilities.json). Система-под-тестом — сам API; клиент (``api``) не бросает
на 4xx, ассертит тест. Роли берутся из свежесозданного tenant'а (``api_roles``), так
что чистка автоматическая (удаление компаний в teardown ``provisioned``).

Ответы-ошибки — application/problem+json с полем ``code``. Локализованный ``detail``
НЕ проверяем: staging отвечает по-китайски (China-first), стабильный ключ — ``code``.
"""

from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.uat, pytest.mark.api]

FORBIDDEN_CODES = {"FORBIDDEN", "error.forbidden"}


def _code(resp) -> str:
    try:
        return (resp.json() or {}).get("code", "")
    except ValueError:
        return ""


# ─────────────────────────── Логин: позитив (роль × приложение) ──────────────
@allure.title("API-AUTH-001 Логин SUPER_ADMIN через WEB")
def test_api_auth_001_login_super_admin(api, api_roles):
    r = api.login(*api_roles["super_admin"])
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body.get("accessToken") and body.get("refreshToken")


@allure.title("API-AUTH-002 Логин SHIPPER_ADMIN через WEB")
def test_api_auth_002_login_shipper_admin(api, api_roles):
    r = api.login(*api_roles["shipper_admin"])
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("accessToken")


@allure.title("API-AUTH-003 Логин SHIPPER_MANAGER через WEB")
def test_api_auth_003_login_shipper_manager(api, api_roles):
    r = api.login(*api_roles["shipper_manager"])
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("accessToken")


@allure.title("API-AUTH-007 Логин TRANSPORT_ADMIN через TRANSPORT_COMPANY_APP")
def test_api_auth_007_login_transport_admin(api, api_roles):
    r = api.login(*api_roles["transport_admin"])
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("accessToken")


@allure.title("API-AUTH-008 Логин SHIPPER_WAREHOUSE через WAREHOUSE_APP")
def test_api_auth_008_login_warehouse(api, api_roles):
    r = api.login(*api_roles["shipper_warehouse"])
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("accessToken")


# ─────────────────────────── Логин: негатив ──────────────────────────────────
@allure.title("API-AUTH-009 Wrong-app: SHIPPER_WAREHOUSE через WEB → 403")
def test_api_auth_009_warehouse_wrong_app(api, api_roles):
    phone, pwd, _ = api_roles["shipper_warehouse"]
    r = api.login(phone, pwd, "WEB")
    assert r.status_code == 403, r.text[:200]
    assert _code(r) == "error.wrong-app"


@allure.title("API-AUTH-014 Wrong-app: TRANSPORT_ADMIN через WAREHOUSE_APP → 403")
def test_api_auth_014_transport_wrong_app(api, api_roles):
    phone, pwd, _ = api_roles["transport_admin"]
    r = api.login(phone, pwd, "WAREHOUSE_APP")
    assert r.status_code == 403, r.text[:200]
    assert _code(r) == "error.wrong-app"


@allure.title("API-AUTH-015 Wrong-app: SUPER_ADMIN через WAREHOUSE_APP → 403")
def test_api_auth_015_super_admin_wrong_app(api, api_roles):
    phone, pwd, _ = api_roles["super_admin"]
    r = api.login(phone, pwd, "WAREHOUSE_APP")
    assert r.status_code == 403, r.text[:200]
    assert _code(r) == "error.wrong-app"


@allure.title("API-AUTH-018 Неверный пароль → 401 error.invalid-credentials")
def test_api_auth_018_wrong_password(api, api_roles):
    phone, _, ct = api_roles["shipper_admin"]
    r = api.login(phone, "WRONG_password_000", ct)
    assert r.status_code == 401, r.text[:200]
    assert _code(r) == "error.invalid-credentials"


@allure.title("API-AUTH-033 Валидация: clientType отсутствует → 400")
def test_api_auth_033_missing_client_type(api, api_roles):
    phone, pwd, _ = api_roles["super_admin"]
    r = api.request("POST", "/auth/login", json={"phone": phone, "password": pwd})
    assert r.status_code == 400, r.text[:200]
    assert _code(r) == "BAD_REQUEST"
    fields = [e.get("field") for e in (r.json().get("errors") or [])]
    assert "clientType" in fields


@allure.title("API-AUTH-034 Валидация: неизвестный clientType enum → 400")
def test_api_auth_034_bad_client_type_enum(api, api_roles):
    phone, pwd, _ = api_roles["super_admin"]
    r = api.login(phone, pwd, "NOT_A_REAL_APP")
    assert r.status_code == 400, r.text[:200]
    assert _code(r) == "BAD_REQUEST"


@allure.title("API-AUTH-079 GET /me без токена → 401 UNAUTHORIZED")
def test_api_auth_079_me_no_token(api):
    r = api.get("/me")
    assert r.status_code == 401, r.text[:200]
    assert _code(r) == "UNAUTHORIZED"


@allure.title("API-AUTH-080 GET /me с битым Bearer → 401")
def test_api_auth_080_me_broken_bearer(api):
    r = api.get("/me", token="broken.token.value")
    assert r.status_code == 401, r.text[:200]


# ─────────────────────────── Refresh ─────────────────────────────────────────
@allure.title("API-AUTH-051 Обновление токена — happy path (ротация)")
def test_api_auth_051_refresh_happy(api, api_roles):
    login = api.login(*api_roles["shipper_admin"])
    assert login.status_code == 200, login.text[:200]
    r = api.refresh(login.json()["refreshToken"])
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("accessToken") and r.json().get("refreshToken")


@allure.title("API-AUTH-054 Битый/поддельный refresh → 401")
def test_api_auth_054_refresh_forged(api):
    r = api.refresh("forged.refresh.value")
    assert r.status_code == 401, r.text[:200]
    assert _code(r) == "error.invalid-credentials"


@allure.title("API-AUTH-055 Валидация: refreshToken пустой → 400")
def test_api_auth_055_refresh_empty(api):
    r = api.refresh("")
    assert r.status_code == 400, r.text[:200]
    assert _code(r) == "BAD_REQUEST"
    fields = [e.get("field") for e in (r.json().get("errors") or [])]
    assert "refreshToken" in fields


# ─────────────────────────── /me: роль → capabilities ────────────────────────
@allure.title("API-AUTH-065 GET /me под SUPER_ADMIN")
def test_api_auth_065_me_super_admin(api, api_roles):
    me = api.get("/me", token=api.token(*api_roles["super_admin"])).json()
    assert me["role"] == "SUPER_ADMIN"
    assert me.get("effectiveCapabilities") == []
    assert not me.get("company")


@allure.title("API-AUTH-066 GET /me под SHIPPER_ADMIN (capabilities = ALL)")
def test_api_auth_066_me_shipper_admin(api, api_roles):
    me = api.get("/me", token=api.token(*api_roles["shipper_admin"])).json()
    assert me["role"] == "SHIPPER_ADMIN"
    caps = me.get("effectiveCapabilities") or []
    assert "ORDER_ENTRY" in caps and "REPORTS" in caps
    assert me.get("company")


@allure.title("API-AUTH-067 GET /me под SHIPPER_MANAGER (без ORDER_ENTRY)")
def test_api_auth_067_me_shipper_manager(api, api_roles):
    me = api.get("/me", token=api.token(*api_roles["shipper_manager"])).json()
    assert me["role"] == "SHIPPER_MANAGER"
    caps = me.get("effectiveCapabilities") or []
    assert caps and "ORDER_ENTRY" not in caps


@allure.title("API-AUTH-070 GET /me под SHIPPER_WAREHOUSE (capabilities = {ORDER_ENTRY})")
def test_api_auth_070_me_warehouse(api, api_roles):
    me = api.get("/me", token=api.token(*api_roles["shipper_warehouse"])).json()
    assert me["role"] == "SHIPPER_WAREHOUSE"
    assert "ORDER_ENTRY" in (me.get("effectiveCapabilities") or [])


@allure.title("API-AUTH-071 GET /me под TRANSPORT_ADMIN (capabilities = NONE)")
def test_api_auth_071_me_transport_admin(api, api_roles):
    me = api.get("/me", token=api.token(*api_roles["transport_admin"])).json()
    assert me["role"] == "TRANSPORT_ADMIN"
    assert me.get("effectiveCapabilities") == []
    assert me.get("company")


# ─────────────────────────── RBAC-гейты (403) ───────────────────────────────
# Гейты проверяем на GET-эндпойнтах: на POST /warehouse/* валидация тела (400)
# срабатывает РАНЬШЕ ролевого гейта, поэтому «отказ» там маскируется 400-м (роль
# всё равно не выполняет действие — это не дыра, а порядок фильтров). Для чистой
# проверки самого гейта нужен запрос без тела и без параметров пути.
@allure.title("API-RBAC-006 SHIPPER_MANAGER → GET /shipper/reports/orders → 403 (нет REPORTS)")
def test_api_rbac_006_manager_reports_denied(api, api_roles):
    tok = api.token(*api_roles["shipper_manager"])
    r = api.get("/shipper/reports/orders", token=tok)
    assert r.status_code == 403, r.text[:200]
    assert _code(r) in FORBIDDEN_CODES


@allure.title("API-RBAC-M03 SHIPPER_MANAGER → GET /shipper/blacklist → 403 (нет BLACKLIST)")
def test_api_rbac_manager_blacklist_denied(api, api_roles):
    tok = api.token(*api_roles["shipper_manager"])
    r = api.get("/shipper/blacklist", token=tok)
    assert r.status_code == 403, r.text[:200]
    assert _code(r) in FORBIDDEN_CODES


@allure.title("API-RBAC-T01 TRANSPORT_ADMIN → GET /shipper/orders → 403")
def test_api_rbac_transport_shipper_scope_denied(api, api_roles):
    tok = api.token(*api_roles["transport_admin"])
    r = api.get("/shipper/orders", token=tok)
    assert r.status_code == 403, r.text[:200]
    assert _code(r) in FORBIDDEN_CODES


@allure.title("API-RBAC-A01 SHIPPER_ADMIN → GET /super-admin/shipper-companies → 403")
def test_api_rbac_admin_super_scope_denied(api, api_roles):
    tok = api.token(*api_roles["shipper_admin"])
    r = api.get("/super-admin/shipper-companies", token=tok)
    assert r.status_code == 403, r.text[:200]
    assert _code(r) in FORBIDDEN_CODES


@allure.title("API-RBAC-W01 SHIPPER_WAREHOUSE → GET /warehouse/orders → 200")
def test_api_rbac_warehouse_own_scope_allowed(api, api_roles):
    tok = api.token(*api_roles["shipper_warehouse"])
    r = api.get("/warehouse/orders", token=tok)
    assert r.status_code in (200, 204), f"{r.status_code} {r.text[:200]}"
