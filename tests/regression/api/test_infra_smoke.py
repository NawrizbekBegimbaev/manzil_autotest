"""Infra smoke for the regression harness — NOT a library case.

Validates that the DEV tenant provisions and every provisioned role can log in
and reach ``/me``. Marked ``infra`` (not ``regression``) so it stays out of the
coverage set and the daily UAT.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.infra


def test_raw_super_admin_login(dev_api, cfg):
    r = dev_api.login(cfg.dev_super_admin_phone, cfg.dev_super_admin_password, "WEB")
    assert r.status_code == 200, f"dev super-admin login: {r.status_code} {r.text[:160]}"
    assert r.json().get("accessToken"), "login 200 but no accessToken"


@pytest.mark.parametrize(
    "role",
    ["super_admin", "shipper_admin", "transport_admin",
     "shipper_manager", "shipper_operator", "shipper_warehouse", "shipper_dispatcher"],
)
def test_provisioned_role_reaches_me(api, role):
    r = api(role).get("/me")
    assert r.status_code == 200, f"[{role}] /me: {r.status_code} {r.text[:160]}"


def test_manager_has_effective_capabilities(api):
    r = api("shipper_manager").get("/me")
    assert r.status_code == 200, f"manager /me: {r.status_code}"
    assert r.json().get("effectiveCapabilities") is not None, \
        "manager /me lacks effectiveCapabilities — provisioning/role wrong"
