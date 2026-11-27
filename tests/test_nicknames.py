# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A star is found by any of its nicknames, and drawn under its own designation.

The workbook's Nicknames column holds every common name of a star, "; " between them
(26 Nov 2026, `data/star_nicknames/`). These read the snapshot in `data/`.
"""
import pytest

from hybrasil.data import snapshot
from hybrasil.data.catalog_loader import build_star_system, catalog_entry, parse_workbook
from hybrasil.data.planetless_loader import parse_planetless, planetless_entry
from hybrasil.viz.export import build_body_info


@pytest.fixture(scope="module")
def workbook():
    return snapshot.load_snapshot_workbook()


@pytest.fixture(scope="module")
def catalog(workbook):
    return parse_workbook(workbook)


@pytest.mark.parametrize("name, host", [
    ("Lacaille 9352", "GJ 887"), ("Luyten's Star", "GJ 273"), ("Lalande 21185", "GJ 411"),
    ("pi Men", "HD 39091"), ("82 G. Eridani", "HD 20794"), ("Noquisi", "GJ 436"),
    ("Toliman", "alf Cen A"), ("Alpha Centauri C", "alf Cen A"), ("UV Ceti", "GJ 65"),
])
def test_a_nickname_opens_its_system(catalog, name, host):
    assert catalog.resolve_host(name) == host


def test_no_nickname_reaches_two_systems(catalog):
    shared = {k: v for k, v in catalog._aliases.items() if len(v) > 1}
    assert not shared, shared


def test_a_star_keeps_its_designation_and_lists_its_names(catalog):
    system = build_star_system(catalog, "GJ 887")
    star = system.get_stars()[0]
    assert star.label() == "GJ 887" and star.aliases == ["Lacaille 9352"]
    assert build_body_info({"gj-887": system})["GJ 887"]["aka"] == ["Lacaille 9352"]


def test_a_star_filed_by_its_gaia_number_is_drawn_under_its_nickname(catalog):
    star = build_star_system(catalog, "Gaia DR3 4188996885011268608").get_stars()[0]
    assert star.label() == "GJ 773 B"


def test_the_web_index_carries_every_star_s_names(catalog, workbook):
    assert "Lacaille 9352" in catalog_entry(catalog, "GJ 887")["nicknames"]
    # A companion's names find the system too.
    assert {"UV Ceti", "BL Ceti", "Luyten 726-8"} <= set(catalog_entry(catalog, "GJ 65")["nicknames"])
    planetless = parse_planetless(workbook)
    assert "Capella" in planetless_entry(planetless["alf Aur"])["aliases"]
    # Names on a component's row, not only the system's first row.
    assert "Mizar B" in planetless_entry(planetless["zet UMa"])["aliases"]
