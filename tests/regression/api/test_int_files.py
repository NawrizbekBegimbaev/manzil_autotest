"""API — generic file upload (06_integrations_sms_dicts.json, INT-049…059, 152).

`POST /api/v1/files` — multipart/form-data, одна часть `file`. Сервис (FileUploadService):
1) пусто/нет файла → 400 error.file.missing; 2) размер > 5 MiB (manzil.storage.max-file-size)
→ 400 error.file.too-large; 3) MIME определяется по МАГИЧЕСКИМ байтам (Apache Tika),
Content-Type части игнорируется — не jpeg/png/webp → 400 error.file.invalid-type.
Больше общего multipart-лимита (6MB) → 413 error.request.too-large (резолвер до сервиса).
Аутентификация обязательна (любая роль); путь НЕ в permitAll → без токена 401.
Ответ 201: {id, previewUrl, expiresAt≈now+24h}.

Границы размера: 5 MiB (5242880) < файл < 6MB (6291456) → 400 too-large (сервис);
файл > 6MB → 413 (multipart-резолвер). Тест 053 берёт 5.5 MiB, 054 — 6.5 MiB.

Один тест ↔ один ID. Прогон на DEV. Реальные картинки не нужны — минимальные валидные
блобы magic-байтов; арбитр детекта — Tika на сервере.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.api]

# ─── минимальные валидные блобы (magic-байты) ────────────────────────────────
JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAT8AR//Z"
)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgYAAAAAQAAeYW"
    "Q8kAAAAASUVORK5CYII="
)
WEBP = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF\n"

MiB = 1024 * 1024


def _upload(client, blob, name="a.jpg", ctype="image/jpeg", token_client=True):
    """POST /files. client — RoleClient (Bearer) или dev_api для анонима."""
    files = {"file": (name, blob, ctype)}
    if token_client:
        return client.post("/files", files=files)
    return client.request("POST", "/files", None, files=files)


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture
def up(api):
    return api("shipper_admin")


# ═══ happy: разрешённые типы ═════════════════════════════════════════════════


@pytest.mark.high
def test_upload_jpeg_049(up):
    """INT-049: валидный JPEG → 201, тело {id, previewUrl, expiresAt}."""
    r = _upload(up, JPEG, "photo.jpg", "image/jpeg")
    assert r.status_code == 201, f"[API-INT-049] {r.status_code} {r.text[:160]}"
    b = r.json()
    assert b.get("id") and b.get("previewUrl") and b.get("expiresAt"), f"[API-INT-049] тело неполное: {b}"


@pytest.mark.medium
def test_upload_png_050(up):
    """INT-050: валидный PNG → 201."""
    r = _upload(up, PNG, "photo.png", "image/png")
    assert r.status_code == 201, f"[API-INT-050] {r.status_code} {r.text[:160]}"


@pytest.mark.low
def test_upload_webp_051(up):
    """INT-051: валидный WEBP → 201."""
    r = _upload(up, WEBP, "photo.webp", "image/webp")
    assert r.status_code == 201, f"[API-INT-051] {r.status_code} {r.text[:160]}"


# ═══ валидация ═══════════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.validation
def test_missing_file_052(up):
    """INT-052: пустой (0 байт) файл → 400 error.file.missing."""
    r = _upload(up, b"", "empty.jpg", "image/jpeg")
    assert r.status_code == 400 and _code(r) == "error.file.missing", f"[API-INT-052] {r.status_code}/{_code(r)}"


@pytest.mark.high
@pytest.mark.boundary
def test_too_large_service_053(up):
    """INT-053: 5.5 MiB (> 5 MiB storage, < 6MB multipart) → 400 error.file.too-large."""
    blob = JPEG + b"\x00" * (int(5.5 * MiB) - len(JPEG))
    r = _upload(up, blob, "big.jpg", "image/jpeg")
    assert r.status_code == 400 and _code(r) == "error.file.too-large", f"[API-INT-053] {r.status_code}/{_code(r)} len={len(blob)}"


@pytest.mark.medium
@pytest.mark.boundary
def test_too_large_multipart_054(up):
    """INT-054: 6.5 MiB (> 6MB multipart) → 413 (резолвер до сервиса).
    code=CONTENT_TOO_LARGE (framework-паттерн: code=status.name() у не-доменных ошибок);
    доменный ключ error.request.too-large локализован в detail/message, не в code."""
    blob = JPEG + b"\x00" * (int(6.5 * MiB) - len(JPEG))
    r = _upload(up, blob, "huge.jpg", "image/jpeg")
    assert r.status_code == 413 and _code(r) == "CONTENT_TOO_LARGE", f"[API-INT-054] {r.status_code}/{_code(r)} len={len(blob)}"


@pytest.mark.high
@pytest.mark.security
def test_fake_mime_pdf_as_jpg_055(up):
    """INT-055: PDF-байты под именем photo.jpg + Content-Type image/jpeg → 400 error.file.invalid-type.
    Тип определяется по содержимому (magic-байты), не по имени/заголовку."""
    r = _upload(up, PDF, "photo.jpg", "image/jpeg")
    assert r.status_code == 400 and _code(r) == "error.file.invalid-type", f"[API-INT-055] {r.status_code}/{_code(r)}"


@pytest.mark.low
@pytest.mark.security
def test_real_jpeg_wrong_ctype_056(up):
    """INT-056: настоящий JPEG с Content-Type application/octet-stream → 201.
    Решение по содержимому: «неправильный» Content-Type не мешает валидной картинке."""
    r = _upload(up, JPEG, "photo.bin", "application/octet-stream")
    assert r.status_code == 201, f"[API-INT-056] {r.status_code} {r.text[:160]}"


# ═══ аутентификация / RBAC ═══════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.rbac
def test_unauthenticated_057(dev_api):
    """INT-057: загрузка без Authorization → 401."""
    r = _upload(dev_api, JPEG, "photo.jpg", "image/jpeg", token_client=False)
    assert r.status_code == 401, f"[API-INT-057] {r.status_code} {r.text[:160]}"


@pytest.mark.medium
@pytest.mark.rbac
def test_any_role_driver_058(dev_api, cfg):
    """INT-058: любая аутентифицированная роль (DRIVER) может загружать → 201."""
    from tests.regression.conftest import RoleClient
    sa = dev_api.token(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    vt = dev_api.request("GET", "/super-admin/vehicle-types?size=1", sa).json()
    vt = (vt.get("content", vt) if isinstance(vt, dict) else vt)[0]["id"]
    import random
    phone = "+99890" + "".join(random.choices("0123456789", k=7))
    drv = dev_api.request("POST", "/super-admin/drivers", sa,
                          json={"fullName": "AT Driver", "phone": phone, "password": cfg.dev_account_password, "vehicleTypeId": vt})
    assert drv.status_code == 201, f"[API-INT-058] driver setup: {drv.status_code} {drv.text[:120]}"
    try:
        d = RoleClient(dev_api, dev_api.token(phone, cfg.dev_account_password, "TRANSPORT_COMPANY_APP"))
        r = _upload(d, JPEG, "photo.jpg", "image/jpeg")
        assert r.status_code == 201, f"[API-INT-058] {r.status_code} {r.text[:160]}"
    finally:
        dev_api.request("DELETE", f"/super-admin/drivers/{drv.json()['id']}", sa)


@pytest.mark.medium
@pytest.mark.security
def test_deactivated_user_059(dev_api, cfg, api):
    """INT-059: деактивированный пользователь со «свежим» токеном → 401/403, файл не сохраняется.
    Создаём staff → логин (токен) → деактивация (DELETE staff) → загрузка старым токеном."""
    from tests.regression.conftest import RoleClient
    s_admin = api("shipper_admin")
    import random
    phone = "+99890" + "".join(random.choices("0123456789", k=7))
    sid = s_admin.post("/shipper/staff", json={"fullName": "AT Deact", "phone": phone, "password": cfg.dev_account_password, "role": "SHIPPER_OPERATOR"}).json()["id"]
    tok = dev_api.token(phone, cfg.dev_account_password, "WEB")
    s_admin.delete(f"/shipper/staff/{sid}")  # деактивация
    r = _upload(RoleClient(dev_api, tok), JPEG, "photo.jpg", "image/jpeg")
    assert r.status_code in (401, 403), f"[API-INT-059] ожидали 401/403 для деактивированного, получили {r.status_code} {r.text[:120]}"


# ═══ i18n ════════════════════════════════════════════════════════════════════


@pytest.mark.low
@pytest.mark.i18n
def test_i18n_invalid_type_152(up):
    """INT-152: error.file.invalid-type локализован для 5 языков (текст ≠ ключ)."""
    seen = {}
    for lang in ("ru", "zh", "uz", "ky", "ug"):
        files = {"file": ("doc.pdf", PDF, "image/jpeg")}
        r = up.request("POST", "/files", files=files, headers={"Accept-Language": lang})
        assert r.status_code == 400 and _code(r) == "error.file.invalid-type", f"[API-INT-152/{lang}] {r.status_code}/{_code(r)}"
        detail = r.json().get("detail") or r.json().get("message") or ""
        assert detail and "error.file.invalid-type" not in detail, f"[API-INT-152/{lang}] текст не локализован: {detail!r}"
        seen[lang] = detail
    assert len({seen["ru"], seen["zh"], seen["uz"]}) >= 2, f"[API-INT-152] переводы не различаются: {seen}"
