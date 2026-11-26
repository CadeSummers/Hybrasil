# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Systems of stars with no planet on file: listed, opened, and drawn as stars and flat bands.

HIP 55507, GJ 680 and GJ 773 B each had a "planet" that turned out to be a companion star. The
candidate is on the Rejected candidates tab and the stars are on Multi-stars, so the system is a
page of its own (Catalog.star_systems()) rather than a refuted star with nothing to open. GJ 4113
and APM 89, whose Gaia "planets" were their own stellar orbits, joined them when their pairs went
onto Multi-stars (data/refuted_pairs/add_pairs.py).
"""

import pytest

from hybrasil.data.catalog_loader import build_star_system, parse_workbook
from hybrasil.data.snapshot import load_snapshot_workbook
from hybrasil.figures import _natural_span_days, build_figure
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.units import J2000
from hybrasil.web.app import CATALOG_PREFIX
from tests.test_band_flatness import _check_figure
from tests.test_web_app import _library

GJ_773_B = "Gaia DR3 4188996885011268608"
GJ_4113 = "Gaia DR3 2052469973468984192"
APM_89 = "Gaia DR3 5486916932205092352"
PAIRS = ("HIP 55507", "GJ 680", GJ_773_B, GJ_4113, APM_89)


@pytest.fixture(scope="module")
def catalog():
    return parse_workbook(load_snapshot_workbook())


@pytest.fixture(scope="module")
def library(catalog):
    return _library(catalog_loader=lambda: catalog)


class TestTheList:
    def test_it_is_the_systems_rows_with_stars_and_no_planet(self, catalog):
        listed = catalog.star_systems()
        assert set(listed) == set(PAIRS)
        # Derived, never a list of names: two or more stars-tab rows, nothing on a planet tab.
        hosts = set(catalog.hosts())
        assert set(listed) == {h for h in catalog.system_rows
                               if h not in hosts and len(catalog.stars_by_host.get(h, [])) >= 2}

    def test_hosts_still_means_a_planet_on_file(self, catalog):
        assert not set(catalog.hosts()) & set(PAIRS)

    def test_a_refuted_star_with_no_companion_on_file_is_not_one(self, catalog):
        assert "Kapteyn" not in catalog.star_systems()
        with pytest.raises(ValueError, match="rejected candidates"):
            catalog.resolve_host("Kapteyn")

    @pytest.mark.parametrize("typed, system", [
        ("HIP 55507", "HIP 55507"), ("HIP 55507 B", "HIP 55507"), ("GJ 680 B", "GJ 680"),
        ("GJ 773 A", GJ_773_B), ("GJ 773 Bb", GJ_773_B), ("GJ 773 B", GJ_773_B),
        ("GJ 4113", GJ_4113), ("GJ 4113 B", GJ_4113), ("APM 89", APM_89), ("APM 89 B", APM_89)])
    def test_any_of_its_stars_opens_it(self, catalog, typed, system):
        assert catalog.resolve_host(typed) == system

    def test_the_rejected_candidates_name_opens_the_star_it_turned_out_to_be(self, catalog):
        # Names are matched without case, and 'HIP 55507 b' the planet was HIP 55507 B the star.
        assert catalog.resolve_host("HIP 55507 b") == "HIP 55507"
        with pytest.raises(ValueError, match="rejected candidate"):
            catalog.resolve_host("Gaia-ASOI-025")


class TestTheSystem:
    @pytest.mark.parametrize("host", PAIRS)
    def test_it_is_its_stars_and_says_what_was_rejected(self, catalog, host):
        system = build_star_system(catalog, host)
        assert {b.body_type for b in system.bodies} == {"star"} and len(system.bodies) >= 2
        assert "No planet on file" in system.description and "0 planets" not in system.description
        assert "Rejected candidates, not drawn: " + ", ".join(catalog.rejected_in(host)) in system.description

    @pytest.mark.parametrize("host", PAIRS)
    def test_its_bands_are_flat_discs(self, catalog, host):
        system = build_star_system(catalog, host, SolventChoice.parse("all"))
        assert system.belt_zones
        for mode in ("static", "animated"):
            fig = build_figure(system, J2000, J2000 + _natural_span_days(system), mode=mode, frames=4)
            _check_figure(fig, system, host)

    def test_the_window_shows_the_tightest_pair_turning(self, catalog):
        # GJ 773 A's projected circle takes a hundred thousand years; the window is set by Bb's orbit.
        system = build_star_system(catalog, GJ_773_B)
        periods = [b.elements.period for b in system.bodies if b.elements is not None]
        assert _natural_span_days(system) == pytest.approx(1.2 * min(periods))
        assert max(periods) > 1000 * min(periods)

    def test_a_gaia_numbered_primary_is_shown_by_its_name(self, catalog):
        for host, name in ((GJ_773_B, "GJ 773 B"), (GJ_4113, "GJ 4113"), (APM_89, "APM 89")):
            assert build_star_system(catalog, host).bodies[0].display_name == name

    @pytest.mark.parametrize("host, companion, days, a_au", [
        (GJ_4113, "GJ 4113 B", 209.3157, 0.584),     # Gaia DR3's period, Kepler III on the inferred masses
        (APM_89, "APM 89 B", 0.69778 * 365.25, 0.584)])   # Vrijmoet et al. 2026, Table 4
    def test_a_pair_turns_in_its_published_period(self, catalog, host, companion, days, a_au):
        b = next(b for b in build_star_system(catalog, host).bodies if b.name == companion)
        assert b.status == "confirmed" and b.elements.semi_major_axis == a_au
        assert b.elements.period == pytest.approx(days, rel=2e-3)

    def test_a_single_wide_pair_is_capped_at_a_century(self, catalog):
        assert _natural_span_days(build_star_system(catalog, "HIP 55507")) == pytest.approx(36525.0)


class TestTheWebApp:
    def test_each_is_listed_once_under_high_star_count(self, library):
        index = library.index()
        for host in PAIRS:
            (e,) = [e for e in index if e["name"] == host]
            assert e["id"] == CATALOG_PREFIX + host and e["kind"] == "planetless" and not e["featured"]
            assert e["n_planets"] == 0 and e["planets"] == [] and e["n_stars"] == e["n_bodies"] >= 2

    def test_a_companion_finds_it(self, library):
        e = next(e for e in library.index() if e["name"] == "HIP 55507")
        assert "HIP 55507 B" in e["aliases"]

    def test_the_planet_systems_are_unchanged(self, library, catalog):
        planetary = {e["name"] for e in library.index()
                     if e["id"].startswith(CATALOG_PREFIX) and e["kind"] == "planetary"}
        assert planetary <= set(catalog.hosts()) and len(planetary) > 380
        assert not planetary & set(PAIRS)

    def test_it_opens(self, library):
        p = library.scene(CATALOG_PREFIX + "HIP 55507")
        assert [b["name"] for b in p["scene"]["bodies"]] == ["HIP 55507", "HIP 55507 B"]
        assert p["scene"]["bands"] and p["body_info"]
