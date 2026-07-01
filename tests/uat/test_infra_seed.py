"""Infra smoke for the API-seed helper (not a UAT case — no `uat` marker)."""

import pytest


@pytest.mark.infra
def test_seed_published(seeder):
    o = seeder.order("published")
    assert o["id"] and o["status"] == "PUBLISHED"


@pytest.mark.infra
def test_seed_selected(seeder):
    o = seeder.order("selected")
    assert o["id"] and o["offerId"] and o["status"] == "SELECTED"
