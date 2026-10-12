# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Brown dwarfs on the planet tabs, drawn inside a Planetless 4+ Stars hierarchy (7 Oct 2026).

A brown dwarf is a planet, not a star (docs/hybrasil-instructions.md section 6). The ones that sat in a
Planetless 4+ Stars hierarchy moved to the planet tabs, filed under the system's 'System / Host', while the stars
and their measured orbits stayed on the tab. These tests build one such system from literal rows: a planet round a
star, a circumbinary one round the barycentre of the whole system -- the pair that lost its brown dwarf has no outer
pair left -- and a moon round a planet.
"""
import pytest

from hybrasil.data.catalog_loader import parse_workbook
from hybrasil.data.planetless_loader import (TAB, build_planetless_system, parse_planetless,
                                                  planetless_entry)
from hybrasil.mechanics.time_series import system_positions_at
from hybrasil.mechanics.units import J2000

PL_HEAD = ["System / Host", "Star (component)", "Role in system", "Distance (ly)", "Mass (M-sun)",
           "Stellar Class", "Luminosity (L-sun)", "Effective temp (K)", "Separation from", "Separation (AU)",
           "Orbital eccentricity (e)", "Orbital period (d)", "Inclination (deg)", "Ascending node (deg)",
           "Argument of periastron (deg)", "Time of periastron (JD)", "Argument of periastron refers to",
           "Node type", "Barycentre from", "Barycentre offset (AU)", "RA (deg, ICRS)", "Dec (deg, ICRS)"]
ORBIT = [0.3, 2000.0, 40.0, 100.0, 30.0, 2451545.0, "secondary (B relative to A)"]


def _row(**kw):
    return [kw.get(h, "") for h in PL_HEAD]


def _workbook(planet_host="Tst AB"):
    a = dict(zip(PL_HEAD, ["Tst", "Tst A", "host (most massive star)", 50.0, 1.0, "G2V", 1.0, 5772]))
    pl = [PL_HEAD,
          _row(**a, **{"Node type": "star", "RA (deg, ICRS)": 10.0, "Dec (deg, ICRS)": 20.0}),
          _row(**{"System / Host": "Tst", "Star (component)": "Tst AB", "Role in system": "subsystem",
                  "Mass (M-sun)": 1.5, "Node type": "subsystem", "Barycentre from": "Tst A",
                  "Barycentre offset (AU)": 10.0}),
          _row(**{"System / Host": "Tst", "Star (component)": "Tst B", "Role in system": "star",
                  "Mass (M-sun)": 0.5, "Stellar Class": "M0V", "Luminosity (L-sun)": 0.05, "Node type": "star",
                  "Separation from": "Tst A", "Separation (AU)": 30.0,
                  **dict(zip(PL_HEAD[10:17], ORBIT))})]
    planets = [["Planet", "Host system (primary star)", "Planet-host star", "Semi-major axis (au)",
                "Orbital period (d)", "Eccentricity", "Mass (M-earth)", "Confidence tier"],
               ["Tst X", "Tst", planet_host, 400.0, 3.0e6, 0.1, 15000.0, "confirmed"],
               ["Tst B b", "Tst", "Tst B", 0.5, 300.0, "", 9000.0, "confirmed"]]
    moons = [["Exomoon", "Host planet", "Host system (primary star)", "Semi-major axis (au)",
              "Orbital period (d)", "Confidence tier"],
             ["Tst X I", "Tst X", "Tst", 2.0, 4000.0, "confirmed"]]
    return {"tabs": {TAB: pl, "Planets within 100 ly": planets, "Exomoons": moons}}


@pytest.fixture(scope="module")
def ps():
    return parse_planetless(_workbook())["Tst"]


class TestTheRecords:
    def test_the_planets_are_filed_with_the_system(self, ps):
        assert [p.name for p in ps.planets] == ["Tst B b", "Tst X"]
        assert [m.name for ms in ps.moons.values() for m in ms] == ["Tst X I"]

    def test_the_catalog_lists_no_second_copy(self):
        cat = parse_workbook(_workbook())
        assert "Tst" not in cat.hosts()
        assert [p.name for p in cat.planetless_planets["Tst"]] == ["Tst B b", "Tst X"]

    def test_a_system_with_planets_is_listed_as_planetary(self, ps):
        e = planetless_entry(ps)
        assert e["kind"] == "planetary" and e["n_planets"] == 2 and "Tst X" in e["aliases"]


class TestTheDrawing:
    def test_each_body_goes_round_the_node_its_row_names(self, ps):
        s = build_planetless_system(ps)
        by = {b.name: b for b in s.bodies}
        assert by["Tst X"].parent == "Tst AB" and by["Tst AB"].body_type == "barycentre"
        assert by["Tst B b"].parent == "Tst B"
        assert by["Tst X I"].parent == "Tst X" and by["Tst X I"].body_type == "moon"
        assert "brown dwarfs" in s.description

    def test_the_whole_system_barycentre_needs_no_outer_pair(self, ps):
        s = build_planetless_system(ps)
        pos = system_positions_at(s, J2000)
        assert all(abs(c) < 1e7 for p in pos.values() for c in p)

    def test_a_host_the_hierarchy_lacks_falls_back_to_the_origin(self):
        s = build_planetless_system(parse_planetless(_workbook(planet_host="Nowhere"))["Tst"])
        assert {b.name: b for b in s.bodies}["Tst X"].parent == "Tst A"
