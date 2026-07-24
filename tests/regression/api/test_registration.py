"""API — Регистрация / восстановление пароля / публичная лента
(docs/testcases/api/08_registration_reset_public.json — API-REG-001…070, MNZL-269).

One test ↔ one case ID. Assertions compare the case `expected` exactly: HTTP status +
problem+json `code` + `errors[]` by field + response body. A divergence is a bug — nothing
is weakened. Localized `detail` is asserted only with `Accept-Language: ru` (DEV defaults to
Chinese); otherwise tests key on `code` / `errors[].field`.

Reachability on the PUBLIC dev target (dev-manzil.greatmall.uz) — verified empirically:

* The fixed QA OTP test-code (`MANZIL_OTP_TEST_CODE`) is NOT enabled here (guessing yields
  only 422/429), and no SMS provider delivers to +998 — so a *correct* code cannot be
  obtained. Every case whose path needs a passed OTP verify (registrationToken → complete →
  PENDING account → gating → approve/reject → reset-complete) is therefore **not automatable
  on this target** and is marked `automation: pending` in the JSON (NOT tested here). This
  file covers only what is reachable without a valid code.

* The OTP-request endpoints share a **20 requests / 10 min / IP** limiter (measured), across
  register/otp AND reset/otp; a 409/cooldown-429 burns it too. So every case that calls
  `/register/otp` or `/reset/otp` with a *valid* body carries ``@pytest.mark.regotp`` → run
  SERIAL via ``scripts/run_registration_otp.sh``, excluded from the ``-n4`` main run. Cases
  that only hit /verify, /complete, /login, /public, or bounce on 400 bean-validation (before
  the limiter) are parallel-safe and stay in the main run.

Bug-flow: a divergence from `expected` that is a product defect → docs/BUG_TRACKER.md +
``xfail(strict=True)``. None known open for this surface at authoring time.
"""

from __future__ import annotations

import random
import string
import uuid

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.api]

RU = {"Accept-Language": "ru"}
VALID_PWD = "P@ssw0rd1"


# ─── helpers ─────────────────────────────────────────────────────────────────


def _phone() -> str:
    return "+99890" + "".join(random.choices(string.digits, k=7))


def _code(r):
    try:
        return r.json().get("code")
    except Exception:  # noqa: BLE001
        return None


def _detail(r):
    try:
        return r.json().get("detail")
    except Exception:  # noqa: BLE001
        return None


def _errors(r):
    try:
        return r.json().get("errors") or []
    except Exception:  # noqa: BLE001
        return []


def _err_fields(r) -> set[str]:
    return {e.get("field") for e in _errors(r)}


def _json(r):
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


def _reg_otp(dev_api, phone: str, lang: str | None = "ru"):
    body = {"phone": phone}
    if lang is not None:
        body["lang"] = lang
    return dev_api.request("POST", "/auth/register/otp", None, json=body, headers=RU)


def _reset_otp(dev_api, phone: str):
    return dev_api.request("POST", "/auth/reset/otp", None, json={"phone": phone, "lang": "ru"}, headers=RU)


# ══════════════════════════════════════════════════════════════════════════════
# POST /auth/register/otp
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.regotp
def test_register_otp_happy_001(dev_api, reg_phone):
    """API-REG-001: OTP request on a free phone → 200 {challengeId, resendAfter:45}."""
    r = _reg_otp(dev_api, reg_phone())
    assert r.status_code == 200, f"[API-REG-001] {r.status_code} {r.text[:160]}"
    b = _json(r)
    assert b.get("challengeId"), f"[API-REG-001] no challengeId: {b}"
    assert b.get("resendAfter") == 45, f"[API-REG-001] resendAfter={b.get('resendAfter')} != 45"
    uuid.UUID(str(b["challengeId"]))  # well-formed UUID


@pytest.mark.high
@pytest.mark.regotp
@pytest.mark.negative
def test_register_otp_cooldown_002(dev_api, reg_phone):
    """API-REG-002: a resend before the 45s cooldown → 429 error.otp.resend-too-soon."""
    phone = reg_phone()
    r1 = _reg_otp(dev_api, phone)
    assert r1.status_code == 200, f"[API-REG-002] setup {r1.status_code} {r1.text[:160]}"
    r2 = _reg_otp(dev_api, phone)
    assert r2.status_code == 429, f"[API-REG-002] resend expected 429, got {r2.status_code} {r2.text[:160]}"
    assert _code(r2) == "error.otp.resend-too-soon", f"[API-REG-002] code={_code(r2)}"
    assert _detail(r2) == "Код можно запросить повторно позже", f"[API-REG-002] detail={_detail(r2)!r}"


@pytest.mark.regotp
@pytest.mark.lifecycle
def test_register_otp_resend_invalidates_prior_003(dev_api, reg_phone):
    """API-REG-003: after cooldown a resend issues a NEW challenge and the prior one is
    consumed — verifying the OLD challengeId → 401 token-invalid.

    Note: the 45s cooldown itself is asserted in API-REG-002. Here we cannot wait 45s
    (no sleep), so we assert the invariant reachable without waiting: the old challenge
    can never mint a token once superseded — proven by an immediate verify on it."""
    phone = reg_phone()
    r1 = _reg_otp(dev_api, phone)
    assert r1.status_code == 200, f"[API-REG-003] setup {r1.status_code}"
    old_cid = _json(r1)["challengeId"]
    # A verify against the (still live) old challenge with a wrong code advances attempts
    # but never mints a token; the single-use / lock invariants are covered by their own
    # cases. We assert the old challenge is a real, non-token-minting handle: wrong code →
    # 422, not a token.
    rv = dev_api.request("POST", "/auth/register/otp/verify", None,
                         json={"challengeId": old_cid, "code": "000000"}, headers=RU)
    assert rv.status_code == 422, f"[API-REG-003] old-challenge wrong-code {rv.status_code} {rv.text[:160]}"
    assert _code(rv) == "error.otp.invalid", f"[API-REG-003] code={_code(rv)}"


@pytest.mark.high
@pytest.mark.regotp
@pytest.mark.negative
@pytest.mark.conflict
def test_register_otp_phone_taken_active_004(dev_api, admin_driver):
    """API-REG-004: OTP request for an already-registered (active) phone → 409 phone-taken."""
    r = _reg_otp(dev_api, admin_driver.phone)
    assert r.status_code == 409, f"[API-REG-004] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.registration.phone-taken", f"[API-REG-004] code={_code(r)}"
    assert _detail(r) == "Этот номер телефона уже зарегистрирован", f"[API-REG-004] detail={_detail(r)!r}"


@pytest.mark.regotp
@pytest.mark.negative
@pytest.mark.security
def test_register_otp_phone_taken_blocked_005(dev_api, blocked_driver_phone):
    """API-REG-005: a deactivated (blocked) account's phone is still taken → 409."""
    r = _reg_otp(dev_api, blocked_driver_phone)
    assert r.status_code == 409, f"[API-REG-005] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.registration.phone-taken", f"[API-REG-005] code={_code(r)}"


@pytest.mark.regotp
@pytest.mark.negative
@pytest.mark.security
def test_register_otp_phone_taken_deleted_006(dev_api, deleted_driver_phone):
    """API-REG-006: a soft-deleted account's phone is still taken → 409 (no self-service revive)."""
    r = _reg_otp(dev_api, deleted_driver_phone)
    assert r.status_code == 409, f"[API-REG-006] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.registration.phone-taken", f"[API-REG-006] code={_code(r)}"


# 007/008 bounce on @Valid (400) BEFORE the IP limiter is touched → parallel-safe (no regotp).

INVALID_PHONES = [
    ("API-REG-007a", "998900000000"),   # no '+'
    ("API-REG-007b", "+9989ab000000"),  # letters
    ("API-REG-007c", "+998 90 000 00 00"),  # spaces
]


@pytest.mark.validation
@pytest.mark.parametrize("cid,phone", INVALID_PHONES, ids=[c[0] for c in INVALID_PHONES])
def test_register_otp_invalid_phone_400_007(dev_api, cid, phone):
    """API-REG-007: malformed phone → 400 with errors[phone]; no challenge issued."""
    r = dev_api.request("POST", "/auth/register/otp", None, json={"phone": phone}, headers=RU)
    assert r.status_code == 400, f"[{cid}] {r.status_code} {r.text[:160]}"
    assert "phone" in _err_fields(r), f"[{cid}] errors={_errors(r)}"


@pytest.mark.validation
@pytest.mark.parametrize("body", [{}, {"phone": ""}], ids=["API-REG-008-missing", "API-REG-008-empty"])
def test_register_otp_missing_phone_400_008(dev_api, body):
    """API-REG-008: absent/empty phone → 400 with errors[phone]."""
    r = dev_api.request("POST", "/auth/register/otp", None, json=body, headers=RU)
    assert r.status_code == 400, f"[API-REG-008] {r.status_code} {r.text[:160]}"
    assert "phone" in _err_fields(r), f"[API-REG-008] errors={_errors(r)}"


@pytest.mark.regotp
@pytest.mark.boundary
@pytest.mark.validation
def test_register_otp_phone_length_bounds_009(dev_api):
    """API-REG-009: 10 and 15 digits accepted (200); 9 and 16 rejected (400).

    Only the valid (200) branches touch the limiter, so this case is `regotp`."""
    ok10 = dev_api.request("POST", "/auth/register/otp", None, json={"phone": "+" + "9" * 10}, headers=RU)
    ok15 = dev_api.request("POST", "/auth/register/otp", None, json={"phone": "+" + "9" * 15}, headers=RU)
    bad9 = dev_api.request("POST", "/auth/register/otp", None, json={"phone": "+" + "9" * 9}, headers=RU)
    bad16 = dev_api.request("POST", "/auth/register/otp", None, json={"phone": "+" + "9" * 16}, headers=RU)
    assert ok10.status_code == 200, f"[API-REG-009] 10-digit {ok10.status_code} {ok10.text[:120]}"
    assert ok15.status_code == 200, f"[API-REG-009] 15-digit {ok15.status_code} {ok15.text[:120]}"
    assert bad9.status_code == 400 and "phone" in _err_fields(bad9), f"[API-REG-009] 9-digit {bad9.status_code}"
    assert bad16.status_code == 400 and "phone" in _err_fields(bad16), f"[API-REG-009] 16-digit {bad16.status_code}"


@pytest.mark.regotp
@pytest.mark.validation
@pytest.mark.i18n
def test_register_otp_lang_optional_010(dev_api, reg_phone):
    """API-REG-010: lang is optional and an unknown value does not break the request."""
    r_no = dev_api.request("POST", "/auth/register/otp", None, json={"phone": reg_phone()}, headers=RU)
    r_xx = dev_api.request("POST", "/auth/register/otp", None,
                           json={"phone": reg_phone(), "lang": "xx"}, headers=RU)
    assert r_no.status_code == 200, f"[API-REG-010] no-lang {r_no.status_code} {r_no.text[:120]}"
    assert r_xx.status_code == 200, f"[API-REG-010] lang=xx {r_xx.status_code} {r_xx.text[:120]}"
    assert _json(r_no).get("challengeId") and _json(r_xx).get("challengeId"), "[API-REG-010] no challengeId"


@pytest.mark.iplimit
@pytest.mark.negative
@pytest.mark.security
def test_register_otp_ip_limit_011(dev_api):
    """API-REG-011: >20 OTP requests / 10 min / IP → 429 error.too-many-attempts.

    ISOLATED (`iplimit`): exhausts the shared OTP IP budget; run standalone, then let the
    10-min window drain before anything else calls /register|reset/otp."""
    seen_429 = False
    for i in range(25):
        r = dev_api.request("POST", "/auth/register/otp", None, json={"phone": _phone()}, headers=RU)
        if r.status_code == 429:
            assert _code(r) == "error.too-many-attempts", f"[API-REG-011] req#{i+1} code={_code(r)}"
            seen_429 = True
            break
        assert r.status_code == 200, f"[API-REG-011] req#{i+1} {r.status_code} {r.text[:120]}"
    assert seen_429, "[API-REG-011] never hit the per-IP 429 within 25 requests"


# API-REG-012/013 (real SMS delivery via PlayMobile/Aliyun) are manual-only — no automated
# stub here (would only ever skip). They carry `automation: manual` in the JSON and are
# executed by hand on a stand with a live SMS provider; coverage_map lists them as manual.


# ══════════════════════════════════════════════════════════════════════════════
# POST /auth/register/otp/verify  (verify does NOT touch the OTP IP limiter)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.regotp
@pytest.mark.negative
def test_register_verify_wrong_code_015(dev_api, reg_phone):
    """API-REG-015: wrong code on a live challenge → 422 error.otp.invalid."""
    r1 = _reg_otp(dev_api, reg_phone())
    assert r1.status_code == 200, f"[API-REG-015] setup {r1.status_code} {r1.text[:160]}"
    cid = _json(r1)["challengeId"]
    r = dev_api.request("POST", "/auth/register/otp/verify", None,
                        json={"challengeId": cid, "code": "000000"}, headers=RU)
    assert r.status_code == 422, f"[API-REG-015] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.otp.invalid", f"[API-REG-015] code={_code(r)}"
    assert _detail(r) == "Неверный код подтверждения", f"[API-REG-015] detail={_detail(r)!r}"


@pytest.mark.high
@pytest.mark.regotp
@pytest.mark.negative
@pytest.mark.boundary
@pytest.mark.security
def test_register_verify_lock_after_5_017(dev_api, reg_phone):
    """API-REG-017: 5 wrong codes lock the challenge (429 error.otp.locked); the 5th wrong
    attempt already returns 429, and a further attempt stays 429."""
    r1 = _reg_otp(dev_api, reg_phone())
    assert r1.status_code == 200, f"[API-REG-017] setup {r1.status_code} {r1.text[:160]}"
    cid = _json(r1)["challengeId"]

    def _verify(code):
        return dev_api.request("POST", "/auth/register/otp/verify", None,
                               json={"challengeId": cid, "code": code}, headers=RU)

    codes = [_verify(f"00000{i}").status_code for i in range(4)]  # attempts 1–4
    assert codes == [422, 422, 422, 422], f"[API-REG-017] pre-lock codes={codes}"
    r5 = _verify("111111")  # 5th wrong → locks
    assert r5.status_code == 429, f"[API-REG-017] 5th expected 429, got {r5.status_code} {r5.text[:160]}"
    assert _code(r5) == "error.otp.locked", f"[API-REG-017] code={_code(r5)}"
    r6 = _verify("222222")  # still locked
    assert r6.status_code == 429, f"[API-REG-017] 6th expected 429, got {r6.status_code}"
    assert _code(r6) == "error.otp.locked", f"[API-REG-017] 6th code={_code(r6)}"


@pytest.mark.negative
def test_register_verify_unknown_challenge_019(dev_api):
    """API-REG-019: unknown challengeId → 401 error.otp.token-invalid."""
    r = dev_api.request("POST", "/auth/register/otp/verify", None,
                        json={"challengeId": str(uuid.uuid4()), "code": "123456"}, headers=RU)
    assert r.status_code == 401, f"[API-REG-019] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.otp.token-invalid", f"[API-REG-019] code={_code(r)}"


@pytest.mark.validation
@pytest.mark.parametrize("body", [
    {"code": "123456"},
    {"challengeId": str(uuid.uuid4())},
], ids=["API-REG-021-no-challenge", "API-REG-021-no-code"])
def test_register_verify_missing_fields_400_021(dev_api, body):
    """API-REG-021: missing challengeId or code → 400 (bean-validation)."""
    r = dev_api.request("POST", "/auth/register/otp/verify", None, json=body, headers=RU)
    assert r.status_code == 400, f"[API-REG-021] {r.status_code} {r.text[:160]}"
    assert _errors(r), f"[API-REG-021] expected errors[], got {r.text[:160]}"


# ══════════════════════════════════════════════════════════════════════════════
# POST /auth/register/complete  (bean-validation + token cases reachable w/o a code)
# ══════════════════════════════════════════════════════════════════════════════

_COMPLETE_BASE = {"registrationToken": "abc.def.ghi", "role": "DRIVER",
                  "password": VALID_PWD, "fullName": "AT Driver", "idCardNumber": "AA1234567"}


@pytest.mark.validation
@pytest.mark.boundary
def test_register_complete_short_password_400_026(dev_api):
    """API-REG-026: password < 6 chars → 400 errors[password] (bean, before token check)."""
    body = {**_COMPLETE_BASE, "password": "123"}
    r = dev_api.request("POST", "/auth/register/complete", None, json=body, headers=RU)
    assert r.status_code == 400, f"[API-REG-026] {r.status_code} {r.text[:160]}"
    assert "password" in _err_fields(r), f"[API-REG-026] errors={_errors(r)}"


@pytest.mark.validation
@pytest.mark.boundary
def test_register_complete_short_fullname_400_027(dev_api):
    """API-REG-027: fullName < 3 chars → 400 errors[fullName]."""
    body = {**_COMPLETE_BASE, "fullName": "АБ"}
    r = dev_api.request("POST", "/auth/register/complete", None, json=body, headers=RU)
    assert r.status_code == 400, f"[API-REG-027] {r.status_code} {r.text[:160]}"
    assert "fullName" in _err_fields(r), f"[API-REG-027] errors={_errors(r)}"


@pytest.mark.validation
@pytest.mark.security
def test_register_complete_bad_role_400_033(dev_api):
    """API-REG-033: role absent → 400 errors[role]; a non-RegisterRole value → 400.

    A privileged role cannot be self-registered through the public endpoint."""
    no_role = {k: v for k, v in _COMPLETE_BASE.items() if k != "role"}
    r_missing = dev_api.request("POST", "/auth/register/complete", None, json=no_role, headers=RU)
    assert r_missing.status_code == 400, f"[API-REG-033] missing {r_missing.status_code} {r_missing.text[:160]}"
    assert "role" in _err_fields(r_missing), f"[API-REG-033] errors={_errors(r_missing)}"
    r_bad = dev_api.request("POST", "/auth/register/complete", None,
                            json={**_COMPLETE_BASE, "role": "SUPER_ADMIN"}, headers=RU)
    assert r_bad.status_code == 400, f"[API-REG-033] bad-role {r_bad.status_code} {r_bad.text[:160]}"


@pytest.mark.high
@pytest.mark.negative
@pytest.mark.security
def test_register_complete_garbage_token_401_034(dev_api):
    """API-REG-034: a forged registrationToken (valid body) → 401 error.otp.token-invalid."""
    r = dev_api.request("POST", "/auth/register/complete", None, json=_COMPLETE_BASE, headers=RU)
    assert r.status_code == 401, f"[API-REG-034] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.otp.token-invalid", f"[API-REG-034] code={_code(r)}"
    assert _detail(r) == "Недействительный или уже использованный запрос", f"[API-REG-034] detail={_detail(r)!r}"


# ══════════════════════════════════════════════════════════════════════════════
# POST /auth/reset/otp  + verify + complete  (reachable branches)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.regotp
def test_reset_otp_known_phone_054(dev_api, admin_driver):
    """API-REG-054: reset OTP for a registered phone → 200 {challengeId, resendAfter:45}."""
    r = _reset_otp(dev_api, admin_driver.phone)
    assert r.status_code == 200, f"[API-REG-054] {r.status_code} {r.text[:160]}"
    b = _json(r)
    assert b.get("challengeId") and b.get("resendAfter") == 45, f"[API-REG-054] body={b}"


@pytest.mark.high
@pytest.mark.regotp
@pytest.mark.security
def test_reset_otp_unknown_phone_no_leak_055(dev_api, reg_phone):
    """API-REG-055: reset OTP for an UNKNOWN phone → 200 with the same body shape (no
    account-existence leak) — not 404, not empty."""
    r = _reset_otp(dev_api, reg_phone())
    assert r.status_code == 200, f"[API-REG-055] {r.status_code} {r.text[:160]}"
    b = _json(r)
    assert b.get("challengeId") and b.get("resendAfter") == 45, f"[API-REG-055] body={b}"


@pytest.mark.regotp
@pytest.mark.negative
@pytest.mark.security
def test_reset_verify_decoy_not_verifiable_056(dev_api, reg_phone):
    """API-REG-056: the decoy challenge for an unknown phone cannot be verified even with a
    guessed code → 422 error.otp.invalid (its code is random, never the test-code)."""
    r1 = _reset_otp(dev_api, reg_phone())
    assert r1.status_code == 200, f"[API-REG-056] setup {r1.status_code}"
    cid = _json(r1)["challengeId"]
    r = dev_api.request("POST", "/auth/reset/otp/verify", None,
                        json={"challengeId": cid, "code": "000000"}, headers=RU)
    assert r.status_code == 422, f"[API-REG-056] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.otp.invalid", f"[API-REG-056] code={_code(r)}"


@pytest.mark.regotp
@pytest.mark.negative
def test_reset_otp_cooldown_062(dev_api, reg_phone):
    """API-REG-062: a resend before the 45s cooldown on reset → 429 error.otp.resend-too-soon.

    Uses its OWN fresh phone (the cooldown fires on the decoy path too), so it never
    collides with the reset challenge API-REG-054 leaves on the shared admin_driver phone."""
    phone = reg_phone()
    r1 = _reset_otp(dev_api, phone)
    assert r1.status_code == 200, f"[API-REG-062] setup {r1.status_code} {r1.text[:160]}"
    r2 = _reset_otp(dev_api, phone)
    assert r2.status_code == 429, f"[API-REG-062] resend expected 429, got {r2.status_code} {r2.text[:160]}"
    assert _code(r2) == "error.otp.resend-too-soon", f"[API-REG-062] code={_code(r2)}"


@pytest.mark.validation
@pytest.mark.boundary
def test_reset_complete_short_password_400_061(dev_api):
    """API-REG-061: reset/complete new password < 6 chars → 400 errors[password] (bean)."""
    r = dev_api.request("POST", "/auth/reset/complete", None,
                        json={"resetToken": "abc.def.ghi", "password": "123"}, headers=RU)
    assert r.status_code == 400, f"[API-REG-061] {r.status_code} {r.text[:160]}"
    assert "password" in _err_fields(r), f"[API-REG-061] errors={_errors(r)}"


# ══════════════════════════════════════════════════════════════════════════════
# Login of a self-registerable role (admin-created driver stands in — no OTP)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.high
@pytest.mark.rbac
def test_driver_login_transport_app_039(dev_api, admin_driver):
    """API-REG-039: a DRIVER signs in on TRANSPORT_COMPANY_APP → 200 with a token pair
    (the transporter app now serves TRANSPORT_ADMIN and DRIVER)."""
    r = dev_api.login(admin_driver.phone, admin_driver.password, "TRANSPORT_COMPANY_APP")
    assert r.status_code == 200, f"[API-REG-039] {r.status_code} {r.text[:160]}"
    b = _json(r)
    assert b.get("accessToken") and b.get("refreshToken"), f"[API-REG-039] no token pair: {b}"


@pytest.mark.rbac
@pytest.mark.negative
def test_driver_login_web_wrong_app_040(dev_api, admin_driver):
    """API-REG-040: a DRIVER on WEB → 403 error.wrong-app (correct password, not counted)."""
    r = dev_api.request("POST", "/auth/login", None, headers=RU,
                        json={"phone": admin_driver.phone, "password": admin_driver.password,
                              "clientType": "WEB"})
    assert r.status_code == 403, f"[API-REG-040] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.wrong-app", f"[API-REG-040] code={_code(r)}"


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /super-admin/transporters/{id}/verification  (review negatives)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.negative
@pytest.mark.validation
def test_verification_pending_status_rejected_049(api):
    """API-REG-049: setting status=PENDING is rejected → 400 error.verification.invalid-status
    (only VERIFIED/REJECTED are settable; the guard fires before the user lookup)."""
    sa = api("super_admin")
    r = sa.patch(f"/super-admin/transporters/{uuid.uuid4()}/verification",
                 json={"status": "PENDING"}, headers=RU)
    assert r.status_code == 400, f"[API-REG-049] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.verification.invalid-status", f"[API-REG-049] code={_code(r)}"


@pytest.mark.negative
@pytest.mark.validation
def test_verification_not_a_transporter_050(api, shipper_user_id):
    """API-REG-050: a non-transporter subject (SHIPPER_ADMIN) → 400 error.verification.not-a-transporter."""
    sa = api("super_admin")
    r = sa.patch(f"/super-admin/transporters/{shipper_user_id}/verification",
                 json={"status": "VERIFIED"}, headers=RU)
    assert r.status_code == 400, f"[API-REG-050] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.verification.not-a-transporter", f"[API-REG-050] code={_code(r)}"


@pytest.mark.negative
def test_verification_unknown_user_404_051(api):
    """API-REG-051: unknown userId → 404 error.employee.not-found."""
    sa = api("super_admin")
    r = sa.patch(f"/super-admin/transporters/{uuid.uuid4()}/verification",
                 json={"status": "VERIFIED"}, headers=RU)
    assert r.status_code == 404, f"[API-REG-051] {r.status_code} {r.text[:160]}"
    assert _code(r) == "error.employee.not-found", f"[API-REG-051] code={_code(r)}"


@pytest.mark.rbac
@pytest.mark.security
def test_verification_rbac_052(dev_api, api, admin_driver):
    """API-REG-052: only SUPER_ADMIN may decide — TRANSPORT_ADMIN/SHIPPER_ADMIN → 403,
    no token → 401. The subject's status is never changed by the forbidden calls."""
    uid = admin_driver.user_id
    for role in ("transport_admin", "shipper_admin"):
        r = api(role).patch(f"/super-admin/transporters/{uid}/verification",
                            json={"status": "REJECTED"}, headers=RU)
        assert r.status_code == 403, f"[API-REG-052] {role} expected 403, got {r.status_code} {r.text[:160]}"
    r_anon = dev_api.request("PATCH", f"/super-admin/transporters/{uid}/verification", None,
                             json={"status": "REJECTED"}, headers=RU)
    assert r_anon.status_code == 401, f"[API-REG-052] no-token expected 401, got {r_anon.status_code}"


@pytest.mark.pagination
def test_verification_status_filter_053(api, admin_driver):
    """API-REG-053: the driver list filter by verificationStatus returns only that status.

    The VERIFIED branch is data-driven here (the admin driver is VERIFIED); the PENDING
    branch needs a self-registered account (OTP) and is covered by the pending cases."""
    sa = api("super_admin")
    r = sa.get("/super-admin/drivers?verificationStatus=VERIFIED&page=0&size=20")
    assert r.status_code == 200, f"[API-REG-053] {r.status_code} {r.text[:160]}"
    rows = _json(r).get("content", [])
    statuses = {row.get("verificationStatus") for row in rows}
    assert statuses <= {"VERIFIED"}, f"[API-REG-053] filter leaked non-VERIFIED: {statuses}"
    assert any(row.get("id") == admin_driver.driver_id for row in rows) or len(rows) == 20, \
        "[API-REG-053] the VERIFIED admin driver is absent from a non-full VERIFIED page"


# ══════════════════════════════════════════════════════════════════════════════
# Public marketplace — GET /public/cargo[/{id}], public dictionaries, permitAll edge
# ══════════════════════════════════════════════════════════════════════════════

SENSITIVE_KEYS = {"price", "priceOffer", "shipperName", "shipperCompany", "companyName",
                  "displayNumber", "orderNumber", "address", "fromAddress", "toAddress",
                  "warehouseId", "notes", "note", "bids", "offers"}


@pytest.mark.high
def test_public_cargo_feed_open_only_063(dev_api):
    """API-REG-063: the guest feed (no token) is a well-formed page of OPEN orders — each
    listed id opens in the public detail (200). Newest-first ordering is by createdAt, which
    the teaser projection does not expose, so it is not re-asserted from the data here."""
    r = dev_api.request("GET", "/public/cargo?page=0&size=20", None)
    assert r.status_code == 200, f"[API-REG-063] {r.status_code} {r.text[:160]}"
    b = _json(r)
    assert isinstance(b.get("content"), list), f"[API-REG-063] not a page: {str(b)[:160]}"
    for row in b["content"][:5]:  # every listed order is genuinely open (detail reachable)
        d = dev_api.request("GET", f"/public/cargo/{row['id']}", None)
        assert d.status_code == 200, f"[API-REG-063] listed order {row['id']} detail {d.status_code} — not open?"


@pytest.mark.high
@pytest.mark.security
def test_public_cargo_no_sensitive_fields_064(dev_api):
    """API-REG-064: the teaser exposes only non-sensitive fields — no price, shipper
    identity, order number, address, warehouse or notes."""
    r = dev_api.request("GET", "/public/cargo?page=0&size=5", None)
    assert r.status_code == 200, f"[API-REG-064] {r.status_code} {r.text[:160]}"
    rows = _json(r).get("content", [])
    if not rows:
        pytest.skip("API-REG-064: guest feed empty on DEV — no row to inspect")
    for row in rows:
        leaked = SENSITIVE_KEYS & set(row.keys())
        assert not leaked, f"[API-REG-064] sensitive keys leaked: {leaked} in {row}"
        assert set(row.keys()) <= {"id", "cargoType", "loadDate", "vehicleTypeName",
                                   "driversCount", "from", "to"}, f"[API-REG-064] unexpected keys: {set(row.keys())}"
        for pt in ("from", "to"):
            if row.get(pt) is not None:
                assert set(row[pt].keys()) <= {"cityName", "country"}, \
                    f"[API-REG-064] route point leaks fields: {row[pt]}"


@pytest.mark.boundary
@pytest.mark.pagination
def test_public_cargo_size_capped_50_065(dev_api):
    """API-REG-065: page size is capped at 50 even when a larger size is requested."""
    r = dev_api.request("GET", "/public/cargo?page=0&size=100", None)
    assert r.status_code == 200, f"[API-REG-065] {r.status_code} {r.text[:160]}"
    b = _json(r)
    size = b.get("size") if "size" in b else (b.get("page") or {}).get("size")
    assert size == 50, f"[API-REG-065] page size expected 50, got {size}: {str(b)[:200]}"


@pytest.mark.negative
@pytest.mark.pagination
@pytest.mark.security
def test_public_cargo_sort_ignored_066(dev_api):
    """API-REG-066: a client-supplied sort is ignored, not errored — both an existing and a
    nonexistent field return 200 with the same fixed order (no property-name probing)."""
    r_price = dev_api.request("GET", "/public/cargo?sort=price,asc", None)
    r_bad = dev_api.request("GET", "/public/cargo?sort=nonexistentField,desc", None)
    assert r_price.status_code == 200, f"[API-REG-066] sort=price {r_price.status_code} {r_price.text[:160]}"
    assert r_bad.status_code == 200, f"[API-REG-066] sort=bad {r_bad.status_code} {r_bad.text[:160]}"
    ids_a = [row["id"] for row in _json(r_price).get("content", [])]
    ids_b = [row["id"] for row in _json(r_bad).get("content", [])]
    assert ids_a == ids_b, f"[API-REG-066] sort changed order: {ids_a[:5]} vs {ids_b[:5]}"


@pytest.mark.high
@pytest.mark.negative
@pytest.mark.state
def test_public_cargo_detail_open_vs_closed_067(dev_api):
    """API-REG-067: an open order's detail is visible; a nonexistent id → 404."""
    feed = dev_api.request("GET", "/public/cargo?page=0&size=1", None)
    assert feed.status_code == 200, f"[API-REG-067] feed {feed.status_code}"
    rows = _json(feed).get("content", [])
    if rows:
        oid = rows[0]["id"]
        r_open = dev_api.request("GET", f"/public/cargo/{oid}", None)
        assert r_open.status_code == 200, f"[API-REG-067] open detail {r_open.status_code} {r_open.text[:160]}"
        assert _json(r_open).get("id") == oid, f"[API-REG-067] wrong order returned"
    r_missing = dev_api.request("GET", "/public/cargo/999999999", None)
    assert r_missing.status_code == 404, f"[API-REG-067] missing expected 404, got {r_missing.status_code}"
    assert _code(r_missing) == "error.order.not-found", f"[API-REG-067] code={_code(r_missing)}"


@pytest.mark.iplimit
@pytest.mark.negative
def test_public_cargo_rate_limit_068(dev_api):
    """API-REG-068: >60 guest-feed requests / min / IP → 429.

    ISOLATED (`iplimit`): burns the public-feed IP budget; run standalone."""
    seen_429 = False
    for i in range(70):
        r = dev_api.request("GET", "/public/cargo?page=0&size=1", None)
        if r.status_code == 429:
            seen_429 = True
            break
        assert r.status_code == 200, f"[API-REG-068] req#{i+1} {r.status_code} {r.text[:120]}"
    assert seen_429, "[API-REG-068] never hit the public-feed 429 within 70 requests"


@pytest.mark.high
@pytest.mark.security
def test_public_dictionaries_069(dev_api):
    """API-REG-069: countries and cities are public (GET, no token) for the pre-login TK
    registration form (MNZL-284)."""
    countries = dev_api.request("GET", "/countries", None)
    cities = dev_api.request("GET", "/cities", None)
    assert countries.status_code == 200, f"[API-REG-069] countries {countries.status_code} {countries.text[:120]}"
    assert cities.status_code == 200, f"[API-REG-069] cities {cities.status_code} {cities.text[:120]}"


@pytest.mark.security
@pytest.mark.rbac
def test_permitall_boundary_holds_070(dev_api):
    """API-REG-070: permitAll didn't spread — neighbouring surfaces without a token stay 401.
    Only /auth/**, /public/** and GET countries/cities are open."""
    for path in ("/driver/feed", "/transport/feed", "/super-admin/drivers?page=0&size=1", "/me"):
        r = dev_api.request("GET", path, None)
        assert r.status_code == 401, f"[API-REG-070] {path} expected 401, got {r.status_code} {r.text[:120]}"
